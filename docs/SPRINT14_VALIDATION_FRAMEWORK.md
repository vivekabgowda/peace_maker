# Sprint 14 — Quant Validation Framework

> Purpose: implement the **top priority from the CIO Return Due-Diligence report** —
> replace frictionless assumptions with realistic costs, and build the statistical
> machinery to decide whether any strategy has a genuine, cost-surviving edge.
> **No live trading. No new trading features.** This sprint measures; it does not
> add ways to trade.

Prerequisite (satisfied): the real Scanner, Journal, and Analytics pages already
exist on `master` (PR #7). This sprint builds on the existing paper engine,
journal, analytics, and backtester.

---

## 1. Objectives (in order)

1. **Realistic trading costs** — segment-specific Indian charges (brokerage, STT,
   exchange transaction charge, GST, SEBI turnover fee, stamp duty) replacing the
   flat blended-bps `FeeModel`.
2. **Slippage modelling** — spread-, volatility-, and size-aware, replacing the
   flat `slippage_bps`.
3. **Statistical validation** — deflated Sharpe, bootstrap confidence intervals,
   multiple-testing correction, parameter-stability.
4. **Walk-forward testing** — rolling out-of-sample evaluation over historical
   candles using the existing backtester.

All four are computable **without Zerodha** (they run over the existing
backtester and paper journal), which is why they go first.

---

## 2. What already exists (reused, not rebuilt)

- `paper_trading/engine.py` — pure `FeeModel` (flat bps) + `ExecutionModel`
  (flat slippage bps). Injected into `service.py` at the `self._fees.cost(...)`
  seam, so costs can be swapped without touching orchestration.
- `analytics/metrics.py` — Sharpe, profit factor, win rate, max drawdown,
  expectancy, expectancy_r, R-multiple already implemented and unit-tested.
- `backtesting/` — `Backtester.run(strategy, …) -> BacktestResult`, `simulator`,
  `stats.apply_to_registry`, `service`, `api`.

## 3. New components

### 3.1 Costs & slippage (`paper_trading/costs.py`)
- `Segment` enum: `EQUITY_DELIVERY`, `EQUITY_INTRADAY`, `FUTURES`, `OPTIONS`.
- `CostBreakdown` dataclass: brokerage, stt, exchange_txn, gst, sebi, stamp_duty,
  total — per side, exact.
- `IndianCostModel`: computes the breakdown per side for a given segment,
  notional, side, and (for STT/stamp asymmetry) buy/sell. Parameters are
  configurable via settings with documented statutory defaults; all pure and
  deterministic.
- `SlippageModel`: `fill_offset(ref_price, side, *, spread_bps, atr_pct, size_ratio)`
  → base half-spread + volatility term (scaled by ATR%) + size/impact term
  (scaled by order size vs typical volume). Deterministic; flat-bps behaviour is
  the zero-vol, zero-size special case (backwards compatible).
- A `FeeModel`-compatible adapter so `service.py` keeps its `cost(notional)` seam;
  the richer per-side breakdown is recorded on the journal.

### 3.2 Validation module (`app/modules/validation/`)
Pure statistics over `BacktestResult` trade lists and journal trades:

- `metrics.py` — per-trade return series → Sharpe (already in analytics; re-exposed
  for the trade-level series), profit factor, expectancy, R.
- `bootstrap.py` — stationary/iid bootstrap → confidence intervals for expectancy,
  Sharpe, profit factor (percentile CIs; configurable resamples).
- `deflated_sharpe.py` — Deflated Sharpe Ratio (Bailey & López de Prado): adjusts
  the observed Sharpe for the number of trials, skew, and kurtosis; returns the
  probability the true Sharpe > 0.
- `multiple_testing.py` — Benjamini–Hochberg (FDR) and Bonferroni corrections over
  a set of p-values (one per strategy/parameter trial).
- `partition.py` — in-sample / out-of-sample split (time-ordered, no leakage).
- `walk_forward.py` — rolling train→test windows over a bar series; runs the
  backtester per test window and aggregates OOS performance + degradation
  (in-sample vs out-of-sample) per strategy.
- `stability.py` — parameter-stability sweep: evaluate a metric across a parameter
  grid and report the dispersion / plateau (knife-edge detection).
- `service.py` — orchestrates a validation run over the strategy library on stored
  candles; persists a `ValidationRun`.
- `orm.py` — `validation_runs` table (JSON payload of results).
- `api.py` — `GET /validation/runs`, `GET /validation/runs/{id}`,
  `POST /validation/run` (admin-triggered), all read-mostly and advisory.

### 3.3 Database
- Migration `0008_validation` — `validation_runs` (id, kind, params JSON,
  results JSON, created_at). Additive; safe `downgrade`.
- Journal cost columns (optional, phase 1b): `entry_cost`, `exit_cost`,
  `slippage_paid` — additive, nullable, backward compatible.

## 4. Statistical method notes (so the numbers are trustworthy)
- **Deflated Sharpe** guards against selection bias from trying many strategies —
  directly answers the CIO report's overfitting concern.
- **Multiple-testing correction** is applied whenever more than one strategy /
  parameter set is evaluated, so a "significant" winner isn't just the best of N
  random draws.
- **Walk-forward** is time-ordered with no look-ahead; the test window is always
  strictly after the train window.
- **Bootstrap CIs** communicate uncertainty explicitly — a positive expectancy
  with a CI spanning zero is reported as *not yet significant*.
- All estimators are pure functions unit-tested against hand-worked or
  reference-valued cases.

## 5. Files

**Modified**
- `backend/app/core/config.py` — cost/slippage/validation settings.
- `backend/app/modules/paper_trading/{engine.py,service.py}` — use `IndianCostModel`
  + `SlippageModel`; record cost breakdown.
- `backend/app/modules/journal/{orm.py,models.py,service.py}` — optional cost columns.
- `backend/app/api/v1/router.py` — mount validation router.
- `backend/migrations/env.py` — register validation ORM.
- `docs/*`, `README.md`, `CHANGELOG.md`.

**Created**
- `backend/app/modules/paper_trading/costs.py`
- `backend/app/modules/validation/{__init__,metrics,bootstrap,deflated_sharpe,multiple_testing,partition,walk_forward,stability,service,api,orm}.py`
- `backend/migrations/versions/0008_validation.py`
- `backend/tests/unit/paper_trading/test_costs.py`
- `backend/tests/unit/validation/test_{bootstrap,deflated_sharpe,multiple_testing,walk_forward,stability}.py`
- `backend/tests/integration/validation/test_validation_api.py`

## 6. Phases (each independently green, advisory-only)
1. **Costs & slippage** — `costs.py` + wire into paper engine/service + journal cost fields + tests.
2. **Validation core** — bootstrap, deflated Sharpe, multiple-testing, partition, stability (pure) + tests.
3. **Walk-forward** — rolling OOS over the backtester + aggregation + tests.
4. **Service + API + migration** — persist validation runs; expose endpoints; integration test.
5. **Docs + CHANGELOG**, final gates, PR.

## 7. Guardrails
- No order-placement path is added; the paper engine remains the only fill path.
- Default behaviour unchanged unless the new models are configured (backwards
  compatible; flat-cost/zero-slippage remain available for tests).
- Additive migrations with safe downgrade; provider/config-gated.

*Advisory-only. This framework measures whether an edge exists; it never trades.*
