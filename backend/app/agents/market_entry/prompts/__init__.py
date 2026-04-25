"""Back-compat shim for prompt loading."""

from __future__ import annotations

from pathlib import Path

_PROMPT_DIR = Path(__file__).parent


def load(name: str) -> str:
    from app.agents.market_entry.profile import MARKET_ENTRY_PROFILE

    try:
        return MARKET_ENTRY_PROFILE.load_prompt(name)
    except KeyError as exc:
        if name.endswith(".md"):
            name = name[:-3]
        safe = name.replace("..", "")
        path = (_PROMPT_DIR / f"{safe}.md").resolve()
        if _PROMPT_DIR.resolve() not in path.parents and path.parent != _PROMPT_DIR.resolve():
            raise FileNotFoundError(name) from exc
        if not path.exists():
            raise FileNotFoundError(f"prompt not found: {name}") from exc
        return path.read_text(encoding="utf-8")


__all__ = ["load"]
