"""Automatic performance-report scheduler + CLI (Sprint 7).

Two ways to generate reports:

- **Automatically** — the feed process runs :meth:`ReportScheduler.tick` on an
  interval. On each tick it asks the pure :func:`due_reports` helper whether a
  daily or weekly report is now due (based on what has already been stored) and
  generates the missing ones. This is what makes the weekly report "generated
  automatically" per the Sprint 7 success criteria.
- **Manually** — ``python -m app.workers.reports --kind weekly`` generates a
  report on demand (used by the e2e validation script and by n8n).
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, date, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.logging import get_logger
from app.modules.analytics.reports import ReportService, due_reports

logger = get_logger("report_scheduler")


class ReportScheduler:
    """Generates daily/weekly reports whenever they become due."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def tick(self) -> list[str]:
        """Generate any reports that are now due. Returns the kinds generated."""
        async with self._session_factory() as session:
            svc = ReportService(session)
            last_daily = await svc.latest("daily")
            last_weekly = await svc.latest("weekly")
            due = due_reports(
                datetime.now(UTC),
                last_daily_start=last_daily.period_start if last_daily else None,
                last_weekly_start=last_weekly.period_start if last_weekly else None,
            )
            generated: list[str] = []
            if "daily" in due:
                # Yesterday's completed day.
                report = await svc.generate_daily(_yesterday())
                generated.append("daily")
                logger.info("scheduled_report", kind="daily", id=report.id)
            if "weekly" in due:
                report = await svc.generate_weekly(_last_week_anchor())
                generated.append("weekly")
                logger.info("scheduled_report", kind="weekly", id=report.id)
            if generated:
                await session.commit()
            return generated


def _yesterday() -> date:
    return (datetime.now(UTC) - timedelta(days=1)).date()


def _last_week_anchor() -> date:
    return (datetime.now(UTC) - timedelta(days=7)).date()


async def _generate(kind: str) -> None:
    from app.core.database import async_session_factory

    async with async_session_factory() as session:
        svc = ReportService(session)
        if kind == "auto":
            generated = await ReportScheduler(async_session_factory).tick()
            print(f"Generated: {generated or 'nothing due'}")
            return
        report = await (svc.generate_weekly() if kind == "weekly" else svc.generate_daily())
        await session.commit()
        print(report.rendered)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a performance report.")
    parser.add_argument(
        "--kind",
        choices=["daily", "weekly", "auto"],
        default="weekly",
        help="daily/weekly generates that report now; auto generates whatever is due.",
    )
    args = parser.parse_args()
    asyncio.run(_generate(args.kind))


if __name__ == "__main__":
    main()
