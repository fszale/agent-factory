from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from agent_factory.builder import build_twin
from agent_factory.config import load_manifest
from agent_factory.registry import TwinRegistry


def test_build_emits_immutable_artifact(tmp_path, bridge_yaml):
    out = tmp_path / "artifacts"
    result = build_twin(bridge_yaml, out)

    assert result.artifact_dir.exists()
    assert result.artifact_dir.name.startswith("filip-")
    assert (result.artifact_dir / "twin.yaml").exists()
    assert (result.artifact_dir / "build.manifest.json").exists()
    assert (result.artifact_dir / "runtime" / "system.md").exists()
    # kernel snapshot pulled in
    assert (result.artifact_dir / "kernel" / "kernel.manifest.json").exists()


def test_build_is_content_addressed_and_reproducible(tmp_path, bridge_yaml):
    a = build_twin(bridge_yaml, tmp_path / "a")
    b = build_twin(bridge_yaml, tmp_path / "b")
    assert a.artifact_hash == b.artifact_hash  # same inputs -> same hash


def test_build_rejects_duplicate_without_overwrite(tmp_path, bridge_yaml):
    out = tmp_path / "artifacts"
    build_twin(bridge_yaml, out)
    with pytest.raises(FileExistsError):
        build_twin(bridge_yaml, out)
    # overwrite allowed
    build_twin(bridge_yaml, out, overwrite=True)


def test_artifact_loads_as_runtime_twin(tmp_path, bridge_yaml):
    result = build_twin(bridge_yaml, tmp_path / "artifacts")
    manifest = load_manifest(result.runtime_manifest_path)
    assert manifest.twin_id == "filip"
    assert "default" in manifest.model_profiles
    # registry can load the deployed artifact directory
    registry = TwinRegistry(result.artifact_dir.parent)
    assert any(t.manifest.twin_id == "filip" for t in registry.list())


def test_overrides_layered_on_kernel(tmp_path, fake_kernel):
    # bridge dir with an override prompt
    bridge_dir = tmp_path / "bridge"
    (bridge_dir / "overrides" / "prompts").mkdir(parents=True)
    (bridge_dir / "overrides" / "prompts" / "custom.md").write_text("custom prompt\n", encoding="utf-8")
    from tests.conftest import make_bridge_spec

    spec = make_bridge_spec(fake_kernel)
    spec["twin"]["overrides"] = {"prompts": "./overrides/prompts/"}
    (bridge_dir / "twin.yaml").write_text(yaml.safe_dump(spec), encoding="utf-8")

    result = build_twin(bridge_dir / "twin.yaml", tmp_path / "artifacts")
    assert (result.artifact_dir / "kernel" / "prompts" / "custom.md").exists()
    manifest = result.build_manifest_path.read_text(encoding="utf-8")
    assert "prompts/custom.md" in manifest
