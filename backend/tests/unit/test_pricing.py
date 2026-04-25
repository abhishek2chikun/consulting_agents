"""Unit tests for the per-provider/model price table (M7.1)."""

from __future__ import annotations

import pytest

from app.agents.pricing import cost_for, lookup_price


def test_lookup_price_returns_known_anthropic_model() -> None:
    price = lookup_price("anthropic", "claude-sonnet-4-5")
    assert price is not None
    assert price["input"] > 0
    assert price["output"] > price["input"]


def test_lookup_price_unknown_returns_none() -> None:
    assert lookup_price("anthropic", "no-such-model-zzz") is None
    assert lookup_price("noprovider", "anything") is None


def test_cost_for_known_model_uses_per_million_pricing() -> None:
    # Construct synthetic: 1M input tokens + 1M output tokens
    # should equal exactly the (input + output) per-million rate.
    price = lookup_price("anthropic", "claude-sonnet-4-5")
    assert price is not None
    cost = cost_for(
        provider="anthropic",
        model="claude-sonnet-4-5",
        input_tokens=1_000_000,
        output_tokens=1_000_000,
    )
    assert cost == pytest.approx(price["input"] + price["output"])


def test_cost_for_unknown_model_returns_zero() -> None:
    """Unknown models are billed as $0 (best-effort, never crashes a run)."""
    assert (
        cost_for(
            provider="anthropic",
            model="future-model-not-in-table",
            input_tokens=10,
            output_tokens=10,
        )
        == 0.0
    )


def test_cost_for_zero_tokens_is_zero() -> None:
    assert (
        cost_for(
            provider="anthropic",
            model="claude-sonnet-4-5",
            input_tokens=0,
            output_tokens=0,
        )
        == 0.0
    )


def test_cost_for_scales_linearly() -> None:
    half = cost_for(
        provider="openai",
        model="gpt-4o",
        input_tokens=500,
        output_tokens=500,
    )
    full = cost_for(
        provider="openai",
        model="gpt-4o",
        input_tokens=1000,
        output_tokens=1000,
    )
    assert full == pytest.approx(half * 2)
