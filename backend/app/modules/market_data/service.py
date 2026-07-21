"""Read-side facade for market data.

Serves the dashboard: live quotes and indicators from the Redis hot cache;
candles, instruments, and sector maps from PostgreSQL. Market breadth and sector
strength are derived on the fly from cached quotes.
"""

from __future__ import annotations

import time
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.market_data import cache
from app.modules.market_data.repository import MarketDataRepository

INDICES = ["NIFTY", "BANKNIFTY", "SENSEX", "INDIAVIX"]


def _pct_change(quote: dict[str, Any]) -> float | None:
    try:
        ltp = float(quote["ltp"])
        prev = float(quote["close"])
        if prev:
            return round((ltp - prev) / prev * 100, 2)
    except (KeyError, TypeError, ValueError):
        return None
    return None


class MarketDataService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = MarketDataRepository(session)

    async def list_instruments(self, *, fno_only: bool = False) -> list[dict[str, Any]]:
        rows = await self._repo.list_instruments(fno_only=fno_only)
        return [
            {
                "id": r.id,
                "symbol": r.symbol,
                "exchange": r.exchange,
                "instrument_type": r.instrument_type,
                "sector": r.sector,
                "in_fno": r.in_fno,
                "lot_size": r.lot_size,
            }
            for r in rows
        ]

    async def get_quote(self, symbol: str) -> dict[str, Any] | None:
        quote = await cache.get_quote(symbol)
        if quote is not None:
            quote["change_pct"] = _pct_change(quote)
        return quote

    async def get_all_quotes(self) -> list[dict[str, Any]]:
        quotes = await cache.get_all_quotes()
        for q in quotes:
            q["change_pct"] = _pct_change(q)
        return quotes

    async def get_indices(self) -> list[dict[str, Any]]:
        out = []
        for symbol in INDICES:
            quote = await self.get_quote(symbol)
            if quote is not None:
                out.append(quote)
        return out

    async def get_indicators(self, symbol: str, timeframe: str) -> dict[str, Any] | None:
        return await cache.get_indicators(symbol, timeframe)

    async def get_option_summary(self, underlying: str) -> dict[str, Any] | None:
        return await cache.get_option_summary(underlying)

    async def get_market_status(self) -> str:
        return await cache.get_market_status() or "unknown"

    async def get_breadth(self) -> dict[str, int]:
        quotes = await self.get_all_quotes()
        advances = declines = unchanged = 0
        for q in quotes:
            if q.get("instrument_type") == "INDEX":
                continue
            change = _pct_change(q)
            if change is None or change == 0:
                unchanged += 1
            elif change > 0:
                advances += 1
            else:
                declines += 1
        return {"advances": advances, "declines": declines, "unchanged": unchanged}

    async def get_sector_strength(self) -> list[dict[str, Any]]:
        sector_map = {r.symbol: r.sector for r in await self._repo.list_instruments()}
        buckets: dict[str, list[float]] = {}
        for q in await self.get_all_quotes():
            sector = sector_map.get(q.get("symbol", ""))
            change = _pct_change(q)
            if sector and sector != "Index" and change is not None:
                buckets.setdefault(sector, []).append(change)
        rows: list[dict[str, Any]] = [
            {"sector": s, "avg_change_pct": round(sum(v) / len(v), 2), "count": len(v)}
            for s, v in buckets.items()
        ]
        rows.sort(key=lambda x: float(x["avg_change_pct"]), reverse=True)
        return rows

    async def get_candles(
        self, symbol: str, timeframe: str, limit: int = 300
    ) -> list[dict[str, Any]]:
        instrument_id = await self._repo.get_instrument_id(symbol)
        if instrument_id is None:
            return []
        candles = await self._repo.recent_candles(instrument_id, timeframe, limit)
        return [
            {
                "ts": c.ts.isoformat(),
                "open": float(c.open),
                "high": float(c.high),
                "low": float(c.low),
                "close": float(c.close),
                "volume": c.volume,
            }
            for c in candles
        ]

    async def get_data_freshness(self) -> dict[str, Any]:
        now = time.time()
        result: dict[str, Any] = {}
        for symbol in INDICES:
            ts = await cache.get_freshness(symbol)
            result[symbol] = round(now - ts, 2) if ts else None
        return result
