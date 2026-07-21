"""Integration tests for the /broker endpoints (auth flow, status, backfill).

Uses FastAPI dependency overrides to inject fake Kite ports — no SDK, no network.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest
from app.core.database import async_session_factory
from app.main import create_app
from app.modules.broker.api import get_kite_http, get_market_provider
from app.modules.broker.provider import ZerodhaProvider
from app.modules.market_data.orm import Instrument
from app.modules.market_data.repository import MarketDataRepository

from tests.unit.broker.fakes import FakeKiteHttp, FakeKiteTicker, ticker_builder_for

pytestmark = pytest.mark.integration

_CREDS = {"email": "broker@example.com", "password": "s3cure-passw0rd"}


@pytest.fixture
async def broker_client() -> AsyncIterator[httpx.AsyncClient]:
    """An app whose Kite HTTP + market provider are fakes."""
    app = create_app()
    http = FakeKiteHttp()
    provider = ZerodhaProvider(
        http, ticker_builder_for(FakeKiteTicker()), api_key="FAKE", access_token="AT"
    )
    app.dependency_overrides[get_kite_http] = lambda: http
    app.dependency_overrides[get_market_provider] = lambda: provider
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


async def _auth(client: httpx.AsyncClient) -> dict[str, str]:
    resp = await client.post("/api/v1/auth/register", json=_CREDS)
    assert resp.status_code == 201, resp.text
    return {"Authorization": f"Bearer {resp.json()['tokens']['access_token']}"}


async def test_broker_endpoints_require_auth(broker_client: httpx.AsyncClient) -> None:
    for path in ["/api/v1/broker/status", "/api/v1/broker/zerodha/login-url"]:
        resp = await broker_client.get(path)
        assert resp.status_code == 401


async def test_providers_lists_zerodha_and_paper(broker_client: httpx.AsyncClient) -> None:
    headers = await _auth(broker_client)
    resp = await broker_client.get("/api/v1/broker/providers", headers=headers)
    assert resp.status_code == 200
    providers = resp.json()["providers"]
    assert {"zerodha", "paper", "simulated"} <= set(providers)


async def test_login_url_and_full_oauth_flow(broker_client: httpx.AsyncClient) -> None:
    headers = await _auth(broker_client)

    url = await broker_client.get("/api/v1/broker/zerodha/login-url", headers=headers)
    assert url.status_code == 200
    assert url.json()["login_url"].startswith("https://kite.zerodha.com/connect/login")

    # Before login: no token.
    before = await broker_client.get("/api/v1/broker/status", headers=headers)
    assert before.json()["token_present"] is False

    # Complete the OAuth callback (Kite would redirect here with request_token).
    cb = await broker_client.get(
        "/api/v1/broker/zerodha/callback?request_token=REQ99", headers=headers
    )
    assert cb.status_code == 200, cb.text
    assert cb.json()["kite_user_id"] == "AB1234"
    assert cb.json()["valid"] is True

    # After login: a valid token is present (and stored encrypted).
    after = await broker_client.get("/api/v1/broker/status", headers=headers)
    body = after.json()
    assert body["token_present"] is True and body["token_valid"] is True


async def test_historical_backfill_persists_candles(broker_client: httpx.AsyncClient) -> None:
    headers = await _auth(broker_client)
    async with async_session_factory() as session:
        session.add(Instrument(symbol="TCS", exchange="NSE", instrument_type="EQ", sector="IT"))
        await session.commit()

    resp = await broker_client.post(
        "/api/v1/broker/historical/backfill"
        "?symbol=TCS&timeframe=1d&start=2025-01-01T00:00:00Z&end=2025-01-05T00:00:00Z",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["candles"] >= 1

    async with async_session_factory() as session:
        iid = await MarketDataRepository(session).get_instrument_id("TCS")
        assert iid is not None
        candles = await MarketDataRepository(session).recent_candles(iid, "1d", 10)
        assert len(candles) >= 1
