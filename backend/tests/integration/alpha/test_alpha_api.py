"""Integration tests for the read-only /alpha endpoints."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import httpx
import pytest
from app.core.database import async_session_factory
from app.modules.market_data.orm import Instrument
from app.modules.market_data.repository import MarketDataRepository

pytestmark = pytest.mark.integration

_CREDS = {"email": "alpha@example.com", "password": "s3cure-passw0rd"}


async def _auth(client: httpx.AsyncClient) -> dict[str, str]:
    resp = await client.post("/api/v1/auth/register", json=_CREDS)
    assert resp.status_code == 201, resp.text
    return {"Authorization": f"Bearer {resp.json()['tokens']['access_token']}"}


async def _seed_universe() -> None:
    """A trending NIFTY benchmark + one trending equity with daily candles."""
    base = datetime(2026, 3, 2, tzinfo=UTC)
    async with async_session_factory() as session:
        session.add(Instrument(symbol="NIFTY", exchange="NSE", instrument_type="INDEX"))
        session.add(
            Instrument(
                symbol="TCS", exchange="NSE", instrument_type="EQ", sector="IT", in_nifty500=True
            )
        )
        await session.flush()
        repo = MarketDataRepository(session)
        ids = await repo.symbol_id_map()
        for sym, start in (("NIFTY", 20000.0), ("TCS", 3000.0)):
            iid = ids[sym]
            for i in range(60):
                px = start * (1 + i * 0.004)  # steady uptrend
                await repo.upsert_candle(
                    iid,
                    "1d",
                    base + timedelta(days=i),
                    Decimal(str(round(px * 0.999, 2))),
                    Decimal(str(round(px * 1.006, 2))),
                    Decimal(str(round(px * 0.994, 2))),
                    Decimal(str(round(px, 2))),
                    1_000_000,
                )
        await session.commit()


async def test_alpha_endpoints_require_auth(client: httpx.AsyncClient) -> None:
    for path in ["/api/v1/alpha/regime", "/api/v1/alpha/strategies", "/api/v1/alpha/opportunities"]:
        resp = await client.get(path)
        assert resp.status_code == 401


async def test_strategy_library_is_exposed(client: httpx.AsyncClient) -> None:
    headers = await _auth(client)
    resp = await client.get("/api/v1/alpha/strategies", headers=headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    keys = {s["key"] for s in data}
    assert {"orb", "ema_trend", "vcp", "relative_strength"} <= keys
    sample = next(s for s in data if s["key"] == "ema_trend")
    assert "compatible_regimes" in sample and "stats" in sample


async def test_regime_and_opportunities_scan(client: httpx.AsyncClient) -> None:
    headers = await _auth(client)
    await _seed_universe()

    regime = await client.get("/api/v1/alpha/regime", headers=headers)
    assert regime.status_code == 200, regime.text
    body = regime.json()
    assert body["primary"] in {"trending_bull", "range", "accumulation"}
    assert "index_trend" in body

    scan = await client.get("/api/v1/alpha/opportunities?top=10", headers=headers)
    assert scan.status_code == 200, scan.text
    payload = scan.json()
    assert "regime" in payload and "top" in payload
    assert payload["universe_size"] >= 1
    # Whatever the verdict, the shape is well-formed and never a bare buy list.
    assert isinstance(payload["no_trade"], bool)
    for opp in payload["top"]:
        assert {"symbol", "direction", "entry", "stop", "explanation", "scores"} <= set(opp)
        assert opp["explanation"]["invalidation"]
