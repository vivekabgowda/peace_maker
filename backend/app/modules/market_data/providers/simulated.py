"""Built-in simulated market provider.

A deterministic, dependency-free reference implementation of
:class:`MarketProvider`. It generates realistic random-walk quotes, synthetic
option chains, and historical candles so the entire real-time pipeline can run
and be tested end-to-end without any external broker. Real providers (Zerodha,
Upstox, …) implement the same interface and drop in via the registry.
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.core.logging import get_logger
from app.modules.market_data.domain.models import (
    Candle,
    Exchange,
    InstrumentDTO,
    InstrumentType,
    OptionChainSnapshot,
    OptionQuote,
    Quote,
)
from app.modules.market_data.providers.base import MarketProvider, ProviderError

logger = get_logger("provider.simulated")

# A representative slice of the Indian market universe.
_UNIVERSE: list[dict[str, object]] = [
    {"symbol": "NIFTY", "type": InstrumentType.INDEX, "base": 24500.0, "sector": "Index"},
    {"symbol": "BANKNIFTY", "type": InstrumentType.INDEX, "base": 51500.0, "sector": "Index"},
    {"symbol": "SENSEX", "type": InstrumentType.INDEX, "base": 80500.0, "sector": "Index"},
    {"symbol": "INDIAVIX", "type": InstrumentType.INDEX, "base": 13.5, "sector": "Index"},
    {"symbol": "RELIANCE", "type": InstrumentType.EQ, "base": 2915.0, "sector": "Energy"},
    {"symbol": "HDFCBANK", "type": InstrumentType.EQ, "base": 1680.0, "sector": "Banking"},
    {"symbol": "ICICIBANK", "type": InstrumentType.EQ, "base": 1250.0, "sector": "Banking"},
    {"symbol": "SBIN", "type": InstrumentType.EQ, "base": 830.0, "sector": "Banking"},
    {"symbol": "TCS", "type": InstrumentType.EQ, "base": 3950.0, "sector": "IT"},
    {"symbol": "INFY", "type": InstrumentType.EQ, "base": 1880.0, "sector": "IT"},
    {"symbol": "TATAMOTORS", "type": InstrumentType.EQ, "base": 970.0, "sector": "Auto"},
    {"symbol": "ITC", "type": InstrumentType.EQ, "base": 465.0, "sector": "FMCG"},
]

_FNO_UNDERLYINGS = {"NIFTY", "BANKNIFTY", "RELIANCE", "HDFCBANK", "ICICIBANK", "TCS", "INFY"}


class _SymbolState:
    """Mutable per-symbol simulation state (session OHLC + random walk)."""

    def __init__(self, base: float, rng: random.Random) -> None:
        self.rng = rng
        self.price = base
        self.open = base
        self.high = base
        self.low = base
        self.prev_close = base
        self.cum_volume = 0
        self.cum_pv = 0.0

    def tick(self, volatility: float) -> None:
        drift = self.rng.gauss(0, volatility) * self.price
        self.price = max(0.05, self.price + drift)
        self.high = max(self.high, self.price)
        self.low = min(self.low, self.price)
        vol = self.rng.randint(100, 5000)
        self.cum_volume += vol
        self.cum_pv += self.price * vol


class SimulatedMarketProvider(MarketProvider):
    """Deterministic in-process market simulator."""

    name = "simulated"

    def __init__(self, *, seed: int = 42, tick_interval: float = 1.0) -> None:
        self._seed = seed
        self._tick_interval = tick_interval
        self._connected = False
        self._subscriptions: set[str] = set()
        self._states: dict[str, _SymbolState] = {}
        self._rng = random.Random(seed)

    async def connect(self) -> None:
        self._connected = True
        for entry in _UNIVERSE:
            symbol = str(entry["symbol"])
            self._states[symbol] = _SymbolState(
                float(entry["base"]),  # type: ignore[arg-type]
                random.Random(f"{self._seed}:{symbol}".__hash__() & 0xFFFFFFFF),
            )
        logger.info("provider_connected", provider=self.name, symbols=len(self._states))

    async def disconnect(self) -> None:
        self._connected = False
        self._subscriptions.clear()
        logger.info("provider_disconnected", provider=self.name)

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def fetch_instruments(self) -> list[InstrumentDTO]:
        out: list[InstrumentDTO] = []
        for entry in _UNIVERSE:
            symbol = str(entry["symbol"])
            itype: InstrumentType = entry["type"]  # type: ignore[assignment]
            is_index = itype == InstrumentType.INDEX
            out.append(
                InstrumentDTO(
                    symbol=symbol,
                    exchange=Exchange.NSE,
                    instrument_type=itype,
                    name=symbol,
                    lot_size=None if is_index else 1,
                    tick_size=Decimal("0.05"),
                    sector=str(entry["sector"]),
                    industry=str(entry["sector"]),
                    in_fno=symbol in _FNO_UNDERLYINGS,
                    in_nifty500=not is_index,
                )
            )
        return out

    async def subscribe(self, symbols: list[str]) -> None:
        if not self._connected:
            raise ProviderError("Cannot subscribe before connect()")
        self._subscriptions.update(s for s in symbols if s in self._states)

    async def unsubscribe(self, symbols: list[str]) -> None:
        self._subscriptions.difference_update(symbols)

    async def stream(self) -> AsyncIterator[Quote]:
        while self._connected:
            for symbol in list(self._subscriptions):
                state = self._states.get(symbol)
                if state is None:
                    continue
                vol = 0.02 if symbol == "INDIAVIX" else 0.0008
                state.tick(vol)
                yield self._to_quote(symbol, state)
            await asyncio.sleep(self._tick_interval)

    def _to_quote(self, symbol: str, s: _SymbolState) -> Quote:
        price = round(s.price, 2)
        spread = max(0.05, price * 0.0002)
        vwap = s.cum_pv / s.cum_volume if s.cum_volume else price
        return Quote(
            symbol=symbol,
            ts=datetime.now(UTC),
            ltp=Decimal(str(price)),
            open=Decimal(str(round(s.open, 2))),
            high=Decimal(str(round(s.high, 2))),
            low=Decimal(str(round(s.low, 2))),
            close=Decimal(str(round(s.prev_close, 2))),
            bid=Decimal(str(round(price - spread, 2))),
            ask=Decimal(str(round(price + spread, 2))),
            volume=s.cum_volume,
            vwap=Decimal(str(round(vwap, 2))),
            atp=Decimal(str(round(vwap, 2))),
            upper_circuit=Decimal(str(round(s.prev_close * 1.10, 2))),
            lower_circuit=Decimal(str(round(s.prev_close * 0.90, 2))),
        )

    async def fetch_option_chain(self, underlying: str, expiry: str) -> OptionChainSnapshot:
        state = self._states.get(underlying)
        if state is None:
            raise ProviderError(f"Unknown underlying: {underlying}")
        spot = state.price
        step = 100.0 if underlying == "NIFTY" else (500.0 if underlying == "BANKNIFTY" else 50.0)
        atm = round(spot / step) * step
        rng = random.Random(f"{underlying}:{expiry}".__hash__() & 0xFFFFFFFF)
        quotes: list[OptionQuote] = []
        for i in range(-5, 6):
            strike = atm + i * step
            for opt_type in ("CE", "PE"):
                moneyness = (spot - strike) if opt_type == "CE" else (strike - spot)
                intrinsic = max(0.0, moneyness)
                ltp = round(intrinsic + rng.uniform(5, 80), 2)
                quotes.append(
                    OptionQuote(
                        strike=Decimal(str(strike)),
                        option_type=opt_type,
                        ltp=Decimal(str(ltp)),
                        oi=rng.randint(1000, 500000),
                        oi_change=rng.randint(-50000, 50000),
                        volume=rng.randint(0, 200000),
                        iv=round(rng.uniform(10, 30), 2),
                    )
                )
        return OptionChainSnapshot(
            underlying=underlying,
            expiry=expiry,
            spot=Decimal(str(round(spot, 2))),
            ts=datetime.now(UTC),
            quotes=quotes,
        )

    async def fetch_historical_candles(
        self, symbol: str, timeframe: str, start: datetime, end: datetime
    ) -> list[Candle]:
        entry = next((e for e in _UNIVERSE if e["symbol"] == symbol), None)
        if entry is None:
            raise ProviderError(f"Unknown symbol: {symbol}")
        minutes = _timeframe_minutes(timeframe)
        rng = random.Random(f"hist:{symbol}:{timeframe}".__hash__() & 0xFFFFFFFF)
        price = float(entry["base"])  # type: ignore[arg-type]
        candles: list[Candle] = []
        cursor = start
        delta = timedelta(minutes=minutes)
        while cursor < end:
            o = price
            price = max(0.05, price * (1 + rng.gauss(0, 0.002)))
            c = price
            hi = max(o, c) * (1 + abs(rng.gauss(0, 0.001)))
            lo = min(o, c) * (1 - abs(rng.gauss(0, 0.001)))
            candles.append(
                Candle(
                    symbol=symbol,
                    timeframe=timeframe,
                    ts=cursor,
                    open=Decimal(str(round(o, 2))),
                    high=Decimal(str(round(hi, 2))),
                    low=Decimal(str(round(lo, 2))),
                    close=Decimal(str(round(c, 2))),
                    volume=rng.randint(10_000, 500_000),
                )
            )
            cursor += delta
        return candles


def _timeframe_minutes(timeframe: str) -> int:
    mapping = {
        "1m": 1,
        "3m": 3,
        "5m": 5,
        "15m": 15,
        "30m": 30,
        "1h": 60,
        "4h": 240,
        "1d": 1440,
        "1w": 10080,
    }
    if timeframe not in mapping:
        raise ProviderError(f"Unsupported timeframe: {timeframe}")
    return mapping[timeframe]
