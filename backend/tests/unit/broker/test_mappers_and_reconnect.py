"""Kite → domain mappers, reconnect backoff, and token expiry math."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from app.modules.broker.mappers import (
    instrument_to_dto,
    kite_candle_to_domain,
    tick_to_quote,
    timeframe_to_interval,
)
from app.modules.broker.reconnect import BackoffPolicy, ReconnectState
from app.modules.broker.token_store import kite_token_expiry
from app.modules.market_data.domain.models import InstrumentType


def test_timeframe_to_interval_maps_and_rejects() -> None:
    assert timeframe_to_interval("5m") == "5minute"
    assert timeframe_to_interval("1d") == "day"
    with pytest.raises(ValueError, match="Unsupported"):
        timeframe_to_interval("3s")


def test_tick_to_quote_normalizes() -> None:
    tick = {
        "instrument_token": 2953217,
        "last_price": 101.5,
        "volume_traded": 500,
        "average_traded_price": 101.2,
        "ohlc": {"open": 100, "high": 102, "low": 99, "close": 100.5},
        "oi": 12345,
        "depth": {"buy": [{"price": 101.4}], "sell": [{"price": 101.6}]},
    }
    q = tick_to_quote(tick, "TCS")
    assert q.symbol == "TCS"
    assert float(q.ltp) == 101.5
    assert float(q.high) == 102.0
    assert q.volume == 500
    assert q.oi == 12345
    assert float(q.bid) == 101.4 and float(q.ask) == 101.6
    assert q.ts.tzinfo is not None  # always tz-aware


def test_instrument_to_dto_flags_fno_and_membership() -> None:
    fut = {
        "tradingsymbol": "NIFTY24DECFUT",
        "instrument_token": 111,
        "segment": "NFO-FUT",
        "exchange": "NFO",
        "instrument_type": "FUT",
        "name": "NIFTY",
    }
    dto = instrument_to_dto(fut, nifty500=set(), fno=set())
    assert dto.in_fno is True
    assert dto.instrument_type is InstrumentType.FUT
    assert dto.provider_token == "111"

    eq = {"tradingsymbol": "TCS", "instrument_token": 222, "segment": "NSE", "exchange": "NSE"}
    dto2 = instrument_to_dto(eq, nifty500={"TCS"}, fno=set())
    assert dto2.in_nifty500 is True and dto2.in_fno is False


def test_index_tradingsymbols_normalize_to_canonical_names() -> None:
    # Kite lists "NIFTY 50" / "NIFTY BANK"; the platform benchmark expects "NIFTY".
    nifty = {"tradingsymbol": "NIFTY 50", "instrument_token": 1, "segment": "INDICES"}
    banknifty = {"tradingsymbol": "NIFTY BANK", "instrument_token": 2, "segment": "INDICES"}
    assert instrument_to_dto(nifty, nifty500=set(), fno=set()).symbol == "NIFTY"
    assert instrument_to_dto(banknifty, nifty500=set(), fno=set()).symbol == "BANKNIFTY"
    # A cash equity is untouched.
    eq = {"tradingsymbol": "RELIANCE", "instrument_token": 3, "segment": "NSE"}
    assert instrument_to_dto(eq, nifty500=set(), fno=set()).symbol == "RELIANCE"


def test_kite_candle_to_domain() -> None:
    row = {
        "date": "2025-01-02T09:15:00+00:00",
        "open": 100,
        "high": 102,
        "low": 99,
        "close": 101,
        "volume": 10,
    }
    c = kite_candle_to_domain(row, "TCS", "5m")
    assert c.symbol == "TCS" and c.timeframe == "5m"
    assert float(c.close) == 101.0 and c.volume == 10
    assert c.ts.tzinfo is not None


def test_backoff_monotonic_capped_and_jitter_bounded() -> None:
    policy = BackoffPolicy(base=1.0, factor=2.0, max_delay=30.0, jitter=0.0)
    assert policy.delay_for(1) == 1.0
    assert policy.delay_for(2) == 2.0
    assert policy.delay_for(3) == 4.0
    assert policy.delay_for(20) == 30.0  # capped
    jittered = BackoffPolicy(base=1.0, factor=2.0, max_delay=30.0, jitter=0.2)
    for attempt in range(1, 8):
        base = min(1.0 * 2 ** (attempt - 1), 30.0)
        d = jittered.delay_for(attempt)
        assert 0.0 <= d <= base * 1.2 + 1e-9


def test_backoff_does_not_overflow_on_huge_attempt_counts() -> None:
    # A broker that rejects the socket instantly (e.g. a 403 upgrade failure)
    # drives the attempt counter into the thousands within seconds. The delay
    # must stay capped at max_delay instead of raising OverflowError from the
    # exponentiation (regression: factor ** (attempt - 1) overflowed a float).
    policy = BackoffPolicy(base=0.5, factor=2.0, max_delay=10.0, jitter=0.0)
    for attempt in (1_000, 100_000, 10_000_000):
        assert policy.delay_for(attempt) == 10.0


def test_reconnect_state_transitions() -> None:
    st = ReconnectState()
    st.on_disconnect()
    assert st.connected is False and st.attempts == 1
    st.on_connect()
    assert st.connected is True and st.attempts == 0 and st.total_reconnects == 1


def test_kite_token_expiry_is_next_0730_ist() -> None:
    # A UTC time well before 07:30 IST → expiry is the same IST day 07:30.
    now = datetime(2026, 3, 10, 0, 0, tzinfo=UTC)  # 05:30 IST
    exp = kite_token_expiry(now)
    assert exp > now
    # After 07:30 IST, expiry rolls to the next day.
    later = datetime(2026, 3, 10, 6, 0, tzinfo=UTC)  # 11:30 IST
    assert kite_token_expiry(later) > exp
