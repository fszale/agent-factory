from __future__ import annotations

import subprocess
import shutil
import tempfile
from pathlib import Path

import yaml


EXPORTED_FILES = [
    "AGENTS.md",
    "CONTEXT.md",
    "PHILOSOPHY.md",
    "README.md",
    "Makefile",
]

EXPORTED_DIRECTORIES = [
    ".agents",
    "skills",
    "prompts",
    "templates",
    "diagrams",
    "docs",
    "scripts",
]


def sync_kernel_artifacts(source_root: str | Path, twin_root: str | Path) -> list[str]:
    source_path = Path(source_root).resolve()
    twin_path = Path(twin_root).resolve()

    if not source_path.exists():
        raise FileNotFoundError(f"Kernel source root does not exist: {source_path}")

    if not (source_path / "AGENTS.md").exists():
        raise FileNotFoundError(
            f"Kernel source root does not appear to be an agent-kernel checkout: {source_path}"
        )

    twin_path.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []

    for file_name in EXPORTED_FILES:
        source_file = source_path / file_name
        if not source_file.exists():
            raise FileNotFoundError(f"Expected kernel file is missing: {source_file}")
        shutil.copy2(source_file, twin_path / file_name)
        copied.append(file_name)

    for directory_name in EXPORTED_DIRECTORIES:
        source_dir = source_path / directory_name
        target_dir = twin_path / directory_name
        if not source_dir.exists():
            raise FileNotFoundError(f"Expected kernel directory is missing: {source_dir}")
        if target_dir.exists():
            shutil.rmtree(target_dir)
        shutil.copytree(source_dir, target_dir)
        copied.append(directory_name)

    return copied


def _looks_like_git_source(source: str) -> bool:
    return source.startswith(("http://", "https://", "git@", "ssh://")) or source.endswith(".git")


def compose_twin_from_kernel_source(
    source: str,
    twin_root: str | Path,
    seed_root: str | Path,
    overwrite: bool = False,
    git_ref: str | None = None,
    manifest_overrides: dict[str, str] | None = None,
) -> list[str]:
    target_path = Path(twin_root).resolve()
    scaffold_path = Path(seed_root).resolve()

    if not scaffold_path.exists():
        raise FileNotFoundError(f"Twin seed does not exist: {scaffold_path}")

    if target_path.exists():
        if not overwrite:
            raise FileExistsError(
                f"Target twin root already exists: {target_path}. Pass overwrite=True to replace it."
            )
        shutil.rmtree(target_path)

    shutil.copytree(scaffold_path, target_path)
    if manifest_overrides:
        _apply_manifest_overrides(target_path / "twin.yaml", manifest_overrides)

    if _looks_like_git_source(source):
        with tempfile.TemporaryDirectory(prefix="agent-factory-kernel-") as temp_dir:
            clone_path = Path(temp_dir) / "kernel"
            clone_cmd = ["git", "clone", "--depth", "1"]
            if git_ref:
                clone_cmd.extend(["--branch", git_ref])
            clone_cmd.extend([source, str(clone_path)])
            subprocess.run(clone_cmd, check=True)
            return sync_kernel_artifacts(clone_path, target_path)

    return sync_kernel_artifacts(source, target_path)


def _apply_manifest_overrides(manifest_path: Path, overrides: dict[str, str]) -> None:
    raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    for key, value in overrides.items():
        if value:
            raw[key] = value
    manifest_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
