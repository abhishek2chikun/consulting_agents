"""M9.2: API dispatch consults PROFILE_REGISTRY."""

from __future__ import annotations

import pytest
from fastapi import HTTPException, status

from app.agents._engine.registry import PROFILE_REGISTRY
from app.api.runs import _profile_for_task_type


def test_market_entry_in_registry() -> None:
    assert "market_entry" in PROFILE_REGISTRY


def test_ma_dispatch_has_no_consulting_profile() -> None:
    assert _profile_for_task_type("ma") is None


def test_unknown_non_ma_task_type_is_rejected_before_worker_dispatch() -> None:
    with pytest.raises(HTTPException) as exc_info:
        _profile_for_task_type("unknown")

    assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
    assert exc_info.value.detail == "unknown task_type: unknown"
