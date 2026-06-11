from __future__ import annotations

import time

import yaml

from agent_factory.autonomy import BudgetMeter
from agent_factory.builder import build_twin
from agent_factory.cloud import LocalScheduler
from agent_factory.persistence import InMemoryStore
from agent_factory.providers import StubProvider
from agent_factory.registry import TwinRegistry
from agent_factory.runtime import TwinRuntime
from agent_factory.tools import ToolContext, dispatch_tool, fire_due_reminders


def _context(tmp_path, bridge_yaml, budget=None):
    artifact = build_twin(bridge_yaml, tmp_path / "artifacts")
    registry = TwinRegistry(artifact.artifact_dir.parent)
    meter = budget or BudgetMeter()
    runtime = TwinRuntime(registry, providers={"stub": StubProvider()}, budget_meter=meter)
    ctx = ToolContext(
        runtime=runtime,
        store=InMemoryStore(),
        scheduler=LocalScheduler(),
        budget=meter,
    )
    return ctx, "filip"


def test_reminder_actually_fires(tmp_path, bridge_yaml):
    ctx, tid = _context(tmp_path, bridge_yaml)
    past = time.time() - 1
    res = dispatch_tool(ctx, tid, "reminder", {"message": "ship it", "fire_at": past})
    assert res.status == "completed"
    fired = fire_due_reminders(ctx)
    assert len(fired) == 1
    assert fired[0]["event_type"] == "reminder.fired"
    # not double-fired
    assert fire_due_reminders(ctx) == []


def test_gated_action_creates_approval(tmp_path, bridge_yaml):
    ctx, tid = _context(tmp_path, bridge_yaml)
    res = dispatch_tool(ctx, tid, "send", {"to": "x", "body": "y"})
    assert res.status == "awaiting_approval"
    assert res.approval_id is not None
    pending = ctx.store.list_approvals(twin_id=tid, status="pending")
    assert len(pending) == 1


def test_search_executes_through_router(tmp_path, bridge_yaml):
    ctx, tid = _context(tmp_path, bridge_yaml)
    res = dispatch_tool(ctx, tid, "search", {"query": "latest in agentic systems"})
    assert res.status == "completed"
    assert res.output["provider"] == "stub"


def test_paused_twin_blocks_dispatch(tmp_path, bridge_yaml):
    meter = BudgetMeter()
    ctx, tid = _context(tmp_path, bridge_yaml, budget=meter)
    meter.pause(tid, reason="manual kill switch")
    res = dispatch_tool(ctx, tid, "search", {"query": "anything"})
    assert res.status == "paused"


def test_runaway_trips_daily_limit_and_autopauses(tmp_path, fake_kernel):
    """Done-criteria: a deliberate runaway hits the daily limit and auto-pauses."""
    from tests.conftest import make_bridge_spec

    spec = make_bridge_spec(
        fake_kernel,
        full_autonomy={
            "enabled": True,
            "guardrails": {
                "daily_token_limit": 200,  # tiny; trips within a few stub calls
                "daily_usd_limit": 1000.0,
                "per_task_token_limit": 1000000,
                "max_actions_per_hour": 100000,
                "allowed_actions": ["research", "search"],
                "kill_switch": True,
            },
        },
    )
    # research must be allowed without approval in full-autonomy
    spec["twin"]["autonomy"]["auto_allow"] = ["research", "search"]
    bridge = tmp_path / "twin.yaml"
    bridge.write_text(yaml.safe_dump(spec), encoding="utf-8")

    meter = BudgetMeter()
    ctx, tid = _context(tmp_path, bridge, budget=meter)

    statuses = []
    for _ in range(10):
        res = dispatch_tool(ctx, tid, "research", {"query": "expensive deep research task"})
        statuses.append(res.status)
        if res.status == "paused":
            break

    assert "paused" in statuses, f"runaway never auto-paused: {statuses}"
    assert meter.is_paused(tid)
