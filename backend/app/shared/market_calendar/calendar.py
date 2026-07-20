"""NSE trading calendar and session model (IST).

Provides holiday detection, session-phase resolution, half-day / Muhurat
handling, and — critically for session-anchored VWAP — the *session open*
timestamp for any point in time. Pure and deterministic (no I/O), so it is
fully unit-testable.

Holiday data is embedded for the covered years. In production this table is
refreshed from the exchange's official calendar; the structure and API stay the
same. Times are IST (Asia/Kolkata).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from enum import StrEnum
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

# Regular session windows (IST).
PRE_OPEN_START = time(9, 0)
PRE_OPEN_END = time(9, 8)
NORMAL_OPEN = time(9, 15)
NORMAL_CLOSE = time(15, 30)
CLOSING_SESSION_START = time(15, 40)
CLOSING_SESSION_END = time(16, 0)

# NSE trading holidays (full-day close). Extend from the official calendar.
_HOLIDAYS: set[date] = {
    # 2025
    date(2025, 2, 26),
    date(2025, 3, 14),
    date(2025, 3, 31),
    date(2025, 4, 10),
    date(2025, 4, 14),
    date(2025, 4, 18),
    date(2025, 5, 1),
    date(2025, 8, 15),
    date(2025, 8, 27),
    date(2025, 10, 2),
    date(2025, 10, 21),
    date(2025, 10, 22),
    date(2025, 11, 5),
    date(2025, 12, 25),
    # 2026 (representative; refresh from exchange)
    date(2026, 1, 26),
    date(2026, 3, 4),
    date(2026, 3, 21),
    date(2026, 3, 31),
    date(2026, 4, 3),
    date(2026, 4, 14),
    date(2026, 5, 1),
    date(2026, 8, 15),
    date(2026, 10, 2),
    date(2026, 11, 9),
    date(2026, 12, 25),
}

# Muhurat trading — a special ~1-hour evening session on Diwali.
_MUHURAT: dict[date, tuple[time, time]] = {
    date(2025, 10, 21): (time(13, 45), time(14, 45)),
    date(2026, 11, 8): (time(13, 45), time(14, 45)),
}

# Half days (early close), if any. Structure ready; populate as announced.
_HALF_DAYS: dict[date, time] = {}


class SessionPhase(StrEnum):
    CLOSED = "closed"
    PRE_OPEN = "pre_open"
    OPEN = "open"
    CLOSING = "closing"
    MUHURAT = "muhurat"


def _to_ist(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    return ts.astimezone(IST)


def is_holiday(d: date) -> bool:
    return d in _HOLIDAYS


def is_weekend(d: date) -> bool:
    return d.weekday() >= 5  # Sat/Sun


def is_muhurat(d: date) -> bool:
    return d in _MUHURAT


def is_trading_day(d: date) -> bool:
    """A day the market trades (normal weekday, or a Muhurat session)."""
    if is_muhurat(d):
        return True
    return not (is_weekend(d) or is_holiday(d))


def is_half_day(d: date) -> bool:
    return d in _HALF_DAYS


def close_time(d: date) -> time:
    """Normal close for the day (accounts for half days / Muhurat)."""
    if d in _MUHURAT:
        return _MUHURAT[d][1]
    return _HALF_DAYS.get(d, NORMAL_CLOSE)


def open_time(d: date) -> time:
    if d in _MUHURAT:
        return _MUHURAT[d][0]
    return NORMAL_OPEN


def session_phase(ts: datetime) -> SessionPhase:
    """Resolve the market session phase for an instant."""
    local = _to_ist(ts)
    d = local.date()
    if not is_trading_day(d):
        return SessionPhase.CLOSED
    t = local.time()
    if is_muhurat(d):
        start, end = _MUHURAT[d]
        return SessionPhase.MUHURAT if start <= t < end else SessionPhase.CLOSED
    if PRE_OPEN_START <= t < NORMAL_OPEN:
        return SessionPhase.PRE_OPEN
    if NORMAL_OPEN <= t < close_time(d):
        return SessionPhase.OPEN
    if CLOSING_SESSION_START <= t < CLOSING_SESSION_END:
        return SessionPhase.CLOSING
    return SessionPhase.CLOSED


def is_market_open(ts: datetime) -> bool:
    return session_phase(ts) in (SessionPhase.OPEN, SessionPhase.MUHURAT)


def session_open_dt(ts: datetime) -> datetime | None:
    """The session-open datetime (UTC) for the session ``ts`` belongs to.

    Used to anchor session VWAP. Returns None when ``ts`` is outside a trading
    session (before pre-open or after close on a trading day, or a non-trading
    day).
    """
    local = _to_ist(ts)
    d = local.date()
    if not is_trading_day(d):
        return None
    o = open_time(d)
    if local.time() < o:
        return None
    if local.time() >= close_time(d) and not is_muhurat(d):
        # After close: still same session for closing-session ticks.
        if not (CLOSING_SESSION_START <= local.time() < CLOSING_SESSION_END):
            return None
    open_local = datetime.combine(d, o, tzinfo=IST)
    return open_local.astimezone(UTC)


def previous_trading_day(d: date) -> date:
    cur = d - timedelta(days=1)
    while not is_trading_day(cur):
        cur -= timedelta(days=1)
    return cur


def next_trading_day(d: date) -> date:
    cur = d + timedelta(days=1)
    while not is_trading_day(cur):
        cur += timedelta(days=1)
    return cur


def nearest_weekly_expiry(d: date) -> date:
    """Next Thursday expiry (rolled back to the previous trading day if holiday)."""
    days_ahead = (3 - d.weekday()) % 7  # Thursday == 3
    expiry = d + timedelta(days=days_ahead)
    while not is_trading_day(expiry):
        expiry -= timedelta(days=1)
    return expiry
