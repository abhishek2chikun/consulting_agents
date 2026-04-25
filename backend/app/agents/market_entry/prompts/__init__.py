"""Prompt loader for market-entry agents.

Each prompt file is a Markdown document under this package.
`load(name)` returns the full prompt text. Subdirectory prompts can be
addressed as `"stage1/market_sizing"`.
"""

from __future__ import annotations

from pathlib import Path

_PROMPT_DIR = Path(__file__).parent


def load(name: str) -> str:
    """Return the prompt body for ``name`` (without ``.md`` extension)."""
    if name.endswith(".md"):
        name = name[:-3]
    safe = name.replace("..", "")
    path = (_PROMPT_DIR / f"{safe}.md").resolve()
    if _PROMPT_DIR.resolve() not in path.parents and path.parent != _PROMPT_DIR.resolve():
        raise FileNotFoundError(name)
    if not path.exists():
        raise FileNotFoundError(f"prompt not found: {name}")
    return path.read_text(encoding="utf-8")


__all__ = ["load"]
