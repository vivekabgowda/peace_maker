"""Technical indicator engine.

``compute_bundle`` (batch) remains for replay/tests. The live ``IndicatorEngine``
now keeps **rolling per-(instrument, timeframe) state** and updates incrementally
on each ``CandleClosed`` — no DB reloads (Technical Design Review R0 #5/#6). It
consumes the OHLCV carried on the event, so it never reads candles back.
"""

from __future__ import annotations

import time
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.logging import get_logger
from app.modules.market_data import cache, metrics
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
from app.shared.indicators.incremental import RollingIndicatorState

logger = get_logger("indicator_engine")


def _last(series: list[float | None]) -> float | None:
    for value in reversed(series):
        if value is not None:
            return value
    return None


def compute_bundle(
    highs: list[float], lows: list[float], closes: list[float], volumes: list[int]
) -> dict[str, float | None]:
    """Batch computation of the latest indicator values (replay/tests)."""
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
    """Stateful engine: incremental update per candle close, cache + persist + emit."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory
        self._states: dict[tuple[int, str], RollingIndicatorState] = {}

    async def on_candle_closed(self, event: CandleClosed) -> None:
        key = (event.instrument_id, event.timeframe)
        state = self._states.get(key)
        if state is None:
            state = RollingIndicatorState()
            self._states[key] = state

        started = time.perf_counter()
        bundle = state.update(
            float(event.high),
            float(event.low),
            float(event.close),
            event.volume,
            event.bar_ts,
        )
        metrics.INDICATOR_UPDATE_SECONDS.observe(time.perf_counter() - started)

        await cache.set_indicators(event.symbol, event.timeframe, bundle)

        persist: dict[str, object] = {
            k: (Decimal(str(round(v, 6))) if v is not None else None)
            for k, v in bundle.items()
            if k in _PERSISTED
        }
        st_dir = bundle.get("supertrend_dir")
        persist["supertrend_dir"] = int(st_dir) if st_dir is not None else None
        async with self._sf() as session:
            await MarketDataRepository(session).upsert_indicators(
                event.instrument_id, event.timeframe, event.bar_ts, persist
            )
            await session.commit()

        event_bus.publish(
            IndicatorCalculated(
                source="indicator_engine",
                instrument_id=event.instrument_id,
                symbol=event.symbol,
                timeframe=event.timeframe,
                bar_ts=event.bar_ts,
                indicators=bundle,
            )
        )
