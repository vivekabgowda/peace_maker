"""Tests for production safety guards (JWT default secret)."""

from __future__ import annotations

import pytest
from app.core.config import Settings
from pydantic import ValidationError


def test_prod_rejects_default_jwt_secret() -> None:
    with pytest.raises(ValidationError):
        Settings(env="production", jwt_secret_key="change-me-in-production-this-is-not-a-secret")


def test_prod_accepts_strong_secret() -> None:
    s = Settings(env="production", jwt_secret_key="a-strong-64-hex-secret-value-1234567890abcdef")
    assert s.is_production


def test_local_allows_default_secret() -> None:
    # Developer convenience: the default is fine outside staging/production.
    s = Settings(env="local")
    assert not s.is_production
