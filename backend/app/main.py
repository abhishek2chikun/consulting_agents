from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.documents import router as documents_router
from app.api.health import router as health_router
from app.api.ping import router as ping_router
from app.api.runs import router as runs_router
from app.api.settings import router as settings_router
from app.api.tasks import router as tasks_router
from app.core.config import get_settings

# V1 is single-user local dev. We allow all localhost ports so that
# Next.js (which increments the port when 3000 is busy) and any other
# local tooling can reach the API without editing this file. In staging
# / production the list should be locked to the exact origin(s).
import re as _re


def _is_localhost_origin(origin: str) -> bool:
    """Return True for any http://localhost:* or http://127.0.0.1:* origin."""
    return bool(_re.match(r"^http://(localhost|127\.0\.0\.1)(:\d+)?$", origin))


def create_app() -> FastAPI:
    """Build and return the FastAPI application instance."""
    settings = get_settings()
    app = FastAPI(title="Consulting Research Agent")

    app.add_middleware(
        CORSMiddleware,
        # allow_origin_regex covers every localhost port so Next.js can run
        # on 3000, 3001, etc. without manual config changes.
        allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
        allow_credentials=False,
        allow_methods=["GET", "PUT", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type"],
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "env": settings.app_env}

    app.include_router(health_router)
    app.include_router(settings_router)
    app.include_router(ping_router)
    app.include_router(tasks_router)
    app.include_router(documents_router)
    app.include_router(runs_router)

    return app


app = create_app()
