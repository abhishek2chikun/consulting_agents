"""Back-compat shim: edges moved to app.agents._engine.edges in M9.1."""

from app.agents._engine.edges import (
    DEFAULT_MAX_STAGE_RETRIES,
    make_route_after_reviewer,
)

__all__ = ["DEFAULT_MAX_STAGE_RETRIES", "make_route_after_reviewer"]
