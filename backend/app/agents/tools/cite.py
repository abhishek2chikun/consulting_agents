"""Evidence registration helper for tool outputs."""

from __future__ import annotations

import hashlib
import json
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Evidence, EvidenceKind


def make_src_id(
    *,
    run_id: uuid.UUID,
    kind: str,
    url: str | None,
    chunk_id: uuid.UUID | None,
    title: str,
    snippet: str,
    provider: str,
) -> str:
    payload = {
        "run_id": str(run_id),
        "kind": kind,
        "url": url,
        "chunk_id": str(chunk_id) if chunk_id is not None else None,
        "title": title,
        "snippet": snippet,
        "provider": provider,
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    return f"src_{digest[:8]}"


async def register_evidence(
    session: AsyncSession,
    run_id: uuid.UUID,
    *,
    kind: EvidenceKind,
    url: str | None,
    chunk_id: uuid.UUID | None,
    title: str,
    snippet: str,
    provider: str,
) -> str:
    src_id = make_src_id(
        run_id=run_id,
        kind=kind.value,
        url=url,
        chunk_id=chunk_id,
        title=title,
        snippet=snippet,
        provider=provider,
    )

    existing = (
        await session.execute(
            select(Evidence).where(Evidence.run_id == run_id, Evidence.src_id == src_id)
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing.src_id

    session.add(
        Evidence(
            run_id=run_id,
            src_id=src_id,
            kind=kind,
            url=url,
            chunk_id=chunk_id,
            title=title,
            snippet=snippet,
            provider=provider,
        )
    )
    await session.commit()
    return src_id


__all__ = ["make_src_id", "register_evidence"]
