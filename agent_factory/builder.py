"""Twin-builder — `factory twin build`.

Reads a bridge `twin.yaml`, resolves the pinned kernel (clone at git tag, with
private-repo auth), layers bridge overrides on top, and emits an immutable,
content-addressed build artifact. The runtime loads artifacts, never raw repos.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from agent_factory.bridge import BridgeConfig, ModelRoute, load_bridge_config

# Kernel artifacts copied into the resolved kernel snapshot.
_KERNEL_FILES = ["AGENTS.md", "CONTEXT.md", "PHILOSOPHY.md", "README.md", "kernel.manifest.json"]
_KERNEL_DIRS = ["skills", "prompts", "templates", ".agents", "docs", "diagrams"]


@dataclass(slots=True)
class BuildResult:
    artifact_dir: Path
    artifact_hash: str
    twin_name: str
    kernel_source: str
    kernel_version: str
    runtime_manifest_path: Path
    build_manifest_path: Path
    files: list[str] = field(default_factory=list)


def _looks_like_git_source(source: str) -> bool:
    return source.startswith(("http://", "https://", "git@", "ssh://")) or source.endswith(".git")


def _normalize_git_url(source: str, auth_token: str | None) -> str:
    url = source
    if "://" not in url and not url.startswith("git@"):
        # bare form like github.com/fszale/agent-kernel
        url = f"https://{url}"
    if not url.endswith(".git") and url.startswith("http"):
        url = f"{url}.git"
    if auth_token and url.startswith("https://"):
        # Inject token for private-repo HTTPS auth (x-access-token works for GitHub Apps/PATs).
        url = url.replace("https://", f"https://x-access-token:{auth_token}@", 1)
    return url


def _resolve_kernel(source: str, version: str, dest: Path, auth_token: str | None) -> None:
    """Clone the kernel at a pinned tag (or copy a local checkout) into `dest`."""
    if _looks_like_git_source(source) or ("://" not in source and "/" in source and not Path(source).exists()):
        url = _normalize_git_url(source, auth_token)
        with tempfile.TemporaryDirectory(prefix="agent-factory-kernel-") as tmp:
            clone = Path(tmp) / "kernel"
            cmd = ["git", "clone", "--depth", "1", "--branch", version, url, str(clone)]
            env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
            result = subprocess.run(cmd, capture_output=True, text=True, env=env)
            if result.returncode != 0:
                raise RuntimeError(
                    f"Failed to clone kernel {source} at pinned tag {version}: {result.stderr.strip()}"
                )
            _verify_pinned_tag(clone, version)
            _copy_kernel_artifacts(clone, dest)
        return

    local = Path(source).resolve()
    if not local.exists():
        raise FileNotFoundError(f"Kernel source not found locally and not a git URL: {source}")
    # For a local git checkout, verify the tag resolves to the current checkout when possible.
    if (local / ".git").exists():
        _verify_pinned_tag(local, version)
    _copy_kernel_artifacts(local, dest)


def _verify_pinned_tag(repo: Path, version: str) -> None:
    tags = subprocess.run(
        ["git", "-C", str(repo), "tag", "--list", version],
        capture_output=True,
        text=True,
    )
    if tags.returncode == 0 and version not in tags.stdout.split():
        raise RuntimeError(
            f"Pinned kernel tag '{version}' does not exist in repo {repo}. "
            "Kernels are pinned, never live-cloned from a branch."
        )


def _copy_kernel_artifacts(src: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    if not (src / "kernel.manifest.json").exists():
        raise FileNotFoundError(
            f"Kernel source {src} has no kernel.manifest.json — not a valid kernel release."
        )
    for name in _KERNEL_FILES:
        if (src / name).exists():
            shutil.copy2(src / name, dest / name)
    for name in _KERNEL_DIRS:
        if (src / name).exists():
            shutil.copytree(src / name, dest / name, dirs_exist_ok=True)


def _apply_overrides(bridge_dir: Path, bridge: BridgeConfig, kernel_dir: Path) -> list[str]:
    """Overlay bridge override dirs on top of the resolved kernel snapshot."""
    applied: list[str] = []
    ov = bridge.twin.overrides
    for rel, target in (("prompts", "prompts"), ("skills", "skills")):
        src_rel = getattr(ov, rel)
        if not src_rel:
            continue
        src = (bridge_dir / src_rel).resolve()
        if not src.exists():
            raise FileNotFoundError(f"override path declared but missing: {src}")
        dest = kernel_dir / target
        dest.mkdir(parents=True, exist_ok=True)
        for item in src.rglob("*"):
            if item.is_file():
                rel_path = item.relative_to(src)
                out = dest / rel_path
                out.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, out)
                applied.append(f"{target}/{rel_path}")
    return applied


def _model_profiles(models: dict[str, ModelRoute]) -> dict[str, dict]:
    profiles: dict[str, dict] = {}
    for capability, route in models.items():
        profile: dict = {"provider": route.provider, "model": route.model}
        if route.api_base:
            profile["api_base"] = route.api_base
        if route.api_key_env:
            profile["api_key_env"] = route.api_key_env
        profile["timeout_seconds"] = route.timeout_seconds
        profile["store"] = route.store
        profiles[capability] = profile
    return profiles


def _default_profile(models: dict[str, ModelRoute]) -> str:
    if "default" in models:
        return "default"
    return next(iter(models))


def _render_system_prompt(bridge: BridgeConfig, kernel_dir: Path) -> str:
    twin = bridge.twin
    lines = [
        f"# {twin.name} — digital twin",
        "",
        twin.description or "",
        "",
        f"Roles: {', '.join(twin.roles)}.",
        "",
        "You operate under the agent-factory autonomy contract: propose-then-confirm is the "
        "default. send/post/purchase/deploy actions are always routed through human approval.",
        "",
    ]
    philosophy = kernel_dir / "PHILOSOPHY.md"
    context = kernel_dir / "CONTEXT.md"
    for extra in (philosophy, context):
        if extra.exists():
            lines.append(f"## From kernel: {extra.name}")
            lines.append(extra.read_text(encoding="utf-8").strip())
            lines.append("")
    return "\n".join(lines).strip() + "\n"


def _hash_directory(root: Path) -> str:
    """Content-address the artifact: sha256 over sorted (relpath, bytes)."""
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_file():
            rel = path.relative_to(root).as_posix()
            digest.update(rel.encode("utf-8"))
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
    return digest.hexdigest()


def build_twin(
    twin_yaml: str | Path,
    output_root: str | Path,
    auth_token: str | None = None,
    overwrite: bool = False,
) -> BuildResult:
    twin_yaml_path = Path(twin_yaml).resolve()
    bridge_dir = twin_yaml_path.parent
    bridge = load_bridge_config(twin_yaml_path)
    twin = bridge.twin

    auth_token = auth_token or os.getenv("KERNEL_AUTH_TOKEN")

    with tempfile.TemporaryDirectory(prefix="agent-factory-build-") as staging_str:
        staging = Path(staging_str) / "artifact"
        kernel_dir = staging / "kernel"
        staging.mkdir(parents=True, exist_ok=True)

        _resolve_kernel(twin.kernel.source, twin.kernel.version, kernel_dir, auth_token)
        applied_overrides = _apply_overrides(bridge_dir, bridge, kernel_dir)

        # Runtime package files (loadable by TwinRegistry).
        (staging / "runtime").mkdir(parents=True, exist_ok=True)
        system_prompt = _render_system_prompt(bridge, kernel_dir)
        (staging / "runtime" / "system.md").write_text(system_prompt, encoding="utf-8")

        # Pull a small set of kernel docs into the knowledge base.
        (staging / "knowledge").mkdir(parents=True, exist_ok=True)
        knowledge_docs: list[str] = []
        for candidate in ["CONTEXT.md", "README.md"]:
            src = kernel_dir / candidate
            if src.exists():
                rel = f"knowledge/{candidate}"
                shutil.copy2(src, staging / "knowledge" / candidate)
                knowledge_docs.append(rel)

        runtime_manifest = {
            "schema_version": "1.0",
            "twin_id": twin.name.replace("-", "_"),
            "name": twin.name,
            "description": twin.description or f"{twin.name} twin",
            "owner": twin.owner or "unknown",
            "tags": list(twin.roles),
            "prompt": {"system_prompt": "runtime/system.md"},
            "knowledge": {"documents": knowledge_docs},
            "model_profiles": _model_profiles(twin.models),
            "default_model_profile": _default_profile(twin.models),
        }
        runtime_manifest_path = staging / "twin.yaml"
        runtime_manifest_path.write_text(
            yaml.safe_dump(runtime_manifest, sort_keys=False), encoding="utf-8"
        )

        artifact_hash = _hash_directory(staging)

        # Finalize: <output_root>/<twin_name>-<hash12>
        out_root = Path(output_root).resolve()
        out_root.mkdir(parents=True, exist_ok=True)
        artifact_dir = out_root / f"{twin.name}-{artifact_hash[:12]}"
        if artifact_dir.exists():
            if not overwrite:
                raise FileExistsError(
                    f"Artifact already exists (same content hash): {artifact_dir}. "
                    "Identical build is reproducible; pass overwrite=True to rebuild."
                )
            shutil.rmtree(artifact_dir)

        build_manifest = {
            "twin_name": twin.name,
            "artifact_hash": artifact_hash,
            "kernel": {"source": twin.kernel.source, "version": twin.kernel.version},
            "roles": twin.roles,
            "models": {k: v.model_dump() for k, v in twin.models.items()},
            "autonomy": twin.autonomy.model_dump(),
            "overrides_applied": applied_overrides,
        }
        (staging / "build.manifest.json").write_text(
            json.dumps(build_manifest, indent=2), encoding="utf-8"
        )

        shutil.copytree(staging, artifact_dir)

    files = sorted(
        p.relative_to(artifact_dir).as_posix() for p in artifact_dir.rglob("*") if p.is_file()
    )
    return BuildResult(
        artifact_dir=artifact_dir,
        artifact_hash=artifact_hash,
        twin_name=twin.name,
        kernel_source=twin.kernel.source,
        kernel_version=twin.kernel.version,
        runtime_manifest_path=artifact_dir / "twin.yaml",
        build_manifest_path=artifact_dir / "build.manifest.json",
        files=files,
    )
