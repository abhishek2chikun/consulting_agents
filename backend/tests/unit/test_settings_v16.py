"""Unit tests for V1.6 Settings additions (run lifecycle + worker config)."""

from __future__ import annotations

import pytest

from app.core.config import Settings


def test_v16_settings_defaults() -> None:
    """The 5 new V1.6 fields should have the documented defaults."""
    settings = Settings()
    assert settings.run_timeout_seconds == 7200
    assert settings.heartbeat_interval_seconds == 30
    assert settings.stale_run_threshold_seconds == 300
    assert settings.worker_concurrency == 4
    assert settings.react_max_iterations == 6


def test_v16_settings_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each new V1.6 field should be overridable via its uppercase env var."""
    monkeypatch.setenv("RUN_TIMEOUT_SECONDS", "10")
    monkeypatch.setenv("HEARTBEAT_INTERVAL_SECONDS", "11")
    monkeypatch.setenv("STALE_RUN_THRESHOLD_SECONDS", "12")
    monkeypatch.setenv("WORKER_CONCURRENCY", "13")
    monkeypatch.setenv("REACT_MAX_ITERATIONS", "14")

    settings = Settings()
    assert settings.run_timeout_seconds == 10
    assert settings.heartbeat_interval_seconds == 11
    assert settings.stale_run_threshold_seconds == 12
    assert settings.worker_concurrency == 13
    assert settings.react_max_iterations == 14
