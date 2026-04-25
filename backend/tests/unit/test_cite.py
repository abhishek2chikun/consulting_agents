"""Unit tests for evidence registration helper (M4.5 backfill)."""

from __future__ import annotations

import uuid

from app.agents.tools.cite import make_src_id


def test_make_src_id_is_stable_for_same_payload() -> None:
    run_id = uuid.uuid4()
    a = make_src_id(
        run_id=run_id,
        kind="web",
        url="https://example.com/x",
        chunk_id=None,
        title="T",
        snippet="S",
        provider="tavily",
    )
    b = make_src_id(
        run_id=run_id,
        kind="web",
        url="https://example.com/x",
        chunk_id=None,
        title="T",
        snippet="S",
        provider="tavily",
    )
    assert a == b
    assert a.startswith("src_")


def test_make_src_id_changes_with_content() -> None:
    run_id = uuid.uuid4()
    a = make_src_id(
        run_id=run_id,
        kind="web",
        url="https://example.com/x",
        chunk_id=None,
        title="T",
        snippet="S1",
        provider="tavily",
    )
    b = make_src_id(
        run_id=run_id,
        kind="web",
        url="https://example.com/x",
        chunk_id=None,
        title="T",
        snippet="S2",
        provider="tavily",
    )
    assert a != b
