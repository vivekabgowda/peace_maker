"""Macro/event calendar for regime overlays (RBI policy, Union Budget, elections).

Like the holiday table in the market calendar, these are embedded data tables
refreshed from official sources; the API is stable. Dates are IST calendar days.
All lookups are pure and deterministic for testability.
"""

from __future__ import annotations

from datetime import date

# RBI Monetary Policy Committee outcome days (high macro sensitivity).
RBI_POLICY_DAYS: set[date] = {
    date(2025, 2, 7),
    date(2025, 4, 9),
    date(2025, 6, 6),
    date(2025, 8, 6),
    date(2025, 10, 1),
    date(2025, 12, 5),
    date(2026, 2, 6),
    date(2026, 4, 8),
    date(2026, 6, 5),
    date(2026, 8, 5),
    date(2026, 10, 7),
    date(2026, 12, 4),
}

# Union Budget presentation days.
BUDGET_DAYS: set[date] = {
    date(2025, 2, 1),
    date(2026, 2, 1),
}

# Election result / high-impact election windows (inclusive ranges).
ELECTION_WINDOWS: list[tuple[date, date]] = [
    (date(2026, 5, 15), date(2026, 5, 20)),
]


def is_rbi_day(d: date) -> bool:
    return d in RBI_POLICY_DAYS


def is_budget_day(d: date) -> bool:
    return d in BUDGET_DAYS


def is_election_event(d: date) -> bool:
    return any(start <= d <= end for start, end in ELECTION_WINDOWS)
