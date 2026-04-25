"""Unit tests for `rag_search` early-exit paths (no DB / no network).

These cover the trivial short-circuit cases (empty query, k <= 0) so they
can run inside `make check` without Postgres or an OpenAI key. The full
end-to-end RAG behavior is covered by
`tests/integration/test_rag_search.py` (skipped without OPENAI_API_KEY).
"""

from __future__ import annotations

import pytest

from app.agents.tools.rag_search import _rag_search_impl


@pytest.mark.asyncio
async def test_rag_search_empty_query_returns_empty() -> None:
    assert await _rag_search_impl("", k=8) == []
    assert await _rag_search_impl("   \n  ", k=8) == []


@pytest.mark.asyncio
async def test_rag_search_zero_k_returns_empty() -> None:
    assert await _rag_search_impl("anything", k=0) == []
    assert await _rag_search_impl("anything", k=-1) == []
