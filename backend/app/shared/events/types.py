"""Typed domain events shared across market-intelligence modules.

Events are immutable Pydantic models. Every event carries a ``ts`` (UTC) and a
``source`` for traceability. Adding a new event = adding a class here; the bus
routes by class name.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


def _now() -> datetime:
    return datetime.now(UTC)


class Event(BaseModel):
    """Base class for all bus events."""

    model_config = ConfigDict(frozen=True)

    ts: datetime = Field(default_factory=_now)
    source: str = "system"


class QuoteUpdated(Event):
    """A normalized live quote for an instrument."""

    instrument_id: int
    symbol: str
    ltp: Decimal
    volume: int = 0
    payload: dict[str, Any] = Field(default_factory=dict)


class CandleClosed(Event):
    """A candle finished forming for an (instrument, timeframe)."""

    instrument_id: int
    symbol: str
    timeframe: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    bar_ts: datetime


class IndicatorCalculated(Event):
    """Latest indicator bundle for an (instrument, timeframe)."""

    instrument_id: int
    symbol: str
    timeframe: str
    bar_ts: datetime
    indicators: dict[str, float | None]


class OptionChainUpdated(Event):
    """Aggregated option-chain metrics refreshed for an underlying/expiry."""

    underlying: str
    expiry: str
    pcr: float | None = None
    max_pain: float | None = None
    total_ce_oi: int = 0
    total_pe_oi: int = 0


class NewsReceived(Event):
    """A normalized, enriched news article."""

    article_id: str
    headline: str
    category: str
    sentiment: float
    impact: float
    symbols: list[str] = Field(default_factory=list)
    sectors: list[str] = Field(default_factory=list)


class MarketStatusChanged(Event):
    """The NSE session phase changed (pre-open/open/closed)."""

    phase: str
