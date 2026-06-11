from __future__ import annotations

from agent_factory.metrics import (
    build_roi_snapshot,
    classify_curve,
    improvement_vs_baseline_pct,
    score_run,
    useful_completion_rate,
    weekly_roi_delta,
)


def test_perfect_run_scores_high():
    s = score_run(
        {
            "outcome": "completed",
            "clarification_count": 0,
            "correction_count": 0,
            "artifact_downloaded": True,
            "repeat_requester": True,
            "feedback_tags": ["accurate", "useful"],
            "operator_review": True,
            "reached_terminal_state": True,
        }
    )
    assert s.usefulness_score > 0.9
    assert s.score_confidence > 0.9


def test_failed_run_scores_low():
    s = score_run({"outcome": "error", "clarification_count": 3, "correction_count": 2})
    assert s.usefulness_score < 0.55


def test_missing_feedback_does_not_zero_score():
    s = score_run({"outcome": "completed"})
    # completion alone (0.30) + neutral priors should land mid-range, not zero
    assert 0.5 < s.usefulness_score < 0.9


def test_operator_score_overrides():
    s = score_run({"outcome": "error", "operator_score": 0.95})
    assert s.usefulness_score == 0.95


def test_improvement_and_delta():
    assert improvement_vs_baseline_pct(120, 100) == 0.2
    assert improvement_vs_baseline_pct(80, 100, "lower_is_better") == 0.2
    assert round(weekly_roi_delta(0.3, 0.2), 4) == 0.1
    assert useful_completion_rate(8, 10) == 0.8


def test_curve_classification():
    assert classify_curve([0.1, 0.2]) == "baseline_forming"
    assert classify_curve([0.1, 0.2, 0.28, 0.32]) == "s_curve"
    assert classify_curve([0.1, 0.3, 0.32, 0.15]) == "rise_decline"
    assert classify_curve([0.0, 0.0, 0.0, 0.0]) == "flat"


def test_build_roi_snapshot():
    snap = build_roi_snapshot(
        week_start="2026-05-25",
        primary_metric_value=120,
        baseline_value=100,
        usefulness_score=0.7,
        useful_completion=0.8,
        prior_improvement_pcts=[0.1, 0.15],
    )
    assert snap.improvement_vs_baseline_pct == 0.2
    assert snap.week_start == "2026-05-25"
    assert "week_start" not in snap.as_fields()
