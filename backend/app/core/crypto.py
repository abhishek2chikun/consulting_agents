"""Fernet wrap/unwrap helpers for at-rest secret encryption.

Public API:
    wrap(plaintext: str) -> str       # encrypt with settings.fernet_key
    unwrap(ciphertext: str) -> str    # decrypt; raises InvalidToken on failure
    generate_key() -> str             # convenience for dev/scripts

Design notes:
- The key is read fresh from `Settings` on each call. Fernet construction is
  microsecond-cheap, and avoiding caching sidesteps a class of test footguns
  where a stale cached cipher outlives `monkeypatch.setenv` + `cache_clear()`.
- Strings in, strings out. Encoding/decoding to UTF-8 happens at the boundary;
  Fernet itself works in bytes.
- `cryptography.fernet.InvalidToken` is allowed to propagate from `unwrap()`.
  It is already a clear, typed exception; wrapping it would only add noise.
"""

from __future__ import annotations

from cryptography.fernet import Fernet

from app.core.config import get_settings

__all__ = ["wrap", "unwrap", "generate_key"]


def _cipher() -> Fernet:
    key = get_settings().fernet_key
    if not key:
        raise ValueError("FERNET_KEY not configured")
    return Fernet(key.encode("utf-8"))


def wrap(plaintext: str) -> str:
    """Encrypt `plaintext` with the configured Fernet key.

    Raises:
        ValueError: if `settings.fernet_key` is empty / unset.
    """
    token = _cipher().encrypt(plaintext.encode("utf-8"))
    return token.decode("utf-8")


def unwrap(ciphertext: str) -> str:
    """Decrypt `ciphertext` with the configured Fernet key.

    Raises:
        ValueError: if `settings.fernet_key` is empty / unset.
        cryptography.fernet.InvalidToken: if the token is malformed, was
            produced with a different key, or has been tampered with.
    """
    plaintext = _cipher().decrypt(ciphertext.encode("utf-8"))
    return plaintext.decode("utf-8")


def generate_key() -> str:
    """Return a fresh base64 Fernet key suitable for `FERNET_KEY`."""
    return Fernet.generate_key().decode("utf-8")
