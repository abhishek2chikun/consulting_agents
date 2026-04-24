"""`/ping` endpoint (M2.6).

Smoke-test surface that exercises the full chat-model resolution path
(`SettingsService` -> `model_overrides` -> `PROVIDER_REGISTRY` -> live
LangChain client) without committing to a full agent run. Useful both
as a frontend "is my key configured?" probe and as an operator-level
diagnostic.

Error mapping rationale:

- ``ValueError`` from ``get_chat_model`` covers two user-actionable
  cases ("no key configured", "unknown provider"). Both surface as
  ``400`` so the client knows the fix is in settings, not on the
  server.
- ``NotImplementedError`` is currently only raised by the AWS Bedrock
  factory (deferred to V1.1). ``501 Not Implemented`` matches the HTTP
  semantics exactly — the route exists, the dependency does not.
- Any other exception (network errors from the provider SDK, etc.)
  falls through to FastAPI's default ``500`` handler. We deliberately
  do NOT catch them here so they remain visible in logs.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from langchain_core.messages import HumanMessage
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.llm import get_chat_model, provider_name_for
from app.core.db import get_session
from app.schemas.ping import PingRequest, PingResponse

router = APIRouter(prefix="/ping", tags=["ping"])


SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.post("", response_model=PingResponse)
async def ping(body: PingRequest, session: SessionDep) -> PingResponse:
    try:
        chat_model = await get_chat_model(body.role, session=session)
    except ValueError as exc:
        # Missing key / unknown provider — caller-actionable, not server fault.
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except NotImplementedError as exc:
        # Provider registered but factory not yet implemented (AWS Bedrock).
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(exc)) from exc

    # `.model` is what the LangChain integrations we care about expose;
    # `.model_name` is the older/alt name (e.g. on legacy ChatOpenAI builds).
    # Defensive lookup keeps the endpoint working across minor SDK churn.
    model_label = getattr(chat_model, "model", None) or getattr(chat_model, "model_name", "unknown")

    result = await chat_model.ainvoke([HumanMessage(content=body.prompt)])

    # `AIMessage.content` is typed as `str | list[ContentBlock]` for
    # multimodal responses. The /ping contract is plain text; coerce
    # any non-string payload via `str()` so the response schema holds.
    raw_content = result.content
    response_text = raw_content if isinstance(raw_content, str) else str(raw_content)

    return PingResponse(
        response=response_text,
        model=str(model_label),
        provider=provider_name_for(chat_model),
    )


__all__ = ["router"]
