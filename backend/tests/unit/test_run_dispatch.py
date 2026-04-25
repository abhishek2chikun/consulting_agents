"""M9.2: API dispatch consults PROFILE_REGISTRY."""

from __future__ import annotations

import importlib
import sys

import pytest
from fastapi import HTTPException, status

from app.agents._engine.registry import PROFILE_REGISTRY
from app.api import runs

_profile_for_task_type = runs._profile_for_task_type


def test_market_entry_in_registry() -> None:
    assert "market_entry" in PROFILE_REGISTRY


def test_agents_package_import_populates_market_entry_profile() -> None:
    original_registry = dict(PROFILE_REGISTRY)
    original_market_entry = sys.modules.pop("app.agents.market_entry", None)
    PROFILE_REGISTRY.clear()
    try:
        import app.agents

        importlib.reload(app.agents)

        assert "market_entry" in PROFILE_REGISTRY
    finally:
        PROFILE_REGISTRY.clear()
        PROFILE_REGISTRY.update(original_registry)
        if original_market_entry is not None:
            sys.modules["app.agents.market_entry"] = original_market_entry


def test_runs_module_import_populates_market_entry_profile() -> None:
    assert "market_entry" in PROFILE_REGISTRY
    assert runs._profile_for_task_type("market_entry") is PROFILE_REGISTRY["market_entry"]


def test_ma_dispatch_has_no_consulting_profile() -> None:
    assert _profile_for_task_type("ma") is None


def test_market_entry_resolves_to_registered_profile() -> None:
    assert _profile_for_task_type("market_entry") is PROFILE_REGISTRY["market_entry"]


def test_unknown_non_ma_task_type_is_rejected_before_worker_dispatch() -> None:
    with pytest.raises(HTTPException) as exc_info:
        _profile_for_task_type("unknown")

    assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
    assert exc_info.value.detail == "unknown task_type: unknown"
