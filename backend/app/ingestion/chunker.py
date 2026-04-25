"""Token-aware chunker for parsed markdown documents.

Uses tiktoken's `cl100k_base` encoding (the OpenAI/Anthropic-compatible BPE)
as a reasonable proxy for chat-model token boundaries. Output chunks are
character-aligned (we encode → take a window → decode), so the boundaries
land between BPE tokens, not arbitrary characters.

Designed to be called from the ingest worker after Docling parsing.
"""

from __future__ import annotations

from dataclasses import dataclass

import tiktoken


@dataclass(frozen=True)
class ChunkPayload:
    ord: int
    text: str


_ENCODING_NAME = "cl100k_base"
_encoding = tiktoken.get_encoding(_ENCODING_NAME)


def chunk(
    markdown: str,
    target_tokens: int = 800,
    overlap_tokens: int = 100,
) -> list[ChunkPayload]:
    """Split markdown into token-windowed chunks.

    Args:
        markdown: input text.
        target_tokens: target chunk size in BPE tokens. Must be > 0.
        overlap_tokens: token overlap between consecutive chunks. Must satisfy
            0 <= overlap_tokens < target_tokens.

    Returns:
        Ordered list of ChunkPayload. Empty / whitespace-only input yields [].
    """
    if target_tokens <= 0:
        raise ValueError("target_tokens must be > 0")
    if overlap_tokens < 0 or overlap_tokens >= target_tokens:
        raise ValueError("overlap_tokens must be in [0, target_tokens)")

    text = markdown.strip()
    if not text:
        return []

    tokens = _encoding.encode(text)
    if len(tokens) <= target_tokens:
        return [ChunkPayload(ord=0, text=text)]

    chunks: list[ChunkPayload] = []
    stride = target_tokens - overlap_tokens
    for i, start in enumerate(range(0, len(tokens), stride)):
        window = tokens[start : start + target_tokens]
        if not window:
            break
        chunk_text = _encoding.decode(window).strip()
        if chunk_text:
            chunks.append(ChunkPayload(ord=i, text=chunk_text))
        # Avoid emitting a trailing tiny tail-only chunk that's entirely
        # contained in the previous one's overlap region. Once the current
        # window has consumed up to the last token, there's nothing new
        # left for the next iteration to add.
        if start + target_tokens >= len(tokens):
            break

    # Renumber `ord` densely (in case any window was empty and skipped).
    return [ChunkPayload(ord=i, text=c.text) for i, c in enumerate(chunks)]
