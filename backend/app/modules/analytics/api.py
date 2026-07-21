"""Performance-analytics REST endpoints (Sprint 7).

Serves the analytics dashboard data (summary, equity curve, per-strategy, daily
P&L) and the stored daily/weekly reports. Read-only.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, status

from app.core.dependencies import CurrentUser, DbSession
from app.modules.analytics.reports import ReportService, report_to_dict
from app.modules.analytics.service import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/summary", summary="Overall performance metrics")
async def summary(_user: CurrentUser, session: DbSession) -> dict[str, Any]:
    return await AnalyticsService(session).summary()


@router.get("/equity-curve", summary="Equity curve points")
async def equity_curve(_user: CurrentUser, session: DbSession) -> dict[str, Any]:
    return await AnalyticsService(session).equity_curve()


@router.get("/by-strategy", summary="Per-strategy performance breakdown")
async def by_strategy(_user: CurrentUser, session: DbSession) -> dict[str, Any]:
    return await AnalyticsService(session).by_strategy()


@router.get("/daily", summary="Daily P&L series")
async def daily(
    _user: CurrentUser,
    session: DbSession,
    days: Annotated[int, Query(ge=1, le=365)] = 30,
) -> dict[str, Any]:
    return await AnalyticsService(session).daily(days=days)


@router.get("/reports", summary="List stored performance reports")
async def list_reports(
    _user: CurrentUser,
    session: DbSession,
    kind: Annotated[str | None, Query(pattern="^(daily|weekly)$")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> dict[str, Any]:
    reports = await ReportService(session).list_reports(kind=kind, limit=limit)
    return {
        "count": len(reports),
        "reports": [
            {
                "id": r.id,
                "kind": r.kind,
                "period_start": r.period_start.isoformat(),
                "period_end": r.period_end.isoformat(),
                "net_pnl": (r.payload.get("metrics") or {}).get("net_pnl"),
            }
            for r in reports
        ],
    }


@router.get("/reports/latest", summary="Latest stored report of a kind")
async def latest_report(
    _user: CurrentUser,
    session: DbSession,
    kind: Annotated[str, Query(pattern="^(daily|weekly)$")] = "weekly",
) -> dict[str, Any]:
    report = await ReportService(session).latest(kind)
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"No {kind} report generated yet"
        )
    return report_to_dict(report)


@router.get("/reports/{report_id}", summary="Get one stored report")
async def get_report(_user: CurrentUser, session: DbSession, report_id: int) -> dict[str, Any]:
    report = await ReportService(session).get(report_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    return report_to_dict(report)


@router.post("/reports/generate", summary="Generate a report now (daily or weekly)")
async def generate_report(
    _user: CurrentUser,
    session: DbSession,
    kind: Annotated[str, Query(pattern="^(daily|weekly)$")] = "weekly",
) -> dict[str, Any]:
    svc = ReportService(session)
    report = await (svc.generate_weekly() if kind == "weekly" else svc.generate_daily())
    await session.commit()
    return report_to_dict(report)
