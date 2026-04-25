# app.agents.tools — agent.md

## Status
**Active (M4.4).** LangChain tools + provider adapters exposed to the
agent stages. V1 currently ships one retrieval tool (`rag_search`) and
three web-search provider adapters (Tavily, Exa, Perplexity) used by
diagnostic and upcoming `web_search` tool flows.

---

## Purpose

Hosts `@tool`-decorated callables that LangGraph / DeepAgents nodes
(landing in M5+) bind to LLM models. Each tool is a small, focused
async function with a clear contract — input schema, output schema,
docstring (which becomes part of the tool prompt the model sees).

`rag_search` is the V1 RAG primitive. Given a natural-language query it
returns the top-k chunks (across all ingested documents) ranked by
cosine similarity to the query embedding, along with the metadata
(`document_id`, `chunk_id`, `ord`, `score`) needed for downstream
citation.

---

## Directory Structure
```text
app/agents/tools/
  __init__.py            # exports rag_search
  rag_search.py          # @tool rag_search + _rag_search_impl + RagHit
  providers/
    __init__.py
    base.py              # SearchResult schema + SearchProvider protocol
    tavily.py            # Tavily /search adapter
    exa.py               # Exa /search adapter
    perplexity.py        # Perplexity chat/completions adapter
```

### Corresponding Tests
```text
backend/tests/unit/test_rag_search.py
  test_rag_search_empty_query_returns_empty
  test_rag_search_zero_k_returns_empty
backend/tests/unit/test_search_provider_base.py
  test_search_result_round_trip_serialization
backend/tests/unit/test_tavily_provider.py
  test_tavily_provider_normalizes_results
backend/tests/unit/test_exa_provider.py
  test_exa_provider_normalizes_results
backend/tests/unit/test_perplexity_provider.py
  test_perplexity_provider_maps_citations_to_results
backend/tests/integration/test_rag_search.py
  test_rag_search_returns_relevant_chunk_after_ingest   # @pytest.mark.integration; skipped without OPENAI_API_KEY
```

Unit tests pin early-exit behavior for `rag_search` and HTTP-response
normalization for each provider adapter. Integration tests cover the
full M3.6 + M3.7 loop (upload → ingest → `rag_search`). Search-adapter
live behavior is currently exercised indirectly via
`/health/search` integration tests with `respx` mocking.

---

## Public API

```python
from app.agents.tools.rag_search import (
    rag_search,          # @tool — async (query: str, k: int = 8) -> list[dict]
    _rag_search_impl,    # async (query, k) -> list[RagHit]; bypasses StructuredTool
    RagHit,              # TypedDict {text, document_id, chunk_id, ord, score}
    DEFAULT_K,           # int = 8
)
from app.agents.tools.providers import SearchProvider, SearchResult
from app.agents.tools.providers.tavily import TavilyProvider
from app.agents.tools.providers.exa import ExaProvider
from app.agents.tools.providers.perplexity import PerplexityProvider
```

### Result shape (`RagHit`)

| Field | Type | Notes |
|---|---|---|
| `text` | `str` | Chunk text (post-Docling, post-chunker). |
| `document_id` | `str` | UUID of the parent `Document`. |
| `chunk_id` | `str` | UUID of the `Chunk` row. |
| `ord` | `int` | 0-based position within the parent document. |
| `score` | `float` | `1 - cosine_distance`. Higher = more similar. For OpenAI's L2-normalized embeddings, lands in [-1, 1]. |

### Behavior

1. Empty / whitespace query → returns `[]` without touching DB or network.
2. `k <= 0` → returns `[]` without touching DB or network.
3. Otherwise: opens its own `AsyncSessionLocal()`, embeds the query via
   `embed_texts` (using the configured OpenAI key), then runs
   `select(Chunk.id, Chunk.document_id, Chunk.text, Chunk.ord,
   Chunk.embedding.cosine_distance(q_vec).label("distance"))
   .order_by(distance).limit(k)`.

The ORM `Chunk.embedding.cosine_distance(...)` comparator is provided
by `pgvector.sqlalchemy` (≥0.4, confirmed) and emits SQL using the
pgvector `<=>` operator. The HNSW index `ix_chunks_embedding_hnsw`
(M3.2) backs the ORDER BY automatically.

---

## Dependencies

| Imports from | What |
|---|---|
| `langchain_core.tools` | `@tool` decorator |
| `sqlalchemy` | `select` + ORM query construction |
| `httpx` | async HTTP clients for provider adapters |
| `pgvector.sqlalchemy` | (transitively, via `Chunk.embedding`) cosine-distance comparator |
| `app.core.db` | `AsyncSessionLocal` |
| `app.ingestion.embedder` | `embed_texts` |
| `app.models.chunk` | `Chunk` ORM class |

| Consumed by | What |
|---|---|
| `tests.unit.test_rag_search` | early-exit paths |
| `tests.unit.test_*_provider` | adapter normalization behavior |
| `tests.integration.test_rag_search` | full ingest+search loop |
| `app.api.health` | `/health/search` diagnostics endpoint |
| Future: agent runtime (M5+) | binds `rag_search` to retrieval / drafting / critique nodes |

---

## Config

None at this layer. The OpenAI key for query embedding is resolved
through `SettingsService` (same path as M3.6 ingest). The HNSW
`ef_search` knob is left at the pgvector default (40); revisit if V1
corpora grow large enough to make the planner skip the index.

---

## Current Progress

- M3.7 — `@tool rag_search` landed. Async-native (verified
  `langchain_core.tools.tool` accepts coroutine functions and yields a
  `StructuredTool` whose `ainvoke` is itself a coroutine). Uses the
  pgvector ORM comparator (`Chunk.embedding.cosine_distance`) rather
  than raw SQL with a string-cast vector — more SQLAlchemy-native,
  avoids manual `CAST(:q AS vector)` boilerplate. Score sign convention
  documented (`1 - distance`, higher better). Two unit tests + one
  integration test (skipped in CI without OPENAI_API_KEY).
- M4.1-M4.4 — Added provider-abstraction layer under `tools/providers`:
  `SearchResult` schema + `SearchProvider` protocol and adapters for
  Tavily, Exa, and Perplexity. Each adapter has a mocked unit test
  (`respx`) and fixture payload under `tests/fixtures/`.

## Next Steps

1. **M5+** — bind `rag_search` to LangGraph retrieval / drafting /
   critique nodes; the binding lives in the per-stage agent modules,
   not here.
2. **M4.5** — implement `web_search` tool factory that consumes these
   adapters and emits evidence-registered `src_id` hits.
3. **V1.1** — consider returning `document_filename` alongside
   `document_id` so citations don't require a second DB hop. Held off
   in V1 because the agent runtime hasn't been written yet and the
   citation surface is undecided.

## Known Issues / Blockers

- **Score sign trap.** pgvector returns DISTANCE (lower = closer). The
  `<=>` operator returns cosine distance ∈ [0, 2]. We invert to
  similarity ∈ [-1, 1] inside `_rag_search_impl` so callers don't have
  to think about it. If the API ever exposes raw distances, surface a
  separate field rather than overloading `score`.
- **No filter on document_id / user.** V1 is single-user and queries
  the entire corpus. When V1.1 introduces multi-user or per-task
  scoping, add an optional `document_ids: list[uuid.UUID] | None`
  parameter and a `WHERE document_id = ANY(:ids)` clause.
- **Tool docstring becomes part of the LangChain prompt.** Keep the
  `rag_search` docstring concise and accurate — the model will read it
  to decide when to call the tool.
