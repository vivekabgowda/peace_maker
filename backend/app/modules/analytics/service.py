"""Analytics service — reads the journal, computes performance (Sprint 7).

Loads closed trades from the trade journal, projects them into
:class:`TradeStat`, and serves the analytics dashboard endpoints and the report
generator. Starting equity comes from the paper account's ``starting_cash`` so
returns and drawdown are expressed against real capital.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.modules.analytics.metrics import (
    PerformanceMetrics,
    TradeStat,
    by_strategy,
    daily_pnl,
)
from app.modules.journal.orm import JournalEntry
from app.modules.paper_trading.orm import PaperAccount


class AnalyticsService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._settings = get_settings()

    async def _starting_equity(self) -> float:
        """Total starting capital across paper accounts (falls back to config)."""
        rows = (await self._db.scalars(select(PaperAccount.starting_cash))).all()
        if rows:
            return float(sum(rows))
        return float(self._settings.paper_starting_cash)

    async def _load_trades(
        self, since: datetime | None = None, until: datetime | None = None
    ) -> list[TradeStat]:
        stmt = select(JournalEntry)
        if since is not None:
            stmt = stmt.where(JournalEntry.exit_ts >= since)
        if until is not None:
            stmt = stmt.where(JournalEntry.exit_ts < until)
        rows = (await self._db.scalars(stmt.order_by(JournalEntry.exit_ts))).all()
        return [
            TradeStat(
                net_pnl=float(r.net_pnl),
                r_multiple=float(r.r_multiple),
                entry_ts=r.entry_ts,
                exit_ts=r.exit_ts,
                strategy_key=r.strategy_key,
                symbol=r.symbol,
                holding_seconds=r.holding_seconds,
            )
            for r in rows
        ]

    async def summary(
        self, since: datetime | None = None, until: datetime | None = None
    ) -> dict[str, object]:
        trades = await self._load_trades(since, until)
        equity = await self._starting_equity()
        metrics = PerformanceMetrics.compute(trades, equity)
        return metrics.as_dict()

    async def equity_curve(self) -> dict[str, object]:
        trades = await self._load_trades()
        equity = await self._starting_equity()
        metrics = PerformanceMetrics.compute(trades, equity)
        return {
            "starting_equity": metrics.starting_equity,
            "ending_equity": metrics.ending_equity,
            "points": metrics.equity_curve,
        }

    async def by_strategy(self) -> dict[str, object]:
        trades = await self._load_trades()
        equity = await self._starting_equity()
        return {"strategies": by_strategy(trades, equity)}

    async def daily(self, days: int = 30) -> dict[str, object]:
        since = datetime.now(UTC) - timedelta(days=days)
        trades = await self._load_trades(since=since)
        series = daily_pnl(trades)
        return {
            "days": [{"date": d.isoformat(), "net_pnl": round(pnl, 2)} for d, pnl in series.items()]
        }

    async def period_metrics(
        self, start: datetime, end: datetime
    ) -> tuple[PerformanceMetrics, dict[str, dict[str, object]]]:
        trades = await self._load_trades(since=start, until=end)
        equity = await self._starting_equity()
        metrics = PerformanceMetrics.compute(trades, equity)
        breakdown = by_strategy(trades, equity)
        return metrics, breakdown


def day_bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime(day.year, day.month, day.day, tzinfo=UTC)
    return start, start + timedelta(days=1)


def week_bounds(anchor: date) -> tuple[datetime, datetime]:
    """Monday 00:00 → next Monday 00:00 (UTC) for the ISO week containing ``anchor``."""
    monday = anchor - timedelta(days=anchor.weekday())
    start = datetime(monday.year, monday.month, monday.day, tzinfo=UTC)
    return start, start + timedelta(days=7)
