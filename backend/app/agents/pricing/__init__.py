"""Pricing consulting type and token-cost helpers."""

from typing import TypedDict

from app.agents._engine.registry import PROFILE_REGISTRY, register_profile
from app.agents.pricing.profile import PRICING_PROFILE


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
        "gemini-2.5-pro": {"input": 1.25, "output": 10.00},
        "gemini-2.5-flash": {"input": 0.30, "output": 2.50},
    },
    "ollama": {
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
    """Return USD cost for a single LLM call."""
    price = lookup_price(provider, model)
    if price is None:
        return 0.0
    return (input_tokens / 1_000_000) * price["input"] + (output_tokens / 1_000_000) * price[
        "output"
    ]


def _register_profile_once() -> None:
    existing = PROFILE_REGISTRY.get("pricing")
    if existing is PRICING_PROFILE:
        return
    if existing is not None:
        raise ValueError("profile 'pricing' already registered with a different object")
    register_profile(PRICING_PROFILE)


_register_profile_once()

__all__ = [
    "PRICE_TABLE",
    "PRICING_PROFILE",
    "TokenPrice",
    "cost_for",
    "lookup_price",
]
