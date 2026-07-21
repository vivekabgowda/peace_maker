"""Unit tests for report scheduling + rendering (pure)."""

from __future__ import annotations

from datetime import UTC, datetime

from app.modules.analytics.metrics import PerformanceMetrics
from app.modules.analytics.reports import due_reports, render_markdown
from app.modules.analytics.service import day_bounds, week_bounds


def test_week_bounds_is_monday_to_monday() -> None:
    # 2026-01-07 is a Wednesday; its ISO week starts Monday 2026-01-05.
    start, end = week_bounds(datetime(2026, 1, 7, tzinfo=UTC).date())
    assert start == datetime(2026, 1, 5, tzinfo=UTC)
    assert end == datetime(2026, 1, 12, tzinfo=UTC)


def test_day_bounds_is_midnight_to_midnight() -> None:
    start, end = day_bounds(datetime(2026, 1, 7, tzinfo=UTC).date())
    assert start == datetime(2026, 1, 7, tzinfo=UTC)
    assert end == datetime(2026, 1, 8, tzinfo=UTC)


def test_due_reports_all_due_when_none_stored() -> None:
    now = datetime(2026, 1, 7, 8, 0, tzinfo=UTC)
    assert due_reports(now, last_daily_start=None, last_weekly_start=None) == {"daily", "weekly"}


def test_due_reports_none_when_up_to_date() -> None:
    now = datetime(2026, 1, 7, 8, 0, tzinfo=UTC)  # Wednesday
    # Yesterday's daily (2026-01-06) and last week's weekly (2025-12-29) already done.
    last_daily = datetime(2026, 1, 6, tzinfo=UTC)
    last_weekly = datetime(2025, 12, 29, tzinfo=UTC)
    assert due_reports(now, last_daily_start=last_daily, last_weekly_start=last_weekly) == set()


def test_due_reports_daily_only_when_daily_stale() -> None:
    now = datetime(2026, 1, 7, 8, 0, tzinfo=UTC)
    last_daily = datetime(2026, 1, 4, tzinfo=UTC)  # stale
    last_weekly = datetime(2025, 12, 29, tzinfo=UTC)  # current
    assert due_reports(now, last_daily_start=last_daily, last_weekly_start=last_weekly) == {"daily"}


def test_render_markdown_contains_key_figures() -> None:
    trades: list = []
    metrics = PerformanceMetrics.compute(trades, 1_000_000.0)
    start = datetime(2026, 1, 5, tzinfo=UTC)
    end = datetime(2026, 1, 12, tzinfo=UTC)
    md = render_markdown("weekly", start, end, metrics, {})
    assert "Weekly performance report" in md
    assert "No closed trades" in md
    assert "no live broker orders were placed" in md.lower()
