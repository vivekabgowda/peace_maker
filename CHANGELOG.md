# Changelog

All notable changes to BKN AI Capital are documented here. The format is based
on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). The platform is
**advisory-only** — no release places live broker orders.

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
