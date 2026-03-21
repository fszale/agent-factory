from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from agent_factory.installer import install_twin
from agent_factory.providers.stub import StubProvider
from agent_factory.registry import TwinRegistry
from agent_factory.runtime import TwinRuntime
from agent_factory.smoke import run_smoke_suite


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_TWIN = ROOT / "tests" / "fixtures" / "sample_twin"


class CLIAndSmokeTests(unittest.TestCase):
    def test_cli_list_outputs_installed_twins(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            install_root = Path(temp_dir) / "installed"
            install_twin(FIXTURE_TWIN, install_root)

            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "agent_factory.cli",
                    "list",
                    "--registry-root",
                    str(install_root),
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            payload = json.loads(completed.stdout)
            self.assertEqual(payload[0]["twin_id"], "sample")

    def test_smoke_suite_passes_for_reference_twin(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            install_root = Path(temp_dir) / "installed"
            install_twin(FIXTURE_TWIN, install_root)
            registry = TwinRegistry(install_root)
            runtime = TwinRuntime(
                registry,
                providers={"xai": StubProvider(), "stub": StubProvider()},
            )
            twin = registry.get("sample")

            results = run_smoke_suite(runtime, twin)
            self.assertGreater(len(results), 0)
            self.assertTrue(all(result.passed for result in results))
