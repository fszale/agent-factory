from __future__ import annotations

from dataclasses import dataclass, field

from agent_factory.autonomy import BudgetMeter, default_autonomy
from agent_factory.pricing import estimate_request_tokens
from agent_factory.providers import (
    ModelProvider,
    OpenAIProvider,
    StubProvider,
    XAIResponsesProvider,
)
from agent_factory.providers.base import GenerationRequest
from agent_factory.registry import TwinRegistry
from agent_factory.router import resolve_profile


@dataclass(slots=True)
class TwinChatResult:
    twin_id: str
    text: str
    model_profile: str
    provider: str
    model: str
    references: list[dict[str, str]]
    response_id: str | None = None
    usage: dict[str, int] = field(default_factory=dict)
    budget: dict[str, float] = field(default_factory=dict)


def build_default_providers() -> dict[str, ModelProvider]:
    return {
        "stub": StubProvider(),
        "xai": XAIResponsesProvider(),
        "openai": OpenAIProvider(),
    }


class TwinRuntime:
    def __init__(
        self,
        registry: TwinRegistry,
        providers: dict[str, ModelProvider] | None = None,
        budget_meter: BudgetMeter | None = None,
    ) -> None:
        self.registry = registry
        self.providers = providers or build_default_providers()
        self.budget = budget_meter or BudgetMeter()

    def chat(
        self,
        twin_id: str,
        user_message: str,
        model_profile: str | None = None,
        top_k: int = 3,
        prior_messages: list[dict[str, str]] | None = None,
        task_tokens_so_far: int = 0,
    ) -> TwinChatResult:
        twin = self.registry.get(twin_id)

        # Kill switch: checked at top of every dispatch.
        self.budget.check_dispatch(twin_id)

        # Capability-based routing (model_profile may name a capability).
        selected_profile, profile = resolve_profile(twin.manifest, model_profile)

        try:
            provider = self.providers[profile.provider]
        except KeyError as exc:
            raise KeyError(
                f"No provider implementation registered for '{profile.provider}'"
            ) from exc

        references = twin.knowledge_base.search(user_message, top_k=top_k)
        system_prompt = twin.render_system_prompt(references)

        # Budget preflight — hard-stop BEFORE the provider call returns.
        guardrails = twin.guardrails
        estimated = estimate_request_tokens(
            system_prompt, user_message, *[r.excerpt for r in references]
        )
        self.budget.preflight(
            twin_id=twin_id,
            provider=profile.provider,
            estimated_tokens=estimated,
            guardrails=guardrails,
            task_tokens_so_far=task_tokens_so_far,
        )

        response = provider.generate(
            GenerationRequest(
                twin_id=twin_id,
                user_message=user_message,
                system_prompt=system_prompt,
                context_blocks=[reference.excerpt for reference in references],
                prior_messages=prior_messages or [],
                model=profile.model,
                timeout_seconds=profile.timeout_seconds,
                provider_options={
                    "store": profile.store,
                    "api_base": profile.api_base,
                    "api_key_env": profile.api_key_env,
                },
            )
        )

        # Reconcile real usage; pause twin if a hard limit is now crossed.
        budget_state = self.budget.record(
            twin_id=twin_id,
            provider=response.provider,
            usage=response.usage,
            guardrails=guardrails,
        )

        return TwinChatResult(
            twin_id=twin_id,
            text=response.text,
            model_profile=selected_profile,
            provider=response.provider,
            model=response.model,
            references=[
                {"source": reference.source, "excerpt": reference.excerpt}
                for reference in references
            ],
            response_id=response.response_id,
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
            budget=budget_state,
        )

    def autonomy_for(self, twin_id: str):
        twin = self.registry.get(twin_id)
        return twin.autonomy or default_autonomy()

    def describe_capabilities(self, twin_id: str) -> dict[str, object]:
        twin = self.registry.get(twin_id)

        def _count_files(directory_name: str) -> int:
            path = twin.base_dir / directory_name
            if not path.exists():
                return 0
            return sum(1 for candidate in path.rglob("*") if candidate.is_file())

        return {
            "twin_id": twin.manifest.twin_id,
            "channels": {key: value.model_dump() for key, value in twin.manifest.channels.items()},
            "model_profiles": {
                key: {
                    "provider": profile.provider,
                    "model": profile.model,
                    "timeout_seconds": profile.timeout_seconds,
                }
                for key, profile in twin.manifest.model_profiles.items()
            },
            "artifacts": {
                "knowledge_documents": len(twin.manifest.knowledge.documents),
                "skills_files": _count_files("skills"),
                "prompt_files": _count_files("prompts"),
                "template_files": _count_files("templates"),
            },
        }
