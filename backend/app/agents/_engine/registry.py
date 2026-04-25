"""M9.1: PROFILE_REGISTRY - slug -> ConsultingProfile."""

from __future__ import annotations

from app.agents._engine.profile import ConsultingProfile

PROFILE_REGISTRY: dict[str, ConsultingProfile] = {}


def register_profile(profile: ConsultingProfile) -> None:
    """Register a profile; raises if slug already registered."""
    if profile.slug in PROFILE_REGISTRY:
        raise ValueError(f"profile {profile.slug!r} already registered")
    profile.validate()
    PROFILE_REGISTRY[profile.slug] = profile


def get_profile(slug: str) -> ConsultingProfile | None:
    return PROFILE_REGISTRY.get(slug)


__all__ = ["PROFILE_REGISTRY", "register_profile", "get_profile"]
