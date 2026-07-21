"""Paper-trading persistence access (Sprint 7).

Translates between the float-based domain (:mod:`models`) and the ``Numeric``
ORM rows. The service layer owns transactions; this layer only reads and stages
writes (``flush``, never ``commit``).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.paper_trading.models import (
    AccountState,
    ExitReason,
    OrderSide,
    OrderType,
    Position,
    PositionStatus,
)
from app.modules.paper_trading.orm import PaperAccount, PaperOrder, PaperPosition


def _f(value: Decimal | float | None) -> float | None:
    return float(value) if value is not None else None


def _d(value: float | None) -> Decimal | None:
    return Decimal(str(value)) if value is not None else None


def _utc(value: datetime | None) -> datetime | None:
    """SQLite returns naive datetimes even for tz-aware columns; treat as UTC so
    arithmetic against tz-aware clocks is dialect-agnostic."""
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


class PaperTradingRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # -- Account ------------------------------------------------------------
    async def get_or_create_account(
        self, user_id: str | None, starting_cash: float
    ) -> PaperAccount:
        stmt = select(PaperAccount)
        stmt = (
            stmt.where(PaperAccount.user_id == user_id)
            if user_id is not None
            else stmt.where(PaperAccount.user_id.is_(None))
        )
        account = await self._db.scalar(stmt)
        if account is None:
            account = PaperAccount(
                user_id=user_id,
                starting_cash=Decimal(str(starting_cash)),
                cash=Decimal(str(starting_cash)),
                realized_pnl=Decimal("0"),
                fees_paid=Decimal("0"),
            )
            self._db.add(account)
            await self._db.flush()
        return account

    @staticmethod
    def account_state(account: PaperAccount) -> AccountState:
        return AccountState(
            starting_cash=float(account.starting_cash),
            cash=float(account.cash),
            realized_pnl=float(account.realized_pnl),
            fees_paid=float(account.fees_paid),
        )

    # -- Orders -------------------------------------------------------------
    async def record_order(self, **kwargs: object) -> PaperOrder:
        order = PaperOrder(**kwargs)
        self._db.add(order)
        await self._db.flush()
        return order

    async def list_orders(self, account_id: int, limit: int = 200) -> list[PaperOrder]:
        stmt = (
            select(PaperOrder)
            .where(PaperOrder.account_id == account_id)
            .order_by(PaperOrder.submitted_at.desc())
            .limit(limit)
        )
        return list((await self._db.scalars(stmt)).all())

    # -- Positions ----------------------------------------------------------
    async def add_position(self, account_id: int, position: Position) -> PaperPosition:
        row = PaperPosition(
            account_id=account_id,
            symbol=position.symbol,
            side=position.side.value,
            quantity=position.quantity,
            entry_price=Decimal(str(position.entry_price)),
            entry_ts=position.entry_ts,
            stop=_d(position.stop),
            target=_d(position.target),
            strategy_key=position.strategy_key,
            source=position.source,
            status=PositionStatus.OPEN.value,
            fees=Decimal(str(position.fees)),
        )
        self._db.add(row)
        await self._db.flush()
        position.id = row.id
        return row

    async def open_positions(self, account_id: int, symbol: str | None = None) -> list[Position]:
        stmt = select(PaperPosition).where(
            PaperPosition.account_id == account_id,
            PaperPosition.status == PositionStatus.OPEN.value,
        )
        if symbol is not None:
            stmt = stmt.where(PaperPosition.symbol == symbol)
        rows = (await self._db.scalars(stmt)).all()
        return [self.to_domain(r) for r in rows]

    async def get_position_row(self, position_id: int) -> PaperPosition | None:
        return await self._db.get(PaperPosition, position_id)

    async def open_position_rows_by_symbol(self, symbol: str) -> list[PaperPosition]:
        """Open positions on ``symbol`` across *all* accounts (used by the tick
        loop, which marks the whole book against a market-wide price)."""
        stmt = select(PaperPosition).where(
            PaperPosition.symbol == symbol,
            PaperPosition.status == PositionStatus.OPEN.value,
        )
        return list((await self._db.scalars(stmt)).all())

    async def open_symbols(self) -> list[str]:
        stmt = (
            select(PaperPosition.symbol)
            .where(PaperPosition.status == PositionStatus.OPEN.value)
            .distinct()
        )
        return list((await self._db.scalars(stmt)).all())

    async def get_account(self, account_id: int) -> PaperAccount | None:
        return await self._db.get(PaperAccount, account_id)

    async def close_position(
        self,
        row: PaperPosition,
        *,
        exit_price: float,
        exit_ts: datetime,
        exit_reason: ExitReason,
        fees: float,
    ) -> None:
        row.status = PositionStatus.CLOSED.value
        row.exit_price = Decimal(str(exit_price))
        row.exit_ts = exit_ts
        row.exit_reason = exit_reason.value
        row.fees = Decimal(str(fees))
        await self._db.flush()

    @staticmethod
    def to_domain(row: PaperPosition) -> Position:
        return Position(
            id=row.id,
            symbol=row.symbol,
            side=OrderSide(row.side),
            quantity=row.quantity,
            entry_price=float(row.entry_price),
            entry_ts=_utc(row.entry_ts),  # type: ignore[arg-type]
            stop=_f(row.stop),
            target=_f(row.target),
            strategy_key=row.strategy_key,
            source=row.source,
            status=PositionStatus(row.status),
            exit_price=_f(row.exit_price),
            exit_ts=_utc(row.exit_ts),
            exit_reason=ExitReason(row.exit_reason) if row.exit_reason else None,
            fees=float(row.fees),
        )

    @staticmethod
    def order_type_of(value: str) -> OrderType:
        return OrderType(value)
