from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agent_factory.installer import install_twin
from agent_factory.registry import TwinRegistry


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_TWIN = ROOT / "tests" / "fixtures" / "sample_twin"


class InstallerAndRegistryTests(unittest.TestCase):
    def test_install_and_load_reference_twin(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            install_root = Path(temp_dir) / "installed"
            installed_dir = install_twin(FIXTURE_TWIN, install_root)
            self.assertTrue((installed_dir / "twin.yaml").exists())

            registry = TwinRegistry(install_root)
            twins = registry.list()
            self.assertEqual(len(twins), 1)
            self.assertEqual(twins[0].manifest.twin_id, "sample")
