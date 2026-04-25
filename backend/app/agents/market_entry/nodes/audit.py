"""Back-compat shim: audit node moved to app.agents._engine.nodes.audit."""

from app.agents._engine.nodes.audit import AUDIT_PATH, build_audit_node

__all__ = ["AUDIT_PATH", "build_audit_node"]
