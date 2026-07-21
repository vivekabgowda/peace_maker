# Sprint 3 — Institutional Alpha Engine

> Advisory only (V1). The Alpha Engine analyses the NSE universe, explains why a
> trade exists, ranks every opportunity, rejects weak setups, and recommends
> **NO TRADE** when conditions are poor. It places **no** orders.

## 1. What was built

An end-to-end alpha pipeline layered on the (production-ready) market-data
platform:

```
                 ┌─────────────────────────────────────────────────────────┐
   market data → │ Regime Engine → Strategy plugins → 11-factor Scoring →   │
  (candles,      │ Explainability → Opportunity Book (rank + NO-TRADE) →    │ → /alpha
   indicators)   │ Portfolio Awareness (correlation / sector / risk caps)   │
                 └─────────────────────────────────────────────────────────┘
```

Every stage after context assembly is **pure and deterministic**, so the whole
engine is unit-testable and behaves identically in a live scan and a backtest.

### Module map

| Package | Responsibility |
|---|---|
| `app/modules/strategy/base.py` | Plugin contracts: `Strategy`, `StrategyContext`, `StrategySignal`, `Series`, `Bar`, `StrategyStats` |
| `app/modules/strategy/registry.py` | `@register()` plugins, enable/disable, discovery |
| `app/modules/strategy/regime_types.py` | `MarketRegime` taxonomy (14 states), hostile/overlay/primary sets |
| `app/modules/strategy/ta.py` | Pure helpers: SMA, CPR/pivots, contraction, slope |
| `app/modules/strategy/library/` | Strategy plugins (breakout / trend / momentum / volatility / gap) |
| `app/modules/scanner/regime.py` | **Market Regime Engine** (Step 1) |
| `app/modules/scanner/macro_events.py` | RBI / Budget / Election event calendar |
| `app/modules/ai_engine/scoring.py` | **11-factor scorecard** (Step 4) |
| `app/modules/scanner/opportunity.py` | Ranking, Top-N, **NO-TRADE** verdict (Step 5) |
| `app/modules/scanner/explain.py` | Structured **explainability** (Step 6) |
| `app/modules/portfolio/awareness.py` | Correlation / sector / risk **portfolio** caps (Step 7) |
| `app/modules/scanner/engine.py` | `AlphaScanner` — pure orchestration |
| `app/modules/scanner/context.py` | Repository-backed context assembly (the I/O seam) |
| `app/modules/scanner/service.py` + `api.py` | Async facade + read-only REST |

## 2. Market Regime Engine (Step 1)

Classifies one **primary** structure regime plus any active **overlays** from the
benchmark index series and the calendars:

- **Primary:** Trending Bull, Trending Bear, Range, Accumulation, Distribution
  (from EMA stack + ADX + range position + drift/breadth).
- **Volatility overlays:** High / Low Volatility (daily ATR as % of price).
- **Event overlays:** Expiry Day, RBI Day, Budget Day, Election Event
  (weekly-expiry + macro calendars).
- **Gap / risk overlays:** Gap-Up Trend, Gap-Down Panic, Global Risk-Off
  (session gap vs. prior close, or an external SGX/VIX cue).

`RegimeState.is_hostile` (Global Risk-Off or Gap-Down Panic) is the platform's
first gate — **every strategy checks the regime before firing**, and a hostile
regime forces a NO-TRADE book.

## 3. Strategy plugin architecture (Step 2)

Each strategy is a stateless plugin declaring its `compatible_regimes`,
`required_history`, and `expected_holding`. It receives a read-only
`StrategyContext` and returns at most one fully-reasoned `StrategySignal`
(direction, entry, stop, targets, calibrated confidence, rationale bullets,
features) — or `None` to **abstain**. No strategy is hardcoded into the scanner;
enabling/disabling is data (`BKN_ALPHA_ENABLED_STRATEGIES`).

**Implemented in this sprint (13, covering every family):**

| Key | Strategy | Family | Horizon |
|---|---|---|---|
| `orb` | Opening Range Breakout | breakout | intraday |
| `vwap_breakout` | VWAP Breakout | breakout | intraday |
| `volume_breakout` | Volume Breakout | breakout | swing |
| `cpr_breakout` | CPR Breakout | breakout | intraday |
| `ema_trend` | EMA Trend | trend | 1–3 weeks |
| `ema_pullback` | EMA Pullback | trend | 3–10 days |
| `vwap_pullback` | VWAP Pullback | trend | intraday |
| `momentum` | Momentum | momentum | 3–15 days |
| `relative_strength` | Relative Strength | momentum | 1–4 weeks |
| `relative_weakness` | Relative Weakness | momentum | 1–3 weeks |
| `vcp` | Volatility Contraction Pattern | volatility | 2–6 weeks |
| `gap_and_go` | Gap & Go | gap | intraday |
| `gap_fill` | Gap Fill | gap | intraday |

