"""Integration tests for the system diagnostics endpoint (Sprint 8)."""

from __future__ import annotations

import httpx
import pytest
from app.modules.market_data import cache

pytestmark = pytest.mark.integration


async def test_diagnostics_is_unauthenticated_and_healthy(client: httpx.AsyncClient) -> None:
    resp = await client.get("/api/v1/health/diagnostics")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "healthy"  # sqlite + fakeredis are up under test
    assert body["broker_connected"] is False  # no live broker, by design
    names = {s["name"] for s in body["services"]}
    assert {"database", "redis", "market_feed", "event_stream"} <= names


async def test_diagnostics_core_services_report_healthy(client: httpx.AsyncClient) -> None:
    body = (await client.get("/api/v1/health/diagnostics")).json()
    services = {s["name"]: s for s in body["services"]}
    assert services["database"]["healthy"] is True
    assert services["redis"]["healthy"] is True
    # Latency is measured for DB and Redis.
    assert services["database"]["latency_ms"] is not None
    assert services["redis"]["latency_ms"] is not None


async def test_diagnostics_reflects_live_mock_pipeline(client: httpx.AsyncClient) -> None:
    # Seed a fresh quote (as the simulated feed would) and confirm the pipeline
    # section + market_feed service pick it up.
    await cache.set_quote(
        "TCS",
        {
            "symbol": "TCS",
            "ltp": "3500.0",
            "volume": 100,
            "vwap": "3499",
            "bid": "3499",
            "ask": "3501",
        },
    )
    body = (await client.get("/api/v1/health/diagnostics")).json()
    feed = next(s for s in body["services"] if s["name"] == "market_feed")
    assert feed["healthy"] is True
    assert feed["meta"]["live_symbols"] >= 1
    assert body["pipeline"]["live_symbols"] >= 1
    assert body["pipeline"]["provider"] == body["market_provider"]
