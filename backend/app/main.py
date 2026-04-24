from fastapi import FastAPI

from app.api.ping import router as ping_router
from app.api.settings import router as settings_router
from app.core.config import get_settings


def create_app() -> FastAPI:
    """Build and return the FastAPI application instance."""
    settings = get_settings()
    app = FastAPI(title="Consulting Research Agent")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "env": settings.app_env}

    app.include_router(settings_router)
    app.include_router(ping_router)

    return app


app = create_app()
