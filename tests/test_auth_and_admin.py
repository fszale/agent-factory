from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from agent_factory.app import create_app
from agent_factory.auth import AuthService, encode_jwt_hs256
from agent_factory.installer import install_twin
from agent_factory.persistence import InMemoryStore
from agent_factory.providers.stub import StubProvider


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_TWIN = ROOT / "tests" / "fixtures" / "sample_twin"


class AuthAndAdminTests(unittest.TestCase):
    def test_admin_can_create_api_client_and_machine_can_use_scoped_endpoints(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            install_root = Path(temp_dir) / "installed"
            install_twin(FIXTURE_TWIN, install_root)

            store = InMemoryStore()
            store.upsert_admin_identity(
                user_id="admin-user",
                email="admin@example.com",
                role="admin",
                allowed_actions=["*"],
                allowed_twins=["*"],
            )
            auth_service = AuthService(store, require_auth=True, supabase_jwt_secret="test-secret")
            app = create_app(
                install_root,
                providers={"xai": StubProvider(), "stub": StubProvider()},
                repository=store,
                auth_service=auth_service,
            )
            client = TestClient(app)

            unauthorized = client.get("/twins")
            self.assertEqual(unauthorized.status_code, 401)

            admin_token = encode_jwt_hs256(
                {
                    "sub": "admin-user",
                    "email": "admin@example.com",
                    "exp": int(time.time()) + 3600,
                },
                "test-secret",
            )
            admin_headers = {"Authorization": f"Bearer {admin_token}"}

            create_client = client.post(
                "/api-clients",
                headers=admin_headers,
                json={
                    "client_id": "factory-agent",
                    "name": "Factory Agent",
                    "factory_id": "factory-a",
                    "allowed_twins": ["sample"],
                    "allowed_actions": [
                        "twin:read",
                        "chat:write",
                        "thread:read",
                        "thread:write",
                        "task:create",
                        "task:read",
                        "capability:read",
                        "event:write",
                    ],
                },
            )
            self.assertEqual(create_client.status_code, 200)
            machine_key = create_client.json()["raw_api_key"]
            machine_headers = {"Authorization": f"Bearer {machine_key}"}

            twins_response = client.get("/twins", headers=machine_headers)
            self.assertEqual(twins_response.status_code, 200)
            self.assertEqual(twins_response.json()[0]["twin_id"], "sample")

            thread_response = client.post("/threads", headers=machine_headers, json={"twin_id": "sample", "title": "Scoped Thread"})
            self.assertEqual(thread_response.status_code, 200)
            thread_id = thread_response.json()["id"]

            message_response = client.post(
                f"/threads/{thread_id}/messages",
                headers=machine_headers,
                json={"message": "How do I improve engineering execution?"},
            )
            self.assertEqual(message_response.status_code, 200)

            task_response = client.post(
                "/tasks",
                headers=machine_headers,
                json={
                    "twin_id": "sample",
                    "task_type": "agent_instruction",
                    "input_payload": {"instruction": "Improve execution"},
                },
            )
            self.assertEqual(task_response.status_code, 200)

            forbidden_admin = client.get("/approvals", headers=machine_headers)
            self.assertEqual(forbidden_admin.status_code, 403)

            audit_response = client.get("/audit", headers=admin_headers)
            self.assertEqual(audit_response.status_code, 200)
            self.assertGreaterEqual(len(audit_response.json()), 2)
