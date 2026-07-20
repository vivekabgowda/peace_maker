"""Technical indicator engine.

``compute_bundle`` is a pure function over OHLCV series returning the latest
value of each indicator — trivially unit-testable. ``IndicatorEngine`` wires it
to the candle store, the hot cache, persistence, and the event bus (emitting
``IndicatorCalculated`` on every close).
"""

from __future__ import annotations

from decimal import Decimal

from app.core.logging import get_logger
from app.modules.market_data import cache
from app.modules.market_data.repository import MarketDataRepository
from app.shared.events import CandleClosed, IndicatorCalculated, event_bus
from app.shared.indicators import (
    adx,
    atr,
    bollinger,
    ema,
    macd,
    rsi,
    supertrend,
    vwap,
)

logger = get_logger("indicator_engine")


def _last(series: list[float | None]) -> float | None:
    for value in reversed(series):
        if value is not None:
            return value
    return None


def compute_bundle(
    highs: list[float], lows: list[float], closes: list[float], volumes: list[int]
) -> dict[str, float | None]:
    """Compute the latest value of every tracked indicator from OHLCV series."""
    if not closes:
        return {}
    macd_res = macd(closes)
    st = supertrend(highs, lows, closes)
    adx_res = adx(highs, lows, closes)
    boll = bollinger(closes)
    st_dir = next((d for d in reversed(st.direction) if d is not None), None)
    return {
        "ema_9": _last(ema(closes, 9)),
        "ema_21": _last(ema(closes, 21)),
        "ema_50": _last(ema(closes, 50)),
        "ema_200": _last(ema(closes, 200)),
        "rsi_14": _last(rsi(closes, 14)),
        "macd": _last(macd_res.macd),
        "macd_signal": _last(macd_res.signal),
        "atr_14": _last(atr(highs, lows, closes, 14)),
        "adx_14": _last(adx_res.adx),
        "vwap": _last(vwap(highs, lows, closes, volumes)),
        "supertrend": _last(st.line),
        "supertrend_dir": float(st_dir) if st_dir is not None else None,
        "bb_upper": _last(boll.upper),
        "bb_lower": _last(boll.lower),
    }


# Columns persisted to the market_indicators table (subset of the bundle).
_PERSISTED = {
    "ema_9",
    "ema_21",
    "ema_50",
    "ema_200",
    "rsi_14",
    "macd",
    "macd_signal",
    "atr_14",
    "adx_14",
    "vwap",
    "supertrend",
}


class IndicatorEngine:
    """Recomputes indicators on candle close and distributes them."""

    def __init__(self, repository: MarketDataRepository) -> None:
        self._repo = repository

    async def on_candle_closed(self, event: CandleClosed) -> None:
        candles = await self._repo.recent_candles(event.instrument_id, event.timeframe, limit=300)
        if len(candles) < 15:
            return
        highs = [float(c.high) for c in candles]
        lows = [float(c.low) for c in candles]
        closes = [float(c.close) for c in candles]
        volumes = [int(c.volume) for c in candles]
        bundle = compute_bundle(highs, lows, closes, volumes)

        await cache.set_indicators(event.symbol, event.timeframe, bundle)

        persist: dict[str, object] = {
            k: (Decimal(str(round(v, 6))) if v is not None else None)
            for k, v in bundle.items()
            if k in _PERSISTED
        }
        st_dir = bundle.get("supertrend_dir")
        persist["supertrend_dir"] = int(st_dir) if st_dir is not None else None
        await self._repo.upsert_indicators(
            event.instrument_id, event.timeframe, event.bar_ts, persist
        )
        await event_bus.publish(
            IndicatorCalculated(
                source="indicator_engine",
                instrument_id=event.instrument_id,
                symbol=event.symbol,
                timeframe=event.timeframe,
                bar_ts=event.bar_ts,
                indicators=bundle,
            )
        )
