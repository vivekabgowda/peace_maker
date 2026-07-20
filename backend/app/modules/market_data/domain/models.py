"""Market-data domain value objects (provider-agnostic).

These are the normalized shapes every provider must produce. The rest of the
platform depends only on these — never on a broker's wire format.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class InstrumentType(StrEnum):
    EQ = "EQ"
    INDEX = "INDEX"
    FUT = "FUT"
    CE = "CE"
    PE = "PE"


class Exchange(StrEnum):
    NSE = "NSE"
    BSE = "BSE"
    NFO = "NFO"


class InstrumentDTO(BaseModel):
    """A tradable/observable instrument from the instrument master."""

    model_config = ConfigDict(frozen=True)

    symbol: str
    exchange: Exchange
    instrument_type: InstrumentType
    name: str | None = None
    lot_size: int | None = None
    tick_size: Decimal | None = None
    isin: str | None = None
    sector: str | None = None
    industry: str | None = None
    in_fno: bool = False
    in_nifty500: bool = False
    # Derivatives-only fields
    underlying: str | None = None
    expiry: datetime | None = None
    strike: Decimal | None = None
    provider_token: str | None = None


class MarketDepthLevel(BaseModel):
    model_config = ConfigDict(frozen=True)
    price: Decimal
    quantity: int
    orders: int = 0


class Quote(BaseModel):
    """A normalized live quote. Not every provider fills every field."""

    model_config = ConfigDict(frozen=True)

    symbol: str
    ts: datetime
    ltp: Decimal
    open: Decimal | None = None
    high: Decimal | None = None
    low: Decimal | None = None
    close: Decimal | None = None  # previous close
    bid: Decimal | None = None
    ask: Decimal | None = None
    volume: int = 0
    vwap: Decimal | None = None
    atp: Decimal | None = None  # average traded price
    oi: int | None = None
    oi_change: int | None = None
    upper_circuit: Decimal | None = None
    lower_circuit: Decimal | None = None
    depth_bids: list[MarketDepthLevel] = Field(default_factory=list)
    depth_asks: list[MarketDepthLevel] = Field(default_factory=list)


class Candle(BaseModel):
    model_config = ConfigDict(frozen=True)
    symbol: str
    timeframe: str
    ts: datetime  # bar open time
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int


class OptionQuote(BaseModel):
    model_config = ConfigDict(frozen=True)
    strike: Decimal
    option_type: str  # CE | PE
    ltp: Decimal
    oi: int = 0
    oi_change: int = 0
    volume: int = 0
    iv: float | None = None
    delta: float | None = None
    gamma: float | None = None
    theta: float | None = None
    vega: float | None = None


class OptionChainSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)
    underlying: str
    expiry: str
    spot: Decimal
    ts: datetime
    quotes: list[OptionQuote] = Field(default_factory=list)
