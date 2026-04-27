"""Integration tests for M6.8 synthesis node."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.agents.market_entry.nodes.synthesis import (
    REPORT_PATH,
    CitationError,
    build_synthesis_node,
)
from app.core.db import AsyncSessionLocal
from app.models import (
    SINGLETON_USER_ID,
    Artifact,
    Evidence,
    EvidenceKind,
    Run,
    RunStatus,
)
from app.testing.fake_chat_model import FakeChatModel


@pytest_asyncio.fixture
async def run_with_evidence() -> AsyncIterator[uuid.UUID]:
    async with AsyncSessionLocal() as session:
        run = Run(
            user_id=SINGLETON_USER_ID,
            task_id="market_entry",
            goal="Enter EU EV-charging market",
            status=RunStatus.running,
        )
        session.add(run)
        await session.commit()
        await session.refresh(run)
        session.add(
            Evidence(
                run_id=run.id,
                src_id="s1",
                title="Source 1",
                url="https://example.com/1",
                snippet="snip",
                kind=EvidenceKind.web,
                provider="tavily",
            )
        )
        session.add(
            Evidence(
                run_id=run.id,
                src_id="s2",
                title="Source 2",
                url="https://example.com/2",
                snippet="snip2",
                kind=EvidenceKind.web,
                provider="tavily",
            )
        )
        await session.commit()
        yield run.id


@pytest.mark.asyncio
async def test_synthesis_writes_final_report_and_appends_sources(
    run_with_evidence: uuid.UUID,
) -> None:
    body = (
        "# Final\n\n"
        "## Executive Summary\n\n"
        "- The market is large [^s1].\n"
        "- Competition is intense [^s2].\n"
    )
    fake = FakeChatModel(responses=[body])
    node = build_synthesis_node(model=fake)

    out = await node(
        {
            "run_id": str(run_with_evidence),
            "goal": "x",
            "artifacts": {"stage1_foundation/findings.md": "Market large [^s1]"},
        }
    )

    report = out["artifacts"][REPORT_PATH]
    assert "## Sources" in report
    assert "[^s1]" in report
    assert "Source 1" in report

    async with AsyncSessionLocal() as session:
        row = (
            await session.execute(
                select(Artifact).where(
                    Artifact.run_id == run_with_evidence,
                    Artifact.path == REPORT_PATH,
                )
            )
        ).scalar_one()
    assert row.kind == "markdown"
    assert "## Sources" in row.content


@pytest.mark.asyncio
async def test_synthesis_self_heals_unknown_citation(
    run_with_evidence: uuid.UUID,
) -> None:
    # Model fabricates an unknown src_id three times in a row; the
    # node should NOT raise — instead it strips the bogus token and
    # still produces a report.
    body = "Bad claim [^ghost]."
    fake = FakeChatModel(responses=[body, body, body])
    node = build_synthesis_node(model=fake)

    out = await node(
        {
            "run_id": str(run_with_evidence),
            "goal": "x",
            "artifacts": {},
        }
    )
    report = out["artifacts"][REPORT_PATH]
    assert "[^ghost]" not in report
    assert "## Sources" in report


@pytest.mark.asyncio
async def test_synthesis_recovers_on_retry(
    run_with_evidence: uuid.UUID,
) -> None:
    # First attempt fabricates, second attempt is clean.
    bad = "Bad claim [^ghost]."
    good = "Good claim [^s1]."
    fake = FakeChatModel(responses=[bad, good, good])
    node = build_synthesis_node(model=fake)

    out = await node(
        {
            "run_id": str(run_with_evidence),
            "goal": "x",
            "artifacts": {},
        }
    )
    report = out["artifacts"][REPORT_PATH]
    assert "[^s1]" in report
    assert "[^ghost]" not in report


def test_citation_error_class_still_exported() -> None:
    # Kept for back-compat with downstream callers / tests.
    assert issubclass(CitationError, ValueError)
