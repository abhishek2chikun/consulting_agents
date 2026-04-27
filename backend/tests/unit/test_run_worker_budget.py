"""Unit tests for the BudgetTracker wiring helper (M7.1)."""

from __future__ import annotations

import uuid

from langchain_core.callbacks import BaseCallbackHandler

from app.agents.budget import BudgetTracker
from app.testing.fake_chat_model import FakeChatModel
from app.workers.run_worker import _attach_budget_tracker, _exception_reason


def _extract_callbacks(bound: object) -> list[BaseCallbackHandler]:
    """Pull the callback list out of a RunnableBinding's config."""
    config = getattr(bound, "config", {})
    callbacks = config.get("callbacks") or []
    # Some LangChain versions wrap it in a CallbackManager; flatten if so.
    if hasattr(callbacks, "handlers"):
        return list(callbacks.handlers)
    return list(callbacks)


def test_attach_budget_tracker_returns_binding_with_tracker() -> None:
    model = FakeChatModel()
    run_id = uuid.uuid4()

    bound = _attach_budget_tracker(model, run_id=run_id, provider="anthropic")

    handlers = _extract_callbacks(bound)
    trackers = [h for h in handlers if isinstance(h, BudgetTracker)]
    assert len(trackers) == 1
    # The binding still exposes with_structured_output (used by stage nodes).
    assert hasattr(bound, "with_structured_output")


def test_attach_budget_tracker_uses_run_id() -> None:
    """Two runs get distinct tracker instances bound to their own run_id."""
    a, b = uuid.uuid4(), uuid.uuid4()
    bound_a = _attach_budget_tracker(FakeChatModel(), run_id=a, provider="anthropic")
    bound_b = _attach_budget_tracker(FakeChatModel(), run_id=b, provider="openai")

    tracker_a = next(h for h in _extract_callbacks(bound_a) if isinstance(h, BudgetTracker))
    tracker_b = next(h for h in _extract_callbacks(bound_b) if isinstance(h, BudgetTracker))
    assert tracker_a._run_id == a
    assert tracker_b._run_id == b
    assert tracker_a._provider == "anthropic"
    assert tracker_b._provider == "openai"


def test_exception_reason_includes_type_for_empty_exception_message() -> None:
    reason = _exception_reason(TimeoutError())

    assert reason == "TimeoutError()"


def test_exception_reason_preserves_cause_when_message_is_empty() -> None:
    try:
        try:
            raise RuntimeError("provider read timed out")
        except RuntimeError as exc:
            raise TimeoutError() from exc
    except TimeoutError as exc:
        reason = _exception_reason(exc)

    assert reason == "TimeoutError: caused by RuntimeError: provider read timed out"
