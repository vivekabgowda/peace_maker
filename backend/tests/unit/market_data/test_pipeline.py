"""End-to-end pipeline test (no DB): provider → candle builder → indicators.

Doubles as the historical-replay test — a batch of candles is replayed through
the indicator engine's pure compute function.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.modules.market_data.candle_builder import CandleBuilder, WorkingCandle
from app.modules.market_data.indicator_engine import compute_bundle
from app.modules.market_data.providers.simulated import SimulatedMarketProvider


async def test_stream_builds_candles() -> None:
    provider = SimulatedMarketProvider(seed=1, tick_interval=0.0)
    await provider.connect()
    await provider.subscribe(["NIFTY"])

    closed: list[WorkingCandle] = []
    builder = CandleBuilder(lambda _s, _tf, c: closed.append(c), timeframes=["1m"])

    ts = datetime(2026, 7, 20, 9, 15, tzinfo=UTC)
    count = 0
    async for quote in provider.stream():
        # Advance synthetic time by 20s per tick so 1m bars close.
        builder.add_quote(quote.symbol, float(quote.ltp), 100, ts)
        ts += timedelta(seconds=20)
        count += 1
        if count >= 12:  # ~4 minutes of ticks
            break
    builder.flush_all()
    assert len(closed) >= 3  # several 1m candles closed
    for bar in closed:
        assert bar.high >= bar.low


async def test_historical_replay_computes_indicators() -> None:
    provider = SimulatedMarketProvider()
    await provider.connect()
    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = start + timedelta(days=250)
    candles = await provider.fetch_historical_candles("RELIANCE", "1d", start, end)

    highs = [float(c.high) for c in candles]
    lows = [float(c.low) for c in candles]
    closes = [float(c.close) for c in candles]
    volumes = [int(c.volume) for c in candles]
    bundle = compute_bundle(highs, lows, closes, volumes)

    assert bundle["ema_9"] is not None
    assert bundle["ema_200"] is not None  # enough history for the slow EMA
    assert bundle["rsi_14"] is not None
    assert 0.0 <= bundle["rsi_14"] <= 100.0
    assert bundle["supertrend_dir"] in (1.0, -1.0)
