from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.ping import router as ping_router
from app.api.settings import router as settings_router
from app.core.config import get_settings

# V1 is single-user local dev: the Next.js frontend runs on
# `http://localhost:3000` and talks to this API on
# `http://localhost:8000`. CORS is intentionally narrow — no wildcard,
# no credentials, no other origins. When V1.1 introduces auth or remote
# deployment, this list moves into `Settings` so it can be configured
# per-environment without code changes.
ALLOWED_ORIGINS: tuple[str, ...] = (
    "http://localhost:3000",
    "http://127.0.0.1:3000",
)


def create_app() -> FastAPI:
    """Build and return the FastAPI application instance."""
    settings = get_settings()
    app = FastAPI(title="Consulting Research Agent")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(ALLOWED_ORIGINS),
        allow_credentials=False,
        allow_methods=["GET", "PUT", "POST", "OPTIONS"],
        allow_headers=["Content-Type"],
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "env": settings.app_env}

    app.include_router(settings_router)
    app.include_router(ping_router)

    return app


app = create_app()
