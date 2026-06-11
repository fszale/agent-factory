"""Metrics service — reads live data from the store for the dashboard.

Exposes ops metrics (tasks, success rate, corrections/task, cost/task by provider)
and the rate-of-improvement curve (from stored roi_snapshots). Kept separate from the
FastAPI layer so it can be unit-tested without HTTP.
"""

from __future__ import annotations

from agent_factory.metrics import score_run
from agent_factory.persistence import PersistenceStore
from agent_factory.pricing import usd_for_tokens


def compute_ops_metrics(store: PersistenceStore, twin_id: str | None = None) -> dict:
    runs = store.list_runs(twin_id=twin_id)
    tasks = store.list_tasks(twin_id=twin_id)
    corrections = store.list_corrections(twin_id=twin_id)
    traces = store.list_traces(twin_id=twin_id)

    completed_runs = [r for r in runs if r.get("status") == "completed"]
    success_rate = (len(completed_runs) / len(runs)) if runs else 0.0
    corrections_per_task = (len(corrections) / len(tasks)) if tasks else 0.0

    # Cost per provider, derived from trace usage signals.
    cost_by_provider: dict[str, float] = {}
    tokens_by_provider: dict[str, int] = {}
    for trace in traces:
        signals = trace.get("signals") or {}
        provider = signals.get("provider")
        usage = signals.get("usage") or {}
        tokens = int(usage.get("total_tokens", 0) or 0)
        if not provider or not tokens:
            continue
        tokens_by_provider[provider] = tokens_by_provider.get(provider, 0) + tokens
        cost_by_provider[provider] = round(
            cost_by_provider.get(provider, 0.0) + usd_for_tokens(provider, tokens), 6
        )

    completed_tasks = [t for t in tasks if t.get("status") == "completed"]
    cost_per_task = (
        round(sum(cost_by_provider.values()) / len(completed_tasks), 6) if completed_tasks else 0.0
    )

    return {
        "twin_id": twin_id,
        "tasks_run": len(tasks),
        "runs": len(runs),
        "success_rate": round(success_rate, 4),
        "mean_corrections_per_task": round(corrections_per_task, 4),
        "cost_by_provider": cost_by_provider,
        "tokens_by_provider": tokens_by_provider,
        "cost_per_task": cost_per_task,
        "traces_captured": len(traces),
    }


def compute_mean_usefulness(store: PersistenceStore, twin_id: str | None = None) -> float:
    traces = store.list_traces(twin_id=twin_id)
    if not traces:
        return 0.0
    scores = []
    for trace in traces:
        signals = dict(trace.get("signals") or {})
        signals.setdefault("outcome", trace.get("outcome"))
        scores.append(score_run(signals).usefulness_score)
    return round(sum(scores) / len(scores), 4)


def roi_curve(store: PersistenceStore, twin_id: str | None = None) -> list[dict]:
    """Return roi snapshots ordered by week for the improvement curve."""
    snapshots = store.list_roi_snapshots(twin_id=twin_id)
    return [
        {
            "week_start": s.get("week_start"),
            "improvement_vs_baseline_pct": s.get("improvement_vs_baseline_pct"),
            "weekly_roi_delta": s.get("weekly_roi_delta"),
            "usefulness_score": s.get("usefulness_score"),
            "curve_classification": s.get("curve_classification"),
        }
        for s in snapshots
    ]
