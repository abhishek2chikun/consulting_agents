"""Reviewer-stage schema (M6.4)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class GateVerdictModel(BaseModel):
    verdict: Literal["advance", "reiterate"]
    stage: str
    attempt: int
    gaps: list[str] = Field(default_factory=list)
    target_agents: list[str] = Field(default_factory=list)
    rationale: str


__all__ = ["GateVerdictModel"]
