"""Pydantic DTOs for run lifecycle APIs (M5.5)."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field


class StrictRequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateRunRequest(StrictRequestModel):
    task_type: str = Field(min_length=1)
    goal: str = Field(min_length=1)
    document_ids: list[str] = Field(default_factory=list)


class CreateRunResponse(BaseModel):
    run_id: uuid.UUID


class SubmitAnswersRequest(StrictRequestModel):
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


class EvidenceItem(BaseModel):
    """One row of `Run.evidence`, suitable for the SourcesSidebar."""

    src_id: str
    kind: str
    url: str | None
    title: str
    snippet: str
    provider: str


class EvidenceListResponse(BaseModel):
    evidence: list[EvidenceItem]


__all__ = [
    "ArtifactContentResponse",
    "CreateRunRequest",
    "CreateRunResponse",
    "EvidenceItem",
    "EvidenceListResponse",
    "RunInfoResponse",
    "SubmitAnswersRequest",
]
