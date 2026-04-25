"""Embedding generation for the ingest pipeline (M3.6).

Wraps `langchain_openai.OpenAIEmbeddings` so the worker doesn't have to
know how the API key is resolved. The key is fetched from
`SettingsService` (encrypted-at-rest in `provider_keys`); the env var
`OPENAI_API_KEY` is **not** consulted directly — that is intentional, so
production behavior matches whatever the user configured via the
Settings page.

Single model, single dimension for V1: `text-embedding-3-small` →
1536-dim vectors. Changing this requires a new column type
(`Vector(N)`) AND a fresh migration; see `app/models/chunk.py`.
"""

from __future__ import annotations

from langchain_openai import OpenAIEmbeddings
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.services.settings_service import SettingsService

# OpenAI's smallest 1536-dim embedding model. Hardcoded for V1; the
# pipeline persists the model name on each `Chunk` row so future
# re-embeddings know which generator produced a given vector.
EMBEDDING_MODEL = "text-embedding-3-small"

# Caps the per-call payload to OpenAI. The langchain client does its
# own batching internally as well, but bounding it here also bounds
# memory growth for very large documents.
EMBEDDING_BATCH_SIZE = 64


async def embed_texts(texts: list[str], *, session: AsyncSession) -> list[list[float]]:
    """Return one embedding vector per input text, in order.

    Args:
        texts: input strings. Empty list yields an empty result.
        session: AsyncSession used **only** to fetch the OpenAI API key
            from `SettingsService`. The session is not written to.

    Raises:
        ValueError: if no `openai` provider key is configured.
        RuntimeError: if any returned vector's length doesn't match the
            configured `EMBEDDING_DIM` — usually a sign someone changed
            `EMBEDDING_DIM` without picking a model whose output matches.
    """
    if not texts:
        return []

    svc = SettingsService(session)
    api_key = await svc.get_provider_key("openai")
    if not api_key:
        raise ValueError("No API key configured for provider 'openai' (required for embeddings)")

    expected_dim = get_settings().embedding_dim
    client = OpenAIEmbeddings(model=EMBEDDING_MODEL, api_key=SecretStr(api_key))

    out: list[list[float]] = []
    for start in range(0, len(texts), EMBEDDING_BATCH_SIZE):
        batch = texts[start : start + EMBEDDING_BATCH_SIZE]
        vectors = await client.aembed_documents(batch)
        for v in vectors:
            if len(v) != expected_dim:
                raise RuntimeError(
                    f"Embedding dim mismatch: got {len(v)}, expected {expected_dim}. "
                    f"Check EMBEDDING_DIM env vs model output size."
                )
        out.extend(vectors)
    return out


__all__ = ["EMBEDDING_BATCH_SIZE", "EMBEDDING_MODEL", "embed_texts"]
