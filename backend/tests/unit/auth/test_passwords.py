"""Unit tests for password hashing."""

from __future__ import annotations

from auth.passwords import hash_password, verify_password


def test_hash_and_verify_roundtrip() -> None:
    digest = hash_password("Secret123")
    assert digest != "Secret123"
    assert verify_password("Secret123", digest)
    assert not verify_password("WrongPass1", digest)
