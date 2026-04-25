# app/ingestion — agent.md

## Status
**Active (M3.6).**
Synchronous Docling-based PDF/document parser, token-aware chunker,
OpenAI embedder, and the async ingest worker are all in place. Uploads
via `POST /documents` now run end-to-end (parse → chunk → embed →
persist `Chunk` rows) as a background `asyncio.Task`.

---

## Purpose

Document ingestion pipeline: parse uploaded files into markdown, split
into chunks, embed each chunk, and persist `Chunk` rows for retrieval.
This module owns all heavy / blocking I/O in the ingest path. Public
callers (the API layer and the agent runtime) must go through the
worker (M3.6) — never import Docling directly.

---

## Directory Structure
```text
app/ingestion/
  __init__.py
  docling_parser.py    # parse_to_markdown(path) -> (markdown, metadata)
  chunker.py           # chunk(markdown, target_tokens, overlap_tokens) -> list[ChunkPayload]
  embedder.py          # embed_texts(texts, *, session) -> list[list[float]]
  worker.py            # run_ingest(document_id) — background pipeline driver
```

### Corresponding Tests
```text
backend/tests/unit/test_docling_parser.py
backend/tests/unit/test_chunker.py
backend/tests/integration/test_ingest_pipeline.py   # live OpenAI; skipped without OPENAI_API_KEY
backend/tests/fixtures/sample.pdf       # 2-page deterministic PDF
```

---

## Public API

```python
from app.ingestion.docling_parser import parse_to_markdown

markdown, metadata = parse_to_markdown(path)
# metadata = {"page_count": int, "source_format": "pdf" | ...}
```

`parse_to_markdown` is **synchronous and blocking**. Async callers must
wrap it with `asyncio.to_thread(parse_to_markdown, path)`.

```python
from app.ingestion.chunker import chunk, ChunkPayload

chunks = chunk(markdown, target_tokens=800, overlap_tokens=100)
# chunks: list[ChunkPayload(ord:int, text:str)]
```

`chunk` uses tiktoken's `cl100k_base` BPE encoding to size windows
(GPT-4 / Claude 3 family compatible). It is pure CPU and fast — no
async wrapping needed. Boundaries land between BPE tokens, not on
sentence/markdown structure (a known V1 limitation; M5+ may revisit).
A trailing tail-tiny window that is wholly contained in the prior
overlap region is suppressed.

```python
from app.ingestion.embedder import EMBEDDING_MODEL, embed_texts

vectors = await embed_texts(["text 1", "text 2"], session=session)
# vectors: list[list[float]] each of length get_settings().embedding_dim (1536)
```

`embed_texts` resolves the OpenAI API key from `SettingsService` (NOT
from `OPENAI_API_KEY`) so it always reflects what the user configured
via the Settings page. Empty input returns `[]`. Dimension mismatch
between the model output and `EMBEDDING_DIM` raises `RuntimeError`.
Hardcoded model: `text-embedding-3-small` (1536-dim). Changing the
model requires a column-type migration on `chunks.embedding`.

```python
import asyncio
from app.ingestion.worker import run_ingest

asyncio.create_task(run_ingest(doc_id))
```

`run_ingest`:
- Owns its own `AsyncSessionLocal()` sessions; do **not** pass one in.
  It runs as a background task long after the originating request has
  closed its session.
- Drives the document through `pending → parsing → embedding → ready`
  (or `→ failed` on any error). The `DocumentStatus` enum has no
  `chunking` member, so chunking is collapsed into the `parsing` state;
  it has no `indexed` member, so terminal-success is `ready`.
- Catches all exceptions, marks the row `failed` with a short error
  message in `Document.error`, and returns normally — so the wrapping
  task completes cleanly and `TASK_REGISTRY`'s done-callback removes
  it without an "exception was never retrieved" warning. The one
  exception is `asyncio.CancelledError`, which is re-raised after
  marking the row failed so cancellation actually propagates.

---

## Dependencies

| Imports from | What |
|---|---|
| `docling.document_converter` | `DocumentConverter` |
| `tiktoken` | `cl100k_base` BPE encoding for token-aware chunking |
| `langchain_openai` | `OpenAIEmbeddings` async client |
| `app.services.settings_service` | `SettingsService.get_provider_key("openai")` |
| `app.core.db` | `AsyncSessionLocal` for the worker's owned sessions |
| `app.models` | `Document`, `DocumentStatus`, `Chunk` |

| Consumed by | What |
|---|---|
| `app.api.documents` | Schedules `run_ingest` after each upload |
| `tests.unit.test_docling_parser` | Docling wrapper unit tests |
| `tests.unit.test_chunker` | chunker unit tests |
| `tests.integration.test_ingest_pipeline` | end-to-end pipeline test |

---

## Config

None. Docling currently uses its built-in defaults (auto OCR, auto
layout). Tunables (e.g. disable OCR, force layout backend) will land
alongside the worker if needed.

---

## Current Progress

- `parse_to_markdown(path)` returns `(markdown, metadata)` with
  `page_count` and `source_format`.
- Verified against Docling 2.91 — `document.pages` is a
  `dict[int, PageItem]`, `export_to_markdown()` returns a clean string.
- Defensive fallback to `document.num_pages()` if the `pages` attr
  changes shape in a future Docling release.
- `chunk(markdown, target_tokens=800, overlap_tokens=100)` produces
  ordered `ChunkPayload(ord, text)` windows using `cl100k_base` BPE.
  Validates args, returns `[]` for empty/whitespace input, returns a
  single chunk when input fits in `target_tokens`.
- `embed_texts(texts, *, session)` wraps `OpenAIEmbeddings` for the
  `text-embedding-3-small` model (1536-dim). Reads the API key from
  `SettingsService` (encrypted-at-rest), batches up to 64 texts per
  call, asserts dim matches `EMBEDDING_DIM`.
- `run_ingest(document_id)` orchestrates the full pipeline as a
  background `asyncio.Task`. `POST /documents` schedules it via
  `TASK_REGISTRY` so a future cancel endpoint can find it.

## Next Steps
1. **M3.7:** thread the worker's status transitions through to a
   user-visible progress indicator on the Documents page (frontend).
2. Re-embed / migration tooling when `EMBEDDING_DIM` ever changes.

## Known Issues / Blockers

- **First-run model downloads.** On a fresh machine Docling downloads
  layout / OCR model weights from Hugging Face (~hundreds of MB) on
  the first `convert()` call. This makes the first run of
  `test_parse_to_markdown_returns_text_and_two_pages` slow and requires
  network access. The test is marked `@pytest.mark.slow` so future CI
  can opt out via `-m "not slow"` once we pre-cache weights.
- Docling pulls a heavy transitive tree (PyTorch, transformers, OCR
  libs). This is expected for V1; do not substitute a lighter parser.
- `docling` does not ship `py.typed`; mypy is configured to ignore
  missing imports for `docling.*` (see `backend/mypy.ini`).
