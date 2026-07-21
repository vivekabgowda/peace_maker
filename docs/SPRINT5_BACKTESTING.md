# Sprint 5 — Backtesting Harness

> Turns each strategy's performance from an *assumption* into an *earned* number.
> The same plugin code runs live and in backtest, so a green backtest is real
> evidence about the live edge — not a separate model.

## 1. Why this closes a loop

Sprints 3–4 shipped the Alpha Engine and the AI Committee. Both already *consume*
`StrategyStats` (win rate, profit factor, expectancy, false-positive rate): the
scoring engine's regime dimension leans on a strategy's win rate once it's
**proven** (≥30 samples), and the committee weights proven strategies more
heavily. Until now those stats were neutral defaults. The backtester populates
them for real and feeds them straight back into the live registry.

## 2. Design — strictly causal replay

The `Backtester` walks a symbol's bars forward one at a time. At bar *i* it
reconstructs exactly the `StrategyContext` the live scanner would have built from
bars `0..i` — the **same** incremental indicator bundle and the **same**
relative-strength math — evaluates the strategy, and on a signal simulates the
trade on the bars that follow.

- **No look-ahead.** Bar *i* never sees bar *i+1*; entry is the signal bar's
  close, exits use only subsequent bars.
- **One position at a time.** After a trade the walk skips forward past its
  holding period — no pyramiding, no overlapping trades per symbol.
- **O(n·k), not O(n²).** Indicators are precomputed once per symbol (incremental,
  causal); the trailing window handed to the strategy is capped at
  `required_history`, since strategies only scan recent bars.

### Trade simulation conventions (documented for honesty)

| Rule | Choice |
|---|---|
| Entry | Signal bar's close |
| Exit | First of: stop hit, first target hit, or time-stop |
| Ambiguous bar (spans stop *and* target) | **Stop assumed first** (pessimistic) |
| Time-stop | Close at `max_holding_bars` (default 20) → outcome `TIMEOUT` |
| P&L unit | **R-multiple** = P&L ÷ initial risk, direction-adjusted |

## 3. Metrics

`BacktestResult` computes, per strategy: trades, win rate, **profit factor** (gross
win-R ÷ gross loss-R), **expectancy** (avg R/trade — the edge), average holding,
**max drawdown** (peak-to-trough of the cumulative-R equity curve), and the
**false-positive rate** (share of signals that lost or timed out flat) — the
engine's discipline metric. `to_stats()` projects these into the live
`StrategyStats`.

## 4. Feeding the live engine

```
Backtester.run(strategy, bars) → BacktestResult → apply_to_registry([...])
                                                        │
                        registry[strategy].stats ◄──────┘  (now proven)
                                    │
        ScoringEngine (regime dim uses win rate) + Committee (weights proven)
```

`apply_to_registry` is opt-in (the API's `apply_stats=true`), so a scan's scoring
only shifts to earned numbers when you deliberately promote a backtest.

## 5. False-positive analysis

The Sprint 3 brief called for false-positive analysis. `false_positive_rate`
surfaces per strategy: a strategy that triggers often but mostly loses or times
out flat scores a high rate and is easy to disable via the allow-list. Combined
with expectancy and profit factor, this is the strategy-validation gate.

## 6. Performance

Cost is dominated by the incremental indicator engine (separately benchmarked at
~0.6 ms/update). A 3-symbol × 300-bar backtest with full indicators runs in
~0.5 s; the perf test guards against O(n²) walk regressions. The backtest is pure
and deterministic, so results are reproducible run to run.

## 7. Scope & honesty

The harness backtests strategies on a **single primary timeframe** with an
optional benchmark series for relative-strength / index-trend inputs. That
faithfully covers the daily swing family (EMA trend/pullback, momentum, volume
breakout, VCP, relative strength/weakness). Intraday, session-dependent
strategies (ORB, VWAP, gap, CPR) need intraday bars and session reconstruction —
they simply abstain here and are the next harness increment. No strategy is
special-cased; each runs through the identical replay.

## 8. Testing

`tests/unit/backtesting/` + `tests/integration/backtesting/` (15 tests):

- **Simulator:** target-win, stop-loss, stop-first ambiguity, time-stop, and
  correct R-multiple sign for longs and shorts.
- **Metrics:** win rate, profit factor, expectancy, max drawdown, equity curve,
  false-positive rate, `to_stats` projection.
- **Engine:** produces trades + metrics; no-look-ahead (short series → no trades);
  one-position-at-a-time advances past the holding period; performance budget.
- **Stats wiring:** `apply_to_registry` marks a strategy proven and shifts live
  scoring — with a fixture that restores default stats so other suites are
  unaffected.
- **API:** auth required; single-strategy metrics; `apply_stats=true` updates the
  registry.

## 9. REST API

| Endpoint | Description |
|---|---|
| `GET /api/v1/backtest/run?strategy=&history=&apply_stats=` | Backtest one or all enabled strategies over stored candles; optionally promote the earned stats into the live registry |

## 10. Module map

| File | Responsibility |
|---|---|
| `backtesting/models.py` | `Trade`, `TradeOutcome`, `BacktestResult` (+ metrics, `to_stats`) |
| `backtesting/simulator.py` | Pure trade simulation (stop/target/time-stop) |
| `backtesting/engine.py` | `Backtester` — causal bar-by-bar replay |
| `backtesting/stats.py` | `apply_to_registry` — promote earned stats |
| `backtesting/service.py` + `api.py` | Repository-backed runner + REST |
