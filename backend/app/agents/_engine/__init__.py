"""Shared consulting-pipeline engine (M9.1)."""

from app.agents._engine.profile import ConsultingProfile, ProfileStage
from app.agents._engine.registry import PROFILE_REGISTRY, get_profile, register_profile

__all__ = [
    "PROFILE_REGISTRY",
    "ConsultingProfile",
    "ProfileStage",
    "get_profile",
    "register_profile",
]
