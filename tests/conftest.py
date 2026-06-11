from __future__ import annotations

import json
from pathlib import Path

import yaml
import pytest


@pytest.fixture
def fake_kernel(tmp_path) -> Path:
    """Minimal but valid local kernel release (no git tag verification needed)."""
    root = tmp_path / "kernel"
    root.mkdir()
    (root / "kernel.manifest.json").write_text(
        json.dumps({"kernel": {"name": "fake-kernel", "version": "v1.0.0", "skills": [], "prompts": []}}),
        encoding="utf-8",
    )
    (root / "CONTEXT.md").write_text("# Kernel context\nReference kernel for tests.\n", encoding="utf-8")
    (root / "README.md").write_text("# Fake kernel\n", encoding="utf-8")
    (root / "PHILOSOPHY.md").write_text("First principles. Pareto.\n", encoding="utf-8")
    for skill_id in ("first-principles", "knowledge-sprints", "agent-factory-design"):
        sd = root / "skills" / skill_id
        sd.mkdir(parents=True)
        (sd / "SKILL.md").write_text(f"# {skill_id}\nReference skill body.\n", encoding="utf-8")
    prompts = root / "prompts"
    prompts.mkdir()
    (prompts / "action-proposal.md").write_text("# action proposal\n", encoding="utf-8")
    return root


def make_bridge_spec(kernel_path: Path, full_autonomy: dict | None = None) -> dict:
    autonomy = {
        "mode": "propose-then-confirm",
        "auto_allow": ["search", "read", "summarize", "reminder", "research"],
        "always_gate": ["send", "post", "purchase", "deploy"],
    }
    if full_autonomy is not None:
        autonomy["full_autonomy"] = full_autonomy
    return {
        "twin": {
            "name": "filip",
            "description": "test twin",
            "owner": "fszale@gmail.com",
            "kernel": {"source": str(kernel_path), "version": "v1.0.0"},
            "roles": ["principal-operator", "fractional-cto"],
            "models": {
                "default": {"provider": "stub", "model": "stub-fast"},
                "social": {"provider": "stub", "model": "stub-social"},
                "research": {"provider": "stub", "model": "stub-research"},
                "engineering": {"provider": "stub", "model": "stub-eng"},
            },
            "autonomy": autonomy,
        }
    }


@pytest.fixture
def bridge_yaml(tmp_path, fake_kernel) -> Path:
    spec = make_bridge_spec(fake_kernel)
    path = tmp_path / "bridge" / "twin.yaml"
    path.parent.mkdir(parents=True)
    path.write_text(yaml.safe_dump(spec), encoding="utf-8")
    return path
