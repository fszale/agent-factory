"""Autonomy enforcement — HITL gate, budget meter, and kill switch.

Three load-bearing safety mechanisms (Phase 1):

1. **HITL gate** — decides whether an action needs human approval. propose-then-confirm
   is forced by default; send/post/purchase/deploy are *always* gated, even in
   full-autonomy mode.
2. **Budget meter** — atomic token + USD counters per twin per day. Hard-stops a task
   BEFORE the provider call returns (preflight estimate) and reconciles real usage
   after, pausing the twin if a hard limit is crossed.
3. **Kill switch** — factory-wide and per-twin pause flags, checked at the top of every
   dispatch. One flag pauses everything.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Callable

from agent_factory.bridge import Autonomy, Guardrails
from agent_factory.pricing import usd_for_tokens
from agent_factory.providers.base import TokenUsage

FACTORY_SCOPE = "__factory__"


class TwinPaused(RuntimeError):
    """Raised when a twin (or the whole factory) is paused via the kill switch."""


class BudgetExceeded(RuntimeError):
    """Raised when a hard budget/usage limit would be crossed. Aborts the task."""

    def __init__(self, message: str, limit_type: str) -> None:
        super().__init__(message)
        self.limit_type = limit_type


class ApprovalRequired(RuntimeError):
    """Raised when an action must route through the HITL queue before executing."""

    def __init__(self, action: str) -> None:
        super().__init__(f"Action '{action}' requires human approval (propose-then-confirm).")
        self.action = action


# --------------------------------------------------------------------------- #
# HITL gate
# --------------------------------------------------------------------------- #
@dataclass(slots=True)
class GateDecision:
    action: str
    allowed_without_approval: bool
    reason: str


def default_autonomy() -> Autonomy:
    """Safe product default for twins with no explicit autonomy block."""
    return Autonomy(
        mode="propose-then-confirm",
        auto_allow=["search", "read", "summarize"],
        always_gate=["send", "post", "purchase", "deploy"],
    )


def evaluate_gate(autonomy: Autonomy, action: str) -> GateDecision:
    # always_gate wins over everything, including full-autonomy.
    if action in autonomy.always_gate:
        return GateDecision(action, False, "action is in always_gate (gated even in full-autonomy)")
    if action in autonomy.auto_allow:
        return GateDecision(action, True, "action is in auto_allow")

    fa = autonomy.full_autonomy
    if fa.enabled and fa.guardrails is not None:
        if action in fa.guardrails.allowed_actions:
            return GateDecision(action, True, "full-autonomy enabled and action whitelisted")
        return GateDecision(action, False, "full-autonomy on but action not in allowed_actions")

    # propose-then-confirm default: anything not auto-allowed needs approval.
    return GateDecision(action, False, "propose-then-confirm default requires approval")


# --------------------------------------------------------------------------- #
# Budget meter + kill switch
# --------------------------------------------------------------------------- #
@dataclass
class _DailyCounter:
    tokens: int = 0
    usd: float = 0.0
    action_times: list[float] = field(default_factory=list)


def _today() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")


def _now() -> float:
    return datetime.now(UTC).timestamp()


class BudgetMeter:
    """In-memory atomic budget meter + kill switch.

    Counters are keyed by (twin_id, date). A factory-wide pause flag short-circuits
    every twin. Designed so a Postgres-backed implementation can swap in behind the
    same method surface (atomic incr + pause flag) without changing callers.
    """

    def __init__(
        self,
        clock: Callable[[], float] = _now,
        date_fn: Callable[[], str] = _today,
    ) -> None:
        self._lock = threading.Lock()
        self._counters: dict[tuple[str, str], _DailyCounter] = {}
        self._paused: dict[str, str | None] = {}  # twin_id/FACTORY_SCOPE -> reason
        self._clock = clock
        self._date_fn = date_fn

    # -- kill switch -------------------------------------------------------- #
    def pause(self, twin_id: str, reason: str = "manual") -> None:
        with self._lock:
            self._paused[twin_id] = reason

    def resume(self, twin_id: str) -> None:
        with self._lock:
            self._paused.pop(twin_id, None)

    def pause_factory(self, reason: str = "manual") -> None:
        self.pause(FACTORY_SCOPE, reason)

    def resume_factory(self) -> None:
        self.resume(FACTORY_SCOPE)

    def pause_reason(self, twin_id: str) -> str | None:
        with self._lock:
            if FACTORY_SCOPE in self._paused:
                return f"factory-wide pause: {self._paused[FACTORY_SCOPE]}"
            return self._paused.get(twin_id)

    def is_paused(self, twin_id: str) -> bool:
        return self.pause_reason(twin_id) is not None

    # -- counters ----------------------------------------------------------- #
    def _counter(self, twin_id: str) -> _DailyCounter:
        key = (twin_id, self._date_fn())
        return self._counters.setdefault(key, _DailyCounter())

    def usage(self, twin_id: str) -> dict[str, float]:
        with self._lock:
            c = self._counter(twin_id)
            return {"tokens": c.tokens, "usd": c.usd}

    def _actions_last_hour(self, counter: _DailyCounter) -> int:
        cutoff = self._clock() - 3600
        counter.action_times = [t for t in counter.action_times if t >= cutoff]
        return len(counter.action_times)

    # -- enforcement -------------------------------------------------------- #
    def check_dispatch(self, twin_id: str) -> None:
        """Top-of-dispatch kill-switch check."""
        reason = self.pause_reason(twin_id)
        if reason is not None:
            raise TwinPaused(f"Twin '{twin_id}' is paused: {reason}")

    def preflight(
        self,
        twin_id: str,
        provider: str,
        estimated_tokens: int,
        guardrails: Guardrails | None,
        task_tokens_so_far: int = 0,
    ) -> None:
        """Hard-stop BEFORE a provider call. Pauses the twin if a daily limit would break."""
        self.check_dispatch(twin_id)
        if guardrails is None:
            return
        with self._lock:
            counter = self._counter(twin_id)

            # Per-task cap: abort the task, but don't pause the twin.
            projected_task = task_tokens_so_far + estimated_tokens
            if projected_task > guardrails.per_task_token_limit:
                raise BudgetExceeded(
                    f"per_task_token_limit exceeded for twin '{twin_id}': "
                    f"{projected_task} > {guardrails.per_task_token_limit}",
                    limit_type="per_task_token_limit",
                )

            # Rate cap.
            if self._actions_last_hour(counter) >= guardrails.max_actions_per_hour:
                raise BudgetExceeded(
                    f"max_actions_per_hour exceeded for twin '{twin_id}': "
                    f"{guardrails.max_actions_per_hour}/hr",
                    limit_type="max_actions_per_hour",
                )

            # Daily token cap -> pause twin.
            projected_tokens = counter.tokens + estimated_tokens
            if projected_tokens > guardrails.daily_token_limit:
                self._paused[twin_id] = "daily_token_limit reached"
                raise BudgetExceeded(
                    f"daily_token_limit would be exceeded for twin '{twin_id}': "
                    f"{projected_tokens} > {guardrails.daily_token_limit}. Twin paused.",
                    limit_type="daily_token_limit",
                )

            # Daily USD cap -> pause twin.
            projected_usd = counter.usd + usd_for_tokens(provider, estimated_tokens)
            if projected_usd > guardrails.daily_usd_limit:
                self._paused[twin_id] = "daily_usd_limit reached"
                raise BudgetExceeded(
                    f"daily_usd_limit would be exceeded for twin '{twin_id}': "
                    f"${projected_usd:.4f} > ${guardrails.daily_usd_limit:.2f}. Twin paused.",
                    limit_type="daily_usd_limit",
                )

    def record(
        self,
        twin_id: str,
        provider: str,
        usage: TokenUsage,
        guardrails: Guardrails | None = None,
    ) -> dict[str, float]:
        """Reconcile real usage after a provider call; pause if a limit is now crossed."""
        tokens = usage.total_tokens or (usage.prompt_tokens + usage.completion_tokens)
        cost = usd_for_tokens(provider, tokens)
        with self._lock:
            counter = self._counter(twin_id)
            counter.tokens += tokens
            counter.usd += cost
            counter.action_times.append(self._clock())

            if guardrails is not None:
                if counter.tokens >= guardrails.daily_token_limit:
                    self._paused[twin_id] = "daily_token_limit reached"
                elif counter.usd >= guardrails.daily_usd_limit:
                    self._paused[twin_id] = "daily_usd_limit reached"
            return {"tokens": counter.tokens, "usd": counter.usd}
