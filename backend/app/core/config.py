from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment / .env file."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    database_url: str = "postgresql+asyncpg://consulting:consulting@localhost:5432/consulting"
    fernet_key: str = ""
    embedding_dim: int = 1536
    # Filesystem destination for uploaded document binaries (M3.3).
    # Resolved relative to the process working directory (i.e. the repo
    # root when uvicorn is launched via the project Makefile). The
    # service ensures the directory exists before writing.
    upload_dir: Path = Path("data/uploads")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached Settings instance."""
    return Settings()
