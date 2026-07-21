"""Integration: paper order -> position -> exit -> journal -> analytics.

Exercised at the service layer against the real (SQLite/Postgres) database so cash
accounting, journal recording, and analytics roll-ups are checked end to end.
"""

from __future__ import annotations

import pytest
from app.core.database import async_session_factory
from app.modules.analytics.reports import ReportService
from app.modules.analytics.service import AnalyticsService
from app.modules.journal.service import JournalService
from app.modules.paper_trading.engine import ExecutionModel, FeeModel
from app.modules.paper_trading.models import ExitReason, OrderRequest, OrderSide
from app.modules.paper_trading.service import PaperTradingService

pytestmark = pytest.mark.integration

_ZERO_COST = {"fee_model": FeeModel(0.0), "execution": ExecutionModel(0.0)}


def _svc(session: object) -> PaperTradingService:
    return PaperTradingService(session, **_ZERO_COST)  # type: ignore[arg-type]


async def test_long_target_hit_records_journal_and_updates_account() -> None:
    async with async_session_factory() as session:
        svc = _svc(session)
        req = OrderRequest(symbol="TCS", side=OrderSide.BUY, quantity=10, stop=95.0, target=110.0)
        result = await svc.submit_order("u1", req, ref_price=100.0)
        await session.commit()
        assert result["status"] == "filled"

        # Cash reserved (10 * 100 = 1000) at zero fees.
        snap = await svc.account_snapshot("u1", {"TCS": 100.0})
        assert snap["cash"] == pytest.approx(999_000.0)
        assert snap["open_positions"] == 1

        # Price prints the target -> position closes at 110.
        closed = await svc.apply_price("TCS", 111.0)
        await session.commit()
        assert len(closed) == 1
        assert closed[0]["exit_reason"] == "target"
        assert closed[0]["exit_price"] == pytest.approx(110.0)
        assert closed[0]["net_pnl"] == pytest.approx(100.0)
        assert closed[0]["r_multiple"] == pytest.approx(2.0)

        # Account: realized +100, cash back to 1,000,100.
        snap2 = await svc.account_snapshot("u1")
        assert snap2["realized_pnl"] == pytest.approx(100.0)
        assert snap2["cash"] == pytest.approx(1_000_100.0)
        assert snap2["open_positions"] == 0

        # Journal recorded exactly one closed trade.
        entries = await JournalService(session).list_entries()
        assert len(entries) == 1
        assert entries[0].outcome == "win"
        assert entries[0].net_pnl == pytest.approx(100.0)

        # Analytics reflects it.
        summary = await AnalyticsService(session).summary()
        assert summary["total_trades"] == 1
        assert summary["win_rate"] == pytest.approx(1.0)
        assert summary["net_pnl"] == pytest.approx(100.0)


async def test_short_stop_hit_is_a_loss() -> None:
    async with async_session_factory() as session:
        svc = _svc(session)
        req = OrderRequest(symbol="INFY", side=OrderSide.SELL, quantity=5, stop=105.0, target=90.0)
        await svc.submit_order("u2", req, ref_price=100.0)
        await session.commit()

        closed = await svc.apply_price("INFY", 106.0)
        await session.commit()
        assert len(closed) == 1
        assert closed[0]["exit_reason"] == "stop"
        # Short stopped at 105 from entry 100: (100-105)*5 = -25.
        assert closed[0]["net_pnl"] == pytest.approx(-25.0)

        entries = await JournalService(session).list_entries()
        assert entries[0].outcome == "loss"


async def test_exit_is_idempotent_when_price_reprints() -> None:
    async with async_session_factory() as session:
        svc = _svc(session)
        req = OrderRequest(symbol="WIPRO", side=OrderSide.BUY, quantity=1, stop=95.0, target=110.0)
        await svc.submit_order("u3", req, ref_price=100.0)
        await session.commit()

        first = await svc.apply_price("WIPRO", 111.0)
        await session.commit()
        second = await svc.apply_price("WIPRO", 112.0)
        await session.commit()
        assert len(first) == 1 and len(second) == 0  # already closed

        entries = await JournalService(session).list_entries()
        assert len(entries) == 1  # not double-recorded


async def test_rejected_order_opens_no_position() -> None:
    async with async_session_factory() as session:
        svc = _svc(session)
        # Long with stop above entry -> rejected.
        req = OrderRequest(symbol="SBIN", side=OrderSide.BUY, quantity=1, stop=105.0)
        result = await svc.submit_order("u4", req, ref_price=100.0)
        await session.commit()
        assert result["status"] == "rejected"
        snap = await svc.account_snapshot("u4")
        assert snap["open_positions"] == 0
        assert snap["cash"] == pytest.approx(1_000_000.0)  # untouched
        orders = await svc.list_orders("u4")
        assert orders[0]["status"] == "rejected"


async def test_manual_close_and_weekly_report_generation() -> None:
    async with async_session_factory() as session:
        svc = _svc(session)
        req = OrderRequest(symbol="HDFC", side=OrderSide.BUY, quantity=2, stop=95.0, target=130.0)
        result = await svc.submit_order("u5", req, ref_price=100.0)
        await session.commit()
        pos_id = int(result["position"]["id"])  # type: ignore[index]

        closed = await svc.close_position(pos_id, 105.0, reason=ExitReason.MANUAL)
        await session.commit()
        assert closed is not None
        assert closed["exit_reason"] == "manual"
        assert closed["net_pnl"] == pytest.approx(10.0)  # (105-100)*2

        # A weekly report generated now covers this trade's exit day.
        report = await ReportService(session).generate_weekly()
        await session.commit()
        assert report.kind == "weekly"
        assert report.payload["metrics"]["net_pnl"] == pytest.approx(10.0)
        assert "Weekly performance report" in report.rendered
