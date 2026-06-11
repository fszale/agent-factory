"""Real tools, dispatched through the autonomy gate.

Four tool families (Phase 1):
  - reminder  : scheduler-backed; MUST actually fire (records an event when due).
  - search    : X/Grok search (social capability route).
  - research  : GPT research (research capability route).
  - engineer  : an engineering action that proposes a repo change (gated by default).

Every dispatch passes through the same kill-switch + HITL policy as a human task.
Delegation does not escalate privilege.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agent_factory.autonomy import (
    ApprovalRequired,
    BudgetExceeded,
    BudgetMeter,
    TwinPaused,
    default_autonomy,
    evaluate_gate,
)
from agent_factory.cloud import Scheduler, now_epoch
from agent_factory.persistence import PersistenceStore
from agent_factory.runtime import TwinRuntime

# Which capability route each tool uses for model calls.
_TOOL_CAPABILITY = {
    "search": "social",
    "research": "research",
    "engineer": "engineering",
}


@dataclass(slots=True)
class ToolContext:
    runtime: TwinRuntime
    store: PersistenceStore
    scheduler: Scheduler
    budget: BudgetMeter


@dataclass(slots=True)
class ToolResult:
    action: str
    status: str  # completed | awaiting_approval | paused | error
    output: dict[str, Any] = field(default_factory=dict)
    approval_id: str | None = None


def dispatch_tool(
    ctx: ToolContext,
    twin_id: str,
    action: str,
    params: dict[str, Any] | None = None,
) -> ToolResult:
    params = params or {}

    # 1. Kill switch.
    try:
        ctx.budget.check_dispatch(twin_id)
    except TwinPaused as exc:
        return ToolResult(action=action, status="paused", output={"detail": str(exc)})

    # 2. HITL gate.
    autonomy = ctx.runtime.autonomy_for(twin_id)
    decision = evaluate_gate(autonomy, action)
    if not decision.allowed_without_approval:
        approval = ctx.store.create_approval(
            twin_id=twin_id,
            scope=action,
            request_payload={"action": action, "params": params, "gate_reason": decision.reason},
        )
        return ToolResult(
            action=action,
            status="awaiting_approval",
            output={"reason": decision.reason},
            approval_id=approval["id"],
        )

    # 3. Execute.
    try:
        output = _execute(ctx, twin_id, action, params)
    except TwinPaused as exc:
        result = ToolResult(action=action, status="paused", output={"detail": str(exc)})
    except BudgetExceeded as exc:
        # A crossed daily limit auto-pauses the twin; surface that as paused.
        status = "paused" if ctx.budget.is_paused(twin_id) else "error"
        result = ToolResult(
            action=action,
            status=status,
            output={"detail": str(exc), "limit_type": exc.limit_type},
        )
    except Exception as exc:  # surface provider/tool errors
        result = ToolResult(action=action, status="error", output={"detail": str(exc)})
    else:
        result = ToolResult(action=action, status="completed", output=output)

    _capture_trace(ctx, twin_id, action, params, result)
    return result


def _capture_trace(ctx: ToolContext, twin_id: str, action: str, params: dict[str, Any], result: ToolResult) -> None:
    """Every interaction writes a structured trace (Phase 2 capture step)."""
    signals: dict[str, Any] = {}
    if isinstance(result.output, dict):
        usage = result.output.get("usage")
        if usage:
            signals["usage"] = usage
        if result.output.get("provider"):
            signals["provider"] = result.output["provider"]
    signals["params_keys"] = sorted(params.keys())
    signals["reached_terminal_state"] = result.status in {"completed", "paused", "awaiting_approval"}
    ctx.store.create_trace(
        twin_id=twin_id,
        task_type=action,
        action=action,
        outcome=result.status,
        signals=signals,
    )


def _execute(ctx: ToolContext, twin_id: str, action: str, params: dict[str, Any]) -> dict[str, Any]:
    if action == "reminder":
        return _schedule_reminder(ctx, twin_id, params)
    if action in {"search", "research"}:
        return _model_tool(ctx, twin_id, action, params)
    if action == "engineer":
        return _engineer(ctx, twin_id, params)
    raise ValueError(f"Unknown tool action: {action}")


def _schedule_reminder(ctx: ToolContext, twin_id: str, params: dict[str, Any]) -> dict[str, Any]:
    fire_at = float(params.get("fire_at", now_epoch()))
    message = str(params.get("message", "reminder"))
    job = ctx.scheduler.schedule(
        fire_at=fire_at,
        payload={"twin_id": twin_id, "message": message, "kind": "reminder"},
    )
    ctx.store.record_event(
        twin_id=twin_id,
        event_type="reminder.scheduled",
        source="tool:reminder",
        payload={"job_id": job.id, "fire_at": fire_at, "message": message},
    )
    return {"job_id": job.id, "fire_at": fire_at, "message": message}


def _model_tool(ctx: ToolContext, twin_id: str, action: str, params: dict[str, Any]) -> dict[str, Any]:
    query = str(params.get("query") or params.get("message") or "")
    if not query:
        raise ValueError(f"'{action}' requires a 'query' parameter")
    capability = _TOOL_CAPABILITY[action]
    result = ctx.runtime.chat(twin_id=twin_id, user_message=query, model_profile=capability)
    return {
        "capability": capability,
        "provider": result.provider,
        "model": result.model,
        "text": result.text,
        "usage": result.usage,
        "budget": result.budget,
    }


def _engineer(ctx: ToolContext, twin_id: str, params: dict[str, Any]) -> dict[str, Any]:
    """Engineering action: produce a proposed change. Pushing happens only after approval."""
    instruction = str(params.get("instruction") or params.get("message") or "")
    if not instruction:
        raise ValueError("'engineer' requires an 'instruction' parameter")
    result = ctx.runtime.chat(twin_id=twin_id, user_message=instruction, model_profile="engineering")
    proposal = ctx.store.create_artifact_proposal(
        twin_id=twin_id,
        artifact_type="engineering-change",
        artifact_path=str(params.get("path", "pending-review")),
        proposal={"instruction": instruction, "proposed_change": result.text},
    )
    return {
        "proposal_id": proposal["id"],
        "proposed_change": result.text,
        "usage": result.usage,
    }


def fire_due_reminders(ctx: ToolContext, now: float | None = None) -> list[dict[str, Any]]:
    """Run all due reminders. Returns the events recorded. Reminders MUST fire."""
    fired: list[dict[str, Any]] = []
    for job in ctx.scheduler.due(now=now):
        event = ctx.store.record_event(
            twin_id=job.payload.get("twin_id", "unknown"),
            event_type="reminder.fired",
            source="scheduler",
            payload={"job_id": job.id, "message": job.payload.get("message")},
        )
        ctx.scheduler.mark_fired(job.id)
        fired.append(event)
    return fired
