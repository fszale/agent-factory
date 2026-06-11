from __future__ import annotations

from agent_factory.config import TwinManifest
from agent_factory.router import resolve_profile_name


def _manifest(profiles: dict[str, dict], default: str) -> TwinManifest:
    return TwinManifest.model_validate(
        {
            "twin_id": "t",
            "name": "t",
            "description": "d",
            "owner": "o",
            "prompt": {"system_prompt": "system.md"},
            "model_profiles": profiles,
            "default_model_profile": default,
        }
    )


def test_exact_capability_match():
    m = _manifest(
        {"research": {"provider": "openai", "model": "gpt-4o"}, "default": {"provider": "stub", "model": "s"}},
        "default",
    )
    assert resolve_profile_name(m, "research") == "research"


def test_alias_fallback_for_engineering():
    m = _manifest(
        {"engineering": {"provider": "xai", "model": "grok"}, "default": {"provider": "stub", "model": "s"}},
        "default",
    )
    assert resolve_profile_name(m, "code") == "engineering"


def test_falls_back_to_default_profile():
    m = _manifest(
        {"default": {"provider": "stub", "model": "s"}},
        "default",
    )
    assert resolve_profile_name(m, "research") == "default"


def test_none_capability_uses_manifest_default():
    m = _manifest({"deep": {"provider": "stub", "model": "s"}}, "deep")
    assert resolve_profile_name(m, None) == "deep"
