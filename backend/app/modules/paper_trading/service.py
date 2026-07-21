"""Paper-trading service — DB-authoritative orchestration (Sprint 7).

Wraps the pure :mod:`engine` with persistence, cash accounting, and journal
recording. The service is the *only* place positions and accounts change, so cash
can never drift: opening reserves the entry notional (+ entry fee); closing
releases it plus realized P&L (minus exit fee).

**Read-only with respect to the broker.** Fills are simulated against live market
prices; there is no code path that submits an order to Zerodha or any broker.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.modules.journal.models import ClosedTrade
from app.modules.journal.service import JournalService
from app.modules.paper_trading import metrics
from app.modules.paper_trading.engine import (
    ExecutionModel,
    FeeModel,
    decide_order,
    exit_fill_price,
    exit_signal,
)
from app.modules.paper_trading.models import (
    AccountState,
    ExitReason,
    OrderRequest,
    OrderStatus,
    Position,
)
from app.modules.paper_trading.orm import PaperAccount, PaperPosition
from app.modules.paper_trading.repository import PaperTradingRepository

logger = get_logger("paper_trading.service")


class PaperTradingService:
    def __init__(
        self,
        db: AsyncSession,
        *,
        settings: Settings | None = None,
        fee_model: FeeModel | None = None,
        execution: ExecutionModel | None = None,
    ) -> None:
        self._db = db
        self._settings = settings or get_settings()
        self._repo = PaperTradingRepository(db)
        self._journal = JournalService(db)
        self._fees = fee_model or FeeModel(self._settings.paper_fee_bps)
        self._exec = execution or ExecutionModel(self._settings.paper_slippage_bps)

    # -- Account ------------------------------------------------------------
    async def get_or_create_account(self, user_id: str | None) -> PaperAccount:
        return await self._repo.get_or_create_account(user_id, self._settings.paper_starting_cash)

    async def account_snapshot(
        self, user_id: str | None, prices: dict[str, float] | None = None
    ) -> dict[str, object]:
        account = await self.get_or_create_account(user_id)
        positions = await self._repo.open_positions(account.id)
        marks = prices or {p.symbol: p.entry_price for p in positions}
        state = self._repo.account_state(account)
        snap = state.as_dict(positions, marks)
        snap["account_id"] = account.id
        snap["unrealized_pnl"] = round(
            sum(p.unrealized_pnl(marks.get(p.symbol, p.entry_price)) for p in positions), 2
        )
        return snap

    # -- Order submission ---------------------------------------------------
    async def submit_order(
        self, user_id: str | None, request: OrderRequest, ref_price: float
    ) -> dict[str, object]:
        """Validate, price, and (if marketable) open a position at ``ref_price``."""
        account = await self.get_or_create_account(user_id)
        ts = datetime.now(UTC)
        decision = decide_order(request, ref_price, ts, execution=self._exec)

        if not decision.accepted:
            await self._repo.record_order(
                account_id=account.id,
                symbol=request.symbol,
                side=request.side.value,
                order_type=request.order_type.value,
                quantity=request.quantity,
                limit_price=(
                    Decimal(str(request.limit_price)) if request.limit_price is not None else None
                ),
                reference_price=Decimal(str(ref_price)),
                fill_price=None,
                status=OrderStatus.REJECTED.value,
                reason=decision.rejected_reason,
                strategy_key=request.strategy_key,
                source=request.source,
                submitted_at=ts,
            )
            metrics.PAPER_ORDERS.labels(status="rejected").inc()
            logger.info(
                "paper_order_rejected", symbol=request.symbol, reason=decision.rejected_reason
            )
            return {"status": "rejected", "reason": decision.rejected_reason}

        fill = decision.fill
        assert fill is not None
        entry_fee = self._fees.cost(fill.notional)

        # Reserve capital: notional + entry fee.
        cost = fill.notional + entry_fee
        account.cash = Decimal(str(float(account.cash) - cost))
        account.fees_paid = Decimal(str(float(account.fees_paid) + entry_fee))

        position = Position(
            symbol=request.symbol,
            side=request.side,
            quantity=request.quantity,
            entry_price=fill.price,
            entry_ts=ts,
            stop=request.stop,
            target=request.target,
            strategy_key=request.strategy_key,
            source=request.source,
            fees=entry_fee,
        )
        await self._repo.add_position(account.id, position)
        await self._repo.record_order(
            account_id=account.id,
            symbol=request.symbol,
            side=request.side.value,
            order_type=request.order_type.value,
            quantity=request.quantity,
            limit_price=(
                Decimal(str(request.limit_price)) if request.limit_price is not None else None
            ),
            reference_price=Decimal(str(ref_price)),
            fill_price=Decimal(str(fill.price)),
            status=OrderStatus.FILLED.value,
            reason=None,
            strategy_key=request.strategy_key,
            source=request.source,
            submitted_at=ts,
        )
        metrics.PAPER_ORDERS.labels(status="filled").inc()
        metrics.PAPER_POSITIONS_OPEN.inc()
        logger.info(
            "paper_order_filled",
            symbol=request.symbol,
            side=request.side.value,
            qty=request.quantity,
            price=round(fill.price, 4),
        )
        return {
            "status": "filled",
            "order_type": request.order_type.value,
            "fill_price": round(fill.price, 4),
            "entry_fee": round(entry_fee, 2),
            "position": position.as_dict(),
        }

    # -- Exit management ----------------------------------------------------
    async def apply_price(
        self, symbol: str, price: float, ts: datetime | None = None
    ) -> list[dict[str, object]]:
        """Mark every open position on ``symbol`` and close those whose stop or
        target the price has hit. Returns a summary per closed trade."""
        ts = ts or datetime.now(UTC)
        rows = await self._repo.open_position_rows_by_symbol(symbol)
        closed: list[dict[str, object]] = []
        for row in rows:
            position = self._repo.to_domain(row)
            reason = exit_signal(position, price)
            if reason is None:
                continue
            fill_price = exit_fill_price(position, price, reason)
            summary = await self._close(row, position, fill_price, ts, reason)
            closed.append(summary)
        return closed

    async def close_position(
        self,
        position_id: int,
        price: float,
        ts: datetime | None = None,
        reason: ExitReason = ExitReason.MANUAL,
    ) -> dict[str, object] | None:
        row = await self._repo.get_position_row(position_id)
        if row is None or row.status != "open":
            return None
        position = self._repo.to_domain(row)
        return await self._close(row, position, price, ts or datetime.now(UTC), reason)

    async def _close(
        self,
        row: PaperPosition,
        position: Position,
        exit_price: float,
        ts: datetime,
        reason: ExitReason,
    ) -> dict[str, object]:
        exit_notional = exit_price * position.quantity
        exit_fee = self._fees.cost(exit_notional)
        total_fees = position.fees + exit_fee  # entry fee already booked at open

        # Finalize the domain position so P&L properties are correct.
        position.exit_price = exit_price
        position.exit_ts = ts
        position.exit_reason = reason
        position.fees = total_fees
        gross = position.gross_pnl
        net = position.net_pnl

        # Cash accounting: release reserved notional + realized gross, minus exit fee.
        account = await self._repo.get_account(row.account_id)
        assert account is not None
        account.cash = Decimal(
            str(float(account.cash) + position.entry_notional + gross - exit_fee)
        )
        account.realized_pnl = Decimal(str(float(account.realized_pnl) + net))
        account.fees_paid = Decimal(str(float(account.fees_paid) + exit_fee))

        await self._repo.close_position(
            row, exit_price=exit_price, exit_ts=ts, exit_reason=reason, fees=total_fees
        )

        # Book of record.
        await self._journal.record(
            ClosedTrade(
                position_id=row.id,
                account_id=row.account_id,
                symbol=position.symbol,
                direction="long" if position.is_long else "short",
                quantity=position.quantity,
                strategy_key=position.strategy_key,
                source=position.source,
                entry_price=position.entry_price,
                entry_ts=position.entry_ts,
                exit_price=exit_price,
                exit_ts=ts,
                exit_reason=reason.value,
                gross_pnl=gross,
                fees=total_fees,
                net_pnl=net,
                r_multiple=position.r_multiple,
                holding_seconds=int(position.holding_seconds),
            )
        )
        metrics.PAPER_POSITIONS_OPEN.dec()
        metrics.PAPER_TRADES_CLOSED.labels(reason=reason.value).inc()
        metrics.PAPER_REALIZED_PNL.set(float(account.realized_pnl))
        logger.info(
            "paper_position_closed",
            symbol=position.symbol,
            reason=reason.value,
            net_pnl=round(net, 2),
            r=round(position.r_multiple, 3),
        )
        return {
            "position_id": row.id,
            "symbol": position.symbol,
            "exit_reason": reason.value,
            "exit_price": round(exit_price, 4),
            "gross_pnl": round(gross, 2),
            "fees": round(total_fees, 2),
            "net_pnl": round(net, 2),
            "r_multiple": round(position.r_multiple, 4),
        }

    # -- Reads --------------------------------------------------------------
    async def list_positions(
        self, user_id: str | None, *, prices: dict[str, float] | None = None
    ) -> list[dict[str, object]]:
        account = await self.get_or_create_account(user_id)
        positions = await self._repo.open_positions(account.id)
        out: list[dict[str, object]] = []
        for p in positions:
            data = p.as_dict()
            if prices and p.symbol in prices:
                data["mark_price"] = round(prices[p.symbol], 4)
                data["unrealized_pnl"] = round(p.unrealized_pnl(prices[p.symbol]), 2)
            out.append(data)
        return out

    async def get_open_position(self, position_id: int) -> Position | None:
        row = await self._repo.get_position_row(position_id)
        if row is None or row.status != "open":
            return None
        return self._repo.to_domain(row)

    async def list_orders(self, user_id: str | None, limit: int = 200) -> list[dict[str, object]]:
        account = await self.get_or_create_account(user_id)
        rows = await self._repo.list_orders(account.id, limit=limit)
        return [
            {
                "id": r.id,
                "symbol": r.symbol,
                "side": r.side,
                "order_type": r.order_type,
                "quantity": r.quantity,
                "fill_price": float(r.fill_price) if r.fill_price is not None else None,
                "status": r.status,
                "reason": r.reason,
                "strategy_key": r.strategy_key,
                "source": r.source,
                "submitted_at": r.submitted_at.isoformat(),
            }
            for r in rows
        ]

    @staticmethod
    def state_of(account: PaperAccount) -> AccountState:
        return PaperTradingRepository.account_state(account)
