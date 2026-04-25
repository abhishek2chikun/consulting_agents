"""Back-compat shim: framing node moved to app.agents._engine.nodes.framing."""

from app.agents._engine.nodes.framing import QUESTIONNAIRE_PATH, build_framing_node

__all__ = ["QUESTIONNAIRE_PATH", "build_framing_node"]
