from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_factory.kernel_sync import compose_twin_from_kernel_source


ROOT = Path(__file__).resolve().parents[1]
GENERIC_SEED = ROOT / "twin_seeds" / "principal-operator"


class KernelImportTests(unittest.TestCase):
    def test_git_source_invokes_clone_before_sync(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target_root = Path(temp_dir) / "filip"

            with patch("agent_factory.kernel_sync.subprocess.run") as run_mock:
                with patch("agent_factory.kernel_sync.sync_kernel_artifacts", return_value=["skills"]) as sync_mock:
                    copied = compose_twin_from_kernel_source(
                        source="https://github.com/fszale/agent-kernel.git",
                        twin_root=target_root,
                        seed_root=GENERIC_SEED,
                        overwrite=True,
                        git_ref="main",
                        manifest_overrides={"twin_id": "filip"},
                    )

            self.assertEqual(copied, ["skills"])
            run_mock.assert_called_once()
            called_command = run_mock.call_args.args[0]
            self.assertIn("git", called_command[0])
            self.assertIn("clone", called_command)
            self.assertIn("--branch", called_command)
            self.assertIn("main", called_command)
            sync_mock.assert_called_once()