Each carries a `StrategyStats` container (win rate, profit factor, expectancy,
false-positive rate) that the backtester populates; until a strategy is *proven*
(≥30 samples) the scorer treats it as unproven and leans on live technicals.

> **Roadmap — remaining library.** The brief lists ~34 strategies. The framework
> is complete and the remaining names (SMC/Order Blocks/Liquidity Sweep/FVG/BOS/
> CHoCH, Darvas, Stage Analysis, Cup & Handle, Flag/Triangle/Rectangle, OI
> build-up/short-covering/long-build-up, PCR extremes, IV expansion/crush,
> sector rotation, breadth thrust, index confirmation) are **pure plugin
> additions** — a new module in `library/`, no changes to the engine, scoring,
> ranking, or API. They land incrementally, each with its own tests and backtest.

## 4. Eleven-factor AI scoring (Step 4)

Every candidate is scored 0–100 on **technical, volume, trend, volatility,
liquidity, sector, news, options, regime, risk, portfolio-impact**, combined
into a weighted composite and a calibrated confidence. Regime and risk carry the
heaviest weights, and a hostile regime applies a hard penalty — a great setup in
a bad tape does not rank. Each dimension is a documented function of observable
features, leaving a clean seam to swap any single dimension for a learned model
later.

## 5. Opportunity Book, ranking & NO-TRADE (Step 5)

The book sorts qualified candidates by composite, assigns ranks, and exposes the
Top-N. It returns **NO-TRADE** when: the regime is hostile, nothing clears the
quality bar (`MIN_COMPOSITE = 55`), or the best composite is below the conviction
floor (`MIN_BEST_COMPOSITE = 60`). A NO-TRADE book shows **no** recommendations —
standing aside means an empty book with a reason.

## 6. Explainability (Step 6)

Every opportunity answers: **why this** (strategy rationale + risk/reward),
**why now** (regime + overlays + trend/volume support), **biggest risk** (the
weakest scored dimension), **invalidation** (the stop and its distance), and a
**confidence breakdown** (all 11 dimensions). *Why not others?* is answered by
the book — each opportunity carries its rank and composite versus peers.

## 7. Portfolio awareness (Step 7)

A greedy pass over the ranked book (best-first) enforces: **correlation
de-duplication** (same sector + direction ≥ threshold is a duplicate), **sector
concentration** caps, a **position count** cap, and a **gross daily-risk** budget.
Existing holdings can be passed in to keep the new book coherent with the book
already on.

## 8. Testing (Step 8)

`tests/unit/alpha/` + `tests/integration/alpha/` (37 tests):

- **Regime:** all primary regimes, volatility/event/gap overlays, risk-off.
- **Strategies:** each fires on its setup and **abstains** otherwise; confidence
  is bounded; compatibility gating.
- **Scoring & ranking:** all 11 dimensions bounded; hostile-regime penalty;
  strict composite ordering; below-floor and hostile **NO-TRADE**.
- **Explainability:** all six questions answered.
- **Portfolio:** sector cap, correlation dedup, opposite-direction allowed, risk
  budget, held-position accounting.
- **End-to-end + API:** full scan produces a ranked, explained book; hostile
  regime and empty universe return NO-TRADE; `/alpha` endpoints require auth and
  return well-formed payloads.

**False-positive discipline** is enforced structurally: strategies abstain by
default, the quality bar rejects sub-threshold candidates, and hostile regimes
veto the whole book — the engine never forces a trade.

## 9. REST API (read-only, advisory)

| Endpoint | Description |
|---|---|
| `GET /api/v1/alpha/regime` | Current market regime + overlays + features |
| `GET /api/v1/alpha/strategies` | Strategy library, enabled flags, and stats |
| `GET /api/v1/alpha/opportunities?fno=&top=` | Ranked Opportunity Book (Top-N) or NO-TRADE |

## 10. Configuration

| Setting | Default | Meaning |
|---|---|---|
| `BKN_ALPHA_BENCHMARK` | `NIFTY` | Index used for regime + relative strength |
| `BKN_ALPHA_ENABLED_STRATEGIES` | *(empty = all)* | CSV allow-list of strategy keys |

## 11. Explicitly out of scope for this sprint

Order execution, position sizing beyond risk budgeting, the live backtesting
harness that populates `StrategyStats` (framework hooks are in place), and the
~21 remaining library strategies (pure plugin additions). No "Buy" signal is ever
produced without full reasoning, and no trade is forced when conditions are poor.
