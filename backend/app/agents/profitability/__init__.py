"""Profitability consulting type (M9.2)."""

from app.agents._engine.registry import PROFILE_REGISTRY, register_profile
from app.agents.profitability.profile import PROFITABILITY_PROFILE


def _register_profile_once() -> None:
    existing = PROFILE_REGISTRY.get("profitability")
    if existing is PROFITABILITY_PROFILE:
        return
    if existing is not None:
        raise ValueError("profile 'profitability' already registered with a different object")
    register_profile(PROFITABILITY_PROFILE)


_register_profile_once()

__all__ = ["PROFITABILITY_PROFILE"]
