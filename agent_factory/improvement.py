"""Improvement loop — reflect + propose (PR-gated, never auto-merge).

Pipeline:
  capture (traces, see tools.py)
    → reflect: score recent traces, find low-scoring patterns
    → propose: emit improvement_candidates + a proposed kernel edit as a PR

Proposals are PR-gated by design: a merged PR = a new kernel version = a reviewable,
reversible upgrade. This module NEVER merges. Publishing goes through a PRPublisher
interface; the default DryRunPRPublisher writes diff + PR body artifacts (no repo
writes). A GitHubPRPublisher can swap in once a token is configured.
"""

from __future__ import annotations

import difflib
import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

from agent_factory.metrics import score_run
from agent_factory.persistence import PersistenceStore
from agent_factory.registry import TwinPackage

# Narrow scope: map a trace action/task_type to the kernel skill it should improve.
# Phase 2 intentionally covers only a few skills (resist scaling coverage early).
ACTION_TO_SKILL: dict[str, str] = {
    "research": "first-principles",
    "search": "knowledge-sprints",
    "engineer": "agent-factory-design",
}

# Don't propose against an area unless it's both low-scoring and has enough evidence.
MIN_SUPPORTING_RUNS = 3
LOW_SCORE_THRESHOLD = 0.55
MAX_SKILLS_PER_RUN = 3


@dataclass(slots=True)
class ProposedPR:
    twin_id: str
    skill_id: str
    file_path: str  # path within the kernel snapshot
    original_text: str
    proposed_text: str
    rationale: str
    supporting_evidence: dict
    branch: str

    def unified_diff(self) -> str:
        return "".join(
            difflib.unified_diff(
                self.original_text.splitlines(keepends=True),
                self.proposed_text.splitlines(keepends=True),
                fromfile=f"a/{self.file_path}",
                tofile=f"b/{self.file_path}",
            )
        )

    def pr_body(self) -> str:
        ev = self.supporting_evidence
        return (
            f"## Auto-proposed kernel improvement: `{self.skill_id}`\n\n"
            f"{self.rationale}\n\n"
            f"### Supporting evidence\n"
            f"- runs observed: {ev.get('runs_observed')}\n"
            f"- mean usefulness: {ev.get('mean_usefulness')}\n"
            f"- failure/low-score share: {ev.get('low_score_share')}\n\n"
            f"> Proposed by the agent-factory improvement loop. **Review required — never auto-merged.** "
            f"Merging this PR = a new kernel version = a reviewable, reversible upgrade.\n"
        )


# --------------------------------------------------------------------------- #
# PR publishers
# --------------------------------------------------------------------------- #
class PRPublisher(ABC):
    mode: str

    @abstractmethod
    def publish(self, pr: ProposedPR) -> dict: ...


class DryRunPRPublisher(PRPublisher):
    """Writes diff + PR body to an artifacts dir. No repo writes, no token."""

    mode = "dry-run"

    def __init__(self, output_dir: str | Path) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def publish(self, pr: ProposedPR) -> dict:
        base = self.output_dir / pr.branch
        base.mkdir(parents=True, exist_ok=True)
        diff_path = base / "change.diff"
        body_path = base / "PR_BODY.md"
        diff_path.write_text(pr.unified_diff(), encoding="utf-8")
        body_path.write_text(pr.pr_body(), encoding="utf-8")
        return {
            "mode": self.mode,
            "branch": pr.branch,
            "diff_path": str(diff_path),
            "pr_body_path": str(body_path),
            "auto_merged": False,
        }


class GitHubPRPublisher(PRPublisher):
    """Opens a real (never auto-merged) PR via the GitHub API. Requires a token."""

    mode = "github"

    def __init__(self, repo: str, token: str | None = None) -> None:
        self.repo = repo
        self.token = token or os.getenv("GITHUB_TOKEN")

    def publish(self, pr: ProposedPR) -> dict:
        if not self.token:
            raise RuntimeError(
                "GitHubPRPublisher requires a GITHUB_TOKEN with write access. "
                "Use DryRunPRPublisher to generate proposal artifacts without a token."
            )
        # Intentionally not implemented this session (dry-run chosen). The branch +
        # diff + body are fully prepared by ProposedPR; wiring create-branch /
        # create-blob / create-PR calls here is the only remaining step.
        raise NotImplementedError(
            "Live GitHub PR creation is staged but disabled. Flip to this publisher "
            "once a GITHUB_TOKEN is configured; the diff/body are already produced."
        )


