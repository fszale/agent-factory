from __future__ import annotations

from pathlib import Path

from agent_factory.builder import build_twin
from agent_factory.improvement import DryRunPRPublisher, reflect_and_propose
from agent_factory.persistence import InMemoryStore
from agent_factory.registry import TwinRegistry


def _twin(tmp_path, bridge_yaml):
    artifact = build_twin(bridge_yaml, tmp_path / "artifacts")
    registry = TwinRegistry(artifact.artifact_dir.parent)
    return registry.get("filip")


def test_reflect_opens_a_dryrun_pr_for_low_scoring_skill(tmp_path, bridge_yaml):
    twin = _twin(tmp_path, bridge_yaml)
    store = InMemoryStore()

    # Capture several low-scoring research traces (research -> first-principles skill).
    for _ in range(5):
        store.create_trace(
            twin_id="filip",
            task_type="research",
            action="research",
            outcome="completed",
            signals={"clarification_count": 4, "correction_count": 3, "outcome": "completed"},
        )

    publisher = DryRunPRPublisher(tmp_path / "prs")
    result = reflect_and_propose(twin, store, publisher)

    assert result.scored_traces == 5
    assert len(result.candidates) >= 1
    pub = result.published[0]
    assert pub["auto_merged"] is False  # never auto-merge
    assert Path(pub["diff_path"]).exists()
    assert Path(pub["pr_body_path"]).exists()
    diff = Path(pub["diff_path"]).read_text()
    assert "Improvement note (auto-proposed" in diff
    # candidate + event recorded
    assert store.list_improvement_candidates(twin_id="filip")
    assert store.list_improvement_events(twin_id="filip")[0]["applied_mode"] == "proposed"


def test_reflect_skips_high_scoring_and_thin_evidence(tmp_path, bridge_yaml):
    twin = _twin(tmp_path, bridge_yaml)
    store = InMemoryStore()
    # Only 2 traces (below MIN_SUPPORTING_RUNS) and high-scoring.
    for _ in range(2):
        store.create_trace(
            twin_id="filip",
            task_type="research",
            action="research",
            outcome="completed",
            signals={"clarification_count": 0, "correction_count": 0, "feedback_tags": ["useful"]},
        )
    result = reflect_and_propose(twin, store, DryRunPRPublisher(tmp_path / "prs"))
    assert result.candidates == []
