from __future__ import annotations

from agent_factory.autonomy import BudgetMeter
from agent_factory.builder import build_twin
from agent_factory.cloud import LocalScheduler
from agent_factory.mcp import (
    METHOD_NOT_FOUND,
    UNAUTHENTICATED,
    MCPServer,
    sign_context,
)
from agent_factory.persistence import InMemoryStore
from agent_factory.providers import StubProvider
from agent_factory.registry import TwinRegistry
from agent_factory.runtime import TwinRuntime
from agent_factory.tools import ToolContext

SECRET = "test-signing-secret"


def _server(tmp_path, bridge_yaml):
    artifact = build_twin(bridge_yaml, tmp_path / "artifacts")
    registry = TwinRegistry(artifact.artifact_dir.parent)
    meter = BudgetMeter()
    runtime = TwinRuntime(registry, providers={"stub": StubProvider()}, budget_meter=meter)
    ctx = ToolContext(runtime=runtime, store=InMemoryStore(), scheduler=LocalScheduler(), budget=meter)
    return MCPServer(ctx, signing_secret=SECRET), ctx


def _rpc(method, params, rid=1):
    return {"jsonrpc": "2.0", "id": rid, "method": method, "params": params}


def test_tools_list(tmp_path, bridge_yaml):
    server, _ = _server(tmp_path, bridge_yaml)
    resp = server.handle(_rpc("tools/list", {}))
    assert "search" in resp["result"]["tools"]


def test_tools_call_search(tmp_path, bridge_yaml):
    server, _ = _server(tmp_path, bridge_yaml)
    resp = server.handle(_rpc("tools/call", {"twin_id": "filip", "name": "search", "arguments": {"query": "x"}}))
    assert resp["result"]["status"] == "completed"


def test_unknown_method(tmp_path, bridge_yaml):
    server, _ = _server(tmp_path, bridge_yaml)
    resp = server.handle(_rpc("does/not-exist", {}))
    assert resp["error"]["code"] == METHOD_NOT_FOUND


def test_delegation_requires_valid_signature(tmp_path, bridge_yaml):
    server, _ = _server(tmp_path, bridge_yaml)
    context = {"origin": "peer-factory", "trace": "abc"}
    resp = server.handle(
        _rpc("agent/delegate", {"twin_id": "filip", "action": "search", "context": context, "signature": "bad"})
    )
    assert resp["error"]["code"] == UNAUTHENTICATED


def test_delegation_auto_allowed_action_runs(tmp_path, bridge_yaml):
    server, ctx = _server(tmp_path, bridge_yaml)
    context = {"origin": "peer-factory"}
    sig = sign_context(context, SECRET)
    resp = server.handle(
        _rpc("agent/delegate", {"twin_id": "filip", "action": "search", "context": context,
                                "signature": sig, "params": {"query": "q"}})
    )
    assert resp["result"]["gated"] is False
    task_id = resp["result"]["task_id"]
    assert resp["result"]["status"] == "pending"
    out = server.process_task(task_id)
    assert out["status"] == "completed"


def test_delegation_does_not_escalate_privilege(tmp_path, bridge_yaml):
    """An always_gate action delegated by a peer is still gated — no privilege escalation."""
    server, _ = _server(tmp_path, bridge_yaml)
    context = {"origin": "peer-factory"}
    sig = sign_context(context, SECRET)
    resp = server.handle(
        _rpc("agent/delegate", {"twin_id": "filip", "action": "send", "context": context,
                                "signature": sig, "params": {"to": "x"}})
    )
    assert resp["result"]["gated"] is True
    assert resp["result"]["status"] == "awaiting_approval"


def test_task_expiry(tmp_path, bridge_yaml):
    server, ctx = _server(tmp_path, bridge_yaml)
    resp = server.handle(
        _rpc("tasks/create", {"twin_id": "filip", "action": "search", "params": {"query": "q"}, "expiry": 1.0})
    )
    task_id = resp["result"]["task_id"]
    out = server.process_task(task_id)  # clock=time.time >> expiry=1.0
    assert out["status"] == "expired"
