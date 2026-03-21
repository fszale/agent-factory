from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from agent_factory.auth import AuthService, Principal, generate_api_key
from agent_factory.persistence import PersistenceStore, build_store_from_env
from agent_factory.providers.base import ModelProvider
from agent_factory.registry import TwinRegistry
from agent_factory.runtime import TwinRuntime
from agent_factory.ui import ADMIN_HTML, INDEX_HTML


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    model_profile: str | None = None
    top_k: int = Field(default=3, ge=1, le=10)


class ThreadCreateRequest(BaseModel):
    twin_id: str
    title: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ThreadMessageRequest(BaseModel):
    message: str = Field(min_length=1)
    model_profile: str | None = None
    top_k: int = Field(default=3, ge=1, le=10)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TaskCreateRequest(BaseModel):
    twin_id: str
    task_type: str
    input_payload: dict[str, Any] = Field(default_factory=dict)
    thread_id: str | None = None
    model_profile: str | None = None
    top_k: int = Field(default=3, ge=1, le=10)
    require_approval: bool = False


class EventCreateRequest(BaseModel):
    twin_id: str
    event_type: str
    source: str
    payload: dict[str, Any] = Field(default_factory=dict)
    status: str = "recorded"


class ApprovalCreateRequest(BaseModel):
    twin_id: str
    scope: str
    request_payload: dict[str, Any] = Field(default_factory=dict)
    thread_id: str | None = None
    run_id: str | None = None


class ApprovalResolveRequest(BaseModel):
    status: str
    resolution_payload: dict[str, Any] = Field(default_factory=dict)


class CorrectionCreateRequest(BaseModel):
    twin_id: str
    scope: str
    instruction: str
    thread_id: str | None = None
    message_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class ArtifactProposalCreateRequest(BaseModel):
    twin_id: str
    artifact_type: str
    artifact_path: str
    proposal: dict[str, Any] = Field(default_factory=dict)
    source_correction_id: str | None = None
    status: str = "proposed"


