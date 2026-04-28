from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment / .env file."""

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        extra="ignore",
    )

    app_env: str = "development"
    database_url: str = "postgresql+asyncpg://consulting:consulting@localhost:5432/consulting"
    fernet_key: str = ""
    aws_region: str = "us-east-1"
    bedrock_api_key: str = ""
    claude_model: str = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
    llm_timeout_sec: int = 300
    llm_max_tokens: int = 16000
    bedrock_retry_max_attempts: int = 5
    bedrock_retry_initial_seconds: float = 1
    bedrock_retry_max_seconds: float = 30
    use_bedrock: bool = False
    embedding_dim: int = 1536
    # Filesystem destination for uploaded document binaries (M3.3).
    # Resolved relative to the process working directory (i.e. the repo
    # root when uvicorn is launched via the project Makefile). The
    # service ensures the directory exists before writing.
    upload_dir: Path = Path("data/uploads")

    # ---- V1.6: run lifecycle + worker fanout knobs ----
    # Hard cap on total wall-clock per run (seconds). Default: 120 minutes.
    run_timeout_seconds: int = 7200
    # How often the heartbeat task bumps `runs.heartbeat_at`.
    heartbeat_interval_seconds: int = 30
    # Runs whose `heartbeat_at` is older than this are considered stale and
    # eligible for reaping by the recovery sweeper.
    stale_run_threshold_seconds: int = 300
    # asyncio.Semaphore cap for intra-stage worker subagent fanout.
    worker_concurrency: int = 4
    # Max ReAct tool-call iterations per stage / worker.
    react_max_iterations: int = 6


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached Settings instance."""
    return Settings()
