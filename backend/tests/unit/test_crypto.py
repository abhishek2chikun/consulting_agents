"""Unit tests for `app.core.crypto` (Fernet wrap/unwrap)."""

from __future__ import annotations

import pytest
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings


def _fresh_key() -> str:
    return Fernet.generate_key().decode()


def _set_key(monkeypatch: pytest.MonkeyPatch, key: str) -> None:
    """Set FERNET_KEY in env and bust the cached Settings instance."""
    monkeypatch.setenv("FERNET_KEY", key)
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _reset_settings_cache() -> None:
    """Ensure each test starts and ends with a clean Settings cache."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_wrap_then_unwrap_roundtrips(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.crypto import unwrap, wrap

    _set_key(monkeypatch, _fresh_key())

    plaintext = "hello"
    ciphertext = wrap(plaintext)

    assert ciphertext != plaintext
    assert isinstance(ciphertext, str)
    assert unwrap(ciphertext) == plaintext


def test_unwrap_with_wrong_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.crypto import unwrap, wrap

    key_a = _fresh_key()
    key_b = _fresh_key()
    assert key_a != key_b

    _set_key(monkeypatch, key_a)
    ciphertext = wrap("secret")

    _set_key(monkeypatch, key_b)
    with pytest.raises(InvalidToken):
        unwrap(ciphertext)


def test_wrap_returns_different_ciphertext_each_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.crypto import wrap

    _set_key(monkeypatch, _fresh_key())

    a = wrap("same-plaintext")
    b = wrap("same-plaintext")

    # Fernet uses a random IV per call, so identical plaintext must produce
    # distinct ciphertexts.
    assert a != b


def test_unwrap_with_empty_ciphertext_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.crypto import unwrap

    _set_key(monkeypatch, _fresh_key())

    with pytest.raises(InvalidToken):
        unwrap("")


def test_wrap_with_unconfigured_key_raises_value_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.crypto import wrap

    _set_key(monkeypatch, "")

    with pytest.raises(ValueError, match="FERNET_KEY"):
        wrap("anything")


def test_generate_key_returns_valid_fernet_key() -> None:
    from app.core.crypto import generate_key

    key = generate_key()
    assert isinstance(key, str)
    # Must be accepted by Fernet — constructor validates length/encoding.
    Fernet(key.encode())
