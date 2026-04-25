"""Fetch URL content and register as web evidence."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any, TypedDict

import httpx
from langchain_core.tools import tool
from readability import Document
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.tools.cite import register_evidence
from app.models.evidence import EvidenceKind


class FetchUrlHit(TypedDict):
    src_id: str
    title: str
    snippet: str
    url: str


def build_fetch_url(
    run_id: uuid.UUID,
    session_factory: Callable[[], AsyncSession],
) -> Any:
    @tool
    async def fetch_url(url: str) -> dict[str, Any]:
        """Fetch URL content, summarize to snippet, and register Evidence."""
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(url)
            response.raise_for_status()

        doc = Document(response.text)
        title = doc.short_title() or url
        summary_html = doc.summary(html_partial=True)
        snippet = _strip_html(summary_html)[:1000]

        async with session_factory() as session:
            src_id = await register_evidence(
                session,
                run_id,
                kind=EvidenceKind.web,
                url=url,
                chunk_id=None,
                title=title,
                snippet=snippet,
                provider="fetch_url",
            )

        hit = FetchUrlHit(src_id=src_id, title=title, snippet=snippet, url=url)
        return dict(hit)

    return fetch_url


def _strip_html(text: str) -> str:
    # Lightweight plaintext extraction without pulling in another parser.
    out: list[str] = []
    inside = False
    for ch in text:
        if ch == "<":
            inside = True
            continue
        if ch == ">":
            inside = False
            continue
        if not inside:
            out.append(ch)
    return " ".join("".join(out).split())


__all__ = ["build_fetch_url"]
