from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from agent_factory.app import create_app
from agent_factory.installer import install_twin
from agent_factory.persistence import InMemoryStore
from agent_factory.providers.stub import StubProvider
from agent_factory.registry import TwinRegistry
from agent_factory.runtime import TwinRuntime


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_TWIN = ROOT / "tests" / "fixtures" / "sample_twin"


class RuntimeAndAPITests(unittest.TestCase):
    def test_runtime_chat_with_stubbed_xai_provider(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            install_root = Path(temp_dir) / "installed"
            install_twin(FIXTURE_TWIN, install_root)
            registry = TwinRegistry(install_root)
            runtime = TwinRuntime(
                registry,
                providers={"xai": StubProvider(), "stub": StubProvider()},
            )

            result = runtime.chat(
                twin_id="sample",
                user_message="How should I improve engineering execution in an agent factory?",
            )

            self.assertEqual(result.provider, "stub")
            self.assertEqual(result.model, "stub-fast")
            self.assertGreater(len(result.references), 0)
            self.assertIn("engineering", result.text.lower())

    def test_api_lists_and_chats_with_installed_twin(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            install_root = Path(temp_dir) / "installed"
            install_twin(FIXTURE_TWIN, install_root)

            app = create_app(
                install_root,
                providers={"xai": StubProvider(), "stub": StubProvider()},
                repository=InMemoryStore(),
            )
            client = TestClient(app)

            list_response = client.get("/twins")
            self.assertEqual(list_response.status_code, 200)
            payload = list_response.json()
            self.assertEqual(len(payload), 1)
            self.assertEqual(payload[0]["twin_id"], "sample")

            chat_response = client.post(
                "/twins/sample/chat",
                json={"message": "What should this twin optimize for?"},
            )
            self.assertEqual(chat_response.status_code, 200)
            chat_payload = chat_response.json()
            self.assertEqual(chat_payload["model"], "stub-fast")
            self.assertGreater(len(chat_payload["references"]), 0)

    def test_threaded_chat_persists_messages_and_runs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            install_root = Path(temp_dir) / "installed"
            install_twin(FIXTURE_TWIN, install_root)
            app = create_app(
                install_root,
                providers={"xai": StubProvider(), "stub": StubProvider()},
                repository=InMemoryStore(),
            )
            client = TestClient(app)

            thread_response = client.post("/threads", json={"twin_id": "sample", "title": "Execution Thread"})
            self.assertEqual(thread_response.status_code, 200)
            thread_id = thread_response.json()["id"]

            send_response = client.post(
                f"/threads/{thread_id}/messages",
                json={"message": "How do I improve engineering execution?"},
            )
            self.assertEqual(send_response.status_code, 200)
            payload = send_response.json()
            self.assertEqual(payload["run"]["status"], "completed")
            self.assertEqual(len(payload["messages"]), 2)

            messages_response = client.get(f"/threads/{thread_id}/messages")
            self.assertEqual(messages_response.status_code, 200)
            messages_payload = messages_response.json()
            self.assertEqual(len(messages_payload), 2)
            self.assertEqual(messages_payload[0]["role"], "user")
            self.assertEqual(messages_payload[1]["role"], "assistant")

    def test_agent_operations_endpoints_record_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            install_root = Path(temp_dir) / "installed"
            install_twin(FIXTURE_TWIN, install_root)
            app = create_app(
                install_root,
                providers={"xai": StubProvider(), "stub": StubProvider()},
                repository=InMemoryStore(),
            )
            client = TestClient(app)

            capabilities = client.get("/twins/sample/capabilities")
            self.assertEqual(capabilities.status_code, 200)
            self.assertIn("model_profiles", capabilities.json())

            task_response = client.post(
                "/tasks",
                json={
                    "twin_id": "sample",
                    "task_type": "agent_instruction",
                    "input_payload": {"instruction": "Improve engineering execution"},
                },
            )
            self.assertEqual(task_response.status_code, 200)
            task_payload = task_response.json()
            self.assertEqual(task_payload["task"]["status"], "completed")

            event_response = client.post(
                "/events",
                json={
                    "twin_id": "sample",
                    "event_type": "sample_task_completed",
                    "source": "test-suite",
                    "payload": {"task_id": task_payload["task"]["id"]},
                },
            )
            self.assertEqual(event_response.status_code, 200)

            correction_response = client.post(
                "/corrections",
                json={
                    "twin_id": "sample",
                    "scope": "response",
                    "instruction": "Prefer more concrete next steps",
                    "payload": {"artifact_path": "prompts/system.md"},
                },
            )
            self.assertEqual(correction_response.status_code, 200)
            correction_payload = correction_response.json()
            self.assertIsNotNone(correction_payload["artifact_proposal"])

            approval_response = client.post(
                "/approvals",
                json={
                    "twin_id": "sample",
                    "scope": "artifact_promotion",
                    "request_payload": {"proposal_id": correction_payload["artifact_proposal"]["id"]},
                },
            )
            self.assertEqual(approval_response.status_code, 200)
            approval_id = approval_response.json()["id"]

            resolve_response = client.post(
                f"/approvals/{approval_id}/resolve",
                json={"status": "approved", "resolution_payload": {"reviewer": "test-suite"}},
            )
            self.assertEqual(resolve_response.status_code, 200)
            self.assertEqual(resolve_response.json()["status"], "approved")
