"""Tool registry and exports for agent-runtime tool modules."""

import uuid
from collections.abc import Callable
from typing import Any

from langchain_core.tools import BaseTool
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.tools.fetch_url import build_fetch_url
from app.agents.tools.rag_search import build_rag_search, rag_search
from app.agents.tools.read_doc import build_read_doc
from app.agents.tools.web_search import build_web_search
from app.agents.tools.write_artifact import build_write_artifact


def build_tools(
    run_id: uuid.UUID,
    session_factory: Callable[[], AsyncSession],
) -> list[BaseTool | Any]:
    """Build run-scoped tool set for agent execution."""
    return [
        build_web_search(run_id, session_factory),
        build_fetch_url(run_id, session_factory),
        build_rag_search(run_id, session_factory),
        build_read_doc(session_factory),
        build_write_artifact(run_id, session_factory),
    ]


__all__ = ["build_tools", "rag_search"]
