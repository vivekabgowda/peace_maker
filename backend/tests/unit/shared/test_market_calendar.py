"""Tests for the NSE trading calendar and session model."""

from __future__ import annotations

from datetime import UTC, date, datetime

from app.shared.market_calendar import (
    IST,
    SessionPhase,
    is_market_open,
    is_muhurat,
    is_trading_day,
    nearest_weekly_expiry,
    session_open_dt,
    session_phase,
)


def _ist(y: int, m: int, d: int, hh: int, mm: int) -> datetime:
    return datetime(y, m, d, hh, mm, tzinfo=IST).astimezone(UTC)


def test_weekend_and_holiday_not_trading() -> None:
    assert not is_trading_day(date(2026, 1, 24))  # Saturday
    assert not is_trading_day(date(2026, 1, 25))  # Sunday
    assert not is_trading_day(date(2026, 1, 26))  # Republic Day holiday
    assert is_trading_day(date(2026, 1, 27))  # Tuesday


def test_session_phases() -> None:
    day = (2026, 1, 27)  # a normal trading Tuesday
    assert session_phase(_ist(*day, 9, 3)) == SessionPhase.PRE_OPEN
    assert session_phase(_ist(*day, 10, 0)) == SessionPhase.OPEN
    assert session_phase(_ist(*day, 15, 45)) == SessionPhase.CLOSING
    assert session_phase(_ist(*day, 17, 0)) == SessionPhase.CLOSED
    assert session_phase(_ist(*day, 8, 0)) == SessionPhase.CLOSED


def test_is_market_open() -> None:
    assert is_market_open(_ist(2026, 1, 27, 11, 0))
    assert not is_market_open(_ist(2026, 1, 27, 16, 30))
    assert not is_market_open(_ist(2026, 1, 26, 11, 0))  # holiday


def test_muhurat_session() -> None:
    assert is_muhurat(date(2026, 11, 8))
    assert session_phase(_ist(2026, 11, 8, 14, 0)) == SessionPhase.MUHURAT
    assert is_market_open(_ist(2026, 11, 8, 14, 0))
    assert session_phase(_ist(2026, 11, 8, 10, 0)) == SessionPhase.CLOSED


def test_session_open_dt_anchors_same_session() -> None:
    a = session_open_dt(_ist(2026, 1, 27, 9, 30))
    b = session_open_dt(_ist(2026, 1, 27, 14, 0))
    c = session_open_dt(_ist(2026, 1, 28, 9, 30))
    assert a is not None and a == b  # same trading day → same session anchor
    assert c is not None and c != a  # next day → new session
    assert session_open_dt(_ist(2026, 1, 27, 8, 0)) is None  # before open


def test_nearest_weekly_expiry_skips_holiday() -> None:
    # 2026-01-22 is a Thursday; verify it returns a valid trading day on/after.
    exp = nearest_weekly_expiry(date(2026, 1, 20))
    assert is_trading_day(exp)
    assert exp.weekday() <= 3
