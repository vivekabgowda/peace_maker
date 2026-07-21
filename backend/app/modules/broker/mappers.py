"""Normalize Kite payloads into the platform's domain models (Sprint 6).

Every broker-specific shape is converted here and nowhere else, so no Kite dict
leaks past the provider boundary. Pure functions — trivially unit-testable.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from app.modules.market_data.domain.models import (
    Candle,
    Exchange,
    InstrumentDTO,
    InstrumentType,
    Quote,
)

# Kite ``interval`` strings ↔ the platform's timeframe codes.
INTERVAL_MAP: dict[str, str] = {
    "1m": "minute",
    "5m": "5minute",
    "15m": "15minute",
    "1h": "60minute",
    "1d": "day",
}

_KITE_SEGMENT_TO_TYPE: dict[str, InstrumentType] = {
    "EQ": InstrumentType.EQ,
    "INDICES": InstrumentType.INDEX,
    "FUT": InstrumentType.FUT,
    "CE": InstrumentType.CE,
    "PE": InstrumentType.PE,
}

_KITE_EXCHANGE: dict[str, Exchange] = {
    "NSE": Exchange.NSE,
    "BSE": Exchange.BSE,
    "NFO": Exchange.NFO,
}


def timeframe_to_interval(timeframe: str) -> str:
    try:
        return INTERVAL_MAP[timeframe]
    except KeyError as exc:
        raise ValueError(f"Unsupported timeframe for Kite: {timeframe!r}") from exc


def _dec(value: Any) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


def tick_to_quote(tick: dict[str, Any], symbol: str) -> Quote:
    """Convert a Kite ticker payload (full/quote mode) into a normalized Quote."""
    ohlc = tick.get("ohlc") or {}
    depth = tick.get("depth") or {}
    ts_raw = tick.get("exchange_timestamp") or tick.get("last_trade_time")
    ts = ts_raw if isinstance(ts_raw, datetime) else datetime.now(UTC)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    return Quote(
        symbol=symbol,
        ts=ts,
        ltp=_dec(tick.get("last_price")) or Decimal("0"),
        open=_dec(ohlc.get("open")),
        high=_dec(ohlc.get("high")),
        low=_dec(ohlc.get("low")),
        close=_dec(ohlc.get("close")),
        volume=int(tick.get("volume_traded") or tick.get("volume") or 0),
        vwap=_dec(tick.get("average_traded_price") or tick.get("average_price")),
        atp=_dec(tick.get("average_traded_price") or tick.get("average_price")),
        oi=int(tick["oi"]) if tick.get("oi") is not None else None,
        oi_change=(
            int(tick["oi_day_high"] - tick["oi_day_low"])
            if tick.get("oi_day_high") is not None and tick.get("oi_day_low") is not None
            else None
        ),
        bid=_dec((depth.get("buy") or [{}])[0].get("price")) if depth.get("buy") else None,
        ask=_dec((depth.get("sell") or [{}])[0].get("price")) if depth.get("sell") else None,
    )


def instrument_to_dto(row: dict[str, Any], *, nifty500: set[str], fno: set[str]) -> InstrumentDTO:
    """Convert a Kite instrument-master row into an InstrumentDTO."""
    symbol = str(row.get("tradingsymbol", ""))
    seg = str(row.get("segment", "")).split("-")[-1]
    itype = _KITE_SEGMENT_TO_TYPE.get(
        str(row.get("instrument_type", "")).upper(),
        InstrumentType.INDEX if "INDICES" in str(row.get("segment", "")) else InstrumentType.EQ,
    )
    exchange = _KITE_EXCHANGE.get(str(row.get("exchange", "NSE")).upper(), Exchange.NSE)
    expiry_raw = row.get("expiry")
    expiry = expiry_raw if isinstance(expiry_raw, datetime) else None
    return InstrumentDTO(
        symbol=symbol,
        exchange=exchange,
        instrument_type=itype,
        name=row.get("name") or symbol,
        lot_size=int(row["lot_size"]) if row.get("lot_size") else None,
        tick_size=_dec(row.get("tick_size")),
        in_nifty500=symbol in nifty500,
        in_fno=symbol in fno or seg in {"FUT", "CE", "PE"},
        underlying=row.get("name") if itype in (InstrumentType.CE, InstrumentType.PE) else None,
        expiry=expiry,
        strike=_dec(row.get("strike")) if row.get("strike") else None,
        provider_token=str(row.get("instrument_token")) if row.get("instrument_token") else None,
    )


def kite_candle_to_domain(row: dict[str, Any], symbol: str, timeframe: str) -> Candle:
    """Convert one Kite historical bar (dict form) into a domain Candle."""
    ts = row["date"]
    if isinstance(ts, str):
        ts = datetime.fromisoformat(ts)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    return Candle(
        symbol=symbol,
        timeframe=timeframe,
        ts=ts,
        open=_dec(row["open"]) or Decimal("0"),
        high=_dec(row["high"]) or Decimal("0"),
        low=_dec(row["low"]) or Decimal("0"),
        close=_dec(row["close"]) or Decimal("0"),
        volume=int(row.get("volume") or 0),
    )
