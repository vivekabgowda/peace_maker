"""Unit tests for the pure paper-trading engine (fills, exits, P&L)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from app.modules.paper_trading.engine import (
    ExecutionModel,
    FeeModel,
    decide_order,
    exit_fill_price,
    exit_signal,
)
from app.modules.paper_trading.models import (
    ExitReason,
    OrderRequest,
    OrderSide,
    OrderType,
    Position,
)

TS = datetime(2026, 1, 27, 5, 0, tzinfo=UTC)


# -- Execution model --------------------------------------------------------
def test_market_buy_pays_up_and_sell_gets_hit() -> None:
    ex = ExecutionModel(slippage_bps=10)  # 10 bps = 0.10% -> 0.1 on a price of 100
    buy = ex.fill_price(OrderSide.BUY, OrderType.MARKET, 100.0, None)
    sell = ex.fill_price(OrderSide.SELL, OrderType.MARKET, 100.0, None)
    assert buy == pytest.approx(100.1)
    assert sell == pytest.approx(99.9)


def test_limit_fills_only_when_marketable() -> None:
    ex = ExecutionModel(slippage_bps=0)
    # Buy limit at 100 while market is 99 -> marketable, fills at/under limit.
    assert ex.fill_price(OrderSide.BUY, OrderType.LIMIT, 99.0, 100.0) == pytest.approx(99.0)
    # Buy limit at 100 while market is 101 -> not marketable.
    assert ex.fill_price(OrderSide.BUY, OrderType.LIMIT, 101.0, 100.0) is None
    # Sell limit at 100 while market is 101 -> marketable.
    assert ex.fill_price(OrderSide.SELL, OrderType.LIMIT, 101.0, 100.0) == pytest.approx(101.0)
    # Sell limit at 100 while market is 99 -> not marketable.
    assert ex.fill_price(OrderSide.SELL, OrderType.LIMIT, 99.0, 100.0) is None


def test_zero_reference_price_never_fills() -> None:
    assert ExecutionModel().fill_price(OrderSide.BUY, OrderType.MARKET, 0.0, None) is None


# -- Order decision ---------------------------------------------------------
def _req(**kw: object) -> OrderRequest:
    base: dict[str, object] = {"symbol": "TCS", "side": OrderSide.BUY, "quantity": 10}
    base.update(kw)
    return OrderRequest(**base)  # type: ignore[arg-type]


def test_decide_rejects_bad_quantity() -> None:
    d = decide_order(_req(quantity=0), 100.0, TS, execution=ExecutionModel())
    assert not d.accepted and d.rejected_reason == "quantity must be positive"


def test_decide_rejects_stop_on_wrong_side_of_fill() -> None:
    # Long with a stop above the fill price is nonsensical.
    d = decide_order(_req(stop=105.0, target=120.0), 100.0, TS, execution=ExecutionModel(0))
    assert not d.accepted and "stop must be below" in (d.rejected_reason or "")


def test_decide_accepts_valid_long() -> None:
    d = decide_order(_req(stop=95.0, target=110.0), 100.0, TS, execution=ExecutionModel(0))
    assert d.accepted
    assert d.fill is not None
    assert d.fill.price == pytest.approx(100.0)
    assert d.fill.quantity == 10


def test_decide_rejects_unmarketable_limit() -> None:
    d = decide_order(
        _req(order_type=OrderType.LIMIT, limit_price=90.0),
        100.0,
        TS,
        execution=ExecutionModel(0),
    )
    assert not d.accepted and "unmarketable" in (d.rejected_reason or "")


# -- Exit signals -----------------------------------------------------------
def _pos(side: OrderSide, entry: float, stop: float, target: float) -> Position:
    return Position(
        symbol="TCS",
        side=side,
        quantity=10,
        entry_price=entry,
        entry_ts=TS,
        stop=stop,
        target=target,
    )


def test_long_exits_on_stop_and_target() -> None:
    pos = _pos(OrderSide.BUY, 100.0, 95.0, 110.0)
    assert exit_signal(pos, 96.0) is None
    assert exit_signal(pos, 95.0) is ExitReason.STOP
    assert exit_signal(pos, 111.0) is ExitReason.TARGET


def test_short_exits_are_mirrored() -> None:
    pos = _pos(OrderSide.SELL, 100.0, 105.0, 90.0)
    assert exit_signal(pos, 104.0) is None
    assert exit_signal(pos, 105.0) is ExitReason.STOP
    assert exit_signal(pos, 89.0) is ExitReason.TARGET


def test_stop_checked_before_target_when_both_hit() -> None:
    pos = _pos(OrderSide.BUY, 100.0, 95.0, 110.0)
    # A price at/below stop returns STOP even if (hypothetically) target also met.
    assert exit_signal(pos, 95.0) is ExitReason.STOP


def test_exit_fill_price_books_at_level() -> None:
    pos = _pos(OrderSide.BUY, 100.0, 95.0, 110.0)
    assert exit_fill_price(pos, 93.0, ExitReason.STOP) == 95.0
    assert exit_fill_price(pos, 115.0, ExitReason.TARGET) == 110.0
    assert exit_fill_price(pos, 103.0, ExitReason.MANUAL) == 103.0


# -- P&L --------------------------------------------------------------------
def test_long_pnl_and_r_multiple() -> None:
    pos = _pos(OrderSide.BUY, 100.0, 95.0, 110.0)
    pos.exit_price = 110.0
    pos.exit_ts = TS + timedelta(hours=2)
    pos.exit_reason = ExitReason.TARGET
    assert pos.gross_pnl == pytest.approx(100.0)  # (110-100)*10
    assert pos.r_multiple == pytest.approx(2.0)  # risk 5 -> reward 10 = 2R
    assert pos.holding_seconds == pytest.approx(7200.0)


def test_short_profit_when_price_falls() -> None:
    pos = _pos(OrderSide.SELL, 100.0, 105.0, 90.0)
    pos.exit_price = 90.0
    assert pos.gross_pnl == pytest.approx(100.0)  # (100-90)*10
    assert pos.r_multiple == pytest.approx(2.0)  # risk 5 -> reward 10


def test_net_pnl_subtracts_fees() -> None:
    pos = _pos(OrderSide.BUY, 100.0, 95.0, 110.0)
    pos.exit_price = 110.0
    pos.fees = 6.0
    assert pos.net_pnl == pytest.approx(94.0)


def test_fee_model_cost() -> None:
    assert FeeModel(3.0).cost(1_000_000.0) == pytest.approx(300.0)  # 3 bps
    assert FeeModel(0.0).cost(1_000_000.0) == 0.0
