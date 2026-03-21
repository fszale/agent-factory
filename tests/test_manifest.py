from __future__ import annotations

import filecmp
import tempfile
import unittest
from pathlib import Path

from agent_factory.config import load_manifest
from agent_factory.kernel_sync import (
    EXPORTED_DIRECTORIES,
    EXPORTED_FILES,
    compose_twin_from_kernel_source,
)


ROOT = Path(__file__).resolve().parents[1]
KERNEL_ROOT = ROOT.parent / "agent-kernel"
FIXTURE_TWIN = ROOT / "tests" / "fixtures" / "sample_twin"
GENERIC_SEED = ROOT / "twin_seeds" / "principal-operator"


def _relative_file_set(root: Path, directories: list[str], files: list[str]) -> set[str]:
    results: set[str] = set()
    for file_name in files:
        if (root / file_name).exists():
            results.add(file_name)
    for directory_name in directories:
        base = root / directory_name
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.is_file():
                results.add(str(path.relative_to(root)))
    return results


class TwinManifestTests(unittest.TestCase):
    def test_sample_fixture_manifest_loads(self) -> None:
        manifest = load_manifest(FIXTURE_TWIN / "twin.yaml")
        self.assertEqual(manifest.twin_id, "sample")
        self.assertEqual(manifest.default_model_profile, "fast")

    def test_generic_seed_uses_requested_reasoning_model(self) -> None:
        manifest = load_manifest(GENERIC_SEED / "twin.yaml")
        self.assertEqual(
            manifest.model_profiles["deep"].model,
            "grok-4.20-0309-reasoning",
        )
        self.assertEqual(manifest.default_model_profile, "deep")
        self.assertEqual(manifest.twin_id, "principal_operator")

    def test_voice_and_avatar_are_provisioned_but_disabled_in_seed(self) -> None:
        manifest = load_manifest(GENERIC_SEED / "twin.yaml")
        self.assertIn("voice", manifest.channels)
        self.assertIn("avatar", manifest.channels)
        self.assertFalse(manifest.channels["voice"].enabled)
        self.assertFalse(manifest.channels["avatar"].enabled)

    def test_import_from_local_kernel_source_composes_twin(self) -> None:
        if not KERNEL_ROOT.exists():
            self.skipTest("Local sibling agent-kernel repo not found")

        with tempfile.TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir) / "filip"
            compose_twin_from_kernel_source(
                source=str(KERNEL_ROOT),
                twin_root=output_root,
                seed_root=GENERIC_SEED,
                overwrite=True,
                manifest_overrides={
                    "twin_id": "filip",
                    "name": "Filip's Digital Twin - Principal Operator",
                    "owner": "Filip Szalewicz",
                },
            )

            manifest = load_manifest(output_root / "twin.yaml")
            self.assertEqual(manifest.twin_id, "filip")
            self.assertTrue((output_root / "skills").exists())
            self.assertTrue((output_root / "prompts").exists())
            self.assertTrue((output_root / "templates").exists())
            self.assertTrue((output_root / "AGENTS.md").exists())

    def test_imported_kernel_bundle_matches_local_export_when_available(self) -> None:
        if not KERNEL_ROOT.exists():
            self.skipTest("Local sibling agent-kernel repo not found")

        with tempfile.TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir) / "filip"
            compose_twin_from_kernel_source(
                source=str(KERNEL_ROOT),
                twin_root=output_root,
                seed_root=GENERIC_SEED,
                overwrite=True,
                manifest_overrides={"twin_id": "filip"},
            )

            expected = _relative_file_set(KERNEL_ROOT, EXPORTED_DIRECTORIES, EXPORTED_FILES)
            actual = _relative_file_set(output_root, EXPORTED_DIRECTORIES, EXPORTED_FILES)
            self.assertEqual(actual, expected)

            for relative_path in sorted(expected):
                self.assertTrue(
                    filecmp.cmp(KERNEL_ROOT / relative_path, output_root / relative_path, shallow=False),
                    msg=f"Kernel export drift detected for {relative_path}",
                )
