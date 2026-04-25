"""Typed state contract for consulting-pipeline LangGraph workflows (M5.4, generalized in M9.1)."""

from __future__ import annotations

from typing import NotRequired, TypedDict


class FramingBrief(TypedDict):
    objective: str
    target_market: str
    constraints: list[str]
    questionnaire_answers: dict[str, str]


class GateVerdict(TypedDict):
    verdict: str
    stage: str
    attempt: int
    gaps: list[str]
    target_agents: list[str]
    rationale: str


class EvidenceRef(TypedDict):
    src_id: str
    title: str
    url: NotRequired[str]


class RunState(TypedDict, total=False):
    run_id: str
    goal: str
    document_ids: list[str]
    framing: FramingBrief
    artifacts: dict[str, str]
    evidence: list[EvidenceRef]
    stage_attempts: dict[str, int]
    gate_verdicts: dict[str, GateVerdict]
    target_agents: list[str] | None
    cancelled: bool


__all__ = ["EvidenceRef", "FramingBrief", "GateVerdict", "RunState"]
