"""Twin deploy — `factory twin deploy <artifact> --cloud gcp|aws`.

Deploy is cloud-agnostic: it talks only to the Scheduler/Queue/SecretStore/Blob
interfaces. The artifact is content-addressed and immutable; deploy uploads it to
object storage and installs it into the runtime registry so the factory can serve it.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from agent_factory.cloud import CloudProviders, build_cloud_providers, now_epoch, write_deploy_record


@dataclass(slots=True)
class DeployResult:
    twin_name: str
    artifact_hash: str
    cloud: str
    blob_uri: str
    registry_path: str | None
    deploy_record_path: str


def _load_build_manifest(artifact_dir: Path) -> dict:
    manifest_path = artifact_dir / "build.manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(
            f"{artifact_dir} is not a valid build artifact (missing build.manifest.json). "
            "Run `factory twin build` first."
        )
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def deploy_twin(
    artifact_dir: str | Path,
    cloud: str,
    registry_root: str | Path | None = None,
    providers: CloudProviders | None = None,
) -> DeployResult:
    artifact = Path(artifact_dir).resolve()
    if not artifact.exists():
        raise FileNotFoundError(f"Artifact directory not found: {artifact}")
    if not (artifact / "twin.yaml").exists():
        raise FileNotFoundError(f"Artifact missing runtime twin.yaml: {artifact}")

    manifest = _load_build_manifest(artifact)
    artifact_hash = manifest["artifact_hash"]
    twin_name = manifest["twin_name"]

    providers = providers or build_cloud_providers(cloud)

    # 1. Upload immutable artifact to object storage (content-addressed key).
    blob_key = f"artifacts/{twin_name}-{artifact_hash[:12]}"
    blob_uri = providers.blob.put_dir(artifact, blob_key)

    # 2. Install into the runtime registry so the factory can serve it.
    registry_path: str | None = None
    if registry_root:
        reg = Path(registry_root).resolve()
        reg.mkdir(parents=True, exist_ok=True)
        target = reg / f"{twin_name}-{artifact_hash[:12]}"
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(artifact, target)
        registry_path = str(target)

    # 3. Record the deploy (provenance + cloud target).
    record = {
        "twin_name": twin_name,
        "artifact_hash": artifact_hash,
        "cloud": providers.cloud,
        "blob_uri": blob_uri,
        "registry_path": registry_path,
        "kernel": manifest.get("kernel"),
        "autonomy_mode": manifest.get("autonomy", {}).get("mode"),
        "deployed_at": now_epoch(),
    }
    record_path = artifact / "deploy.record.json"
    write_deploy_record(record_path, record)

    return DeployResult(
        twin_name=twin_name,
        artifact_hash=artifact_hash,
        cloud=providers.cloud,
        blob_uri=blob_uri,
        registry_path=registry_path,
        deploy_record_path=str(record_path),
    )
