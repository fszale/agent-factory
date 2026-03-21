from __future__ import annotations

from dataclasses import dataclass

from agent_factory.providers import ModelProvider, StubProvider, XAIResponsesProvider
from agent_factory.providers.base import GenerationRequest
from agent_factory.registry import TwinRegistry


@dataclass(slots=True)
class TwinChatResult:
    twin_id: str
    text: str
    model_profile: str
    provider: str
    model: str
    references: list[dict[str, str]]
    response_id: str | None = None


def build_default_providers() -> dict[str, ModelProvider]:
    return {
        "stub": StubProvider(),
        "xai": XAIResponsesProvider(),
    }


class TwinRuntime:
    def __init__(
        self,
        registry: TwinRegistry,
        providers: dict[str, ModelProvider] | None = None,
    ) -> None:
        self.registry = registry
        self.providers = providers or build_default_providers()

    def chat(
        self,
        twin_id: str,
        user_message: str,
        model_profile: str | None = None,
        top_k: int = 3,
        prior_messages: list[dict[str, str]] | None = None,
    ) -> TwinChatResult:
        twin = self.registry.get(twin_id)
        selected_profile = model_profile or twin.manifest.default_model_profile
        try:
            profile = twin.manifest.model_profiles[selected_profile]
        except KeyError as exc:
            raise KeyError(
                f"Unknown model profile '{selected_profile}' for twin '{twin_id}'"
            ) from exc

        try:
            provider = self.providers[profile.provider]
        except KeyError as exc:
            raise KeyError(
                f"No provider implementation registered for '{profile.provider}'"
            ) from exc

        references = twin.knowledge_base.search(user_message, top_k=top_k)
        response = provider.generate(
            GenerationRequest(
                twin_id=twin_id,
                user_message=user_message,
                system_prompt=twin.render_system_prompt(references),
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
        )

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
