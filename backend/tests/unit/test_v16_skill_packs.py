"""Unit tests for V1.6 consulting skill packs."""

from __future__ import annotations

from pathlib import Path

import pytest

SKILL_SLUGS = (
    "market-sizing",
    "evidence-discipline",
    "unit-economics",
    "competitive-intelligence",
)


def _skill_path(slug: str) -> Path:
    return Path(__file__).parents[2] / "app" / "skills" / slug / "SKILL.md"


def _split_frontmatter(content: str) -> tuple[str, str]:
    assert content.startswith("---\n")
    _, frontmatter, body = content.split("---\n", 2)
    return frontmatter, body


@pytest.mark.parametrize("slug", SKILL_SLUGS)
def test_v16_skill_pack_exists_with_frontmatter_and_substantive_body(slug: str) -> None:
    path = _skill_path(slug)

    assert path.exists(), f"Missing skill pack: {path}"

    frontmatter, body = _split_frontmatter(path.read_text(encoding="utf-8"))
    body_lines = [line for line in body.splitlines() if line.strip()]

    assert f"name: {slug}" in frontmatter.splitlines()
    assert any(
        line.startswith("description: ") and line.removeprefix("description: ").strip()
        for line in frontmatter.splitlines()
    )
    assert len(body_lines) >= 40
