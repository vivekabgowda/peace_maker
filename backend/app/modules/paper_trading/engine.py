"""Paper-trading execution engine — the pure, deterministic core (Sprint 7).

No I/O, no DB, no clock of its own: every decision is a pure function of its
inputs. The stateful, DB-backed orchestration lives in :mod:`service`; this module
just answers three questions the same way live or in a test:

- **What price does an order fill at?** (:class:`ExecutionModel`)
- **Should an open position exit at this price, and why?** (:func:`exit_signal`)
- **What does it cost?** (:class:`FeeModel`)

There is deliberately no path that places a real broker order.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.modules.paper_trading.models import (
    ExitReason,
    Fill,
    OrderRequest,
    OrderSide,
    OrderType,
    Position,
)


@dataclass(frozen=True, slots=True)
class FeeModel:
    """A simple, symmetric cost model (bps of notional per side).

    Real Indian-equity costs (brokerage + STT + exchange + GST + stamp) are
    non-linear; a single blended bps figure is a defensible paper-trading proxy
    and keeps P&L honest rather than frictionless. Zero-cost is available for
    tests by constructing ``FeeModel(0.0)``.
    """

    bps: float = 3.0  # ~0.03% blended per side

    def cost(self, notional: float) -> float:
        return abs(notional) * self.bps / 10_000.0

    def charge(self, *, notional: float, side: object = None, segment: object = None) -> float:
        """`CostModel`-protocol method; the flat model ignores side/segment."""
        return self.cost(notional)


@dataclass(frozen=True, slots=True)
class ExecutionModel:
    """Turns an order + a reference (last-traded) price into a fill.

    - **MARKET** fills at the reference price adjusted by ``slippage_bps`` against
      the taker (buys fill a touch higher, sells a touch lower).
    - **LIMIT** fills only if the reference price is already marketable
      (buy limit ≥ price, sell limit ≤ price); otherwise there is no fill — paper
      V1 has no resting book.
    """

    slippage_bps: float = 1.0

    def fill_price(
        self,
        side: OrderSide,
        order_type: OrderType,
        ref_price: float,
        limit_price: float | None,
    ) -> float | None:
        if ref_price <= 0:
            return None
        slip = ref_price * self.slippage_bps / 10_000.0
        if order_type is OrderType.MARKET:
            return ref_price + slip if side is OrderSide.BUY else ref_price - slip
        # LIMIT: only if already marketable at the reference price.
        assert limit_price is not None  # guaranteed by OrderRequest.validate
        if side is OrderSide.BUY and ref_price <= limit_price:
            # Price improvement: fill at the better of limit / ref.
            return min(limit_price, ref_price + slip)
        if side is OrderSide.SELL and ref_price >= limit_price:
            return max(limit_price, ref_price - slip)
        return None


def exit_signal(position: Position, price: float) -> ExitReason | None:
    """Whether an open position should exit at ``price`` — stop first, then target.

    Stop is checked before target so that a bar which straddles both is treated
    conservatively (assume the adverse level traded first). Direction-aware:
    a long stops out below its stop and targets above; a short is the mirror.
    """
    if position.is_long:
        if position.stop is not None and price <= position.stop:
            return ExitReason.STOP
        if position.target is not None and price >= position.target:
            return ExitReason.TARGET
    else:
        if position.stop is not None and price >= position.stop:
            return ExitReason.STOP
        if position.target is not None and price <= position.target:
            return ExitReason.TARGET
    return None


def exit_fill_price(position: Position, price: float, reason: ExitReason) -> float:
    """The price a stop/target exit is booked at.

    Stops book at the level itself (a realistic-to-slightly-optimistic paper
    assumption — no stop slippage modelled); targets book at the level; manual/EOD
    book at the live price.
    """
    if reason is ExitReason.STOP and position.stop is not None:
        return position.stop
    if reason is ExitReason.TARGET and position.target is not None:
        return position.target
    return price


@dataclass(frozen=True, slots=True)
class OrderDecision:
    """Outcome of submitting an order: either a fill or a rejection reason."""

    fill: Fill | None
    rejected_reason: str | None = None

    @property
    def accepted(self) -> bool:
        return self.fill is not None


def decide_order(
    request: OrderRequest,
    ref_price: float,
    ts: object,
    *,
    execution: ExecutionModel,
) -> OrderDecision:
    """Validate and price an order into a fill-or-reject decision (pure)."""
    from datetime import datetime

    error = request.validate()
    if error is not None:
        return OrderDecision(fill=None, rejected_reason=error)
    price = execution.fill_price(request.side, request.order_type, ref_price, request.limit_price)
    if price is None:
        return OrderDecision(fill=None, rejected_reason="unmarketable (no fill at reference price)")
    # Guard stop/target against the actual fill price.
    long = request.side is OrderSide.BUY
    if request.stop is not None:
        if long and request.stop >= price:
            return OrderDecision(fill=None, rejected_reason="stop must be below the fill price")
        if not long and request.stop <= price:
            return OrderDecision(fill=None, rejected_reason="stop must be above the fill price")
    assert isinstance(ts, datetime)
    return OrderDecision(
        fill=Fill(
            symbol=request.symbol,
            side=request.side,
            quantity=request.quantity,
            price=price,
            ts=ts,
        )
    )
