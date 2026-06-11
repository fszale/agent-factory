from __future__ import annotations

import pytest

from agent_factory.autonomy import (
    BudgetExceeded,
    BudgetMeter,
    TwinPaused,
    default_autonomy,
    evaluate_gate,
)
from agent_factory.bridge import Autonomy, FullAutonomy, Guardrails
from agent_factory.providers.base import TokenUsage


# ---- HITL gate ------------------------------------------------------------- #
def test_always_gate_wins_even_in_full_autonomy():
    autonomy = Autonomy(
        mode="full-autonomy",
        auto_allow=["search"],
        always_gate=["send", "deploy"],
        full_autonomy=FullAutonomy(
            enabled=True,
            guardrails=Guardrails(
                daily_token_limit=10,
                daily_usd_limit=1,
                per_task_token_limit=5,
                max_actions_per_hour=10,
                allowed_actions=["send", "search"],
                kill_switch=True,
            ),
        ),
    )
    # send is in always_gate -> gated even though full-autonomy + whitelisted
    assert evaluate_gate(autonomy, "send").allowed_without_approval is False
    assert evaluate_gate(autonomy, "search").allowed_without_approval is True


def test_propose_then_confirm_gates_non_auto_allow():
    autonomy = default_autonomy()
    assert evaluate_gate(autonomy, "search").allowed_without_approval is True
    assert evaluate_gate(autonomy, "post").allowed_without_approval is False
    assert evaluate_gate(autonomy, "anything-else").allowed_without_approval is False


# ---- kill switch ----------------------------------------------------------- #
def test_kill_switch_per_twin_and_factory():
    meter = BudgetMeter()
    meter.pause("filip", reason="manual")
    with pytest.raises(TwinPaused):
        meter.check_dispatch("filip")
    meter.resume("filip")
    meter.check_dispatch("filip")  # no raise

    meter.pause_factory(reason="incident")
    with pytest.raises(TwinPaused):
        meter.check_dispatch("any-twin")


# ---- budget meter / runaway test ------------------------------------------ #
def _guardrails(**overrides) -> Guardrails:
    base = dict(
        daily_token_limit=1000,
        daily_usd_limit=100.0,
        per_task_token_limit=10000,
        max_actions_per_hour=1000,
        allowed_actions=["research"],
        kill_switch=True,
    )
    base.update(overrides)
    return Guardrails(**base)


def test_preflight_hard_stops_and_pauses_on_daily_token_limit():
    meter = BudgetMeter()
    g = _guardrails(daily_token_limit=1000)
    # record near the cap
    meter.record("filip", "stub", TokenUsage.from_total(950), guardrails=g)
    # next estimated request would cross the daily cap -> hard stop + pause
    with pytest.raises(BudgetExceeded) as exc:
        meter.preflight("filip", "stub", estimated_tokens=100, guardrails=g)
    assert exc.value.limit_type == "daily_token_limit"
    assert meter.is_paused("filip")  # twin auto-paused


def test_per_task_limit_aborts_without_pausing():
    meter = BudgetMeter()
    g = _guardrails(per_task_token_limit=100)
    with pytest.raises(BudgetExceeded) as exc:
        meter.preflight("filip", "stub", estimated_tokens=150, guardrails=g)
    assert exc.value.limit_type == "per_task_token_limit"
    assert not meter.is_paused("filip")  # task aborted, twin still live


def test_no_guardrails_means_no_budget_enforcement():
    meter = BudgetMeter()
    # propose-then-confirm twin: guardrails None -> preflight is a no-op (still checks kill switch)
    meter.preflight("filip", "stub", estimated_tokens=10_000_000, guardrails=None)
