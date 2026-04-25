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
        ("stage4_demand", ["StageOutput", "stage4_demand.md", "[^src_id]"]),
        ("stage5_strategy", ["StageOutput", "stage5_strategy.md", "[^src_id]"]),
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


@pytest.mark.parametrize("name", ["stage4_demand", "stage5_strategy"])
def test_new_stage_prompts_follow_structured_evidence_contract(name: str) -> None:
    text = load(name)

    assert "StageOutput" in text
    assert "artifacts" in text
    assert "evidence" in text
    assert "[^src_id]" in text
    assert "[1]" not in text
    assert "[2]" not in text
    assert "final_report.md" not in text


def test_synthesis_prompt_includes_five_stage_report_sections() -> None:
    text = load("synthesis")

    for section in [
        "Executive Summary",
        "Engagement Context",
        "Market Foundation",
        "Competitive Landscape",
        "Risk Assessment",
        "Demand Validation",
        "Entry Strategy",
        "Sources",
    ]:
        assert section in text
