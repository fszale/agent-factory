from __future__ import annotations

import shutil
from pathlib import Path

from agent_factory.config import load_manifest


def install_twin(source_dir: str | Path, destination_root: str | Path, overwrite: bool = False) -> Path:
    source_path = Path(source_dir).resolve()
    destination_path = Path(destination_root).resolve()
    manifest = load_manifest(source_path / "twin.yaml")
    target_dir = destination_path / manifest.twin_id

    destination_path.mkdir(parents=True, exist_ok=True)

    if target_dir.exists():
        if not overwrite:
            raise FileExistsError(
                f"Twin '{manifest.twin_id}' is already installed at {target_dir}. Pass overwrite=True to replace it."
            )
        shutil.rmtree(target_dir)

    shutil.copytree(source_path, target_dir)
    load_manifest(target_dir / "twin.yaml")
    return target_dir
