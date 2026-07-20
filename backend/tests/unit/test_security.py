"""Unit tests for password hashing and JWT primitives (no I/O)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from app.core.config import get_settings
from app.core.security import (
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_password_hash_roundtrip() -> None:
    hashed = hash_password("s3cure-passw0rd")
    assert hashed != "s3cure-passw0rd"
    assert verify_password("s3cure-passw0rd", hashed) is True
    assert verify_password("wrong", hashed) is False


def test_password_hashes_are_salted_unique() -> None:
    assert hash_password("same") != hash_password("same")


def test_access_token_contains_expected_claims() -> None:
    token, jti, _ = create_access_token("user-123", extra_claims={"role": "user"})
    payload = decode_token(token, expected_type="access")
    assert payload["sub"] == "user-123"
    assert payload["type"] == "access"
    assert payload["role"] == "user"
    assert payload["jti"] == jti


def test_wrong_token_type_rejected() -> None:
    token, _, _ = create_refresh_token("user-123")
    with pytest.raises(TokenError):
        decode_token(token, expected_type="access")


def test_tampered_token_rejected() -> None:
    token, _, _ = create_access_token("user-123")
    with pytest.raises(TokenError):
        decode_token(token + "tamper", expected_type="access")


def test_expired_token_rejected() -> None:
    settings = get_settings()
    past = datetime.now(UTC) - timedelta(minutes=5)
    expired = jwt.encode(
        {"sub": "user-123", "type": "access", "jti": "x", "exp": int(past.timestamp())},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    with pytest.raises(TokenError):
        decode_token(expired, expected_type="access")
