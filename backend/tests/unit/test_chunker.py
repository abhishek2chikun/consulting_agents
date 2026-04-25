import pytest
import tiktoken

from app.ingestion.chunker import ChunkPayload, chunk

_enc = tiktoken.get_encoding("cl100k_base")


def _token_count(text: str) -> int:
    return len(_enc.encode(text))


def test_chunk_short_text_returns_single_chunk() -> None:
    text = "Hello world, this is short."
    chunks = chunk(text, target_tokens=800, overlap_tokens=100)
    assert len(chunks) == 1
    assert chunks[0].ord == 0
    assert chunks[0].text == text


def test_chunk_long_text_respects_target_size() -> None:
    paragraph = "The quick brown fox jumps over the lazy dog. " * 200
    chunks = chunk(paragraph, target_tokens=400, overlap_tokens=50)
    assert len(chunks) >= 2
    for c in chunks:
        assert _token_count(c.text) <= 400 + 5, f"chunk ord={c.ord} too large"


def test_chunks_overlap_by_configured_amount() -> None:
    paragraph = "alpha bravo charlie delta echo foxtrot golf hotel " * 200
    chunks = chunk(paragraph, target_tokens=300, overlap_tokens=80)
    assert len(chunks) >= 2
    for i in range(len(chunks) - 1):
        a_tokens = _enc.encode(chunks[i].text)
        b_tokens = _enc.encode(chunks[i + 1].text)
        a_tail = a_tokens[-80:]
        b_head = b_tokens[:80]
        match_count = sum(1 for x, y in zip(a_tail, b_head) if x == y)
        assert match_count >= 40, (
            f"insufficient overlap between chunks {i}/{i + 1}: {match_count}/80 tokens match"
        )


def test_chunks_preserve_order() -> None:
    paragraph = " ".join(f"word{i}" for i in range(2000))
    chunks = chunk(paragraph, target_tokens=200, overlap_tokens=20)
    assert [c.ord for c in chunks] == list(range(len(chunks)))
    assert "word0" in chunks[0].text
    assert "word1999" in chunks[-1].text


def test_chunk_empty_text_returns_empty() -> None:
    assert chunk("", 800, 100) == []
    assert chunk("   \n  ", 800, 100) == []


def test_chunk_validates_args() -> None:
    with pytest.raises(ValueError, match="target_tokens"):
        chunk("hi", target_tokens=0, overlap_tokens=0)
    with pytest.raises(ValueError, match="overlap_tokens"):
        chunk("hi", target_tokens=100, overlap_tokens=100)
    with pytest.raises(ValueError, match="overlap_tokens"):
        chunk("hi", target_tokens=100, overlap_tokens=-1)


def test_chunk_returns_chunk_payload_dataclass() -> None:
    chunks = chunk("hello world", 800, 100)
    assert isinstance(chunks[0], ChunkPayload)
    assert chunks[0].ord == 0
