"""Cost-aware, out-of-sample strategy evaluation (Sprint 14).

The backtester replays signals frictionlessly in R-multiples. This layer:

1. Converts realistic round-trip costs (Indian charges + slippage) into an R
   haircut per trade — so expectancy is measured *net*, as the CIO report
   requires. Costs bite harder on tight-stop trades (cost is a larger fraction
   of the per-unit risk), which is realistic.
2. Splits the trade history into contiguous temporal folds and checks whether
   the net edge persists out-of-sample across time, rather than resting on one
   lucky period.

Pure functions over the backtester's :class:`Trade` list — no DB, no re-running
the engine — so it is fully unit-testable.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.modules.backtesting.models import Trade
from app.modules.paper_trading.costs import IndianCostModel, Segment, SlippageModel
from app.modules.paper_trading.models import OrderSide
from app.modules.validation.bootstrap import bootstrap_ci
from app.modules.validation.deflated_sharpe import evaluate_returns
from app.modules.validation.statistics import mean


def roundtrip_cost_bps(
    *,
    cost_model: IndianCostModel,
    slippage: SlippageModel,
    notional: float,
    segment: Segment,
    atr_pct: float = 0.0,
) -> float:
    """Round-trip (buy+sell) cost in basis points of notional at a reference size."""
    buy = cost_model.charge(notional=notional, side=OrderSide.BUY, segment=segment)
    sell = cost_model.charge(notional=notional, side=OrderSide.SELL, segment=segment)
    cost_bps = (buy + sell) / notional * 10_000.0 if notional > 0 else 0.0
    # Slippage is charged on entry and exit (two crossings of the spread).
    slip_bps = 2.0 * slippage.offset_bps(atr_pct=atr_pct)
    return cost_bps + slip_bps


def cost_in_r(trade: Trade, *, roundtrip_bps: float) -> float:
    """Round-trip cost expressed in units of the trade's initial risk (R)."""
    risk = trade.risk_per_unit
    if risk <= 0:
        return 0.0
    per_unit_cost = roundtrip_bps / 10_000.0 * trade.entry
    return per_unit_cost / risk


def net_r_series(trades: Sequence[Trade], *, roundtrip_bps: float) -> list[float]:
    """Per-trade net R after deducting the cost haircut."""
    return [t.r_multiple - cost_in_r(t, roundtrip_bps=roundtrip_bps) for t in trades]


def _profit_factor(rs: Sequence[float]) -> float:
    gain = sum(r for r in rs if r > 0)
    loss = -sum(r for r in rs if r < 0)
    return gain / loss if loss > 0 else 0.0


@dataclass(frozen=True, slots=True)
class Fold:
    index: int
    n_trades: int
    net_expectancy_r: float
    win_rate: float

    def as_dict(self) -> dict[str, float | int]:
        return {
            "index": self.index,
            "n_trades": self.n_trades,
            "net_expectancy_r": round(self.net_expectancy_r, 4),
            "win_rate": round(self.win_rate, 4),
        }


def walk_forward(
    trades: Sequence[Trade], *, roundtrip_bps: float, folds: int = 4, n_trials: int = 1
) -> dict[str, object]:
    """Net-of-cost, out-of-sample-consistency report for one strategy's trades."""
    ordered = sorted(trades, key=lambda t: t.exit_ts)
    net_all = net_r_series(ordered, roundtrip_bps=roundtrip_bps)
    gross_all = [t.r_multiple for t in ordered]
    n = len(ordered)

    fold_reports: list[Fold] = []
    if n >= folds >= 1:
        size = n // folds
        for i in range(folds):
            lo = i * size
            hi = n if i == folds - 1 else (i + 1) * size
            seg = ordered[lo:hi]
            seg_net = net_all[lo:hi]
            if not seg:
                continue
            wins = sum(1 for r in seg_net if r > 0)
            fold_reports.append(
                Fold(
                    index=i,
                    n_trades=len(seg),
                    net_expectancy_r=mean(seg_net),
                    win_rate=wins / len(seg),
                )
            )

    positive_folds = sum(1 for f in fold_reports if f.net_expectancy_r > 0)
    consistency = positive_folds / len(fold_reports) if fold_reports else 0.0
    ci = bootstrap_ci(net_all, mean, resamples=1000)
    sharpe_eval = evaluate_returns(net_all, n_trials=n_trials)

    return {
        "n_trades": n,
        "gross_expectancy_r": round(mean(gross_all), 4),
        "net_expectancy_r": round(mean(net_all), 4),
        "net_profit_factor": round(_profit_factor(net_all), 4),
        "cost_drag_r": round(mean(gross_all) - mean(net_all), 4),
        "roundtrip_cost_bps": round(roundtrip_bps, 4),
        "expectancy_ci": ci.as_dict(),
        "sharpe": sharpe_eval,
        "folds": [f.as_dict() for f in fold_reports],
        "oos_consistency": round(consistency, 4),
        "verdict_significant": bool(ci.significant and ci.point > 0),
    }