# --------------------------------------------------------------------------- #
# Reflect + propose
# --------------------------------------------------------------------------- #
@dataclass(slots=True)
class ReflectResult:
    twin_id: str
    candidates: list[dict] = field(default_factory=list)
    published: list[dict] = field(default_factory=list)
    scored_traces: int = 0


def _aggregate_by_skill(traces: list[dict]) -> dict[str, dict]:
    """Score each trace and aggregate usefulness per kernel skill area."""
    agg: dict[str, dict] = {}
    for trace in traces:
        action = trace.get("action") or trace.get("task_type")
        skill_id = ACTION_TO_SKILL.get(action)
        if not skill_id:
            continue
        signals = dict(trace.get("signals") or {})
        signals.setdefault("outcome", trace.get("outcome"))
        score = score_run(signals)
        bucket = agg.setdefault(skill_id, {"scores": [], "low": 0})
        bucket["scores"].append(score.usefulness_score)
        if score.usefulness_score < LOW_SCORE_THRESHOLD:
            bucket["low"] += 1
    return agg


def _propose_text(original: str, skill_id: str, evidence: dict) -> str:
    note = (
        f"\n\n## Improvement note (auto-proposed {evidence.get('runs_observed')} runs)\n"
        f"Recent runs using `{skill_id}` showed a low usefulness share "
        f"({evidence.get('low_score_share')}). Tighten this skill: ask one clarifying "
        f"question up front when scope is ambiguous, and lead with the concrete "
        f"deliverable before the reasoning.\n"
    )
    return original.rstrip() + note


def reflect_and_propose(
    twin: TwinPackage,
    store: PersistenceStore,
    publisher: PRPublisher,
    since: str | None = None,
) -> ReflectResult:
    twin_id = twin.manifest.twin_id
    traces = store.list_traces(twin_id=twin_id, since=since)
    agg = _aggregate_by_skill(traces)

    result = ReflectResult(twin_id=twin_id, scored_traces=len(traces))

    # Rank low-performing skills; take the worst few (narrow scope).
    ranked = sorted(
        agg.items(),
        key=lambda kv: (sum(kv[1]["scores"]) / len(kv[1]["scores"])) if kv[1]["scores"] else 1.0,
    )
    for skill_id, bucket in ranked[:MAX_SKILLS_PER_RUN]:
        scores = bucket["scores"]
        if len(scores) < MIN_SUPPORTING_RUNS:
            continue
        mean = sum(scores) / len(scores)
        if mean >= LOW_SCORE_THRESHOLD:
            continue

        skill_file = twin.base_dir / "kernel" / "skills" / skill_id / "SKILL.md"
        if not skill_file.exists():
            continue
        original = skill_file.read_text(encoding="utf-8")
        evidence = {
            "runs_observed": len(scores),
            "mean_usefulness": round(mean, 4),
            "low_score_share": round(bucket["low"] / len(scores), 4),
        }
        proposed = _propose_text(original, skill_id, evidence)
        pr = ProposedPR(
            twin_id=twin_id,
            skill_id=skill_id,
            file_path=f"skills/{skill_id}/SKILL.md",
            original_text=original,
            proposed_text=proposed,
            rationale=(
                f"`{skill_id}` is underperforming (mean usefulness {evidence['mean_usefulness']} "
                f"over {evidence['runs_observed']} runs). Proposing a targeted edit to reduce "
                f"clarification burden and improve deliverable-first structure."
            ),
            supporting_evidence=evidence,
            branch=f"improve/{twin_id}/{skill_id}",
        )

        candidate = store.create_improvement_candidate(
            twin_id=twin_id,
            candidate_type="prompt_variant_reorder",
            payload={
                "skill_id": skill_id,
                "evidence": evidence,
                "rationale": pr.rationale,
            },
        )
        publish_meta = publisher.publish(pr)
        # Record the proposal in the existing artifact_proposals table + an event.
        store.create_artifact_proposal(
            twin_id=twin_id,
            artifact_type="kernel-skill-edit",
            artifact_path=pr.file_path,
            proposal={"branch": pr.branch, "diff": pr.unified_diff(), "publish": publish_meta},
        )
        store.create_improvement_event(
            twin_id=twin_id,
            candidate_id=candidate["id"],
            change_type="kernel_skill_edit_proposed",
            applied_mode="proposed",  # never auto-applied
            payload={"publish": publish_meta, "evidence": evidence},
        )
        result.candidates.append(candidate)
        result.published.append(publish_meta)

    return result
