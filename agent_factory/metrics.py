"""Scoring + rate-of-improvement engine.

Implemented in Python from the digital-twin-factory design specs
(`docs/self-improvement.md`, `docs/rate-of-improvement.md`). The plan called for
"porting tested TypeScript"; in reality those docs are a spec, not shipped code, so
this is a faithful Python implementation of the same formulas (the 6-component
usefulness score, RoI deltas, curve classification).

All derived scores are normalized to 0.0–1.0.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Usefulness composite weights (self-improvement.md §"Usefulness Score").
_W_COMPLETION = 0.30
_W_CLARIFICATION = 0.20
_W_CORRECTION = 0.15
_W_ARTIFACT = 0.15
_W_REPEAT = 0.10
_W_FEEDBACK = 0.10

POSITIVE_TAGS = {"accurate", "useful", "great_format", "helpful"}
NEGATIVE_TAGS = {"too_vague", "missed_context", "too_slow", "incorrect", "needs_follow_up", "not_helpful"}


def _burden_to_score(count: int) -> float:
    """Fewer is better: 0 -> 1.0, then decays. 1/(1+count)."""
    return 1.0 / (1.0 + max(0, count))


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


@dataclass(slots=True)
class RunScore:
    usefulness_score: float
    score_confidence: float
    components: dict[str, float] = field(default_factory=dict)


def score_run(signals: dict) -> RunScore:
    """Compute the 6-component usefulness score + confidence from a run's signals.

    Recognized signals (all optional):
      outcome ("completed"/...), clarification_count, correction_count,
      artifact_opened, artifact_downloaded, repeat_requester (bool),
      feedback_tags (list[str]), operator_review (bool), reached_terminal_state (bool).
    """
    outcome = signals.get("outcome")
    completion_success = 1.0 if outcome == "completed" else 0.0

    low_clarification = _burden_to_score(int(signals.get("clarification_count", 0)))
    low_correction = _burden_to_score(int(signals.get("correction_count", 0)))

    artifact_engagement = 0.0
    if signals.get("artifact_downloaded"):
        artifact_engagement = 1.0
    elif signals.get("artifact_opened"):
        artifact_engagement = 0.5

    repeat_usage = 1.0 if signals.get("repeat_requester") else 0.0

    tags = {str(t).lower() for t in signals.get("feedback_tags", [])}
    pos = len(tags & POSITIVE_TAGS)
    neg = len(tags & NEGATIVE_TAGS)
    if pos or neg:
        # Map net sentiment from [-1, 1] to [0, 1]; missing feedback handled below.
        explicit_feedback = _clamp(0.5 + 0.5 * ((pos - neg) / max(1, pos + neg)))
    else:
        # Missing explicit feedback should not zero the score: use a neutral prior.
        explicit_feedback = 0.5

    components = {
        "completion_success": completion_success,
        "low_clarification_burden": low_clarification,
        "low_correction_burden": low_correction,
        "artifact_engagement": artifact_engagement,
        "repeat_usage_signal": repeat_usage,
        "explicit_feedback_signal": explicit_feedback,
    }
    usefulness = (
        _W_COMPLETION * completion_success
        + _W_CLARIFICATION * low_clarification
        + _W_CORRECTION * low_correction
        + _W_ARTIFACT * artifact_engagement
        + _W_REPEAT * repeat_usage
        + _W_FEEDBACK * explicit_feedback
    )

    # Operator review can override automated scoring when present.
    if "operator_score" in signals:
        usefulness = _clamp(float(signals["operator_score"]))

    confidence = _score_confidence(signals)
    return RunScore(usefulness_score=round(_clamp(usefulness), 4), score_confidence=confidence, components=components)


def _score_confidence(signals: dict) -> float:
    factors = 0
    present = 0
    # number of observed signals
    observed = sum(
        1
        for k in ("clarification_count", "correction_count", "artifact_opened",
                  "artifact_downloaded", "repeat_requester", "feedback_tags")
        if k in signals and signals.get(k) not in (None, [], {})
    )
    factors += 1
    present += min(1.0, observed / 4.0)
    # operator review present
    factors += 1
    present += 1.0 if signals.get("operator_review") else 0.0
    # artifact interaction data present
    factors += 1
    present += 1.0 if (signals.get("artifact_opened") or signals.get("artifact_downloaded")) else 0.0
    # reached terminal state
    factors += 1
    present += 1.0 if signals.get("reached_terminal_state") else 0.0
    return round(present / factors, 4) if factors else 0.0


# --------------------------------------------------------------------------- #
# Rate of improvement
# --------------------------------------------------------------------------- #
def improvement_vs_baseline_pct(current: float, baseline: float, direction: str = "higher_is_better") -> float:
    if baseline == 0:
        return 0.0
    if direction == "lower_is_better":
        return (baseline - current) / abs(baseline)
    return (current - baseline) / abs(baseline)


def weekly_roi_delta(current_week_pct: float, previous_week_pct: float) -> float:
    return current_week_pct - previous_week_pct


def useful_completion_rate(useful_completed: int, eligible_completed: int) -> float:
    if eligible_completed <= 0:
        return 0.0
    return useful_completed / eligible_completed


def classify_curve(weekly_improvement_pcts: list[float]) -> str:
    """Classify the improvement curve shape. Needs >= 4 weeks of data."""
    pts = list(weekly_improvement_pcts)
    if len(pts) < 4:
        return "baseline_forming"

    first, last = pts[0], pts[-1]
    peak = max(pts)
    spread = peak - min(pts)

    # Noisy / implausible movement.
    if spread > 1.5 or any(abs(p) > 5.0 for p in pts):
        return "investigate"

    # Little or no movement.
    if abs(last - first) < 0.02 and spread < 0.05:
        return "flat"

    # Rose then fell back materially from the peak.
    peak_idx = pts.index(peak)
    if peak_idx < len(pts) - 1 and (peak - last) > 0.10 and peak > first:
        return "rise_decline"

    # Strong early improvement that holds / tapers up.
    if last >= first:
        return "s_curve"

    return "investigate"


@dataclass(slots=True)
class RoiSnapshot:
    week_start: str
    primary_metric_value: float
    baseline_value: float
    improvement_vs_baseline_pct: float
    weekly_roi_delta: float
    usefulness_score: float
    useful_completion_rate: float
    curve_classification: str
    data_quality_score: float

    def as_fields(self) -> dict:
        return {
            "primary_metric_value": self.primary_metric_value,
            "baseline_value": self.baseline_value,
            "improvement_vs_baseline_pct": self.improvement_vs_baseline_pct,
            "weekly_roi_delta": self.weekly_roi_delta,
            "usefulness_score": self.usefulness_score,
            "useful_completion_rate": self.useful_completion_rate,
            "curve_classification": self.curve_classification,
            "data_quality_score": self.data_quality_score,
        }


def build_roi_snapshot(
    week_start: str,
    primary_metric_value: float,
    baseline_value: float,
    usefulness_score: float,
    useful_completion: float,
    prior_improvement_pcts: list[float] | None = None,
    direction: str = "higher_is_better",
    data_quality_score: float = 1.0,
) -> RoiSnapshot:
    prior = prior_improvement_pcts or []
    improvement = improvement_vs_baseline_pct(primary_metric_value, baseline_value, direction)
    prev = prior[-1] if prior else 0.0
    delta = weekly_roi_delta(improvement, prev)
    curve = classify_curve([*prior, improvement])
    return RoiSnapshot(
        week_start=week_start,
        primary_metric_value=primary_metric_value,
        baseline_value=baseline_value,
        improvement_vs_baseline_pct=round(improvement, 4),
        weekly_roi_delta=round(delta, 4),
        usefulness_score=round(usefulness_score, 4),
        useful_completion_rate=round(useful_completion, 4),
        curve_classification=curve,
        data_quality_score=data_quality_score,
    )
