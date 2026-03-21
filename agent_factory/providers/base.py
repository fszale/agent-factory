from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class GenerationRequest:
    twin_id: str
    user_message: str
    system_prompt: str
    context_blocks: list[str]
    prior_messages: list[dict[str, str]]
    model: str
    timeout_seconds: int
    provider_options: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class GenerationResponse:
    text: str
    provider: str
    model: str
    raw: dict[str, Any] | None = None
    response_id: str | None = None


class ModelProvider(ABC):
    name: str

    @abstractmethod
    def generate(self, request: GenerationRequest) -> GenerationResponse:
        raise NotImplementedError
