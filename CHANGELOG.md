# Changelog

All notable changes to BKN AI Capital are documented here. The format is based
on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). The platform is
**advisory-only** — no release places live broker orders.

## [Unreleased] — Quant validation framework (Sprint 14, part 1)

Implements the CIO due-diligence report's top priority: replace frictionless
assumptions with realistic costs and add the statistics to decide whether a
strategy has a genuine, cost-surviving edge. **No live trading; measures only.**

### Added

- **Realistic Indian trading costs** (`paper_trading/costs.py`) — `IndianCostModel`
  computes segment-specific statutory charges (brokerage, STT, exchange txn, GST,
  SEBI turnover fee, stamp duty) with buy/sell asymmetry; `SlippageModel` adds
  volatility- and size-aware slippage. Wired into the paper engine via a
  `CostModel` seam and selectable with `paper_cost_model` (default `flat` keeps
  existing behaviour; `realistic` is the honest stack).
- **Statistical validation core** (`validation/`) — Probabilistic and Deflated
  Sharpe (Bailey & López de Prado), percentile bootstrap confidence intervals
  with a significance flag, Bonferroni and Benjamini–Hochberg multiple-testing
  corrections, time-ordered OOS / walk-forward partitioning, and
  parameter-stability analysis. Pure Python (no numpy dependency).
- **Cost-aware walk-forward evaluation** — converts costs into an R haircut per
  trade, splits history into temporal folds, and reports gross vs net
  expectancy, cost drag, net profit factor, bootstrap CI, deflated Sharpe, OOS
  consistency, and a significance verdict.
- **Validation service + API** — `POST /validation/run` (admin) backtests the
  library, applies costs, evaluates each strategy OOS, corrects for multiple
  testing across the library, reports survivors, and persists a run;
  `GET /validation/runs`, `GET /validation/runs/{id}` (authed). New
  `validation_runs` table (migration `0008`).

### Changed

- `BacktestService` exposes `run_results()` (raw results) so the validation
  layer can post-process trades; `run()` behaviour is unchanged.

### Notes

- Additive and backward-compatible: default cost behaviour and existing tests
  are unchanged; the realistic model is opt-in. Advisory-only preserved — no
  order path is added.
- The real Scanner, Journal, and Analytics pages already shipped in PR #7; this
  sprint builds the validation backend on top of the existing engine.

## [Unreleased] — Application layer & production hardening (Sprints 9–13)

Completes the V1 advisory application: every module page is wired to real
backend APIs (no mock data in the UI), plus a full production-hardening pass.

### Added

- **Settings page (Sprint 9)** — Profile (name, email, password change),
  Trading defaults (risk %, daily loss limit, max open trades, timeframe),
  Notifications (email / trade / browser with real permission prompt),
  Appearance (runtime accent theming), and Security (sign out / log out
  everywhere). Backed by a new persisted `preferences` JSON column, a
  `POST /auth/change-password` endpoint (revokes all sessions) and
  `POST /auth/logout-all`.
- **Portfolio page (Sprint 10)** — paper account summary, open positions,
  equity curve, daily returns, allocation, and risk metrics (max drawdown,
  exposure %, win rate, Sharpe, profit factor). Built entirely on existing
  paper-trading and analytics endpoints.
- **Recommendations page (Sprint 11)** — ranked opportunity book with the AI
  committee's vote and full reasoning (bull/bear cases, per-agent
  contributions, veto reasons); filters by strategy, confidence, sector, and
  direction; 30s auto-refresh.
- **Admin dashboard (Sprint 12)** — RBAC-guarded operations console: live
  system health (DB, Redis, market feed, WebSocket, event queue), user & role
  management, **editable AI-committee configuration** (agent enable/weight and
  CIO thresholds, applied at deliberation time), an in-process log ring buffer,
  and an append-only audit trail. New `committee_config` and `audit_log` tables
  (migration `0007`).
- **Production hardening (Sprint 13)** — app-wide error boundaries, request
  timeouts, resilient WebSocket reconnection, mobile/tablet navigation, a
  lazy-loaded chart bundle, and a defence-in-depth admin route guard. Added
  API-client tests. This changelog and an updated README.

### Changed

- The AI committee's Chief Investment Officer is now configurable (role
  weights + conviction thresholds) with backward-compatible defaults; the
  committee reads the persisted operator configuration when deliberating.
- The header ticker strip now shows **real** index quotes (Nifty, Bank Nifty,
  Sensex, VIX) instead of static placeholders, reusing the dashboard's query
  cache.
- The app shell loads the current user once, app-wide, fixing role-based
  navigation gating and removing duplicate `/me` requests.
- `/charts` no longer ships the ~50 kB charting library on initial load
  (lazy-loaded via `next/dynamic`): first-load JS dropped from ~159 kB to
  ~96 kB.
- API client: enforces a 15s request timeout and normalizes network/timeout
  failures; TanStack Query retries transient errors but never a 4xx.

### Removed

- The placeholder `EmptyState` component and all "arriving in Sprint N"
  placeholder copy from module pages.

### Security

- New privileged endpoints are admin-only (RBAC); role changes and committee
  configuration edits are recorded in the audit trail. Password changes and
  "log out everywhere" revoke all refresh tokens.

### Notes

- **No breaking API changes.** New columns are additive (`user_profiles.preferences`,
  the new admin tables) with safe defaults; existing endpoints are unchanged.
- Advisory-only is preserved end to end — no code path places a live broker order.

## [0.1.0-alpha] — Foundations through Charts (Sprints 1–8)

Backend platform (auth, market intelligence, alpha engine, AI committee,
backtesting, Zerodha read-only data, paper trading, analytics) and the initial
frontend shell with Dashboard, Scanner, Charts, Journal, Analytics, and
Diagnostics pages.
