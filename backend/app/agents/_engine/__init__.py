"""Shared consulting-pipeline engine (M9.1)."""

from app.agents._engine.profile import ConsultingProfile, ProfileStage, WorkerSpec
from app.agents._engine.registry import PROFILE_REGISTRY, get_profile, register_profile

__all__ = [
    "PROFILE_REGISTRY",
    "ConsultingProfile",
    "ProfileStage",
    "WorkerSpec",
    "get_profile",
    "register_profile",
]
