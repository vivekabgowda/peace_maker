"""Tests for news normalization and the simulated market provider."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.modules.market_data.providers.simulated import SimulatedMarketProvider
from app.modules.news.normalize import content_id, normalize


def test_sentiment_positive_vs_negative() -> None:
    pos = normalize("Company posts strong results, beats estimates", None, "test")
    neg = normalize("Company shares fall after downgrade on concerns", None, "test")
    assert pos.sentiment > 0
    assert neg.sentiment < 0


def test_category_detection() -> None:
    assert normalize("Q2 results beat estimates", None, "s").category == "earnings"
    assert normalize("RBI keeps repo rate unchanged", None, "s").category == "policy"


def test_symbol_and_sector_mapping() -> None:
    art = normalize("RELIANCE announces record dividend", None, "s")
    assert "RELIANCE" in art.symbols
    assert "Energy" in art.sectors


def test_dedup_id_stable_and_normalized() -> None:
    a = content_id("Nifty hits  new   high", "src")
    b = content_id("nifty hits new high", "src")
    assert a == b  # whitespace + case normalized


def test_impact_score_bounded() -> None:
    art = normalize("RBI probe on results triggers downgrade", None, "s")
    assert 0.0 <= art.impact <= 1.0
    assert art.impact > 0.3  # multiple high-impact keywords


async def test_simulated_provider_stream_and_chain() -> None:
    provider = SimulatedMarketProvider(seed=7, tick_interval=0.0)
    await provider.connect()
    assert provider.is_connected

    instruments = await provider.fetch_instruments()
    assert any(i.symbol == "NIFTY" for i in instruments)

    await provider.subscribe(["NIFTY", "RELIANCE"])
    quotes = []
    async for quote in provider.stream():
        quotes.append(quote)
        if len(quotes) >= 4:
            break
    assert {q.symbol for q in quotes} <= {"NIFTY", "RELIANCE"}
    assert all(q.ltp > 0 for q in quotes)
    assert all(q.upper_circuit is not None for q in quotes)

    chain = await provider.fetch_option_chain("NIFTY", "2026-07-31")
    assert chain.underlying == "NIFTY"
    assert len(chain.quotes) == 22  # 11 strikes x CE/PE
    assert {q.option_type for q in chain.quotes} == {"CE", "PE"}

    await provider.disconnect()
    assert not provider.is_connected


async def test_simulated_historical_candles() -> None:
    provider = SimulatedMarketProvider()
    await provider.connect()
    start = datetime(2026, 7, 1, tzinfo=UTC)
    end = start + timedelta(hours=2)
    candles = await provider.fetch_historical_candles("RELIANCE", "5m", start, end)
    assert len(candles) == 24  # 2h / 5m
    for c in candles:
        assert c.high >= c.low
        assert c.low <= c.open <= c.high
