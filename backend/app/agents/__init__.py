"""Agent runtime package.

Re-exports the LLM provider registry and resolution helpers so callers
can write ``from app.agents import get_chat_model`` instead of reaching
into the ``app.agents.llm`` submodule directly. Mirrors the pattern used
by ``app.models``.
"""

from app.agents.llm import (
    DEFAULT_PROVIDER,
    LLM_PROVIDERS,
    PROVIDER_REGISTRY,
    get_chat_model,
    provider_name_for,
)

__all__ = [
    "DEFAULT_PROVIDER",
    "LLM_PROVIDERS",
    "PROVIDER_REGISTRY",
    "get_chat_model",
    "provider_name_for",
]
