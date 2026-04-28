"""Unit tests for V1.6 Settings additions (run lifecycle + worker config)."""

from __future__ import annotations

import pytest

from app.core.config import Settings

V16_ENV_VARS = (
    "RUN_TIMEOUT_SECONDS",
    "HEARTBEAT_INTERVAL_SECONDS",
    "STALE_RUN_THRESHOLD_SECONDS",
    "WORKER_CONCURRENCY",
    "REACT_MAX_ITERATIONS",
    "BEDROCK_RETRY_MAX_ATTEMPTS",
    "BEDROCK_RETRY_INITIAL_SECONDS",
    "BEDROCK_RETRY_MAX_SECONDS",
)


def test_v16_settings_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """The 5 new V1.6 fields should have the documented defaults."""
    for env_var in V16_ENV_VARS:
        monkeypatch.delenv(env_var, raising=False)

    settings = Settings(_env_file=None)
    assert settings.run_timeout_seconds == 7200
    assert settings.heartbeat_interval_seconds == 30
    assert settings.stale_run_threshold_seconds == 300
    assert settings.worker_concurrency == 4
    assert settings.react_max_iterations == 6
    assert settings.bedrock_retry_max_attempts == 5
    assert settings.bedrock_retry_initial_seconds == 1
    assert settings.bedrock_retry_max_seconds == 30


def test_v16_settings_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each new V1.6 field should be overridable via its uppercase env var."""
    monkeypatch.setenv("RUN_TIMEOUT_SECONDS", "10")
    monkeypatch.setenv("HEARTBEAT_INTERVAL_SECONDS", "11")
    monkeypatch.setenv("STALE_RUN_THRESHOLD_SECONDS", "12")
    monkeypatch.setenv("WORKER_CONCURRENCY", "13")
    monkeypatch.setenv("REACT_MAX_ITERATIONS", "14")
    monkeypatch.setenv("BEDROCK_RETRY_MAX_ATTEMPTS", "15")
    monkeypatch.setenv("BEDROCK_RETRY_INITIAL_SECONDS", "0.25")
    monkeypatch.setenv("BEDROCK_RETRY_MAX_SECONDS", "16")

    settings = Settings()
    assert settings.run_timeout_seconds == 10
    assert settings.heartbeat_interval_seconds == 11
    assert settings.stale_run_threshold_seconds == 12
    assert settings.worker_concurrency == 13
    assert settings.react_max_iterations == 14
    assert settings.bedrock_retry_max_attempts == 15
    assert settings.bedrock_retry_initial_seconds == 0.25
    assert settings.bedrock_retry_max_seconds == 16
