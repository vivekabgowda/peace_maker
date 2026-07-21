"""Paper-trading domain models (Sprint 7).

The paper-trading engine simulates order execution against **live, read-only**
market prices. It never touches a broker's order API — there is no live order
path anywhere in the platform. These dataclasses are the pure domain: an order, a
fill, and a position. All arithmetic lives here (and in :mod:`engine`) so it is
identical whether driven by live ticks or replayed in a test.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class OrderSide(StrEnum):
    BUY = "buy"
    SELL = "sell"

    @property
    def opposite(self) -> OrderSide:
        return OrderSide.SELL if self is OrderSide.BUY else OrderSide.BUY

    @property
    def sign(self) -> int:
        """+1 for a long-opening BUY, -1 for a short-opening SELL."""
        return 1 if self is OrderSide.BUY else -1


class OrderType(StrEnum):
    MARKET = "market"
    LIMIT = "limit"


class OrderStatus(StrEnum):
    FILLED = "filled"
    REJECTED = "rejected"
    # LIMIT orders that do not cross on submission are rejected in this simple
    # model (no resting order book in paper V1) with reason "unmarketable".


class PositionStatus(StrEnum):
    OPEN = "open"
    CLOSED = "closed"


class ExitReason(StrEnum):
    STOP = "stop"
    TARGET = "target"
    MANUAL = "manual"
    EOD = "eod"  # squared off at end of day / session


@dataclass(frozen=True, slots=True)
class OrderRequest:
    """A request to open a paper position. Validated by the engine before fill."""

    symbol: str
    side: OrderSide
    quantity: int
    order_type: OrderType = OrderType.MARKET
    limit_price: float | None = None
    stop: float | None = None
    target: float | None = None
    strategy_key: str | None = None
    source: str = "manual"  # "manual" | "scanner" | "committee"

    def validate(self) -> str | None:
        """Return an error string if the request is malformed, else ``None``."""
        if self.quantity <= 0:
            return "quantity must be positive"
        if self.order_type is OrderType.LIMIT and self.limit_price is None:
            return "limit_price is required for a LIMIT order"
        if self.limit_price is not None and self.limit_price <= 0:
            return "limit_price must be positive"
        long = self.side is OrderSide.BUY
        # Stops/targets must sit on the correct side of a sensible reference. We
        # validate their mutual ordering against each other here; the fill price
        # check happens in the engine where the market price is known.
        if self.stop is not None and self.target is not None:
            if long and not (self.stop < self.target):
                return "for a BUY, stop must be below target"
            if not long and not (self.stop > self.target):
                return "for a SELL, stop must be above target"
        return None


@dataclass(frozen=True, slots=True)
class Fill:
    """The result of executing an order against a reference price."""

    symbol: str
    side: OrderSide
    quantity: int
    price: float
    ts: datetime

    @property
    def notional(self) -> float:
        return self.price * self.quantity


@dataclass(slots=True)
class Position:
    """An open or closed paper position (a round-trip once closed).

    ``direction`` is derived from the opening side: a BUY opens LONG, a SELL opens
    SHORT. P&L is signed by direction so a short that falls is a profit.
    """

    symbol: str
    side: OrderSide  # opening side
    quantity: int
    entry_price: float
    entry_ts: datetime
    stop: float | None = None
    target: float | None = None
    strategy_key: str | None = None
    source: str = "manual"
    status: PositionStatus = PositionStatus.OPEN
    exit_price: float | None = None
    exit_ts: datetime | None = None
    exit_reason: ExitReason | None = None
    fees: float = 0.0
    id: int | None = None

    @property
    def is_long(self) -> bool:
        return self.side is OrderSide.BUY

    @property
    def direction_sign(self) -> int:
        return 1 if self.is_long else -1

    @property
    def entry_notional(self) -> float:
        return self.entry_price * self.quantity

    @property
    def risk_per_unit(self) -> float:
        if self.stop is None:
            return 0.0
        return abs(self.entry_price - self.stop)

    def unrealized_pnl(self, price: float) -> float:
        """Mark-to-market P&L at ``price`` (before fees)."""
        return (price - self.entry_price) * self.quantity * self.direction_sign

    @property
    def gross_pnl(self) -> float:
        """Realized gross P&L once closed (0 while open)."""
        if self.exit_price is None:
            return 0.0
        return (self.exit_price - self.entry_price) * self.quantity * self.direction_sign

    @property
    def net_pnl(self) -> float:
        return self.gross_pnl - self.fees

    @property
    def r_multiple(self) -> float:
        """Realized P&L in units of initial per-unit risk (R)."""
        risk = self.risk_per_unit
        if risk <= 0 or self.exit_price is None:
            return 0.0
        move = (self.exit_price - self.entry_price) * self.direction_sign
        return move / risk

    @property
    def holding_seconds(self) -> float:
        if self.exit_ts is None:
            return 0.0
        return (self.exit_ts - self.entry_ts).total_seconds()

    def as_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "symbol": self.symbol,
            "side": self.side.value,
            "direction": "long" if self.is_long else "short",
            "quantity": self.quantity,
            "entry_price": round(self.entry_price, 4),
            "entry_ts": self.entry_ts.isoformat(),
            "stop": self.stop,
            "target": self.target,
            "strategy_key": self.strategy_key,
            "source": self.source,
            "status": self.status.value,
            "exit_price": None if self.exit_price is None else round(self.exit_price, 4),
            "exit_ts": self.exit_ts.isoformat() if self.exit_ts else None,
            "exit_reason": self.exit_reason.value if self.exit_reason else None,
            "gross_pnl": round(self.gross_pnl, 2),
            "fees": round(self.fees, 2),
            "net_pnl": round(self.net_pnl, 2),
            "r_multiple": round(self.r_multiple, 4),
        }


@dataclass(slots=True)
class AccountState:
    """A paper account: starting capital, free cash, and realized P&L.

    Cash is reserved at an open position's entry notional and released (plus P&L)
    at close, so ``equity`` = cash + Σ(open-position mark-to-market value).
    """

    starting_cash: float
    cash: float
    realized_pnl: float = 0.0
    fees_paid: float = 0.0

    def equity(self, open_positions: list[Position], prices: dict[str, float]) -> float:
        invested = 0.0
        for pos in open_positions:
            mark = prices.get(pos.symbol, pos.entry_price)
            invested += pos.entry_notional + pos.unrealized_pnl(mark)
        return self.cash + invested

    def as_dict(
        self, open_positions: list[Position], prices: dict[str, float]
    ) -> dict[str, object]:
        equity = self.equity(open_positions, prices)
        return {
            "starting_cash": round(self.starting_cash, 2),
            "cash": round(self.cash, 2),
            "realized_pnl": round(self.realized_pnl, 2),
            "fees_paid": round(self.fees_paid, 2),
            "equity": round(equity, 2),
            "return_pct": (
                round((equity - self.starting_cash) / self.starting_cash * 100.0, 4)
                if self.starting_cash
                else 0.0
            ),
            "open_positions": len(open_positions),
        }
