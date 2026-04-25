"""Framing-stage Pydantic schemas (M6.2).

Used by the framing node's `with_structured_output` call, and as the
declared shape of the `framing/questionnaire.json` artifact rendered in
the frontend questionnaire form.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class QuestionItem(BaseModel):
    id: str = Field(..., description="snake_case identifier")
    label: str
    type: Literal["text", "select", "multiselect"] = "text"
    options: list[str] = Field(default_factory=list)
    helper: str | None = None
    required: bool = True


class Questionnaire(BaseModel):
    items: list[QuestionItem]


class FramingBriefModel(BaseModel):
    objective: str
    target_market: str
    constraints: list[str] = Field(default_factory=list)
    questionnaire_answers: dict[str, str] = Field(default_factory=dict)


class FramingResponse(BaseModel):
    """Top-level structured response from the framing model call."""

    brief: FramingBriefModel
    questionnaire: Questionnaire


__all__ = [
    "FramingBriefModel",
    "FramingResponse",
    "QuestionItem",
    "Questionnaire",
]
