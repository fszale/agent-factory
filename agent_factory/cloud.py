"""Cloud abstraction — depend on roles, not services.

The app code imports these interfaces, never a cloud SDK directly. This is the Pareto
cut for multi-cloud: ~5 interfaces cover ~95% of portability needs. Local in-process
implementations let the whole runtime + tests run with zero cloud dependencies; the
gcp/aws deploy modules wire the same interfaces to real services.
"""

from __future__ import annotations

import json
import shutil
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4


# --------------------------------------------------------------------------- #
# Scheduler — heartbeat / reminders that must actually fire.
# --------------------------------------------------------------------------- #
@dataclass(slots=True)
class ScheduledJob:
    id: str
    fire_at: float  # epoch seconds
    payload: dict[str, Any]
    fired: bool = False
    fired_at: float | None = None


class Scheduler(ABC):
    @abstractmethod
    def schedule(self, fire_at: float, payload: dict[str, Any]) -> ScheduledJob: ...

    @abstractmethod
    def due(self, now: float | None = None) -> list[ScheduledJob]: ...

    @abstractmethod
    def mark_fired(self, job_id: str) -> None: ...


class LocalScheduler(Scheduler):
    """In-process scheduler. A background tick (or explicit poll) fires due jobs.

    `due()` makes reminders verifiable in tests without wall-clock waits.
    """

    def __init__(self) -> None:
        self._jobs: dict[str, ScheduledJob] = {}
        self._lock = threading.Lock()

    def schedule(self, fire_at: float, payload: dict[str, Any]) -> ScheduledJob:
        job = ScheduledJob(id=str(uuid4()), fire_at=fire_at, payload=payload)
        with self._lock:
            self._jobs[job.id] = job
        return job

    def due(self, now: float | None = None) -> list[ScheduledJob]:
        now = now if now is not None else time.time()
        with self._lock:
            return [j for j in self._jobs.values() if not j.fired and j.fire_at <= now]

    def mark_fired(self, job_id: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.fired = True
                job.fired_at = time.time()

    def run_due(self, handler: Callable[[ScheduledJob], None], now: float | None = None) -> int:
        fired = 0
        for job in self.due(now=now):
            handler(job)
            self.mark_fired(job.id)
            fired += 1
        return fired


# --------------------------------------------------------------------------- #
# Queue — async task dispatch.
# --------------------------------------------------------------------------- #
class Queue(ABC):
    @abstractmethod
    def enqueue(self, payload: dict[str, Any]) -> str: ...

    @abstractmethod
    def dequeue(self) -> dict[str, Any] | None: ...


class LocalQueue(Queue):
    def __init__(self) -> None:
        self._items: list[dict[str, Any]] = []
        self._lock = threading.Lock()

    def enqueue(self, payload: dict[str, Any]) -> str:
        msg_id = str(uuid4())
        with self._lock:
            self._items.append({"id": msg_id, "payload": payload})
        return msg_id

    def dequeue(self) -> dict[str, Any] | None:
        with self._lock:
            return self._items.pop(0) if self._items else None


# --------------------------------------------------------------------------- #
# SecretStore — secrets referenced by name, never written into repos.
# --------------------------------------------------------------------------- #
class SecretStore(ABC):
    @abstractmethod
    def get(self, name: str) -> str | None: ...


class EnvSecretStore(SecretStore):
    """Resolves secret *names* from the process environment (local dev default)."""

    def __init__(self, env: dict[str, str] | None = None) -> None:
        import os

        self._env = env if env is not None else dict(os.environ)

    def get(self, name: str) -> str | None:
        return self._env.get(name)


# --------------------------------------------------------------------------- #
# Blob — object storage for build artifacts.
# --------------------------------------------------------------------------- #
class Blob(ABC):
    @abstractmethod
    def put_dir(self, local_dir: str | Path, key: str) -> str: ...

    @abstractmethod
    def exists(self, key: str) -> bool: ...


class LocalBlob(Blob):
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def put_dir(self, local_dir: str | Path, key: str) -> str:
        dest = self.root / key
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(local_dir, dest)
        return str(dest)

    def exists(self, key: str) -> bool:
        return (self.root / key).exists()


# --------------------------------------------------------------------------- #
# Provider bundle.
# --------------------------------------------------------------------------- #
@dataclass(slots=True)
class CloudProviders:
    cloud: str
    scheduler: Scheduler
    queue: Queue
    secrets: SecretStore
    blob: Blob
    meta: dict[str, Any] = field(default_factory=dict)


def build_cloud_providers(cloud: str, blob_root: str | Path | None = None) -> CloudProviders:
    """Return the provider bundle for a target cloud.

    `local` uses in-process impls. `gcp`/`aws` currently also use local impls behind
    the same interfaces — the deploy modules (deploy/gcp, deploy/aws) provision the
    real services; swapping in SDK-backed impls is a drop-in once those exist.
    """
    cloud = cloud.lower()
    if cloud not in {"local", "gcp", "aws"}:
        raise ValueError(f"Unknown cloud '{cloud}'. Expected one of: local, gcp, aws.")
    root = Path(blob_root) if blob_root else Path.cwd() / ".factory-blobs"
    return CloudProviders(
        cloud=cloud,
        scheduler=LocalScheduler(),
        queue=LocalQueue(),
        secrets=EnvSecretStore(),
        blob=LocalBlob(root),
        meta={"interface_backed": True},
    )


def now_epoch() -> float:
    return datetime.now(UTC).timestamp()


def write_deploy_record(path: str | Path, record: dict[str, Any]) -> None:
    Path(path).write_text(json.dumps(record, indent=2), encoding="utf-8")
