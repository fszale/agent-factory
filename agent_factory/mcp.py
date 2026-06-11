"""Peer-capable MCP server (JSON-RPC 2.0).

One protocol for both tool access (vertical) and agent/factory delegation (horizontal).
Delegated work uses the Tasks primitive (async, durable, with retry + expiry) — not
synchronous calls. Topology is federated: this server is a thin, policy-aware domain
service. It holds no extra orchestration state beyond the durable task store.

Security invariants:
  - Delegated context is signed (HMAC) and verified on receipt.
  - Every delegation passes through the SAME autonomy/HITL policy as a human task.
    Delegation never escalates privilege.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Any

from agent_factory.autonomy import evaluate_gate
from agent_factory.persistence import PersistenceStore
from agent_factory.tools import ToolContext, dispatch_tool

JSONRPC_VERSION = "2.0"

# JSON-RPC error codes.
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603
# Application codes.
UNAUTHENTICATED = -32001
TASK_EXPIRED = -32002


def _canonical(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign_context(context: dict, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), _canonical(context), hashlib.sha256).hexdigest()


def verify_context(context: dict, signature: str, secret: str) -> bool:
    expected = sign_context(context, secret)
    return hmac.compare_digest(expected, signature or "")


@dataclass(slots=True)
class DelegationEnvelope:
    twin_id: str
    action: str
    params: dict
    context: dict
    signature: str
    expiry: float | None = None
    max_attempts: int = 3


class MCPServer:
    AVAILABLE_TOOLS = ["reminder", "search", "research", "engineer"]

    def __init__(
        self,
        tool_ctx: ToolContext,
        signing_secret: str,
        clock=time.time,
    ) -> None:
        self.ctx = tool_ctx
        self.secret = signing_secret
        self._clock = clock

    # -- JSON-RPC dispatch -------------------------------------------------- #
    def handle(self, request: dict) -> dict:
        if not isinstance(request, dict) or request.get("jsonrpc") != JSONRPC_VERSION or "method" not in request:
            return self._error(request.get("id") if isinstance(request, dict) else None, INVALID_REQUEST, "Invalid JSON-RPC request")
        req_id = request.get("id")
        method = request["method"]
        params = request.get("params") or {}
        try:
            handler = {
                "tools/list": self._tools_list,
                "tools/call": self._tools_call,
                "tasks/create": self._tasks_create,
                "tasks/get": self._tasks_get,
                "agent/delegate": self._agent_delegate,
            }.get(method)
            if handler is None:
                return self._error(req_id, METHOD_NOT_FOUND, f"Unknown method: {method}")
            return self._ok(req_id, handler(params))
        except _RpcError as exc:
            return self._error(req_id, exc.code, exc.message, exc.data)
        except Exception as exc:  # pragma: no cover - defensive
            return self._error(req_id, INTERNAL_ERROR, str(exc))

    # -- handlers ----------------------------------------------------------- #
    def _tools_list(self, params: dict) -> dict:
        return {"tools": list(self.AVAILABLE_TOOLS)}

    def _tools_call(self, params: dict) -> dict:
        twin_id = params.get("twin_id")
        action = params.get("name") or params.get("action")
        if not twin_id or not action:
            raise _RpcError(INVALID_PARAMS, "tools/call requires 'twin_id' and 'name'")
        result = dispatch_tool(self.ctx, twin_id, action, params.get("arguments") or params.get("params") or {})
        return {"status": result.status, "action": result.action, "output": result.output, "approval_id": result.approval_id}

    def _tasks_create(self, params: dict) -> dict:
        twin_id = params.get("twin_id")
        action = params.get("action")
        if not twin_id or not action:
            raise _RpcError(INVALID_PARAMS, "tasks/create requires 'twin_id' and 'action'")
        expiry = params.get("expiry")
        task = self.ctx.store.create_task(
            twin_id=twin_id,
            task_type=f"delegated:{action}",
            payload={
                "action": action,
                "params": params.get("params") or {},
                "expiry": expiry,
                "attempts": 0,
                "max_attempts": int(params.get("max_attempts", 3)),
                "origin": params.get("origin", "peer"),
            },
            status="pending",
        )
        return {"task_id": task["id"], "status": task["status"]}

    def _tasks_get(self, params: dict) -> dict:
        task_id = params.get("task_id")
        task = self.ctx.store.get_task(task_id) if task_id else None
        if not task:
            raise _RpcError(INVALID_PARAMS, f"Unknown task_id: {task_id}")
        return {"task_id": task["id"], "status": task["status"], "result": task.get("result", {})}

    def _agent_delegate(self, params: dict) -> dict:
        """Horizontal delegation from a peer agent/factory. Signed + policy-gated."""
        context = params.get("context") or {}
        signature = params.get("signature", "")
        if not verify_context(context, signature, self.secret):
            raise _RpcError(UNAUTHENTICATED, "Invalid or missing context signature")

        twin_id = params.get("twin_id")
        action = params.get("action")
        if not twin_id or not action:
            raise _RpcError(INVALID_PARAMS, "agent/delegate requires 'twin_id' and 'action'")

        # Delegation passes through the SAME policy as a human task — no privilege escalation.
        autonomy = self.ctx.runtime.autonomy_for(twin_id)
        decision = evaluate_gate(autonomy, action)

        # Create a durable, async task record either way (Tasks primitive).
        task = self.ctx.store.create_task(
            twin_id=twin_id,
            task_type=f"delegated:{action}",
            payload={
                "action": action,
                "params": params.get("params") or {},
                "expiry": params.get("expiry"),
                "attempts": 0,
                "max_attempts": int(params.get("max_attempts", 3)),
                "origin": context.get("origin", "peer"),
                "signed_context": context,
                "requires_approval": not decision.allowed_without_approval,
            },
            status="awaiting_approval" if not decision.allowed_without_approval else "pending",
        )
        self.ctx.store.record_audit_event(
            actor_type="peer",
            actor_id=str(context.get("origin", "unknown")),
            action="agent.delegate",
            target_type="task",
            target_id=task["id"],
            twin_id=twin_id,
            payload={"action": action, "gated": not decision.allowed_without_approval},
        )
        return {
            "task_id": task["id"],
            "status": task["status"],
            "gated": not decision.allowed_without_approval,
            "gate_reason": decision.reason,
        }

    # -- async worker ------------------------------------------------------- #
    def process_task(self, task_id: str) -> dict:
        """Execute one durable task with retry + expiry semantics."""
        task = self.ctx.store.get_task(task_id)
        if not task:
            raise _RpcError(INVALID_PARAMS, f"Unknown task_id: {task_id}")
        payload = task["payload"]

        if task["status"] == "awaiting_approval":
            return {"task_id": task_id, "status": "awaiting_approval"}

        expiry = payload.get("expiry")
        if expiry is not None and self._clock() > float(expiry):
            updated = self.ctx.store.update_task(task_id, status="expired", result={"reason": "expired before execution"})
            return {"task_id": task_id, "status": updated["status"]}

        attempts = int(payload.get("attempts", 0)) + 1
        result = dispatch_tool(self.ctx, task["twin_id"], payload["action"], payload.get("params") or {})

        if result.status == "completed":
            updated = self.ctx.store.update_task(task_id, status="completed", result=result.output)
        elif result.status in {"error"} and attempts < int(payload.get("max_attempts", 3)):
            new_payload = {**payload, "attempts": attempts}
            updated = self.ctx.store.update_task(task_id, status="pending", payload=new_payload, result={"last_error": result.output})
        else:
            final = "paused" if result.status == "paused" else ("awaiting_approval" if result.status == "awaiting_approval" else "failed")
            new_payload = {**payload, "attempts": attempts}
            updated = self.ctx.store.update_task(task_id, status=final, payload=new_payload, result=result.output)
        return {"task_id": task_id, "status": updated["status"], "attempts": attempts}

    # -- helpers ------------------------------------------------------------ #
    @staticmethod
    def _ok(req_id: Any, result: dict) -> dict:
        return {"jsonrpc": JSONRPC_VERSION, "id": req_id, "result": result}

    @staticmethod
    def _error(req_id: Any, code: int, message: str, data: Any = None) -> dict:
        err = {"code": code, "message": message}
        if data is not None:
            err["data"] = data
        return {"jsonrpc": JSONRPC_VERSION, "id": req_id, "error": err}


class _RpcError(Exception):
    def __init__(self, code: int, message: str, data: Any = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data
