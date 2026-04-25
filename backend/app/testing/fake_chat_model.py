"""Deterministic FakeChatModel for tests.

Supports two interaction modes used by V1 nodes:

1. ``invoke([HumanMessage(...)])`` — returns a scripted ``AIMessage``
   from the ``responses`` queue.
2. ``with_structured_output(schema).invoke(...)`` — returns the next
   pre-staged structured payload (a dict or pydantic model) from the
   ``structured_responses`` queue. The returned value is parsed into
   ``schema`` if it's a Pydantic model class.

Tool-calling support is intentionally minimal: each scripted response
may include ``tool_calls`` to be returned on the AIMessage; callers can
script a sequence of tool calls followed by a final text response.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable, Sequence
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import Runnable
from pydantic import BaseModel


class _StructuredRunnable(Runnable[Any, Any]):
    """Runnable returned by ``FakeChatModel.with_structured_output``."""

    def __init__(self, parent: FakeChatModel, schema: type[Any] | None) -> None:
        self._parent = parent
        self._schema = schema

    def invoke(self, input: Any, config: Any = None, **_: Any) -> Any:  # noqa: A002
        if not self._parent.structured_responses:
            raise AssertionError("FakeChatModel: no scripted structured response left")
        payload = self._parent.structured_responses.popleft()
        self._parent.structured_calls.append((self._schema, input))
        if isinstance(self._schema, type) and issubclass(self._schema, BaseModel):
            if isinstance(payload, BaseModel):
                return payload
            return self._schema.model_validate(payload)
        return payload

    async def ainvoke(self, input: Any, config: Any = None, **kwargs: Any) -> Any:  # noqa: A002
        return self.invoke(input, config, **kwargs)


class FakeChatModel(BaseChatModel):
    """Scripted chat model for tests.

    Construct with ``responses`` (an iterable of strings or
    ``AIMessage`` instances) and/or ``structured_responses`` (an
    iterable of dicts or pydantic models). Each ``invoke``/``ainvoke``
    call pops the next scripted item.
    """

    responses: deque[str | AIMessage] = deque()
    structured_responses: deque[Any] = deque()
    calls: list[Sequence[BaseMessage]] = []
    structured_calls: list[tuple[Any, Any]] = []

    model_config = {"arbitrary_types_allowed": True}

    def __init__(
        self,
        *,
        responses: Iterable[str | AIMessage] | None = None,
        structured_responses: Iterable[Any] | None = None,
    ) -> None:
        super().__init__()
        # Pydantic v2: assign via __dict__ to bypass field strict typing.
        object.__setattr__(self, "responses", deque(responses or ()))
        object.__setattr__(self, "structured_responses", deque(structured_responses or ()))
        object.__setattr__(self, "calls", [])
        object.__setattr__(self, "structured_calls", [])

    @property
    def _llm_type(self) -> str:
        return "fake-chat-model"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        self.calls.append(messages)
        if not self.responses:
            raise AssertionError("FakeChatModel: no scripted response left")
        nxt = self.responses.popleft()
        if isinstance(nxt, str):
            ai = AIMessage(content=nxt)
        else:
            ai = nxt
        return ChatResult(generations=[ChatGeneration(message=ai)])

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        return self._generate(messages, stop, run_manager, **kwargs)

    def with_structured_output(  # type: ignore[override]
        self,
        schema: type[Any] | None = None,
        **_: Any,
    ) -> Runnable[Any, Any]:
        return _StructuredRunnable(self, schema)


__all__ = ["FakeChatModel"]
