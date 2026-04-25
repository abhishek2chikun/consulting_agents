"""Back-compat shim: reviewer node moved to app.agents._engine.nodes.reviewer."""

from app.agents._engine.nodes.reviewer import make_reviewer_node

__all__ = ["make_reviewer_node"]
