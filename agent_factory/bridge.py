"""Bridge contract (twin.yaml) — the pinned contract between a bridge repo and the factory.

This is distinct from `config.TwinManifest`, which is the *runtime* package format the
registry loads. The twin-builder reads a bridge `twin.yaml` (this module), resolves the
pinned kernel, layers overrides, and emits a runtime package + build manifest.

Validates against `schemas/twin.schema.json` (frozen in Phase 0).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, model_validator

_VERSION_RE = re.compile(r"^v[0-9]+\.[0-9]+\.[0-9]+$")
_NAME_RE = re.compile(r"^[a-z0-9_-]+$")


class KernelRef(BaseModel):
    source: str = Field(description="Full git repo URL for this twin's kernel (may differ per customer).")
    version: str = Field(description="Pinned git tag. Never 'latest' or a branch name.")

    @model_validator(mode="after")
    def _validate(self) -> "KernelRef":
        if not _VERSION_RE.match(self.version):
            raise ValueError(
                f"kernel.version must be a pinned semver git tag like 'v1.4.0', got '{self.version}'"
            )
        if self.version in {"latest", "main", "master", "HEAD"}:
            raise ValueError("kernel.version must be pinned, never a branch or 'latest'")
        return self


class ModelRoute(BaseModel):
    provider: str
    model: str
    api_base: str | None = None
    api_key_env: str | None = None
    timeout_seconds: int = 3600
    store: bool = False


class Overrides(BaseModel):
    prompts: str | None = None
    skills: str | None = None


class Guardrails(BaseModel):
    daily_token_limit: int = Field(ge=1)
    daily_usd_limit: float = Field(ge=0)
    per_task_token_limit: int = Field(ge=1)
    max_actions_per_hour: int = Field(ge=1)
    allowed_actions: list[str] = Field(default_factory=list)
    kill_switch: bool = True


class FullAutonomy(BaseModel):
    enabled: bool = False
    guardrails: Guardrails | None = None

    @model_validator(mode="after")
    def _require_guardrails_when_enabled(self) -> "FullAutonomy":
        if self.enabled and self.guardrails is None:
            raise ValueError(
                "full_autonomy.enabled=true requires a complete guardrails block "
                "(daily_token_limit, daily_usd_limit, per_task_token_limit, "
                "max_actions_per_hour, allowed_actions, kill_switch)."
            )
        return self


class Autonomy(BaseModel):
    mode: Literal["propose-then-confirm", "full-autonomy"] = "propose-then-confirm"
    auto_allow: list[str] = Field(default_factory=list)
    always_gate: list[str] = Field(default_factory=list)
    full_autonomy: FullAutonomy = Field(default_factory=FullAutonomy)

    @model_validator(mode="after")
    def _enforce_product_default(self) -> "Autonomy":
        # full-autonomy mode is only valid if explicitly opted in via full_autonomy.enabled
        if self.mode == "full-autonomy" and not self.full_autonomy.enabled:
            raise ValueError(
                "autonomy.mode='full-autonomy' requires autonomy.full_autonomy.enabled=true "
                "with a valid guardrails block."
            )
        return self


class TwinSpec(BaseModel):
    name: str
    description: str | None = None
    owner: str | None = None
    kernel: KernelRef
    roles: list[str] = Field(min_length=1)
    overrides: Overrides = Field(default_factory=Overrides)
    models: dict[str, ModelRoute] = Field(min_length=1)
    autonomy: Autonomy

    @model_validator(mode="after")
    def _validate(self) -> "TwinSpec":
        if not _NAME_RE.match(self.name):
            raise ValueError(f"twin.name must match ^[a-z0-9_-]+$, got '{self.name}'")
        return self


class BridgeConfig(BaseModel):
    """Top-level twin.yaml: a single `twin:` key."""

    twin: TwinSpec


def load_bridge_config(path: str | Path) -> BridgeConfig:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or "twin" not in raw:
        raise ValueError(f"{path} is not a valid bridge twin.yaml (missing top-level 'twin:' key)")
    return BridgeConfig.model_validate(raw)
