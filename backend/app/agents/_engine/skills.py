"""Consulting skill prompt loading and injection."""

from __future__ import annotations

from functools import lru_cache
from importlib import resources

_SKILL_PACKAGE = "app.skills"


@lru_cache(maxsize=64)
def load_skill(slug: str) -> str:
    """Read SKILL.md for `slug`, strip YAML frontmatter, return body.

    Raises FileNotFoundError if the slug doesn't exist.
    """
    path = resources.files(_SKILL_PACKAGE) / slug / "SKILL.md"

    try:
        content = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Skill slug not found: {slug}") from exc

    return _strip_frontmatter(content)


def _strip_frontmatter(content: str) -> str:
    """Remove YAML frontmatter from a skill body when present."""
    for delimiter in ("---\n", "---\r\n"):
        if not content.startswith(delimiter):
            continue

        parts = content.split(delimiter, 2)
        if len(parts) == 3:
            content = parts[2]
        break

    return content.lstrip("\r\n")


def render_skills_block(slugs: tuple[str, ...]) -> str:
    """Return applicable consulting skill bodies in deterministic slug order."""
    if not slugs:
        return ""

    bodies = "\n\n".join(load_skill(slug) for slug in slugs)
    return f"## Applicable Consulting Skills\n\n{bodies}"


def inject_skills(system_prompt: str, slugs: tuple[str, ...]) -> str:
    """Prepend rendered skills to system_prompt when slugs are provided."""
    if not slugs:
        return system_prompt

    return f"{render_skills_block(slugs)}\n\n{system_prompt}"
