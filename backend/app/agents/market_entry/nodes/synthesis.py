"""Back-compat shim: synthesis node moved to app.agents._engine.nodes.synthesis."""

from app.agents._engine.nodes.synthesis import (
    CITATION_RE,
    REPORT_PATH,
    CitationError,
    build_synthesis_node,
)

__all__ = ["CITATION_RE", "CitationError", "REPORT_PATH", "build_synthesis_node"]
