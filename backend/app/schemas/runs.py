"""Pydantic DTOs for run lifecycle APIs (M5.5)."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


class CreateRunRequest(BaseModel):
    task_type: str = Field(min_length=1)
    goal: str = Field(min_length=1)
    document_ids: list[str] = Field(default_factory=list)


class CreateRunResponse(BaseModel):
    run_id: uuid.UUID


class SubmitAnswersRequest(BaseModel):
    answers: dict[str, str]


class RunInfoResponse(BaseModel):
    run_id: uuid.UUID
    task_type: str
    goal: str
    status: str
    artifact_paths: list[str]


class ArtifactContentResponse(BaseModel):
    path: str
    kind: str
    content: str


__all__ = [
    "ArtifactContentResponse",
    "CreateRunRequest",
    "CreateRunResponse",
    "RunInfoResponse",
    "SubmitAnswersRequest",
]
