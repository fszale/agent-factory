from __future__ import annotations

import os
from typing import Any

import httpx

from agent_factory.providers.base import (
    GenerationRequest,
    GenerationResponse,
    ModelProvider,
    TokenUsage,
)


class OpenAIProvider(ModelProvider):
    """OpenAI chat-completions provider — used for the `research` capability route."""

    name = "openai"

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client()

    def generate(self, request: GenerationRequest) -> GenerationResponse:
        api_base = request.provider_options.get("api_base") or "https://api.openai.com/v1"
        api_key_env = request.provider_options.get("api_key_env") or "OPENAI_API_KEY"
        api_key = os.getenv(api_key_env)
        if not api_key:
            raise RuntimeError(
                f"Missing OpenAI API key. Set {api_key_env} before using provider '{self.name}'."
            )

        payload = {
            "model": request.model,
            "messages": self._build_messages(request),
        }
        response = self._client.post(
            f"{api_base.rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=request.timeout_seconds,
        )
        response.raise_for_status()
        body = response.json()
        return GenerationResponse(
            text=self._extract_text(body),
            provider=self.name,
            model=request.model,
            raw=body,
            response_id=body.get("id"),
            usage=self._extract_usage(body),
        )

    @staticmethod
    def _build_messages(request: GenerationRequest) -> list[dict[str, str]]:
        items: list[dict[str, str]] = [{"role": "system", "content": request.system_prompt}]
        for message in request.prior_messages:
            role = message.get("role", "user")
            if role not in {"user", "assistant", "system"}:
                role = "user"
            items.append({"role": role, "content": message.get("content", "")})
        items.append({"role": "user", "content": request.user_message})
        return items

    @staticmethod
    def _extract_text(body: dict[str, Any]) -> str:
        choices = body.get("choices", [])
        if choices:
            content = choices[0].get("message", {}).get("content")
            if isinstance(content, str) and content.strip():
                return content.strip()
        raise RuntimeError("OpenAI response did not contain model text in a known field")

    @staticmethod
    def _extract_usage(body: dict[str, Any]) -> TokenUsage:
        usage = body.get("usage") or {}
        return TokenUsage(
            prompt_tokens=int(usage.get("prompt_tokens", 0)),
            completion_tokens=int(usage.get("completion_tokens", 0)),
            total_tokens=int(usage.get("total_tokens", 0)),
        )
