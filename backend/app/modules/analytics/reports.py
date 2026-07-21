"""Performance reports — daily & weekly, generated automatically (Sprint 7).

A report bundles the period's :class:`PerformanceMetrics` plus a per-strategy
breakdown, renders a human-readable markdown summary, and persists both. The feed
process's report scheduler calls :meth:`ReportService.generate_daily` /
:meth:`generate_weekly` on a schedule; the API exposes the stored reports.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.modules.analytics.metrics import PerformanceMetrics
from app.modules.analytics.orm import PerformanceReport
from app.modules.analytics.service import AnalyticsService, day_bounds, week_bounds

logger = get_logger("analytics.reports")


def _fmt_secs(seconds: float) -> str:
    if seconds <= 0:
        return "—"
    if seconds < 3600:
        return f"{seconds / 60:.0f}m"
    if seconds < 86400:
        return f"{seconds / 3600:.1f}h"
    return f"{seconds / 86400:.1f}d"


def render_markdown(
    kind: str,
    start: datetime,
    end: datetime,
    metrics: PerformanceMetrics,
    breakdown: dict[str, dict[str, object]],
) -> str:
    """Render a report as markdown (also the body persisted to the DB)."""
    period = (
        start.date().isoformat()
        if kind == "daily"
        else f"{start.date().isoformat()} → {(end - timedelta(days=1)).date().isoformat()}"
    )
    m = metrics
    verdict = "🟢 profitable" if m.net_pnl > 0 else "🔴 down" if m.net_pnl < 0 else "⚪ flat"
    lines = [
        f"# {kind.capitalize()} performance report — {period}",
        "",
        f"**Result:** {verdict}  ·  **Net P&L:** ₹{m.net_pnl:,.2f}  "
        f"·  **Return:** {m.return_pct:.2f}%",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Trades | {m.total_trades} |",
        f"| Win rate | {m.win_rate * 100:.1f}% ({m.wins}W / {m.losses}L / {m.breakeven}BE) |",
        f"| Net P&L | ₹{m.net_pnl:,.2f} |",
        f"| Gross profit / loss | ₹{m.gross_profit:,.2f} / ₹{m.gross_loss:,.2f} |",
        f"| Profit factor | {m.profit_factor:.2f} |",
        f"| Expectancy | ₹{m.expectancy:,.2f} ({m.expectancy_r:.2f}R) |",
        f"| Avg win / loss | ₹{m.avg_win:,.2f} / ₹{m.avg_loss:,.2f} |",
        f"| Payoff ratio | {m.payoff_ratio:.2f} |",
        f"| Best / worst | ₹{m.best_trade:,.2f} / ₹{m.worst_trade:,.2f} |",
        f"| Max drawdown | ₹{m.max_drawdown:,.2f} ({m.max_drawdown_pct:.2f}%) |",
        f"| Sharpe (daily, annualized) | {m.sharpe:.2f} |",
        f"| Avg holding | {_fmt_secs(m.avg_holding_seconds)} |",
        f"| Equity | ₹{m.starting_equity:,.2f} → ₹{m.ending_equity:,.2f} |",
    ]
    if breakdown:
        lines += [
            "",
            "## By strategy",
            "",
            "| Strategy | Trades | Win% | Net P&L | PF |",
            "|---|---|---|---|---|",
        ]
        for name, data in breakdown.items():
            d = data  # dict from PerformanceMetrics.as_dict()
            lines.append(
                f"| {name} | {d['total_trades']} | "
                f"{cast(float, d['win_rate']) * 100:.0f}% | ₹{cast(float, d['net_pnl']):,.2f} | "
                f"{cast(float, d['profit_factor']):.2f} |"
            )
    if m.total_trades == 0:
        lines += ["", "_No closed trades in this period._"]
    lines += [
        "",
        "---",
        "_Paper-trading performance. Advisory-only platform — no live broker orders were placed._",
    ]
    return "\n".join(lines)


class ReportService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._analytics = AnalyticsService(db)

    async def generate(self, kind: str, start: datetime, end: datetime) -> PerformanceReport:
        metrics, breakdown = await self._analytics.period_metrics(start, end)
        payload: dict[str, object] = {
            "kind": kind,
            "period_start": start.isoformat(),
            "period_end": end.isoformat(),
            "metrics": metrics.as_dict(),
            "by_strategy": breakdown,
        }
        rendered = render_markdown(kind, start, end, metrics, breakdown)
        report = await self._upsert(kind, start, end, payload, rendered)
        logger.info(
            "report_generated",
            kind=kind,
            period_start=start.isoformat(),
            trades=metrics.total_trades,
        )
        return report

    async def generate_daily(self, day: date | None = None) -> PerformanceReport:
        day = day or (datetime.now(UTC).date())
        start, end = day_bounds(day)
        return await self.generate("daily", start, end)

    async def generate_weekly(self, anchor: date | None = None) -> PerformanceReport:
        anchor = anchor or (datetime.now(UTC).date())
        start, end = week_bounds(anchor)
        return await self.generate("weekly", start, end)

    async def _upsert(
        self,
        kind: str,
        start: datetime,
        end: datetime,
        payload: dict[str, object],
        rendered: str,
    ) -> PerformanceReport:
        # Portable upsert on (kind, period_start): delete-then-insert works on
        # both SQLite and Postgres and keeps exactly one row per period.
        existing = await self._db.scalar(
            select(PerformanceReport).where(
                PerformanceReport.kind == kind, PerformanceReport.period_start == start
            )
        )
        if existing is not None:
            existing.period_end = end
            existing.payload = payload
            existing.rendered = rendered
            await self._db.flush()
            return existing
        report = PerformanceReport(
            kind=kind,
            period_start=start,
            period_end=end,
            payload=payload,
            rendered=rendered,
        )
        self._db.add(report)
        await self._db.flush()
        return report

    async def list_reports(
        self, kind: str | None = None, limit: int = 30
    ) -> list[PerformanceReport]:
        stmt = select(PerformanceReport).order_by(PerformanceReport.period_end.desc())
        if kind:
            stmt = stmt.where(PerformanceReport.kind == kind)
        return list((await self._db.scalars(stmt.limit(limit))).all())

    async def latest(self, kind: str) -> PerformanceReport | None:
        result: PerformanceReport | None = await self._db.scalar(
            select(PerformanceReport)
            .where(PerformanceReport.kind == kind)
            .order_by(PerformanceReport.period_end.desc())
            .limit(1)
        )
        return result

    async def get(self, report_id: int) -> PerformanceReport | None:
        return await self._db.get(PerformanceReport, report_id)


def report_to_dict(report: PerformanceReport) -> dict[str, object]:
    return {
        "id": report.id,
        "kind": report.kind,
        "period_start": report.period_start.isoformat(),
        "period_end": report.period_end.isoformat(),
        "payload": report.payload,
        "rendered": report.rendered,
        "created_at": report.created_at.isoformat() if report.created_at else None,
    }


def due_reports(
    now: datetime,
    *,
    last_daily_start: datetime | None,
    last_weekly_start: datetime | None,
) -> set[str]:
    """Pure scheduling decision: which reports are due at ``now``.

    - A **daily** report for *yesterday* is due once we are past midnight UTC and
      it has not yet been generated.
    - A **weekly** report for *last week* is due once the new ISO week has begun
      (Monday UTC) and it has not yet been generated.
    """
    due: set[str] = set()
    yesterday = (now - timedelta(days=1)).date()
    daily_start, _ = day_bounds(yesterday)
    if last_daily_start is None or last_daily_start < daily_start:
        due.add("daily")

    last_week_anchor = (now - timedelta(days=7)).date()
    weekly_start, _ = week_bounds(last_week_anchor)
    if last_weekly_start is None or last_weekly_start < weekly_start:
        due.add("weekly")
    return due
