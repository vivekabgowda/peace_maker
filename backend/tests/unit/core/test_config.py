"""Regression tests for settings env parsing.

`docker compose` sets list-typed settings like ``BKN_CORS_ORIGINS`` as a plain
comma-separated string. pydantic-settings would JSON-decode list fields from env
*before* our validator runs, raising a SettingsError on a non-JSON string — which
crashed the backend container on first boot. These lock in that CSV, JSON-array,
and default forms all parse.
"""

from __future__ import annotations

import pytest
from app.core.config import Settings


def test_cors_origins_accepts_plain_string(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BKN_CORS_ORIGINS", "http://localhost:3000")
    assert Settings().cors_origins == ["http://localhost:3000"]


def test_cors_origins_accepts_csv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BKN_CORS_ORIGINS", "http://a.com, http://b.com")
    assert Settings().cors_origins == ["http://a.com", "http://b.com"]


def test_cors_origins_accepts_json_array(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BKN_CORS_ORIGINS", '["http://x.com","http://y.com"]')
    assert Settings().cors_origins == ["http://x.com", "http://y.com"]


def test_list_defaults_apply_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BKN_CORS_ORIGINS", raising=False)
    monkeypatch.delenv("BKN_MARKET_TIMEFRAMES", raising=False)
    settings = Settings()
    assert settings.cors_origins == ["http://localhost:3000"]
    assert settings.market_timeframes == ["1m", "5m", "15m", "1h", "1d"]


def test_market_timeframes_csv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BKN_MARKET_TIMEFRAMES", "1m,5m,1d")
    assert Settings().market_timeframes == ["1m", "5m", "1d"]
