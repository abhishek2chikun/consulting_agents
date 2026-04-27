# Consulting Research Agent — Backend

FastAPI backend for the Consulting Research Agent. Async SQLAlchemy + PostgreSQL + pgvector, Pydantic v2, LangGraph, Docling.

## Requirements

| Tool | Version | Notes |
|------|---------|-------|
| Python | ≥ 3.12 | |
| [uv](https://docs.astral.sh/uv/) | latest | package manager (`pip install uv`) |
| Docker Desktop | latest | runs Postgres + pgvector |

---

## Quick start (full stack)

From the **repo root**, one command boots Postgres, the backend, and the frontend together:

```bash
make dev
```

This runs:
1. `make db-up` — starts Postgres 16 + pgvector in Docker on port `5432`
2. `uvicorn app.main:app --reload --port 8000`
3. `pnpm dev` (frontend on port `3000`)

Press `Ctrl+C` to stop everything.

---

## Backend-only setup

### 1. Environment

```bash
cd backend
cp .env.example .env
```

Edit `.env`:

```env
APP_ENV=development

# Postgres (matches the Docker Compose defaults)
DATABASE_URL=postgresql+asyncpg://consulting:consulting@localhost:5432/consulting

# Fernet key for encrypting provider API keys at rest.
# Generate one with:
#   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
FERNET_KEY=<your-generated-key>
```

### 2. Install dependencies

```bash
cd backend
uv sync --dev
```

### 3. Start Postgres

```bash
# from repo root
make db-up
```

Postgres 16 + pgvector starts in the background on `localhost:5432`.  
Credentials: `consulting / consulting`, database: `consulting`.

### 4. Run migrations

```bash
# from repo root
make migrate

# or directly from backend/
cd backend && uv run alembic upgrade head
```

### 5. Start the API server

```bash
cd backend
uv run uvicorn app.main:app --reload --port 8000
```

The API is now available at **http://localhost:8000**.

---

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Liveness check |
| `GET` | `/health/search?q=...` | Test active search provider |
| `POST` | `/ping` | Smoke-test an LLM provider |
| `GET` | `/tasks` | List consulting task types |
| `GET` | `/settings` | Full settings snapshot |
| `GET` | `/settings/providers` | Provider key status (`has_key` flags) |
| `PUT` | `/settings/providers/{provider}` | Set a provider API key |
| `PUT` | `/settings/model_overrides` | Set per-role model overrides |
| `PUT` | `/settings/search_provider` | Set active search provider |
| `PUT` | `/settings/max_stage_retries` | Set max retries (1–5) |
| `POST` | `/documents` | Upload a context document (multipart) |
| `GET` | `/documents` | List uploaded documents |
| `DELETE` | `/documents/{id}` | Delete a document |
| `POST` | `/runs` | Create a new agent run |
| `GET` | `/runs/{id}` | Get run status and artifact paths |
| `GET` | `/runs/{id}/stream` | SSE stream of live run events |
| `POST` | `/runs/{id}/answers` | Submit framing questionnaire answers |
| `POST` | `/runs/{id}/cancel` | Cancel a running run |
| `GET` | `/runs/{id}/artifacts/{path}` | Fetch a run artifact |
| `GET` | `/runs/{id}/evidence` | List cited evidence items |

Interactive docs: **http://localhost:8000/docs** (Swagger UI) or `/redoc`.

---

## Provider API keys

Keys are stored **encrypted** (Fernet) in Postgres and never exposed in API responses.
Set them via the Settings UI at `http://localhost:3000/settings` or directly:

```bash
# Anthropic
curl -X PUT http://localhost:8000/settings/providers/anthropic \
  -H "Content-Type: application/json" \
  -d '{"key": "sk-ant-..."}'

# OpenAI (needed for document embeddings)
curl -X PUT http://localhost:8000/settings/providers/openai \
  -H "Content-Type: application/json" \
  -d '{"key": "sk-..."}'

# Search providers: tavily | exa | perplexity
curl -X PUT http://localhost:8000/settings/providers/tavily \
  -H "Content-Type: application/json" \
  -d '{"key": "tvly-..."}'

# Set active search provider
curl -X PUT http://localhost:8000/settings/search_provider \
  -H "Content-Type: application/json" \
  -d '{"provider": "tavily"}'
```

---

## Makefile targets

Run from the **repo root**:

```bash
make db-up             # Start Postgres + pgvector
make db-down           # Stop and remove the container (data volume persists)
make db-logs           # Tail Postgres logs
make db-shell          # Open a psql shell
make migrate           # Apply Alembic migrations (alembic upgrade head)
make migrate-rev m="message"  # Autogenerate a new migration
make dev               # Start full stack (db + backend + frontend)
make check             # Lint + typecheck + fast tests
make check-integration # Integration tests (requires make db-up)
make precommit-install # Install pre-commit git hook
```

---

## Testing

```bash
cd backend

# Fast unit tests (no Postgres, no network)
uv run pytest tests/unit -v

# All tests including integration (requires make db-up)
uv run pytest -v

# Skip slow tests (first-run Docling model downloads)
uv run pytest -m "not slow" -v
```

---

## Lint & type checking

```bash
cd backend
uv run ruff check .           # lint
uv run ruff format --check .  # format check
uv run mypy app               # strict type checking
```

Or use the root gate: `make check`

---

## Database management

```bash
# Apply all pending migrations
make migrate

# Create a new auto-generated migration
make migrate-rev m="add_run_table"

# Connect to Postgres directly
make db-shell
```

Migrations live in `backend/alembic/versions/`. The current schema includes:  
`users` → `settings_kv` → `provider_keys` → `task_types` → `documents` → `chunks`
