from __future__ import annotations

import os
from typing import Any

import httpx

from agent_factory.providers.base import GenerationRequest, GenerationResponse, ModelProvider


class XAIResponsesProvider(ModelProvider):
    name = "xai"

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client()

    def generate(self, request: GenerationRequest) -> GenerationResponse:
        api_base = request.provider_options.get("api_base") or "https://api.x.ai/v1"
        api_key_env = request.provider_options.get("api_key_env") or "XAI_API_KEY"
        api_key = os.getenv(api_key_env)
        if not api_key:
            raise RuntimeError(
                f"Missing xAI API key. Set {api_key_env} in the environment before using provider '{self.name}'."
            )

        payload = {
            "model": request.model,
            "input": self._build_input(request),
            "store": bool(request.provider_options.get("store", False)),
        }

        response = self._client.post(
            f"{api_base.rstrip('/')}/responses",
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
        )

    @staticmethod
    def _build_input(request: GenerationRequest) -> list[dict[str, str]]:
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
        if isinstance(body.get("output_text"), str) and body["output_text"].strip():
            return body["output_text"].strip()

        fragments: list[str] = []
        for item in body.get("output", []):
            for content in item.get("content", []):
                text = content.get("text")
                if text:
                    fragments.append(str(text).strip())

        if fragments:
            return "\n".join(fragment for fragment in fragments if fragment)

        choices = body.get("choices", [])
        if choices:
            message = choices[0].get("message", {})
            content = message.get("content")
            if isinstance(content, str):
                return content.strip()

        raise RuntimeError("xAI response did not contain model text in a known field")
