"""Integration tests for the /backtest endpoint."""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import httpx
import pytest
from app.core.database import async_session_factory
from app.modules.market_data.orm import Instrument
from app.modules.market_data.repository import MarketDataRepository
from app.modules.strategy.base import StrategyStats
from app.modules.strategy.registry import registry

pytestmark = pytest.mark.integration

_CREDS = {"email": "backtest@example.com", "password": "s3cure-passw0rd"}


@pytest.fixture(autouse=True)
def _restore_stats():  # type: ignore[no-untyped-def]
    yield
    for strat in registry.all():
        strat.stats = StrategyStats()


async def _auth(client: httpx.AsyncClient) -> dict[str, str]:
    resp = await client.post("/api/v1/auth/register", json=_CREDS)
    assert resp.status_code == 201, resp.text
    return {"Authorization": f"Bearer {resp.json()['tokens']['access_token']}"}


async def _seed() -> None:
    base = datetime(2025, 1, 1, tzinfo=UTC)
    closes = [100.0]
    for i in range(320):
        closes.append(closes[-1] * (1 + 0.006 * math.sin(i / 9) + 0.004))
    async with async_session_factory() as session:
        session.add(Instrument(symbol="NIFTY", exchange="NSE", instrument_type="INDEX"))
        session.add(Instrument(symbol="TCS", exchange="NSE", instrument_type="EQ", sector="IT"))
        await session.flush()
        repo = MarketDataRepository(session)
        ids = await repo.symbol_id_map()
        for sym, scale in (("NIFTY", 200.0), ("TCS", 30.0)):
            iid = ids[sym]
            for i, c in enumerate(closes):
                px = c * scale
                await repo.upsert_candle(
                    iid,
                    "1d",
                    base + timedelta(days=i),
                    Decimal(str(round(px * 0.999, 2))),
                    Decimal(str(round(px * 1.01, 2))),
                    Decimal(str(round(px * 0.99, 2))),
                    Decimal(str(round(px, 2))),
                    1_000_000,
                )
        await session.commit()


async def test_backtest_requires_auth(client: httpx.AsyncClient) -> None:
    resp = await client.get("/api/v1/backtest/run")
    assert resp.status_code == 401


async def test_backtest_single_strategy_returns_metrics(client: httpx.AsyncClient) -> None:
    headers = await _auth(client)
    await _seed()
    resp = await client.get("/api/v1/backtest/run?strategy=ema_trend&history=340", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["results"]) == 1
    result = body["results"][0]
    assert result["strategy"] == "ema_trend"
    for key in (
        "trades",
        "win_rate",
        "profit_factor",
        "expectancy_r",
        "false_positive_rate",
        "is_proven",
    ):
        assert key in result


async def test_backtest_apply_stats_updates_registry(client: httpx.AsyncClient) -> None:
    headers = await _auth(client)
    await _seed()
    resp = await client.get(
        "/api/v1/backtest/run?strategy=ema_trend&history=340&apply_stats=true", headers=headers
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    result = body["results"][0]
    if result["trades"] > 0:
        assert "ema_trend" in body["stats_applied"]
        assert registry.get("ema_trend").stats.trades == result["trades"]
