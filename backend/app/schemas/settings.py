"""Pydantic DTOs for the Settings REST API (M2.4).

DTO design notes:

- Provider keys are stored encrypted server-side; responses NEVER contain
  raw key material. `ProviderInfo` exposes a boolean `has_key` flag only.
- `SetProviderKeyRequest.key` enforces non-empty input at the boundary so
  the service layer never has to decide whether an empty string is a
  "delete" intent (it is not — an explicit DELETE endpoint will be added
  when the UX needs it).
- `SearchProviderRequest.provider` is a closed `Literal` enum. The set of
  supported search providers is small and product-defined; allowing an
  arbitrary string would let callers persist garbage that the agent
  runtime would later have to defensively reject.
- `MaxStageRetriesRequest.value` is bounded `1..5` per spec. Below 1 makes
  retries pointless; above 5 risks runaway agent loops.
- `ModelOverridesRequest.overrides` keys (roles) are deliberately
  open-ended for V1 — the agent runtime hasn't locked down its role set
  yet (M5). Each value is structurally validated as a {provider, model}
  pair so we don't accept malformed entries.
- `SettingsSnapshot` is the consolidated GET payload used by the
  frontend bootstrap. Defaults (`model_overrides={}`, `search_provider=None`,
  `max_stage_retries=2`) match the agent runtime defaults.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ProviderInfo(BaseModel):
    """Per-provider key presence flag. Never carries the key itself."""

    provider: str
    has_key: bool


class ProvidersResponse(BaseModel):
    """GET /settings/providers payload."""

    providers: list[ProviderInfo]


class SetProviderKeyRequest(BaseModel):
    """PUT /settings/providers/{provider} body."""

    key: str = Field(min_length=1)


class ModelOverride(BaseModel):
    """A single role -> (provider, model) override entry."""

    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)


class ModelOverridesRequest(BaseModel):
    """PUT /settings/model_overrides body."""

    overrides: dict[str, ModelOverride]


SearchProviderName = Literal["duckduckgo", "tavily", "exa", "perplexity"]


class SearchProviderRequest(BaseModel):
    """PUT /settings/search_provider body."""

    provider: SearchProviderName


class MaxStageRetriesRequest(BaseModel):
    """PUT /settings/max_stage_retries body."""

    value: int = Field(ge=1, le=5)


class SettingsSnapshot(BaseModel):
    """GET /settings full snapshot used by the frontend bootstrap."""

    providers: list[ProviderInfo]
    model_overrides: dict[str, ModelOverride] = Field(default_factory=dict)
    search_provider: SearchProviderName | None = None
    max_stage_retries: int = 2


__all__ = [
    "MaxStageRetriesRequest",
    "ModelOverride",
    "ModelOverridesRequest",
    "ProviderInfo",
    "ProvidersResponse",
    "SearchProviderName",
    "SearchProviderRequest",
    "SetProviderKeyRequest",
    "SettingsSnapshot",
]
