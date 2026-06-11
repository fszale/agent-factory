"""Capability-based model router.

The bridge twin.yaml routes *capabilities* (research, social, engineering, default)
to providers+models. After build, each capability becomes a runtime model profile of
the same name. The router resolves a capability to a concrete profile, with no
hardcoded model choices — everything comes from config.
"""

from __future__ import annotations

from agent_factory.config import ModelProfile, TwinManifest

# Map an input term to the candidate profile names it should resolve to.
_CAPABILITY_ALIASES: dict[str, tuple[str, ...]] = {
    "research": ("research",),
    "social": ("social",),
    "engineering": ("engineering",),
    "engineer": ("engineering",),
    "code": ("engineering",),
    "reminder": ("default", "fast"),
}


def resolve_profile_name(manifest: TwinManifest, capability: str | None) -> str:
    """Map a capability (or explicit profile name) to a defined profile key."""
    profiles = manifest.model_profiles
    if capability is None:
        return manifest.default_model_profile

    # Exact profile/capability match wins.
    if capability in profiles:
        return capability

    # Try aliases for the capability.
    for candidate in _CAPABILITY_ALIASES.get(capability, ()):
        if candidate in profiles:
            return candidate

    # Fall back to a 'default' profile, then the manifest default.
    if "default" in profiles:
        return "default"
    return manifest.default_model_profile


def resolve_profile(manifest: TwinManifest, capability: str | None) -> tuple[str, ModelProfile]:
    name = resolve_profile_name(manifest, capability)
    return name, manifest.model_profiles[name]
