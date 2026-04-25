"""Unit tests for market-entry prompt loader (M6.1)."""

from __future__ import annotations

import pytest

from app.agents.market_entry.prompts import load


@pytest.mark.parametrize(
    "name,must_contain",
    [
        ("framing", ["questionnaire", "FramingBrief"]),
        ("reviewer", ["GateVerdict"]),
        ("synthesis", ["final_report"]),
        ("audit", ["audit"]),
        ("stage1_foundation", ["market_sizing", "customer", "regulatory"]),
        ("stage2_competitive", ["competitor", "channel", "pricing"]),
        ("stage3_risk", ["risk"]),
    ],
)
def test_load_returns_non_empty_with_expected_tokens(name: str, must_contain: list[str]) -> None:
    text = load(name)
    assert isinstance(text, str)
    assert text.strip(), f"prompt {name} should be non-empty"
    for token in must_contain:
        assert token in text, f"prompt {name} missing expected token {token!r}"


def test_load_unknown_prompt_raises() -> None:
    with pytest.raises(FileNotFoundError):
        load("does_not_exist")


def test_load_substage_prompt() -> None:
    text = load("stage1/market_sizing")
    assert text.strip()
    assert "market" in text.lower()
