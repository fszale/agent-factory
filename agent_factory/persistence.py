from __future__ import annotations

import os
from abc import ABC, abstractmethod
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import httpx


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


class PersistenceStore(ABC):
    @abstractmethod
    def create_thread(self, twin_id: str, title: str | None = None, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def list_threads(self, twin_id: str | None = None) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def get_thread(self, thread_id: str) -> dict[str, Any] | None:
        raise NotImplementedError

    @abstractmethod
    def append_message(
        self,
        thread_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def list_messages(self, thread_id: str) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def create_run(
        self,
        twin_id: str,
        run_type: str,
        status: str,
        input_payload: dict[str, Any],
        thread_id: str | None = None,
        task_id: str | None = None,
        model_profile: str | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def update_run(self, run_id: str, **fields: Any) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def list_runs(self, twin_id: str | None = None, thread_id: str | None = None) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def get_run(self, run_id: str) -> dict[str, Any] | None:
        raise NotImplementedError

    @abstractmethod
    def create_task(
        self,
        twin_id: str,
        task_type: str,
        payload: dict[str, Any],
        status: str = "pending",
        thread_id: str | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def update_task(self, task_id: str, **fields: Any) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def list_tasks(self, twin_id: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def get_task(self, task_id: str) -> dict[str, Any] | None:
        raise NotImplementedError

    @abstractmethod
    def record_event(
        self,
        twin_id: str,
        event_type: str,
        source: str,
        payload: dict[str, Any],
        status: str = "recorded",
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def list_events(self, twin_id: str | None = None, event_type: str | None = None) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def create_approval(
        self,
        twin_id: str,
        scope: str,
        request_payload: dict[str, Any],
        thread_id: str | None = None,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def resolve_approval(self, approval_id: str, status: str, resolution_payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def list_approvals(self, twin_id: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def create_correction(
        self,
        twin_id: str,
        scope: str,
        instruction: str,
        thread_id: str | None = None,
        message_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def list_corrections(self, twin_id: str | None = None, thread_id: str | None = None) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def create_artifact_proposal(
        self,
        twin_id: str,
        artifact_type: str,
        artifact_path: str,
        proposal: dict[str, Any],
        source_correction_id: str | None = None,
        status: str = "proposed",
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def list_artifact_proposals(self, twin_id: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def create_api_client(
        self,
        client_id: str,
        name: str,
        key_prefix: str,
        key_hash: str,
        factory_id: str | None = None,
        allowed_twins: list[str] | None = None,
        allowed_actions: list[str] | None = None,
        rate_limit_per_minute: int = 60,
        metadata: dict[str, Any] | None = None,
        status: str = "active",
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def list_api_clients(self, status: str | None = None) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def get_api_client_by_prefix(self, key_prefix: str) -> dict[str, Any] | None:
        raise NotImplementedError

    @abstractmethod
    def touch_api_client_usage(self, api_client_row_id: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def upsert_admin_identity(
        self,
        user_id: str,
        email: str | None,
        role: str = "admin",
        allowed_twins: list[str] | None = None,
        allowed_actions: list[str] | None = None,
        status: str = "active",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def get_admin_identity(self, user_id: str) -> dict[str, Any] | None:
        raise NotImplementedError

    @abstractmethod
    def list_admin_identities(self, status: str | None = None) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def record_audit_event(
        self,
        actor_type: str,
        actor_id: str,
        action: str,
        target_type: str,
        target_id: str | None = None,
        twin_id: str | None = None,
        factory_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def list_audit_events(
        self,
        twin_id: str | None = None,
        actor_type: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError


class InMemoryStore(PersistenceStore):
    def __init__(self) -> None:
        self._tables: dict[str, dict[str, dict[str, Any]]] = {
            "threads": {},
            "messages": {},
            "runs": {},
            "tasks": {},
            "events": {},
            "approvals": {},
            "corrections": {},
            "artifact_proposals": {},
            "api_clients": {},
            "admin_identities": {},
            "audit_events": {},
            "traces": {},
            "roi_snapshots": {},
            "improvement_candidates": {},
            "improvement_events": {},
        }

    def _insert(self, table: str, row: dict[str, Any], row_id: str | None = None) -> dict[str, Any]:
        if row_id is None and "id" not in row:
            row = deepcopy(row)
            row["id"] = str(uuid4())
        identifier = row_id or row["id"]
        self._tables[table][identifier] = deepcopy(row)
        return deepcopy(row)

    def _update(self, table: str, row_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        current = deepcopy(self._tables[table][row_id])
        current.update(fields)
        if "updated_at" in current:
            current["updated_at"] = utc_now()
        self._tables[table][row_id] = deepcopy(current)
        return deepcopy(current)

    def _list(self, table: str) -> list[dict[str, Any]]:
        return [deepcopy(item) for item in self._tables[table].values()]

    def create_thread(self, twin_id: str, title: str | None = None, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        timestamp = utc_now()
        return self._insert(
            "threads",
            {
                "id": str(uuid4()),
                "twin_id": twin_id,
                "title": title or f"{twin_id} thread",
                "status": "active",
                "metadata": metadata or {},
                "created_at": timestamp,
                "updated_at": timestamp,
            },
        )

    def list_threads(self, twin_id: str | None = None) -> list[dict[str, Any]]:
        items = self._list("threads")
        if twin_id:
            items = [item for item in items if item["twin_id"] == twin_id]
        return sorted(items, key=lambda item: item["created_at"])

    def get_thread(self, thread_id: str) -> dict[str, Any] | None:
        item = self._tables["threads"].get(thread_id)
        return deepcopy(item) if item else None

    def append_message(
        self,
        thread_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        timestamp = utc_now()
        row = self._insert(
            "messages",
            {
                "id": str(uuid4()),
                "thread_id": thread_id,
                "role": role,
                "content": content,
                "metadata": metadata or {},
                "run_id": run_id,
                "created_at": timestamp,
            },
        )
        if thread_id in self._tables["threads"]:
            self._tables["threads"][thread_id]["updated_at"] = timestamp
        return row

    def list_messages(self, thread_id: str) -> list[dict[str, Any]]:
        items = [item for item in self._list("messages") if item["thread_id"] == thread_id]
        return sorted(items, key=lambda item: item["created_at"])

    def create_run(
        self,
        twin_id: str,
        run_type: str,
        status: str,
        input_payload: dict[str, Any],
        thread_id: str | None = None,
        task_id: str | None = None,
        model_profile: str | None = None,
    ) -> dict[str, Any]:
        timestamp = utc_now()
        return self._insert(
            "runs",
            {
                "id": str(uuid4()),
                "twin_id": twin_id,
                "thread_id": thread_id,
                "task_id": task_id,
                "run_type": run_type,
                "status": status,
                "model_profile": model_profile,
                "provider": None,
                "model": None,
                "input_payload": input_payload,
                "output_payload": {},
                "error": None,
                "created_at": timestamp,
                "updated_at": timestamp,
            },
        )

    def update_run(self, run_id: str, **fields: Any) -> dict[str, Any]:
        return self._update("runs", run_id, fields)

    def list_runs(self, twin_id: str | None = None, thread_id: str | None = None) -> list[dict[str, Any]]:
        items = self._list("runs")
        if twin_id:
            items = [item for item in items if item["twin_id"] == twin_id]
        if thread_id:
            items = [item for item in items if item["thread_id"] == thread_id]
        return sorted(items, key=lambda item: item["created_at"])

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        item = self._tables["runs"].get(run_id)
        return deepcopy(item) if item else None

    def create_task(
        self,
        twin_id: str,
        task_type: str,
        payload: dict[str, Any],
        status: str = "pending",
        thread_id: str | None = None,
    ) -> dict[str, Any]:
        timestamp = utc_now()
        return self._insert(
            "tasks",
            {
                "id": str(uuid4()),
                "twin_id": twin_id,
                "thread_id": thread_id,
                "task_type": task_type,
                "status": status,
                "payload": payload,
                "result": {},
                "run_id": None,
                "created_at": timestamp,
                "updated_at": timestamp,
            },
        )

    def update_task(self, task_id: str, **fields: Any) -> dict[str, Any]:
        return self._update("tasks", task_id, fields)

    def list_tasks(self, twin_id: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
        items = self._list("tasks")
        if twin_id:
            items = [item for item in items if item["twin_id"] == twin_id]
        if status:
            items = [item for item in items if item["status"] == status]
        return sorted(items, key=lambda item: item["created_at"])

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        item = self._tables["tasks"].get(task_id)
        return deepcopy(item) if item else None

    def record_event(
        self,
        twin_id: str,
        event_type: str,
        source: str,
        payload: dict[str, Any],
        status: str = "recorded",
    ) -> dict[str, Any]:
        return self._insert(
            "events",
            {
                "id": str(uuid4()),
                "twin_id": twin_id,
                "event_type": event_type,
                "source": source,
                "payload": payload,
                "status": status,
                "created_at": utc_now(),
            },
        )

    def list_events(self, twin_id: str | None = None, event_type: str | None = None) -> list[dict[str, Any]]:
        items = self._list("events")
        if twin_id:
            items = [item for item in items if item["twin_id"] == twin_id]
        if event_type:
            items = [item for item in items if item["event_type"] == event_type]
        return sorted(items, key=lambda item: item["created_at"])

    def create_approval(
        self,
        twin_id: str,
        scope: str,
        request_payload: dict[str, Any],
        thread_id: str | None = None,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        timestamp = utc_now()
        return self._insert(
            "approvals",
            {
                "id": str(uuid4()),
                "twin_id": twin_id,
                "thread_id": thread_id,
                "run_id": run_id,
                "scope": scope,
                "status": "pending",
                "request_payload": request_payload,
                "resolution_payload": {},
                "created_at": timestamp,
                "updated_at": timestamp,
                "resolved_at": None,
            },
        )

    def resolve_approval(self, approval_id: str, status: str, resolution_payload: dict[str, Any]) -> dict[str, Any]:
        return self._update(
            "approvals",
            approval_id,
            {
                "status": status,
                "resolution_payload": resolution_payload,
                "resolved_at": utc_now(),
            },
        )

    def list_approvals(self, twin_id: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
        items = self._list("approvals")
        if twin_id:
            items = [item for item in items if item["twin_id"] == twin_id]
        if status:
            items = [item for item in items if item["status"] == status]
        return sorted(items, key=lambda item: item["created_at"])

    def create_correction(
        self,
        twin_id: str,
        scope: str,
        instruction: str,
        thread_id: str | None = None,
        message_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._insert(
            "corrections",
            {
                "id": str(uuid4()),
                "twin_id": twin_id,
                "thread_id": thread_id,
                "message_id": message_id,
                "scope": scope,
                "instruction": instruction,
                "payload": payload or {},
                "created_at": utc_now(),
            },
        )

    def list_corrections(self, twin_id: str | None = None, thread_id: str | None = None) -> list[dict[str, Any]]:
        items = self._list("corrections")
        if twin_id:
            items = [item for item in items if item["twin_id"] == twin_id]
        if thread_id:
            items = [item for item in items if item["thread_id"] == thread_id]
        return sorted(items, key=lambda item: item["created_at"])

    def create_artifact_proposal(
        self,
        twin_id: str,
        artifact_type: str,
        artifact_path: str,
        proposal: dict[str, Any],
        source_correction_id: str | None = None,
        status: str = "proposed",
    ) -> dict[str, Any]:
        timestamp = utc_now()
        return self._insert(
            "artifact_proposals",
            {
                "id": str(uuid4()),
                "twin_id": twin_id,
                "artifact_type": artifact_type,
                "artifact_path": artifact_path,
                "proposal": proposal,
                "source_correction_id": source_correction_id,
                "status": status,
                "created_at": timestamp,
                "updated_at": timestamp,
            },
        )

    def list_artifact_proposals(self, twin_id: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
        items = self._list("artifact_proposals")
        if twin_id:
            items = [item for item in items if item["twin_id"] == twin_id]
        if status:
            items = [item for item in items if item["status"] == status]
        return sorted(items, key=lambda item: item["created_at"])

    def create_api_client(
        self,
        client_id: str,
        name: str,
        key_prefix: str,
        key_hash: str,
        factory_id: str | None = None,
        allowed_twins: list[str] | None = None,
        allowed_actions: list[str] | None = None,
        rate_limit_per_minute: int = 60,
        metadata: dict[str, Any] | None = None,
        status: str = "active",
    ) -> dict[str, Any]:
        timestamp = utc_now()
        return self._insert(
            "api_clients",
            {
                "id": str(uuid4()),
                "client_id": client_id,
                "factory_id": factory_id,
                "name": name,
                "key_prefix": key_prefix,
                "key_hash": key_hash,
                "status": status,
                "allowed_twins": allowed_twins or ["*"],
                "allowed_actions": allowed_actions or [],
                "rate_limit_per_minute": rate_limit_per_minute,
                "metadata": metadata or {},
                "last_used_at": None,
                "created_at": timestamp,
                "updated_at": timestamp,
            },
        )

    def list_api_clients(self, status: str | None = None) -> list[dict[str, Any]]:
        items = self._list("api_clients")
        if status:
            items = [item for item in items if item["status"] == status]
        return sorted(items, key=lambda item: item["created_at"])

    def get_api_client_by_prefix(self, key_prefix: str) -> dict[str, Any] | None:
        for item in self._tables["api_clients"].values():
            if item["key_prefix"] == key_prefix:
                return deepcopy(item)
        return None

    def touch_api_client_usage(self, api_client_row_id: str) -> dict[str, Any]:
        return self._update("api_clients", api_client_row_id, {"last_used_at": utc_now()})

    def upsert_admin_identity(
        self,
        user_id: str,
        email: str | None,
        role: str = "admin",
        allowed_twins: list[str] | None = None,
        allowed_actions: list[str] | None = None,
        status: str = "active",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        timestamp = utc_now()
        existing = self._tables["admin_identities"].get(user_id)
        row = {
            "user_id": user_id,
            "email": email,
            "role": role,
            "allowed_twins": allowed_twins or ["*"],
            "allowed_actions": allowed_actions or ["*"],
            "status": status,
            "metadata": metadata or {},
            "created_at": existing["created_at"] if existing else timestamp,
            "updated_at": timestamp,
        }
        return self._insert("admin_identities", row, row_id=user_id)

    def get_admin_identity(self, user_id: str) -> dict[str, Any] | None:
        item = self._tables["admin_identities"].get(user_id)
        return deepcopy(item) if item else None

    def list_admin_identities(self, status: str | None = None) -> list[dict[str, Any]]:
        items = self._list("admin_identities")
        if status:
            items = [item for item in items if item["status"] == status]
        return sorted(items, key=lambda item: item["created_at"])

    def record_audit_event(
        self,
        actor_type: str,
        actor_id: str,
        action: str,
        target_type: str,
        target_id: str | None = None,
        twin_id: str | None = None,
        factory_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._insert(
            "audit_events",
            {
                "id": str(uuid4()),
                "actor_type": actor_type,
                "actor_id": actor_id,
                "factory_id": factory_id,
                "action": action,
                "target_type": target_type,
                "target_id": target_id,
                "twin_id": twin_id,
                "payload": payload or {},
                "created_at": utc_now(),
            },
        )

    def list_audit_events(
        self,
        twin_id: str | None = None,
        actor_type: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        items = self._list("audit_events")
        if twin_id:
            items = [item for item in items if item["twin_id"] == twin_id]
        if actor_type:
            items = [item for item in items if item["actor_type"] == actor_type]
        return sorted(items, key=lambda item: item["created_at"], reverse=True)[:limit]

    # -- Phase 2: improvement loop tables ---------------------------------- #
    def create_trace(
        self,
        twin_id: str,
        task_type: str,
        action: str,
        outcome: str,
        signals: dict[str, Any] | None = None,
        scores: dict[str, Any] | None = None,
        run_id: str | None = None,
        thread_id: str | None = None,
        correction_id: str | None = None,
    ) -> dict[str, Any]:
        return self._insert(
            "traces",
            {
                "id": str(uuid4()),
                "twin_id": twin_id,
                "task_type": task_type,
                "action": action,
                "outcome": outcome,
                "signals": signals or {},
                "scores": scores or {},
                "run_id": run_id,
                "thread_id": thread_id,
                "correction_id": correction_id,
                "created_at": utc_now(),
            },
        )

    def list_traces(self, twin_id: str | None = None, since: str | None = None, limit: int = 1000) -> list[dict[str, Any]]:
        items = self._list("traces")
        if twin_id:
            items = [i for i in items if i["twin_id"] == twin_id]
        if since:
            items = [i for i in items if i["created_at"] >= since]
        return sorted(items, key=lambda i: i["created_at"])[:limit]

    def create_roi_snapshot(self, twin_id: str, week_start: str, fields: dict[str, Any]) -> dict[str, Any]:
        row = {"id": str(uuid4()), "twin_id": twin_id, "week_start": week_start, "created_at": utc_now()}
        row.update(fields)
        return self._insert("roi_snapshots", row)

    def list_roi_snapshots(self, twin_id: str | None = None) -> list[dict[str, Any]]:
        items = self._list("roi_snapshots")
        if twin_id:
            items = [i for i in items if i["twin_id"] == twin_id]
        return sorted(items, key=lambda i: i["week_start"])

    def create_improvement_candidate(self, twin_id: str, candidate_type: str, payload: dict[str, Any], status: str = "proposed") -> dict[str, Any]:
        timestamp = utc_now()
        row = {
            "id": str(uuid4()),
            "twin_id": twin_id,
            "candidate_type": candidate_type,
            "status": status,
            "payload": payload,
            "created_at": timestamp,
            "updated_at": timestamp,
        }
        return self._insert("improvement_candidates", row)

    def update_improvement_candidate(self, candidate_id: str, **fields: Any) -> dict[str, Any]:
        return self._update("improvement_candidates", candidate_id, fields)

    def list_improvement_candidates(self, twin_id: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
        items = self._list("improvement_candidates")
        if twin_id:
            items = [i for i in items if i["twin_id"] == twin_id]
        if status:
            items = [i for i in items if i["status"] == status]
        return sorted(items, key=lambda i: i["created_at"])

    def create_improvement_event(self, twin_id: str, candidate_id: str, change_type: str, applied_mode: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._insert(
            "improvement_events",
            {
                "id": str(uuid4()),
                "twin_id": twin_id,
                "candidate_id": candidate_id,
                "change_type": change_type,
                "applied_mode": applied_mode,
                "payload": payload,
                "created_at": utc_now(),
            },
        )

    def list_improvement_events(self, twin_id: str | None = None) -> list[dict[str, Any]]:
        items = self._list("improvement_events")
        if twin_id:
            items = [i for i in items if i["twin_id"] == twin_id]
        return sorted(items, key=lambda i: i["created_at"])


class SupabaseStore(PersistenceStore):
    def __init__(self, url: str, service_role_key: str, client: httpx.Client | None = None) -> None:
        self.url = url.rstrip("/")
        self.service_role_key = service_role_key
        self.client = client or httpx.Client()

    def _headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        headers = {
            "apikey": self.service_role_key,
            "Authorization": f"Bearer {self.service_role_key}",
            "Content-Type": "application/json",
        }
        if extra:
            headers.update(extra)
        return headers

    def _list(self, table: str, params: dict[str, str] | None = None) -> list[dict[str, Any]]:
        response = self.client.get(
            f"{self.url}/rest/v1/{table}",
            params=params,
            headers=self._headers(),
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def _insert(self, table: str, row: dict[str, Any], upsert: bool = False, on_conflict: str | None = None) -> dict[str, Any]:
        headers = self._headers({"Prefer": "return=representation"})
        if upsert:
            prefer_value = "resolution=merge-duplicates,return=representation"
            headers["Prefer"] = prefer_value
        params = {"on_conflict": on_conflict} if on_conflict else None
        response = self.client.post(
            f"{self.url}/rest/v1/{table}",
            headers=headers,
            params=params,
            json=row,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()[0]

    def _update(self, table: str, selector: dict[str, str], fields: dict[str, Any]) -> dict[str, Any]:
        payload = deepcopy(fields)
        if "updated_at" not in payload:
            payload["updated_at"] = utc_now()
        response = self.client.patch(
            f"{self.url}/rest/v1/{table}",
            params=selector,
            headers=self._headers({"Prefer": "return=representation"}),
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        body = response.json()
        return body[0] if body else {}

    def _get_one(self, table: str, selector: dict[str, str]) -> dict[str, Any] | None:
        params = {"select": "*", "limit": "1"}
        params.update(selector)
        items = self._list(table, params=params)
        return items[0] if items else None

    def create_thread(self, twin_id: str, title: str | None = None, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        timestamp = utc_now()
        return self._insert(
            "threads",
            {
                "twin_id": twin_id,
                "title": title or f"{twin_id} thread",
                "status": "active",
                "metadata": metadata or {},
                "created_at": timestamp,
                "updated_at": timestamp,
            },
        )

    def list_threads(self, twin_id: str | None = None) -> list[dict[str, Any]]:
        params = {"select": "*", "order": "created_at.asc"}
        if twin_id:
            params["twin_id"] = f"eq.{twin_id}"
        return self._list("threads", params=params)

    def get_thread(self, thread_id: str) -> dict[str, Any] | None:
        return self._get_one("threads", {"id": f"eq.{thread_id}"})

    def append_message(
        self,
        thread_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        row = self._insert(
            "messages",
            {
                "thread_id": thread_id,
                "role": role,
                "content": content,
                "metadata": metadata or {},
                "run_id": run_id,
                "created_at": utc_now(),
            },
        )
        self._update("threads", {"id": f"eq.{thread_id}"}, {})
        return row

    def list_messages(self, thread_id: str) -> list[dict[str, Any]]:
        return self._list("messages", {"select": "*", "thread_id": f"eq.{thread_id}", "order": "created_at.asc"})

    def create_run(
        self,
        twin_id: str,
        run_type: str,
        status: str,
        input_payload: dict[str, Any],
        thread_id: str | None = None,
        task_id: str | None = None,
        model_profile: str | None = None,
    ) -> dict[str, Any]:
        timestamp = utc_now()
        return self._insert(
            "runs",
            {
                "twin_id": twin_id,
                "thread_id": thread_id,
                "task_id": task_id,
                "run_type": run_type,
                "status": status,
                "model_profile": model_profile,
                "provider": None,
                "model": None,
                "input_payload": input_payload,
                "output_payload": {},
                "error": None,
                "created_at": timestamp,
                "updated_at": timestamp,
            },
        )

    def update_run(self, run_id: str, **fields: Any) -> dict[str, Any]:
        return self._update("runs", {"id": f"eq.{run_id}"}, fields)

    def list_runs(self, twin_id: str | None = None, thread_id: str | None = None) -> list[dict[str, Any]]:
        params = {"select": "*", "order": "created_at.asc"}
        if twin_id:
            params["twin_id"] = f"eq.{twin_id}"
        if thread_id:
            params["thread_id"] = f"eq.{thread_id}"
        return self._list("runs", params=params)

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        return self._get_one("runs", {"id": f"eq.{run_id}"})

    def create_task(
        self,
        twin_id: str,
        task_type: str,
        payload: dict[str, Any],
        status: str = "pending",
        thread_id: str | None = None,
    ) -> dict[str, Any]:
        timestamp = utc_now()
        return self._insert(
            "tasks",
            {
                "twin_id": twin_id,
                "thread_id": thread_id,
                "task_type": task_type,
                "status": status,
                "payload": payload,
                "result": {},
                "run_id": None,
                "created_at": timestamp,
                "updated_at": timestamp,
            },
        )

    def update_task(self, task_id: str, **fields: Any) -> dict[str, Any]:
        return self._update("tasks", {"id": f"eq.{task_id}"}, fields)

    def list_tasks(self, twin_id: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
        params = {"select": "*", "order": "created_at.asc"}
        if twin_id:
            params["twin_id"] = f"eq.{twin_id}"
        if status:
            params["status"] = f"eq.{status}"
        return self._list("tasks", params=params)

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        return self._get_one("tasks", {"id": f"eq.{task_id}"})

    def record_event(
        self,
        twin_id: str,
        event_type: str,
        source: str,
        payload: dict[str, Any],
        status: str = "recorded",
    ) -> dict[str, Any]:
        return self._insert(
            "events",
            {
                "twin_id": twin_id,
                "event_type": event_type,
                "source": source,
                "payload": payload,
                "status": status,
                "created_at": utc_now(),
            },
        )

    def list_events(self, twin_id: str | None = None, event_type: str | None = None) -> list[dict[str, Any]]:
        params = {"select": "*", "order": "created_at.asc"}
        if twin_id:
            params["twin_id"] = f"eq.{twin_id}"
        if event_type:
            params["event_type"] = f"eq.{event_type}"
        return self._list("events", params=params)

    def create_approval(
        self,
        twin_id: str,
        scope: str,
        request_payload: dict[str, Any],
        thread_id: str | None = None,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        timestamp = utc_now()
        return self._insert(
            "approvals",
            {
                "twin_id": twin_id,
                "thread_id": thread_id,
                "run_id": run_id,
                "scope": scope,
                "status": "pending",
                "request_payload": request_payload,
                "resolution_payload": {},
                "created_at": timestamp,
                "updated_at": timestamp,
                "resolved_at": None,
            },
        )

    def resolve_approval(self, approval_id: str, status: str, resolution_payload: dict[str, Any]) -> dict[str, Any]:
        return self._update(
            "approvals",
            {"id": f"eq.{approval_id}"},
            {"status": status, "resolution_payload": resolution_payload, "resolved_at": utc_now()},
        )

    def list_approvals(self, twin_id: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
        params = {"select": "*", "order": "created_at.asc"}
        if twin_id:
            params["twin_id"] = f"eq.{twin_id}"
        if status:
            params["status"] = f"eq.{status}"
        return self._list("approvals", params=params)

    def create_correction(
        self,
        twin_id: str,
        scope: str,
        instruction: str,
        thread_id: str | None = None,
        message_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._insert(
            "corrections",
            {
                "twin_id": twin_id,
                "thread_id": thread_id,
                "message_id": message_id,
                "scope": scope,
                "instruction": instruction,
                "payload": payload or {},
                "created_at": utc_now(),
            },
        )

    def list_corrections(self, twin_id: str | None = None, thread_id: str | None = None) -> list[dict[str, Any]]:
        params = {"select": "*", "order": "created_at.asc"}
        if twin_id:
            params["twin_id"] = f"eq.{twin_id}"
        if thread_id:
            params["thread_id"] = f"eq.{thread_id}"
        return self._list("corrections", params=params)

    def create_artifact_proposal(
        self,
        twin_id: str,
        artifact_type: str,
        artifact_path: str,
        proposal: dict[str, Any],
        source_correction_id: str | None = None,
        status: str = "proposed",
    ) -> dict[str, Any]:
        timestamp = utc_now()
        return self._insert(
            "artifact_proposals",
            {
                "twin_id": twin_id,
                "artifact_type": artifact_type,
                "artifact_path": artifact_path,
                "proposal": proposal,
                "source_correction_id": source_correction_id,
                "status": status,
                "created_at": timestamp,
                "updated_at": timestamp,
            },
        )

    def list_artifact_proposals(self, twin_id: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
        params = {"select": "*", "order": "created_at.asc"}
        if twin_id:
            params["twin_id"] = f"eq.{twin_id}"
        if status:
            params["status"] = f"eq.{status}"
        return self._list("artifact_proposals", params=params)

    def create_api_client(
        self,
        client_id: str,
        name: str,
        key_prefix: str,
        key_hash: str,
        factory_id: str | None = None,
        allowed_twins: list[str] | None = None,
        allowed_actions: list[str] | None = None,
        rate_limit_per_minute: int = 60,
        metadata: dict[str, Any] | None = None,
        status: str = "active",
    ) -> dict[str, Any]:
        timestamp = utc_now()
        return self._insert(
            "api_clients",
            {
                "client_id": client_id,
                "factory_id": factory_id,
                "name": name,
                "key_prefix": key_prefix,
                "key_hash": key_hash,
                "status": status,
                "allowed_twins": allowed_twins or ["*"],
                "allowed_actions": allowed_actions or [],
                "rate_limit_per_minute": rate_limit_per_minute,
                "metadata": metadata or {},
                "last_used_at": None,
                "created_at": timestamp,
                "updated_at": timestamp,
            },
        )

    def list_api_clients(self, status: str | None = None) -> list[dict[str, Any]]:
        params = {"select": "*", "order": "created_at.asc"}
        if status:
            params["status"] = f"eq.{status}"
        return self._list("api_clients", params=params)

    def get_api_client_by_prefix(self, key_prefix: str) -> dict[str, Any] | None:
        return self._get_one("api_clients", {"key_prefix": f"eq.{key_prefix}"})

    def touch_api_client_usage(self, api_client_row_id: str) -> dict[str, Any]:
        return self._update("api_clients", {"id": f"eq.{api_client_row_id}"}, {"last_used_at": utc_now()})

    def upsert_admin_identity(
        self,
        user_id: str,
        email: str | None,
        role: str = "admin",
        allowed_twins: list[str] | None = None,
        allowed_actions: list[str] | None = None,
        status: str = "active",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        timestamp = utc_now()
        return self._insert(
            "admin_identities",
            {
                "user_id": user_id,
                "email": email,
                "role": role,
                "allowed_twins": allowed_twins or ["*"],
                "allowed_actions": allowed_actions or ["*"],
                "status": status,
                "metadata": metadata or {},
                "created_at": timestamp,
                "updated_at": timestamp,
            },
            upsert=True,
            on_conflict="user_id",
        )

    def get_admin_identity(self, user_id: str) -> dict[str, Any] | None:
        return self._get_one("admin_identities", {"user_id": f"eq.{user_id}"})

    def list_admin_identities(self, status: str | None = None) -> list[dict[str, Any]]:
        params = {"select": "*", "order": "created_at.asc"}
        if status:
            params["status"] = f"eq.{status}"
        return self._list("admin_identities", params=params)

    def record_audit_event(
        self,
        actor_type: str,
        actor_id: str,
        action: str,
        target_type: str,
        target_id: str | None = None,
        twin_id: str | None = None,
        factory_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._insert(
            "audit_events",
            {
                "actor_type": actor_type,
                "actor_id": actor_id,
                "factory_id": factory_id,
                "action": action,
                "target_type": target_type,
                "target_id": target_id,
                "twin_id": twin_id,
                "payload": payload or {},
                "created_at": utc_now(),
            },
        )

    def list_audit_events(
        self,
        twin_id: str | None = None,
        actor_type: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        params = {"select": "*", "order": "created_at.desc", "limit": str(limit)}
        if twin_id:
            params["twin_id"] = f"eq.{twin_id}"
        if actor_type:
            params["actor_type"] = f"eq.{actor_type}"
        return self._list("audit_events", params=params)

    # -- Phase 2: improvement loop tables ---------------------------------- #
    def create_trace(
        self,
        twin_id: str,
        task_type: str,
        action: str,
        outcome: str,
        signals: dict[str, Any] | None = None,
        scores: dict[str, Any] | None = None,
        run_id: str | None = None,
        thread_id: str | None = None,
        correction_id: str | None = None,
    ) -> dict[str, Any]:
        return self._insert(
            "traces",
            {
                "twin_id": twin_id,
                "task_type": task_type,
                "action": action,
                "outcome": outcome,
                "signals": signals or {},
                "scores": scores or {},
                "run_id": run_id,
                "thread_id": thread_id,
                "correction_id": correction_id,
                "created_at": utc_now(),
            },
        )

    def list_traces(self, twin_id: str | None = None, since: str | None = None, limit: int = 1000) -> list[dict[str, Any]]:
        params = {"select": "*", "order": "created_at.asc", "limit": str(limit)}
        if twin_id:
            params["twin_id"] = f"eq.{twin_id}"
        if since:
            params["created_at"] = f"gte.{since}"
        return self._list("traces", params=params)

    def create_roi_snapshot(self, twin_id: str, week_start: str, fields: dict[str, Any]) -> dict[str, Any]:
        row = {"twin_id": twin_id, "week_start": week_start, "created_at": utc_now()}
        row.update(fields)
        return self._insert("roi_snapshots", row)

    def list_roi_snapshots(self, twin_id: str | None = None) -> list[dict[str, Any]]:
        params = {"select": "*", "order": "week_start.asc"}
        if twin_id:
            params["twin_id"] = f"eq.{twin_id}"
        return self._list("roi_snapshots", params=params)

    def create_improvement_candidate(self, twin_id: str, candidate_type: str, payload: dict[str, Any], status: str = "proposed") -> dict[str, Any]:
        timestamp = utc_now()
        return self._insert(
            "improvement_candidates",
            {
                "twin_id": twin_id,
                "candidate_type": candidate_type,
                "status": status,
                "payload": payload,
                "created_at": timestamp,
                "updated_at": timestamp,
            },
        )

    def update_improvement_candidate(self, candidate_id: str, **fields: Any) -> dict[str, Any]:
        return self._update("improvement_candidates", {"id": f"eq.{candidate_id}"}, fields)

    def list_improvement_candidates(self, twin_id: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
        params = {"select": "*", "order": "created_at.asc"}
        if twin_id:
            params["twin_id"] = f"eq.{twin_id}"
        if status:
            params["status"] = f"eq.{status}"
        return self._list("improvement_candidates", params=params)

    def create_improvement_event(self, twin_id: str, candidate_id: str, change_type: str, applied_mode: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._insert(
            "improvement_events",
            {
                "twin_id": twin_id,
                "candidate_id": candidate_id,
                "change_type": change_type,
                "applied_mode": applied_mode,
                "payload": payload,
                "created_at": utc_now(),
            },
        )

    def list_improvement_events(self, twin_id: str | None = None) -> list[dict[str, Any]]:
        params = {"select": "*", "order": "created_at.asc"}
        if twin_id:
            params["twin_id"] = f"eq.{twin_id}"
        return self._list("improvement_events", params=params)


def build_store_from_env() -> PersistenceStore:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if url and key:
        return SupabaseStore(url=url, service_role_key=key)
    return InMemoryStore()
