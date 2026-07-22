"""Unit tests for the realistic Indian cost model + slippage (Sprint 14).

Values are hand-worked from the statutory defaults so a rate change that breaks
the maths is caught immediately.
"""

from __future__ import annotations

import pytest
from app.modules.paper_trading.costs import IndianCostModel, Segment, SlippageModel
from app.modules.paper_trading.models import OrderSide

M = IndianCostModel()
N = 100_000.0  # ₹1,00,000 turnover


def test_equity_intraday_sell_breakdown() -> None:
    b = M.charges(notional=N, side=OrderSide.SELL, segment=Segment.EQUITY_INTRADAY)
    assert b.brokerage == pytest.approx(20.0)  # min(20, 30)
    assert b.exchange_txn == pytest.approx(2.97)
    assert b.sebi == pytest.approx(0.10)
    assert b.stt == pytest.approx(25.0)  # 0.025% sell only
    assert b.stamp_duty == pytest.approx(0.0)  # buy-side only
    assert b.gst == pytest.approx(0.18 * (20.0 + 2.97 + 0.10))
    assert b.total == pytest.approx(52.2226, abs=1e-4)


def test_equity_intraday_buy_has_stamp_not_stt() -> None:
    b = M.charges(notional=N, side=OrderSide.BUY, segment=Segment.EQUITY_INTRADAY)
    assert b.stt == pytest.approx(0.0)
    assert b.stamp_duty == pytest.approx(3.0)  # 0.003% buy
    assert b.total == pytest.approx(30.2226, abs=1e-4)


def test_equity_delivery_is_brokerage_free_but_stt_both_sides() -> None:
    buy = M.charges(notional=N, side=OrderSide.BUY, segment=Segment.EQUITY_DELIVERY)
    sell = M.charges(notional=N, side=OrderSide.SELL, segment=Segment.EQUITY_DELIVERY)
    assert buy.brokerage == 0.0 and sell.brokerage == 0.0
    assert buy.stt == pytest.approx(100.0)  # 0.1% both sides
    assert sell.stt == pytest.approx(100.0)
    assert buy.stamp_duty == pytest.approx(15.0)  # buy only
    assert sell.stamp_duty == pytest.approx(0.0)
    assert buy.total == pytest.approx(118.6226, abs=1e-4)


def test_brokerage_capped_at_flat_fee_for_large_turnover() -> None:
    big = M.charges(notional=10_000_000.0, side=OrderSide.SELL, segment=Segment.EQUITY_INTRADAY)
    assert big.brokerage == pytest.approx(20.0)  # cap, not 0.03% of 1cr


def test_costs_scale_and_are_non_negative() -> None:
    for seg in Segment:
        for side in (OrderSide.BUY, OrderSide.SELL):
            b = M.charges(notional=N, side=side, segment=seg)
            for v in b.as_dict().values():
                assert v >= 0.0
            assert b.total > 0.0


def test_fee_model_shim_matches_sell_total() -> None:
    assert M.cost(N) == pytest.approx(
        M.charges(notional=N, side=OrderSide.SELL, segment=Segment.EQUITY_INTRADAY).total
    )


def test_zero_notional_is_zero_cost() -> None:
    b = M.charges(notional=0.0, side=OrderSide.BUY, segment=Segment.FUTURES)
    assert b.total == pytest.approx(0.0)


# --- slippage ---------------------------------------------------------------

S = SlippageModel()


def test_slippage_flat_when_no_vol_or_size() -> None:
    assert S.offset_bps() == pytest.approx(0.5)  # half of 1bp base spread
    assert S.fill_price(ref_price=100.0, side=OrderSide.BUY) == pytest.approx(100.005)
    assert S.fill_price(ref_price=100.0, side=OrderSide.SELL) == pytest.approx(99.995)


def test_slippage_grows_with_volatility_and_size() -> None:
    off = S.offset_bps(atr_pct=2.0, size_ratio=0.5)
    assert off == pytest.approx(0.5 + 5.0 * 2.0 + 10.0 * 0.5)  # 15.5 bps
    buy = S.fill_price(ref_price=100.0, side=OrderSide.BUY, atr_pct=2.0, size_ratio=0.5)
    assert buy == pytest.approx(100.155, abs=1e-6)


def test_slippage_always_against_the_taker() -> None:
    buy = S.fill_price(ref_price=250.0, side=OrderSide.BUY, atr_pct=1.0, size_ratio=0.2)
    sell = S.fill_price(ref_price=250.0, side=OrderSide.SELL, atr_pct=1.0, size_ratio=0.2)
    assert buy > 250.0 > sell


def test_slippage_ignores_negative_inputs() -> None:
    assert S.offset_bps(atr_pct=-5.0, size_ratio=-1.0) == pytest.approx(0.5)


# --- service selection ------------------------------------------------------


def test_service_selects_cost_model_from_settings() -> None:
    from unittest.mock import MagicMock

    from app.core.config import get_settings
    from app.modules.paper_trading.engine import FeeModel
    from app.modules.paper_trading.service import PaperTradingService

    base = get_settings()
    realistic = base.model_copy(update={"paper_cost_model": "realistic"})
    flat = base.model_copy(update={"paper_cost_model": "flat"})

    assert isinstance(PaperTradingService(MagicMock(), settings=realistic)._fees, IndianCostModel)
    assert isinstance(PaperTradingService(MagicMock(), settings=flat)._fees, FeeModel)
