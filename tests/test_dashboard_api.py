from __future__ import annotations

from fastapi.testclient import TestClient

from agent_factory.app import create_app
from agent_factory.builder import build_twin
from agent_factory.deploy import deploy_twin
from agent_factory.cloud import build_cloud_providers
from agent_factory.metrics import build_roi_snapshot
from agent_factory.persistence import InMemoryStore
from agent_factory.providers import StubProvider


def _client(tmp_path, bridge_yaml):
    artifact = build_twin(bridge_yaml, tmp_path / "artifacts")
    deploy_twin(
        artifact.artifact_dir,
        cloud="local",
        registry_root=tmp_path / "registry",
        providers=build_cloud_providers("local", blob_root=tmp_path / "blobs"),
    )
    store = InMemoryStore()
    app = create_app(
        tmp_path / "registry",
        providers={"stub": StubProvider()},
        repository=store,
    )
    return TestClient(app), store


def test_ops_metrics_endpoint(tmp_path, bridge_yaml):
    client, store = _client(tmp_path, bridge_yaml)
    store.create_task(twin_id="filip", task_type="research", payload={}, status="completed")
    run = store.create_run(twin_id="filip", run_type="task", status="completed", input_payload={})
    store.create_trace(
        twin_id="filip", task_type="research", action="research", outcome="completed",
        signals={"provider": "xai", "usage": {"total_tokens": 1000}},
    )
    resp = client.get("/metrics/ops?twin_id=filip")
    assert resp.status_code == 200
    data = resp.json()
    assert data["tasks_run"] == 1
    assert data["success_rate"] == 1.0
    assert "xai" in data["cost_by_provider"]
    assert "mean_usefulness" in data


def test_roi_endpoint_returns_curve(tmp_path, bridge_yaml):
    client, store = _client(tmp_path, bridge_yaml)
    snap = build_roi_snapshot("2026-05-18", 110, 100, 0.7, 0.8, prior_improvement_pcts=[])
    store.create_roi_snapshot("filip", snap.week_start, snap.as_fields())
    resp = client.get("/metrics/roi?twin_id=filip")
    assert resp.status_code == 200
    curve = resp.json()["curve"]
    assert len(curve) == 1
    assert curve[0]["improvement_vs_baseline_pct"] == 0.1


def test_hitl_queue_endpoint(tmp_path, bridge_yaml):
    client, store = _client(tmp_path, bridge_yaml)
    store.create_approval(twin_id="filip", scope="send", request_payload={"to": "x"})
    resp = client.get("/dashboard/hitl-queue?twin_id=filip")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_reflect_endpoint_triggers_loop(tmp_path, bridge_yaml):
    client, store = _client(tmp_path, bridge_yaml)
    for _ in range(5):
        store.create_trace(
            twin_id="filip", task_type="research", action="research", outcome="completed",
            signals={"clarification_count": 5, "correction_count": 3},
        )
    resp = client.post("/improvements/reflect?twin_id=filip")
    assert resp.status_code == 200
    body = resp.json()
    assert body["scored_traces"] == 5
    assert len(body["candidates"]) >= 1
    # surfaced via the improvements listing
    listing = client.get("/improvements?twin_id=filip").json()
    assert len(listing["candidates"]) >= 1
