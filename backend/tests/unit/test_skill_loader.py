"""Unit tests for consulting skill prompt injection."""

from __future__ import annotations

import pytest

from app.agents._engine.skills import inject_skills, load_skill, render_skills_block


def test_load_skill_strips_yaml_frontmatter() -> None:
    body = load_skill("market-sizing")
    before_first_heading = body.split("#", maxsplit=1)[0]

    assert not body.startswith("---")
    assert "name:" not in before_first_heading
    assert body.startswith("# Market Sizing")


def test_load_skill_uses_lru_cache_hits() -> None:
    load_skill.cache_clear()

    load_skill("market-sizing")
    before = load_skill.cache_info()
    load_skill("market-sizing")
    after = load_skill.cache_info()

    assert after.hits == before.hits + 1


def test_load_skill_missing_slug_raises_file_not_found_error() -> None:
    with pytest.raises(FileNotFoundError, match="does-not-exist"):
        load_skill("does-not-exist")


def test_render_skills_block_empty_tuple_returns_empty_string() -> None:
    assert render_skills_block(()) == ""


def test_render_skills_block_preserves_slug_order() -> None:
    block = render_skills_block(("market-sizing", "evidence-discipline"))

    assert block.index("# Market Sizing") < block.index("# Evidence Discipline")


def test_render_skills_block_header_injected_exactly() -> None:
    block = render_skills_block(("market-sizing",))

    assert block.startswith("## Applicable Consulting Skills")
    assert block.splitlines()[0] == "## Applicable Consulting Skills"


def test_inject_skills_passthrough_for_empty_tuple() -> None:
    prompt = "System prompt\nwith formatting."

    assert inject_skills(prompt, ()) == prompt


def test_inject_skills_prepends_block_for_non_empty_tuple() -> None:
    prompt = "System prompt"
    expected_block = render_skills_block(("market-sizing",))

    assert inject_skills(prompt, ("market-sizing",)) == f"{expected_block}\n\n{prompt}"