class ApiClientCreateRequest(BaseModel):
    client_id: str
    name: str
    factory_id: str | None = None
    allowed_twins: list[str] = Field(default_factory=lambda: ["*"])
    allowed_actions: list[str] = Field(default_factory=list)
    rate_limit_per_minute: int = Field(default=60, ge=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AdminIdentityUpsertRequest(BaseModel):
    user_id: str
    email: str | None = None
    role: str = "admin"
    allowed_twins: list[str] = Field(default_factory=lambda: ["*"])
    allowed_actions: list[str] = Field(default_factory=lambda: ["*"])
    status: str = "active"
    metadata: dict[str, Any] = Field(default_factory=dict)


def create_app(
    registry_root: str | Path,
    providers: dict[str, ModelProvider] | None = None,
    repository: PersistenceStore | None = None,
    auth_service: AuthService | None = None,
) -> FastAPI:
    registry = TwinRegistry(registry_root)
    runtime = TwinRuntime(registry, providers=providers)
    store = repository or build_store_from_env()
    auth = auth_service or AuthService(store)

    app = FastAPI(title="agent-factory", version="0.3.0")
    app.state.registry = registry
    app.state.runtime = runtime
    app.state.store = store
    app.state.auth = auth

    def _principal(request: Request) -> Principal:
        return auth.authenticate_request(request)

    def _authorize(
        request: Request,
        scopes: list[str] | None = None,
        twin_id: str | None = None,
        admin_only: bool = False,
    ) -> Principal:
        principal = _principal(request)
        return auth.require(principal, scopes=scopes, twin_id=twin_id, admin_only=admin_only)

    def _audit(
        principal: Principal,
        action: str,
        target_type: str,
        target_id: str | None = None,
        twin_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        store.record_audit_event(
            actor_type=principal.kind,
            actor_id=principal.identifier,
            action=action,
            target_type=target_type,
            target_id=target_id,
            twin_id=twin_id,
            factory_id=principal.factory_id,
            payload=payload,
        )

    def _get_twin_or_404(twin_id: str) -> dict[str, object]:
        try:
            twin = registry.get(twin_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {
            "twin_id": twin.manifest.twin_id,
            "name": twin.manifest.name,
            "description": twin.manifest.description,
            "owner": twin.manifest.owner,
            "tags": twin.manifest.tags,
            "default_model_profile": twin.manifest.default_model_profile,
            "model_profiles": {
                key: profile.model_dump() for key, profile in twin.manifest.model_profiles.items()
            },
            "channels": {key: channel.model_dump() for key, channel in twin.manifest.channels.items()},
            "guardrails": twin.manifest.guardrails.model_dump(),
            "corrections": twin.manifest.corrections.model_dump(),
        }

    def _run_chat(
        twin_id: str,
        message: str,
        model_profile: str | None,
        top_k: int,
        prior_messages: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        try:
            result = runtime.chat(
                twin_id=twin_id,
                user_message=message,
                model_profile=model_profile,
                top_k=top_k,
                prior_messages=prior_messages or [],
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        return {
            "twin_id": result.twin_id,
            "response": result.text,
            "model_profile": result.model_profile,
            "provider": result.provider,
            "model": result.model,
            "references": result.references,
            "response_id": result.response_id,
        }

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return INDEX_HTML

    @app.get("/admin", response_class=HTMLResponse)
    def admin_index() -> str:
        return ADMIN_HTML

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/me")
    def me(request: Request) -> dict[str, Any]:
        return _principal(request).as_dict()

    @app.get("/twins")
    def list_twins(request: Request) -> list[dict[str, object]]:
        _authorize(request, scopes=["twin:read"])
        items: list[dict[str, object]] = []
        for twin in registry.list():
            items.append(
                {
                    "twin_id": twin.manifest.twin_id,
                    "name": twin.manifest.name,
                    "default_model_profile": twin.manifest.default_model_profile,
                    "channels": {key: channel.model_dump() for key, channel in twin.manifest.channels.items()},
                }
            )
        return items

    @app.get("/twins/{twin_id}")
    def get_twin(twin_id: str, request: Request) -> dict[str, object]:
        _authorize(request, scopes=["twin:read"], twin_id=twin_id)
        return _get_twin_or_404(twin_id)

    @app.get("/twins/{twin_id}/capabilities")
    def get_capabilities(twin_id: str, request: Request) -> dict[str, object]:
        _authorize(request, scopes=["capability:read"], twin_id=twin_id)
        try:
            return runtime.describe_capabilities(twin_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/twins/{twin_id}/chat")
    def chat(twin_id: str, request: Request, body: ChatRequest) -> dict[str, object]:
        principal = _authorize(request, scopes=["chat:write"], twin_id=twin_id)
        result = _run_chat(
            twin_id=twin_id,
            message=body.message,
            model_profile=body.model_profile,
            top_k=body.top_k,
        )
        _audit(principal, "chat", "twin", target_id=twin_id, twin_id=twin_id, payload={"model_profile": body.model_profile})
        return result

    @app.get("/threads")
    def list_threads(request: Request, twin_id: str | None = None) -> list[dict[str, Any]]:
        principal = _authorize(request, scopes=["thread:read"], twin_id=twin_id)
        threads = store.list_threads(twin_id=twin_id)
        if "*" in principal.allowed_twins:
            return threads
        return [thread for thread in threads if principal.can_access_twin(thread["twin_id"])]

    @app.post("/threads")
    def create_thread(request: Request, body: ThreadCreateRequest) -> dict[str, Any]:
        principal = _authorize(request, scopes=["thread:write"], twin_id=body.twin_id)
        _get_twin_or_404(body.twin_id)
        thread = store.create_thread(
            twin_id=body.twin_id,
            title=body.title,
            metadata=body.metadata,
        )
        _audit(principal, "thread.create", "thread", target_id=thread["id"], twin_id=body.twin_id)
        return thread

    @app.get("/threads/{thread_id}")
    def get_thread(thread_id: str, request: Request) -> dict[str, Any]:
        thread = store.get_thread(thread_id)
        if not thread:
            raise HTTPException(status_code=404, detail=f"Unknown thread_id '{thread_id}'")
        _authorize(request, scopes=["thread:read"], twin_id=thread["twin_id"])
        return thread

    @app.get("/threads/{thread_id}/messages")
    def list_thread_messages(thread_id: str, request: Request) -> list[dict[str, Any]]:
        thread = store.get_thread(thread_id)
        if not thread:
            raise HTTPException(status_code=404, detail=f"Unknown thread_id '{thread_id}'")
        _authorize(request, scopes=["thread:read"], twin_id=thread["twin_id"])
        return store.list_messages(thread_id)

    @app.post("/threads/{thread_id}/messages")
    def create_thread_message(thread_id: str, request: Request, body: ThreadMessageRequest) -> dict[str, Any]:
        thread = store.get_thread(thread_id)
        if not thread:
            raise HTTPException(status_code=404, detail=f"Unknown thread_id '{thread_id}'")
        principal = _authorize(request, scopes=["chat:write"], twin_id=thread["twin_id"])

        prior_messages = [
            {"role": item["role"], "content": item["content"]}
            for item in store.list_messages(thread_id)
            if item["role"] in {"user", "assistant"}
        ]
        run = store.create_run(
            twin_id=thread["twin_id"],
            run_type="thread_message",
            status="running",
            input_payload={"message": body.message, "metadata": body.metadata},
            thread_id=thread_id,
            model_profile=body.model_profile,
        )
        user_message = store.append_message(
            thread_id=thread_id,
            role="user",
            content=body.message,
            metadata=body.metadata,
            run_id=run["id"],
        )

        result = _run_chat(
            twin_id=thread["twin_id"],
            message=body.message,
            model_profile=body.model_profile,
            top_k=body.top_k,
            prior_messages=prior_messages,
        )
        assistant_message = store.append_message(
            thread_id=thread_id,
            role="assistant",
            content=result["response"],
            metadata={
                "references": result["references"],
                "provider": result["provider"],
                "model": result["model"],
                "response_id": result["response_id"],
            },
            run_id=run["id"],
        )
        updated_run = store.update_run(
            run["id"],
            status="completed",
            provider=result["provider"],
            model=result["model"],
            output_payload={"assistant_message_id": assistant_message["id"], "references": result["references"]},
        )
        _audit(principal, "thread.message", "thread", target_id=thread_id, twin_id=thread["twin_id"], payload={"run_id": updated_run["id"]})

        return {
            "thread": thread,
            "run": updated_run,
            "messages": [user_message, assistant_message],
        }

    @app.get("/runs")
    def list_runs(request: Request, twin_id: str | None = None, thread_id: str | None = None) -> list[dict[str, Any]]:
        if thread_id:
            thread = store.get_thread(thread_id)
            if thread:
                _authorize(request, scopes=["run:read"], twin_id=thread["twin_id"])
            else:
                raise HTTPException(status_code=404, detail=f"Unknown thread_id '{thread_id}'")
        else:
            _authorize(request, scopes=["run:read"], twin_id=twin_id)
        return store.list_runs(twin_id=twin_id, thread_id=thread_id)

    @app.get("/runs/{run_id}")
    def get_run(run_id: str, request: Request) -> dict[str, Any]:
        run = store.get_run(run_id)
        if not run:
            raise HTTPException(status_code=404, detail=f"Unknown run_id '{run_id}'")
        _authorize(request, scopes=["run:read"], twin_id=run["twin_id"])
        return run

    @app.get("/tasks")
    def list_tasks(request: Request, twin_id: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
        _authorize(request, scopes=["task:read"], twin_id=twin_id)
        return store.list_tasks(twin_id=twin_id, status=status)

    @app.post("/tasks")
    def create_task(request: Request, body: TaskCreateRequest) -> dict[str, Any]:
        principal = _authorize(request, scopes=["task:create"], twin_id=body.twin_id)
        try:
            twin = registry.get(body.twin_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        task = store.create_task(
            twin_id=body.twin_id,
            task_type=body.task_type,
            payload=body.input_payload,
            status="pending",
            thread_id=body.thread_id,
        )

        requires_approval = body.require_approval or (
            body.task_type in twin.manifest.guardrails.human_approval_required_actions
        )
        if requires_approval:
            approval = store.create_approval(
                twin_id=body.twin_id,
                scope=body.task_type,
                request_payload=body.input_payload,
                thread_id=body.thread_id,
            )
            updated_task = store.update_task(task["id"], status="awaiting_approval", result={"approval_id": approval["id"]})
            _audit(principal, "task.create.awaiting_approval", "task", target_id=task["id"], twin_id=body.twin_id)
            return {"task": updated_task, "approval": approval}

        run = store.create_run(
            twin_id=body.twin_id,
            run_type=f"task:{body.task_type}",
            status="running",
            input_payload=body.input_payload,
            thread_id=body.thread_id,
            task_id=task["id"],
            model_profile=body.model_profile,
        )
        message = str(
            body.input_payload.get("message")
            or body.input_payload.get("prompt")
            or body.input_payload.get("instruction")
            or body.input_payload
        )
        prior_messages: list[dict[str, str]] = []
        if body.thread_id:
            prior_messages = [
                {"role": item["role"], "content": item["content"]}
                for item in store.list_messages(body.thread_id)
                if item["role"] in {"user", "assistant"}
            ]
        result = _run_chat(
            twin_id=body.twin_id,
            message=message,
            model_profile=body.model_profile,
            top_k=body.top_k,
            prior_messages=prior_messages,
        )
        updated_run = store.update_run(
            run["id"],
            status="completed",
            provider=result["provider"],
            model=result["model"],
            output_payload={"response": result["response"], "references": result["references"]},
        )
        updated_task = store.update_task(
            task["id"],
            status="completed",
            run_id=updated_run["id"],
            result={"response": result["response"], "references": result["references"]},
        )
        _audit(principal, "task.create", "task", target_id=task["id"], twin_id=body.twin_id, payload={"run_id": updated_run["id"]})
        return {"task": updated_task, "run": updated_run}

    @app.get("/tasks/{task_id}")
    def get_task(task_id: str, request: Request) -> dict[str, Any]:
        task = store.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail=f"Unknown task_id '{task_id}'")
        _authorize(request, scopes=["task:read"], twin_id=task["twin_id"])
        return task

    @app.get("/events")
    def list_events(request: Request, twin_id: str | None = None, event_type: str | None = None) -> list[dict[str, Any]]:
        _authorize(request, scopes=["event:read"], twin_id=twin_id)
        return store.list_events(twin_id=twin_id, event_type=event_type)

    @app.post("/events")
    def create_event(request: Request, body: EventCreateRequest) -> dict[str, Any]:
        principal = _authorize(request, scopes=["event:write"], twin_id=body.twin_id)
        _get_twin_or_404(body.twin_id)
        event = store.record_event(
            twin_id=body.twin_id,
            event_type=body.event_type,
            source=body.source,
            payload=body.payload,
            status=body.status,
        )
        _audit(principal, "event.create", "event", target_id=event["id"], twin_id=body.twin_id)
        return event

    @app.get("/approvals")
    def list_approvals(request: Request, twin_id: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
        _authorize(request, scopes=["approval:read"], twin_id=twin_id, admin_only=True)
        return store.list_approvals(twin_id=twin_id, status=status)

    @app.post("/approvals")
    def create_approval(request: Request, body: ApprovalCreateRequest) -> dict[str, Any]:
        principal = _authorize(request, scopes=["approval:write"], twin_id=body.twin_id, admin_only=True)
        _get_twin_or_404(body.twin_id)
        approval = store.create_approval(
            twin_id=body.twin_id,
            scope=body.scope,
            request_payload=body.request_payload,
            thread_id=body.thread_id,
            run_id=body.run_id,
        )
        _audit(principal, "approval.create", "approval", target_id=approval["id"], twin_id=body.twin_id)
        return approval

    @app.post("/approvals/{approval_id}/resolve")
    def resolve_approval(approval_id: str, request: Request, body: ApprovalResolveRequest) -> dict[str, Any]:
        principal = _authorize(request, scopes=["approval:resolve"], admin_only=True)
        try:
            approval = store.resolve_approval(approval_id, body.status, body.resolution_payload)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        _audit(principal, "approval.resolve", "approval", target_id=approval_id, twin_id=approval.get("twin_id"), payload={"status": body.status})
        return approval

    @app.get("/corrections")
    def list_corrections(request: Request, twin_id: str | None = None, thread_id: str | None = None) -> list[dict[str, Any]]:
        _authorize(request, scopes=["correction:read"], twin_id=twin_id, admin_only=True)
        return store.list_corrections(twin_id=twin_id, thread_id=thread_id)

    @app.post("/corrections")
    def create_correction(request: Request, body: CorrectionCreateRequest) -> dict[str, Any]:
        principal = _authorize(request, scopes=["correction:write"], twin_id=body.twin_id, admin_only=True)
        try:
            twin = registry.get(body.twin_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        correction = store.create_correction(
            twin_id=body.twin_id,
            scope=body.scope,
            instruction=body.instruction,
            thread_id=body.thread_id,
            message_id=body.message_id,
            payload=body.payload,
        )
        proposal = None
        if twin.manifest.corrections.promote_changes_via_review:
            artifact_path = str(body.payload.get("artifact_path", "pending-review"))
            proposal = store.create_artifact_proposal(
                twin_id=body.twin_id,
                artifact_type="correction-derived",
                artifact_path=artifact_path,
                proposal={
                    "scope": body.scope,
                    "instruction": body.instruction,
                    "payload": body.payload,
                },
                source_correction_id=correction["id"],
            )
        _audit(principal, "correction.create", "correction", target_id=correction["id"], twin_id=body.twin_id)
        return {"correction": correction, "artifact_proposal": proposal}

    @app.get("/artifacts")
    def list_artifacts(request: Request, twin_id: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
        _authorize(request, scopes=["artifact:read"], twin_id=twin_id, admin_only=True)
        return store.list_artifact_proposals(twin_id=twin_id, status=status)

    @app.post("/artifacts")
    def create_artifact(request: Request, body: ArtifactProposalCreateRequest) -> dict[str, Any]:
        principal = _authorize(request, scopes=["artifact:write"], twin_id=body.twin_id, admin_only=True)
        _get_twin_or_404(body.twin_id)
        artifact = store.create_artifact_proposal(
            twin_id=body.twin_id,
            artifact_type=body.artifact_type,
            artifact_path=body.artifact_path,
            proposal=body.proposal,
            source_correction_id=body.source_correction_id,
            status=body.status,
        )
        _audit(principal, "artifact.create", "artifact_proposal", target_id=artifact["id"], twin_id=body.twin_id)
        return artifact

    @app.get("/api-clients")
    def list_api_clients(request: Request, status: str | None = None) -> list[dict[str, Any]]:
        _authorize(request, scopes=["client:read"], admin_only=True)
        return store.list_api_clients(status=status)

    @app.post("/api-clients")
    def create_api_client(request: Request, body: ApiClientCreateRequest) -> dict[str, Any]:
        principal = _authorize(request, scopes=["client:write"], admin_only=True)
        raw_api_key, key_prefix, key_hash = generate_api_key()
        client = store.create_api_client(
            client_id=body.client_id,
            name=body.name,
            key_prefix=key_prefix,
            key_hash=key_hash,
            factory_id=body.factory_id,
            allowed_twins=body.allowed_twins,
            allowed_actions=body.allowed_actions,
            rate_limit_per_minute=body.rate_limit_per_minute,
            metadata=body.metadata,
        )
        _audit(principal, "api_client.create", "api_client", target_id=client["id"], payload={"client_id": body.client_id})
        response = dict(client)
        response["raw_api_key"] = raw_api_key
        return response

    @app.get("/admin-identities")
    def list_admin_identities(request: Request, status: str | None = None) -> list[dict[str, Any]]:
        _authorize(request, scopes=["admin:read"], admin_only=True)
        return store.list_admin_identities(status=status)

    @app.post("/admin-identities")
    def upsert_admin_identity(request: Request, body: AdminIdentityUpsertRequest) -> dict[str, Any]:
        principal = _authorize(request, scopes=["admin:write"], admin_only=True)
        admin_identity = store.upsert_admin_identity(
            user_id=body.user_id,
            email=body.email,
            role=body.role,
            allowed_twins=body.allowed_twins,
            allowed_actions=body.allowed_actions,
            status=body.status,
            metadata=body.metadata,
        )
        _audit(principal, "admin_identity.upsert", "admin_identity", target_id=body.user_id)
        return admin_identity

    @app.get("/audit")
    def list_audit(request: Request, twin_id: str | None = None, actor_type: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        _authorize(request, scopes=["audit:read"], twin_id=twin_id, admin_only=True)
        return store.list_audit_events(twin_id=twin_id, actor_type=actor_type, limit=limit)

    @app.get("/admin/overview")
    def admin_overview(request: Request, twin_id: str | None = None) -> dict[str, Any]:
        _authorize(request, scopes=["admin:read"], twin_id=twin_id, admin_only=True)
        return {
            "threads": len(store.list_threads(twin_id=twin_id)),
            "runs": len(store.list_runs(twin_id=twin_id)),
            "tasks": len(store.list_tasks(twin_id=twin_id)),
            "approvals_pending": len(store.list_approvals(twin_id=twin_id, status="pending")),
            "corrections": len(store.list_corrections(twin_id=twin_id)),
            "artifact_proposals": len(store.list_artifact_proposals(twin_id=twin_id)),
            "api_clients": len(store.list_api_clients(status="active")),
        }

    return app
