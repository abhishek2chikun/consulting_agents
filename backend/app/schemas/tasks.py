"""Pydantic DTOs for the tasks catalog API (M3.1).

The endpoint returns a bare `list[TaskTypeInfo]` rather than wrapping
under a `{tasks: [...]}` envelope because the spec test asserts the
top-level shape is a list. Frontend consumers iterate directly.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class TaskTypeInfo(BaseModel):
    """One row of the task-type catalog as exposed over HTTP."""

    slug: str = Field(min_length=1)
    name: str
    description: str | None = None
    enabled: bool


__all__ = ["TaskTypeInfo"]
