from __future__ import annotations

import json

from agent_factory.builder import build_twin
from agent_factory.cloud import build_cloud_providers
from agent_factory.deploy import deploy_twin
from agent_factory.registry import TwinRegistry


def test_deploy_installs_and_records(tmp_path, bridge_yaml):
    artifact = build_twin(bridge_yaml, tmp_path / "artifacts")
    providers = build_cloud_providers("aws", blob_root=tmp_path / "blobs")
    result = deploy_twin(
        artifact.artifact_dir,
        cloud="aws",
        registry_root=tmp_path / "registry",
        providers=providers,
    )
    assert result.cloud == "aws"
    assert result.registry_path is not None
    # registry serves the deployed twin
    registry = TwinRegistry(tmp_path / "registry")
    assert any(t.manifest.twin_id == "filip" for t in registry.list())
    # deploy record written with provenance
    record = json.loads((artifact.artifact_dir / "deploy.record.json").read_text())
    assert record["artifact_hash"] == artifact.artifact_hash
    assert record["autonomy_mode"] == "propose-then-confirm"


def test_deploy_rejects_non_artifact(tmp_path):
    bad = tmp_path / "notanartifact"
    bad.mkdir()
    try:
        deploy_twin(bad, cloud="gcp")
    except FileNotFoundError:
        return
    raise AssertionError("expected FileNotFoundError for non-artifact dir")
