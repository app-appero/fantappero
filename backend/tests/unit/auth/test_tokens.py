"""Unit tests for opaque token helpers."""

from __future__ import annotations

from auth.tokens import generate_opaque_token, hash_token


def test_generate_opaque_token_unique() -> None:
    first = generate_opaque_token()
    second = generate_opaque_token()
    assert first != second
    assert len(first) >= 32


def test_hash_token_deterministic() -> None:
    assert hash_token("abc") == hash_token("abc")
    assert hash_token("abc") != hash_token("def")
