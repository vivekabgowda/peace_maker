"""Realistic Indian transaction costs and slippage (Sprint 14).

The Sprint 7 :class:`FeeModel` used a single blended bps figure. That is
frictionless enough to flatter a strategy's edge, which is exactly what the CIO
due-diligence report flagged. This module models the *actual* statutory cost
stack for NSE trades so paper P&L reflects what a real account would keep, and a
volatility/size-aware slippage model so fills aren't unrealistically clean.

Everything here is pure and deterministic — no I/O, no clock — so every rupee is
unit-tested against hand-worked cases. Defaults encode the prevailing statutory
rates (2024) and are overridable via settings; they are documented inline so the
file cannot silently drift from reality.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.modules.paper_trading.models import OrderSide


class Segment(StrEnum):
    """Instrument segment — determines which charges apply and at what rate."""

    EQUITY_DELIVERY = "equity_delivery"
    EQUITY_INTRADAY = "equity_intraday"
    FUTURES = "futures"
    OPTIONS = "options"


@dataclass(frozen=True, slots=True)
class CostBreakdown:
    """Exact per-side cost decomposition (all values in INR, >= 0)."""

    brokerage: float
    stt: float
    exchange_txn: float
    gst: float
    sebi: float
    stamp_duty: float

    @property
    def total(self) -> float:
        return round(
            self.brokerage + self.stt + self.exchange_txn + self.gst + self.sebi + self.stamp_duty,
            4,
        )

    def as_dict(self) -> dict[str, float]:
        return {
            "brokerage": round(self.brokerage, 4),
            "stt": round(self.stt, 4),
            "exchange_txn": round(self.exchange_txn, 4),
            "gst": round(self.gst, 4),
            "sebi": round(self.sebi, 4),
            "stamp_duty": round(self.stamp_duty, 4),
            "total": self.total,
        }


@dataclass(frozen=True, slots=True)
class IndianCostModel:
    """Computes the statutory + brokerage cost of one side of an NSE trade.

    Rates default to prevailing 2024 values. Brokerage is the discount-broker
    model (min of a flat fee and a percentage, per executed order); delivery
    equity is brokerage-free at most discount brokers. STT and stamp duty are
    charged asymmetrically (buy vs sell) exactly as the exchanges levy them.
    """

    # Brokerage: min(flat_fee, pct * turnover) per side; 0 flat ⇒ pure percentage.
    brokerage_flat: float = 20.0
    brokerage_pct: float = 0.0003  # 0.03%
    # Exchange transaction charge (fraction of turnover), NSE.
    exch_txn_equity: float = 0.0000297  # 0.00297%
    exch_txn_futures: float = 0.0000173  # 0.00173%
    exch_txn_options: float = 0.0003503  # 0.03503% (on premium)
    # GST on (brokerage + exchange txn + sebi).
    gst_rate: float = 0.18
    # SEBI turnover fee (fraction of turnover).
    sebi_rate: float = 0.000001  # ₹10 per crore
    # STT (fraction of turnover). Asymmetric: see _stt().
    stt_delivery: float = 0.001  # 0.1% both buy & sell
    stt_intraday_sell: float = 0.00025  # 0.025% sell only
    stt_futures_sell: float = 0.0002  # 0.02% sell only
    stt_options_sell: float = 0.001  # 0.1% sell only, on premium
    # Stamp duty (fraction of turnover), buy side only.
    stamp_delivery: float = 0.00015  # 0.015% buy
    stamp_intraday: float = 0.00003  # 0.003% buy
    stamp_futures: float = 0.00002  # 0.002% buy
    stamp_options: float = 0.00003  # 0.003% buy

    def _brokerage(self, segment: Segment, turnover: float) -> float:
        if segment is Segment.EQUITY_DELIVERY:
            return 0.0  # delivery is typically brokerage-free at discount brokers
        pct = self.brokerage_pct * turnover
        if self.brokerage_flat <= 0:
            return pct
        return min(self.brokerage_flat, pct) if pct > 0 else 0.0

    def _stt(self, segment: Segment, side: OrderSide, turnover: float) -> float:
        is_sell = side is OrderSide.SELL
        if segment is Segment.EQUITY_DELIVERY:
            return self.stt_delivery * turnover  # both sides
        if segment is Segment.EQUITY_INTRADAY:
            return self.stt_intraday_sell * turnover if is_sell else 0.0
        if segment is Segment.FUTURES:
            return self.stt_futures_sell * turnover if is_sell else 0.0
        return self.stt_options_sell * turnover if is_sell else 0.0

    def _exch_txn(self, segment: Segment, turnover: float) -> float:
        if segment in (Segment.EQUITY_DELIVERY, Segment.EQUITY_INTRADAY):
            return self.exch_txn_equity * turnover
        if segment is Segment.FUTURES:
            return self.exch_txn_futures * turnover
        return self.exch_txn_options * turnover

    def _stamp(self, segment: Segment, side: OrderSide, turnover: float) -> float:
        if side is not OrderSide.BUY:
            return 0.0  # stamp duty is buy-side only
        rate = {
            Segment.EQUITY_DELIVERY: self.stamp_delivery,
            Segment.EQUITY_INTRADAY: self.stamp_intraday,
            Segment.FUTURES: self.stamp_futures,
            Segment.OPTIONS: self.stamp_options,
        }[segment]
        return rate * turnover

    def charges(
        self,
        *,
        notional: float,
        side: OrderSide,
        segment: Segment = Segment.EQUITY_INTRADAY,
    ) -> CostBreakdown:
        """Full per-side cost breakdown for a trade of ``notional`` rupees."""
        turnover = abs(notional)
        brokerage = self._brokerage(segment, turnover)
        exch = self._exch_txn(segment, turnover)
        sebi = self.sebi_rate * turnover
        stt = self._stt(segment, side, turnover)
        stamp = self._stamp(segment, side, turnover)
        gst = self.gst_rate * (brokerage + exch + sebi)
        return CostBreakdown(
            brokerage=brokerage,
            stt=stt,
            exchange_txn=exch,
            gst=gst,
            sebi=sebi,
            stamp_duty=stamp,
        )

    def charge(
        self,
        *,
        notional: float,
        side: OrderSide,
        segment: Segment = Segment.EQUITY_INTRADAY,
    ) -> float:
        """Per-side total cost — the `CostModel` seam used by the paper service."""
        return self.charges(notional=notional, side=side, segment=segment).total

    def cost(self, notional: float) -> float:
        """`FeeModel`-compatible shim: sell-side total (worst case, includes STT)."""
        return self.charges(notional=notional, side=OrderSide.SELL).total


@dataclass(frozen=True, slots=True)
class SlippageModel:
    """Volatility- and size-aware slippage. Flat-bps is the zero-vol, zero-size case.

    The fill is moved against the taker by:
      base half-spread (bps) + volatility term (k_vol * ATR%) + impact term
      (k_size * size_ratio), where size_ratio = order qty / typical bar volume.
    All terms are non-negative; a BUY fills higher, a SELL lower.
    """

    base_spread_bps: float = 1.0
    k_vol_bps: float = 5.0  # bps per 1.0 of ATR% (i.e. per 1% ATR)
    k_size_bps: float = 10.0  # bps per 1.0 of size_ratio

    def offset_bps(self, *, atr_pct: float = 0.0, size_ratio: float = 0.0) -> float:
        """Total one-way slippage in bps (>= half the base spread)."""
        vol = self.k_vol_bps * max(0.0, atr_pct)
        impact = self.k_size_bps * max(0.0, size_ratio)
        return self.base_spread_bps / 2.0 + vol + impact

    def fill_price(
        self,
        *,
        ref_price: float,
        side: OrderSide,
        atr_pct: float = 0.0,
        size_ratio: float = 0.0,
    ) -> float:
        if ref_price <= 0:
            return ref_price
        slip = ref_price * self.offset_bps(atr_pct=atr_pct, size_ratio=size_ratio) / 10_000.0
        return ref_price + slip if side is OrderSide.BUY else ref_price - slip
