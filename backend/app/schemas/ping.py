"""Pydantic DTOs for the `/ping` endpoint (M2.6).

`/ping` is a deliberately small surface used by the frontend (and
operators) to verify that a per-role chat model is configured and
reachable. The role defaults to ``"framing"`` — alphabetically first
in the V1 role set and the model used for the opening stage of every
agent run, so a successful ping there is the most useful smoke signal.

The 10 000-character `prompt` ceiling is a defensive guardrail; the
endpoint isn't meant to carry full agent prompts and unbounded input
would be an easy footgun for accidental large requests.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class PingRequest(BaseModel):
    """POST /ping body."""

    prompt: str = Field(min_length=1, max_length=10_000)
    role: str = Field(default="framing", min_length=1)


class PingResponse(BaseModel):
    """POST /ping response payload.

    `provider` is the registry key (``"anthropic"``, ``"openai"``, ...)
    derived from the LangChain class name via
    ``app.agents.provider_name_for``. ``"unknown"`` indicates the
    constructed model isn't in the V1 registry — primarily a test
    signal for fakes; a real production response should never see it.
    """

    response: str
    model: str
    provider: str


__all__ = ["PingRequest", "PingResponse"]
