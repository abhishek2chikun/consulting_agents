"""Per-provider/per-model price table for token-cost estimation (M7.1).

V1 stores prices in code, not config. The intent is rough cost
visibility in the UI — not invoicing. Rates are USD per 1 million
tokens, separated into ``input`` (prompt) and ``output`` (completion).

Rates source: each provider's public pricing page as of the last commit
that touched this file. They drift; treat the dollars shown in the UI
as a "ballpark" and re-confirm against the provider invoice for
anything operationally important.

Lookup is intentionally tolerant: an unknown ``(provider, model)`` pair
returns ``None`` from :func:`lookup_price` and a flat ``0.0`` from
:func:`cost_for`. We never want a missing price entry to crash a live
agent run.
"""

from __future__ import annotations

from typing import TypedDict


class TokenPrice(TypedDict):
    """USD per 1 million tokens for a single model."""

    input: float
    output: float


# Rates per 1M tokens. Keep keys lowercase, matching `LLM_PROVIDERS`.
PRICE_TABLE: dict[str, dict[str, TokenPrice]] = {
    "anthropic": {
        "claude-sonnet-4-5": {"input": 3.00, "output": 15.00},
        "claude-opus-4-5": {"input": 15.00, "output": 75.00},
        "claude-haiku-4-5": {"input": 0.80, "output": 4.00},
        # Legacy aliases that may surface via response_metadata.
        "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
        "claude-3-5-haiku-20241022": {"input": 0.80, "output": 4.00},
    },
    "openai": {
        "gpt-4o": {"input": 2.50, "output": 10.00},
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "gpt-4o-2024-08-06": {"input": 2.50, "output": 10.00},
        "gpt-4o-mini-2024-07-18": {"input": 0.15, "output": 0.60},
    },
    "google": {
        # Gemini 2.5 Pro tiered pricing — first 200k input tokens.
        "gemini-2.5-pro": {"input": 1.25, "output": 10.00},
        "gemini-2.5-flash": {"input": 0.30, "output": 2.50},
    },
    "ollama": {
        # Local models cost nothing to call (the user already paid in
        # electricity + hardware). Listed explicitly so the UI shows
        # $0.00 instead of `unknown` for local Llama variants.
        "llama3.2": {"input": 0.0, "output": 0.0},
        "llama3.1": {"input": 0.0, "output": 0.0},
    },
}


def lookup_price(provider: str, model: str) -> TokenPrice | None:
    """Return the price entry for `(provider, model)` or `None`."""
    by_model = PRICE_TABLE.get(provider)
    if by_model is None:
        return None
    return by_model.get(model)


def cost_for(
    *,
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
) -> float:
    """Return USD cost for a single LLM call.

    Returns 0.0 when the model is not in the table — V1 prefers
    "best-effort visibility, never crash" over strictness.
    """
    price = lookup_price(provider, model)
    if price is None:
        return 0.0
    return (input_tokens / 1_000_000) * price["input"] + (output_tokens / 1_000_000) * price[
        "output"
    ]


__all__ = ["PRICE_TABLE", "TokenPrice", "cost_for", "lookup_price"]
