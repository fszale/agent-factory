from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, model_validator


class ModelProfile(BaseModel):
    provider: str
    model: str
    timeout_seconds: int = 3600
    store: bool = False
    api_base: str | None = None
    api_key_env: str | None = None


class ChannelConfig(BaseModel):
    enabled: bool = False
    provider: str | None = None
    notes: str | None = None


class PromptConfig(BaseModel):
    system_prompt: str


class KnowledgeConfig(BaseModel):
    documents: list[str] = Field(default_factory=list)


class GuardrailConfig(BaseModel):
    autonomy_level: Literal["L0", "L1", "L2", "L3"] = "L1"
    correction_required_for_self_modification: bool = True
    allow_external_side_effects: bool = False
    human_approval_required_actions: list[str] = Field(default_factory=list)


class CorrectionPolicy(BaseModel):
    scopes: list[str] = Field(default_factory=list)
    promote_changes_via_review: bool = True


class EvalConfig(BaseModel):
    smoke_file: str | None = None


class TwinManifest(BaseModel):
    schema_version: str = "1.0"
    twin_id: str
    name: str
    description: str
    owner: str
    tags: list[str] = Field(default_factory=list)
    prompt: PromptConfig
    knowledge: KnowledgeConfig = Field(default_factory=KnowledgeConfig)
    model_profiles: dict[str, ModelProfile]
    default_model_profile: str
    channels: dict[str, ChannelConfig] = Field(default_factory=dict)
    guardrails: GuardrailConfig = Field(default_factory=GuardrailConfig)
    corrections: CorrectionPolicy = Field(default_factory=CorrectionPolicy)
    evals: EvalConfig = Field(default_factory=EvalConfig)

    @model_validator(mode="after")
    def ensure_default_model_profile_exists(self) -> "TwinManifest":
        if self.default_model_profile not in self.model_profiles:
            raise ValueError(
                f"default_model_profile '{self.default_model_profile}' is not defined in model_profiles"
            )
        return self


def _ensure_relative_file_exists(base_dir: Path, relative_path: str, field_name: str) -> None:
    resolved = base_dir / relative_path
    if not resolved.exists() or not resolved.is_file():
        raise FileNotFoundError(
            f"{field_name} references missing file: {resolved}"
        )


def load_manifest(manifest_path: str | Path) -> TwinManifest:
    manifest_file = Path(manifest_path).resolve()
    base_dir = manifest_file.parent
    raw = yaml.safe_load(manifest_file.read_text(encoding="utf-8"))
    manifest = TwinManifest.model_validate(raw)

    _ensure_relative_file_exists(base_dir, manifest.prompt.system_prompt, "prompt.system_prompt")

    for index, document in enumerate(manifest.knowledge.documents):
        _ensure_relative_file_exists(base_dir, document, f"knowledge.documents[{index}]")

    if manifest.evals.smoke_file:
        _ensure_relative_file_exists(base_dir, manifest.evals.smoke_file, "evals.smoke_file")

    return manifest
