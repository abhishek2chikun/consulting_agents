from fastapi import FastAPI

from app.core.config import get_settings


def create_app() -> FastAPI:
    """Build and return the FastAPI application instance."""
    settings = get_settings()
    app = FastAPI(title="Consulting Research Agent")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "env": settings.app_env}

    return app


app = create_app()
