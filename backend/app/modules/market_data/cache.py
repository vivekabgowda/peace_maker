"""Redis-backed hot cache for the latest market state.

Stores the most recent quote, indicator bundle, option-chain summary, market
status, and per-symbol data-freshness timestamps. All accessors degrade
gracefully: if Redis is unavailable they return ``None``/empty rather than
raising, so read endpoints never hard-fail on a cache outage.
"""

from __future__ import annotations

import json
import time
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.redis import get_redis

logger = get_logger("market_cache")

_QUOTE_KEY = "md:quote:{symbol}"
_INDICATOR_KEY = "md:ind:{symbol}:{tf}"
_OPTION_KEY = "md:opt:{underlying}"
_FRESH_KEY = "md:fresh:{symbol}"
_STATUS_KEY = "md:status"
_QUOTE_INDEX = "md:quotes:index"


async def _safe(coro: Any) -> Any:
    try:
        return await coro
    except Exception:
        return None


async def set_quote(symbol: str, quote: dict[str, Any]) -> None:
    r = get_redis()
    payload = json.dumps(quote, default=str)
    ttl = get_settings().quote_cache_ttl_seconds
    try:
        pipe = r.pipeline()
        # TTL so a stopped feed does not leave stale quotes looking "live".
        pipe.set(_QUOTE_KEY.format(symbol=symbol), payload, ex=ttl)
        pipe.set(_FRESH_KEY.format(symbol=symbol), str(time.time()), ex=ttl)
        pipe.sadd(_QUOTE_INDEX, symbol)
        await pipe.execute()
    except Exception:
        logger.debug("cache_set_quote_failed", symbol=symbol)


async def get_quote(symbol: str) -> dict[str, Any] | None:
    raw = await _safe(get_redis().get(_QUOTE_KEY.format(symbol=symbol)))
    return json.loads(raw) if raw else None


async def get_all_quotes() -> list[dict[str, Any]]:
    symbols = await _safe(get_redis().smembers(_QUOTE_INDEX)) or set()
    out: list[dict[str, Any]] = []
    for symbol in symbols:
        quote = await get_quote(symbol)
        if quote is not None:
            out.append(quote)
    return out


async def set_indicators(symbol: str, timeframe: str, indicators: dict[str, Any]) -> None:
    key = _INDICATOR_KEY.format(symbol=symbol, tf=timeframe)
    await _safe(get_redis().set(key, json.dumps(indicators, default=str)))


async def get_indicators(symbol: str, timeframe: str) -> dict[str, Any] | None:
    raw = await _safe(get_redis().get(_INDICATOR_KEY.format(symbol=symbol, tf=timeframe)))
    return json.loads(raw) if raw else None


async def set_option_summary(underlying: str, summary: dict[str, Any]) -> None:
    await _safe(
        get_redis().set(_OPTION_KEY.format(underlying=underlying), json.dumps(summary, default=str))
    )


async def get_option_summary(underlying: str) -> dict[str, Any] | None:
    raw = await _safe(get_redis().get(_OPTION_KEY.format(underlying=underlying)))
    return json.loads(raw) if raw else None


async def get_freshness(symbol: str) -> float | None:
    raw = await _safe(get_redis().get(_FRESH_KEY.format(symbol=symbol)))
    return float(raw) if raw else None


async def set_market_status(status: str) -> None:
    await _safe(get_redis().set(_STATUS_KEY, status))


async def get_market_status() -> str | None:
    result = await _safe(get_redis().get(_STATUS_KEY))
    return result if isinstance(result, str) else None
