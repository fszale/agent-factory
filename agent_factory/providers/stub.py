from __future__ import annotations

from agent_factory.pricing import estimate_request_tokens, estimate_tokens
from agent_factory.providers.base import (
    GenerationRequest,
    GenerationResponse,
    ModelProvider,
    TokenUsage,
)


class StubProvider(ModelProvider):
    name = "stub"

    def generate(self, request: GenerationRequest) -> GenerationResponse:
        context_preview = " | ".join(request.context_blocks[:2]) or "no-context"
        turns_preview = f"{len(request.prior_messages)} prior turns"
        text = (
            f"[stub:{request.model}] "
            f"Answering as {request.twin_id}: {request.user_message}\n"
            f"Context: {context_preview}\n"
            f"History: {turns_preview}"
        )
        prompt_tokens = estimate_request_tokens(
            request.system_prompt, request.user_message, *request.context_blocks
        )
        completion_tokens = estimate_tokens(text)
        return GenerationResponse(
            text=text,
            provider=self.name,
            model=request.model,
            raw={"context_blocks": request.context_blocks, "prior_messages": request.prior_messages},
            usage=TokenUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
            ),
        )
