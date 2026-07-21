# BKN AI Capital — Full Technical Report

_Generated: 2026-07-21 · Default branch `master` @ `79199b9c` (v0.1.0-alpha) · Status: alpha, advisory-only_

> **What this is.** BKN AI Capital is an institutional-grade, AI-assisted,
> **advisory-only** trading platform for the Indian (NSE) equity/F&O market. It
> ingests market data, detects setups, runs them past a committee of analyst
> agents, backtests strategies, and lets users **paper-trade** — with **no live
> broker order-placement path anywhere in the codebase**, by design.
>
> **Honest framing up front:** the backend engine is substantial and CI-green;
> the **frontend is mostly placeholder**; the **"AI committee" agents are
> deterministic rule engines, not LLM calls** (the interface is built to swap in
> LLMs later); and several modules (`risk`, `notifications`, `admin`) are stubs
> whose logic currently lives elsewhere or is not yet built. Details in
> §11–§13.

---

## 1. System Architecture

**Style:** modular monolith in code, service-oriented at runtime. Pure-core /
thin-I/O-shell throughout — deterministic engines (indicators, strategies,
scoring, committee, backtest, paper fills) are pure functions, identical live and
in tests.

**Runtime processes (two entrypoints, one codebase):**
- **API** (`app.main:app`, FastAPI/uvicorn) — auth, REST, WebSocket fan-out. Never ingests.
- **Feed** (`python -m app.feed`, single-instance, lock-guarded) — the ingestion + workers pipeline.

```mermaid
flowchart LR
  subgraph Feed process (single instance)
    PROV[MarketProvider<br/>simulated / zerodha] --> BUS[Async event bus]
    BUS --> CB[Candle builder] --> IND[Indicator engine]
    BUS --> PT[Paper position manager]
    RS[Report scheduler] --> DB
    IND --> DB[(Postgres+TimescaleDB)]
    BUS --> RSTR[(Redis Streams)]
    BUS --> CACHE[(Redis quote cache)]
  end
  subgraph API process (N workers)
    REST[REST /api/v1] --> DB
    REST --> CACHE
    WS[WebSocket gateway] --> RSTR
  end
  FE[Next.js frontend] --> REST
  FE <-. live quotes .-> WS
  n8n[n8n automation] --> REST
```

**Key architectural decisions**
- **Provider abstraction** (`MarketProvider` ABC + registry): the platform never depends on a concrete broker; `simulated` and `zerodha` are drop-in.
- **Second seam for the SDK** (Sprint 6): SDK-agnostic `KiteHttpPort`/`KiteTickerPort` Protocols so `kiteconnect` is imported only in lazy adapters and the module is fully testable with fakes.
- **Typed async event bus**: fire-and-forget publish, bounded per-subscriber queues + dead-letter, Prometheus metrics — one slow consumer can't backpressure ingestion.
- **Cross-instance fan-out**: Redis Streams bridge so any API worker can push WS events (R3).
- **Decoupled workers**: supervised loops (crash → backoff → circuit breaker → heartbeat) for quote stream, option poll, session watch, news poll, paper-position manager, report scheduler.

---

## 2. Folder Structure

```
peace_maker/
├── backend/                     # FastAPI service (~14.9k LOC Python)
│   ├── app/
│   │   ├── main.py              # API app factory
│   │   ├── feed/                # dedicated ingestion process + health server (:8001)
│   │   ├── api/v1/router.py     # aggregates all module routers
│   │   ├── core/                # config, database, redis, security, dependencies, logging, errors
│   │   ├── workers/             # report scheduler CLI
│   │   ├── websocket/           # WS gateway, channels
│   │   ├── shared/              # events (bus/types/stream), indicators, market_calendar, supervision, types
│   │   └── modules/             # bounded contexts (see §5, §6)
│   │       ├── market_data/ committee/ strategy/ paper_trading/ broker/
│   │       ├── scanner/ analytics/ backtesting/ auth/ news/ journal/
│   │       ├── ai_engine/ health/ users/ portfolio/
│   │       └── risk/ notifications/ admin/           # stubs
│   ├── migrations/versions/     # Alembic 0001–0005
│   └── tests/                   # unit/ + integration/ (42 files, 227 tests)
├── frontend/                    # Next.js App Router (~1.4k LOC TS/TSX)
│   └── src/{app,components,features,lib,stores,types}/
├── infra/                       # compose(prod), db init, nginx, observability(prometheus/grafana), env templates
├── automation/n8n/             # workflow JSON (weekly report)
├── scripts/                     # dev-up / dev-down / validate / backup / deploy / seed
├── docs/                        # 00–12 numbered docs + SPRINT2–8 + reviews + this report
├── docker-compose.yml           # dev stack
└── Makefile                     # up/down/purge/validate/report/test/lint
```

---

## 3. Technology Stack

| Layer | Choices |
|---|---|
| **Backend** | Python 3.12, FastAPI 0.115, uvicorn + gunicorn, Pydantic v2 / pydantic-settings |
| **Persistence** | PostgreSQL 16 + **TimescaleDB 2.17** (hypertables), SQLAlchemy 2.0 async + asyncpg, Alembic (async) |
| **Cache / streams** | Redis 7 (hot quote cache, WS tickets, Redis Streams fan-out) |
| **Auth / security** | JWT (PyJWT), Argon2id (passlib/argon2-cffi), Fernet (cryptography) for broker-token-at-rest |
| **Observability** | structlog (JSON), prometheus-client, Grafana dashboard |
| **Broker (optional)** | Zerodha `kiteconnect` (extra; market-data + auth only) |
| **Frontend** | Next.js (App Router, standalone output), React 18, TypeScript, TanStack Query, Zustand, Tailwind CSS |
| **Testing** | pytest + pytest-asyncio + coverage + fakeredis (backend); Vitest + Testing Library + jsdom (frontend) |
| **Quality gates** | Ruff, Black, MyPy `--strict` (backend); Prettier, ESLint, tsc (frontend) |
| **Infra** | Docker + Compose, Nginx (prod), n8n (automation) |
| **Test DB** | SQLite (aiosqlite) default + real Postgres+Timescale in CI |

---

## 4. Database Schema

**14 tables across 5 migrations** (`0001`→`0005`, linear, single head; migration test does `upgrade head → downgrade base → upgrade head` on real Timescale each CI run).

| Domain | Tables | Notes |
|---|---|---|
| Identity | `users`, `user_profiles`, `refresh_tokens` | Argon2 hashes, RBAC role, risk-profile, rotating refresh tokens |
| Market data | `instruments`, `candles`*, `market_indicators`*, `option_chain_snapshots`* | `*` = TimescaleDB **hypertables** (compression + retention policies in `0003`); `candles` PK `(instrument_id, timeframe, ts)`; option snapshots natural composite PK `(underlying, expiry, ts)` |
| News | `news_articles` | normalized/deduped, sentiment + impact + symbol/sector mapping |
| Broker | `broker_tokens` | one row/broker, **Fernet-encrypted** access token, expiry |
| Paper trading | `paper_accounts`, `paper_orders`, `paper_positions` | `Numeric(18,4)` money, FK cascade, status indexes |
| Journal & analytics | `journal_entries`, `performance_reports` | denormalized P&L/R/outcome per closed trade; stored daily/weekly reports |

All money is `Numeric(18,4)`; all timestamps `DateTime(timezone=True)`; constraint naming convention enforced for reliable Alembic autogenerate.

---

## 5. AI Agents (AI Investment Committee)

**Seven specialist agents review the same `CommitteeBrief`, each emits a structured `AgentReport` with `Finding`s citing exact rules; a CIO synthesizes the final decision.**

| Agent | Focus |
|---|---|
| Chief Market Strategist | regime alignment, thesis coherence |
| Technical Analyst | indicator/structure confirmation |
| Options Analyst | PCR / max-pain / IV / OI positioning |
| News Analyst | catalyst sentiment & impact |
| Risk Manager | risk-gating, invalidation, sizing sanity |
| Portfolio Manager | correlation/exposure/concentration |
| Devil's Advocate | adversarial counter-case |

**→ CIO synthesis** (`cio.py`) weights/vetoes/measures disagreement and calibrates confidence into a final, explainable recommendation. Orchestrated by `committee.py` + `service.py`, exposed at `/api/v1/committee`, with Prometheus metrics.

> **Important:** every agent is a **deterministic rule engine**, not an LLM call —
> there is no `anthropic`/`openai`/LLM dependency in the stack. This is a
> deliberate explainability choice; the `Agent.review(brief) -> report` interface
> is intentionally narrow so any agent can later be swapped for an LLM-backed
> analyst without touching the CIO/orchestrator/API. **"AI" today means a
> transparent multi-agent expert system, not generative models.**

---

## 6. Trading Engine

There is **no live trading engine** (no order goes to a broker). Two engines exist:

**a) Alpha / signal engine (advisory):** strategy plugin framework (`strategy/base.py`) + a **market-regime engine** + a strategy library (**breakout, gap, momentum, trend, volatility**) → the **scanner** produces an **Opportunity Book** with an **11-factor AI score** (`ai_engine/scoring.py`), risk-reward, full explanation, and a **NO-TRADE verdict** when the environment is hostile. Portfolio-awareness adjusts for existing exposure. Risk-gating (quality floors, hostile-regime standing-aside) lives in `scanner/opportunity.py` + `regime.py`.

**b) Paper-trading engine (Sprint 7):** simulates fills against **live read-only prices**. Pure core (`engine.py`: fill/slippage, direction-aware stop/target exits, P&L, fee model) + DB-authoritative service (`service.py`: cash accounting — open reserves notional+fee, close releases +P&L−fee) + event-driven runner in the feed. Every close writes a `journal_entries` row; analytics + reports roll up from there. REST at `/api/v1/paper`.

**Backtesting (Sprint 5):** bar-by-bar replay + trade simulator (`backtesting/`) produces `BacktestResult`s that feed **earned** `StrategyStats` back into the live scoring engine — so a strategy's live confidence is earned, not assumed.

---

## 7. Risk Management

Risk is currently **distributed, not a standalone service** (the `risk/` module is a
scaffold stub). Implemented controls:
- **Regime gating** — hostile regimes trigger a book-wide NO-TRADE; low regime confidence emits size-down warnings.
- **Quality floors** — `MIN_COMPOSITE` / `MIN_BEST_COMPOSITE` thresholds; sub-threshold setups are suppressed.
- **Committee Risk Manager agent** — per-recommendation risk findings, invalidation levels, sizing sanity; **Devil's Advocate** adds an adversarial veto path.
- **Explicit invalidation + risk-reward** on every opportunity/signal.
- **Paper accounting** — cash can't drift; per-trade fees + slippage modelled.

**Not yet built:** a consolidated Risk Service (portfolio-level circuit breakers, daily/weekly loss limits, anti-chase throttles, position-sizing calculator). The roadmap places these at S12/S15 (M3/M4).

---

## 8. APIs

REST under `/api/v1` (all data endpoints require JWT; `/health/*` are open). 11 routers:

| Prefix | Purpose |
|---|---|
| `/health` | live, ready, **diagnostics** (all-subsystem status) |
| `/auth` | register, login, refresh (rotating), logout |
| `/users` | profile + risk-profile |
| `/market` | providers, status, instruments, indices, quotes, candles, indicators, breadth, option-chain |
| `/news` | ingested, enriched articles |
| `/alpha` (scanner) | scans, Opportunity Book, explanations |
| `/committee` | run the committee, agent opinions, CIO decision |
| `/backtest` | run backtests, apply earned stats |
| `/broker` | Zerodha login-url, OAuth callback, status, historical backfill (**no orders**) |
| `/paper` | submit/close paper orders, positions, account |
| `/journal`, `/analytics` | closed-trade log + notes/tags; summary, equity-curve, by-strategy, daily, reports |
| **WebSocket** | `/api/v1/ws` — authenticated channels, live quote/breadth/candle fan-out |

Auto-generated OpenAPI at `/docs`. The e2e validator asserts **no order-placement endpoint** exists in the schema.

---

## 9. Docker Deployment

**Dev:** `docker-compose.yml` — postgres(+TimescaleDB), redis, backend (auto-migrates on start), **feed** (workers), frontend, n8n. Health checks on every service; `make up` blocks on `docker compose up --wait`. One-command up/down/purge; `make validate` runs the e2e check; `make report` generates a weekly report.

**Prod:** `infra/compose/docker-compose.prod.yml` + Nginx reverse proxy (`infra/docker/nginx/prod.conf`) + `scripts/deploy.sh` (pull → migrate → rolling restart → health-check → rollback on failure). Observability: Prometheus scrape config + Grafana dashboard in `infra/observability/`.

**Images:** multi-stage backend (Python 3.12) and frontend (Next.js standalone) Dockerfiles; both built (no push) in CI. macOS bring-up documented in `docs/SPRINT8_MAC_SETUP.md`.

---

## 10. Current Completion %

Estimates are judgment calls against a **V1 advisory product** and the 18-sprint
beta roadmap (M0–M7). Backend-heavy; frontend-light.

| Area | Completion | Notes |
|---|---:|---|
| Infra / deployment / CI | **95%** | one-command local, prod compose, health, diagnostics, green CI |
| Market data pipeline | **90%** | simulated fully; Zerodha built but unverified live |
| Alpha engine (regime/strategies/scoring/scanner) | **85%** | 5 strategy families; more families + tuning pending |
| AI committee | **70%** | 7 agents + CIO, rule-based (LLM swap pending) |
| Backtesting | **80%** | replay + earned stats; walk-forward/robustness pending |
| Paper trading / journal / analytics / reports | **80%** | works end-to-end; single account, simplified margin |
| Auth / identity / RBAC | **85%** | register/login/refresh/roles solid |
| Risk management (consolidated) | **35%** | distributed controls only; no Risk Service |
| **Frontend UI** | **30%** | shell + login + live dashboard + diagnostics real; journal/analytics/portfolio/scanner/recommendations/charts/admin are placeholders |
| Notifications / alerts | **15%** | n8n weekly-report workflow only |
| Live broker execution | **0% (out of V1 scope)** | advisory-only by design |

**Overall: ~60% of the V1 advisory product; ~45–50% of the full beta (M7) roadmap.** The core advisory *pipeline* is largely complete on the backend; the product-facing UI and the consolidated risk/notification layers are the biggest gaps.

---

## 11. Remaining Roadmap

Per `docs/11-roadmap.md` (18 sprints, phases P0–P7, milestones M0–M7). Built so
far maps to the market-intelligence → alpha → committee → backtesting → broker-data
→ local-deployment → paper-trading slices. Remaining, roughly in order:

1. **Frontend build-out** — real Scanner, Recommendation Detail (reasoning surface), Portfolio, Journal, Analytics, Charts, Admin pages (roadmap S9/S12/S15/S16/S17).
2. **Consolidated Risk Service** — portfolio circuit breakers, daily/weekly loss limits, anti-chase throttles, position sizing (M3/M4).
3. **Recommendation lifecycle** — invalidation monitors, live setup→recommendation promotion, alerting (S12).
4. **Notification Service** — n8n criteria alerts + EOD report + delivery channels (S17).
5. **Live market-data validation** — verify Zerodha against real Kite credentials; subscriptions at scale.
6. **Analytics depth** — attribution, behavioral analytics, richer equity/expectancy views (S17).
7. **Backtesting hardening** — walk-forward, regression harness, robustness (S18).
8. **Beta hardening** — perf/security review, runbooks, load test, onboarding (M7).
9. **Post-V1** — futures support, advanced options, execution (only if/when the product moves beyond advisory).

---

## 12. Known Limitations

- **Advisory-only:** no order execution anywhere (intentional for V1).
- **Frontend is mostly placeholder:** only login, live dashboard, and diagnostics are functional pages; the rest render an `EmptyState` scheduled for later sprints.
- **"AI" is rule-based:** committee agents and news sentiment are deterministic heuristics, not LLMs (swappable by design).
- **Zerodha path unverified live:** built and fully fake-tested, but never exercised against real Kite credentials/market hours.
- **Simulated data by default:** all local/CI runs use the simulated provider.
- **Paper model simplifications:** one default account per user; short "margin" reserves notional; blended-bps fees; stops book at the level (no stop slippage); limit orders that aren't immediately marketable are rejected (no resting book).
- **Diagnostics endpoint is unauthenticated** and `broker_connected` is hardcoded `false` (correct for V1, but not dynamic).
- **Portfolio module** is awareness-only (~145 LOC), not a full position/P&L tracker.
- **Release tag `v0.1.0-alpha` and feature-branch deletion** are pending manual UI actions (sandbox git-proxy blocked tag push / ref delete).

---

## 13. Technical Debt

- **Stub modules** `risk/`, `notifications/`, `admin/` (4 LOC each) — placeholders that imply capability not yet present; risk logic is scattered across scanner/committee and should be consolidated.
- **Frontend/back-end feature skew** — backend endpoints exist (journal/analytics/paper) with no UI consuming them yet; risk of drift.
- **Duplicated tz-coercion** — naive→UTC coercion for SQLite appears in broker, paper_trading, (repository layers); candidate for a shared helper.
- **`# type: ignore` at ORM boundaries** — a few `Numeric`↔`float` and `_utc(...)` casts; acceptable but worth a typed value-object.
- **Single squash commit on `master`** — per-sprint history now lives only in the (still-open) branch/PR record; future work should merge with cleaner intent.
- **No load/perf tests in CI** — micro-benchmarks exist in docs but aren't gated.
- **Provider registry lazy-imports** — pragmatic but slightly implicit; documented.
- **Reports scheduler coverage** — the worker CLI/loop is lightly tested (pure `due_reports` is well-tested; the loop wrapper is not).

---

## 14. Test Coverage

- **Backend:** **227 test functions across 42 files**, unit + integration. Full suite **225 passed / 2 skipped** (the 2 are wall-clock perf gates skipped under coverage tracing). **Line coverage ≈ 84%** (`--cov=app`, no `fail_under` gate). Runs on **SQLite by default and real Postgres+TimescaleDB in CI** (dual-backend, so Postgres-specific paths — ON CONFLICT, native types, tz-aware — are exercised).
  - Test areas: `market_data, alpha (scanner), committee, backtesting, broker, paper_trading, analytics, health, security, shared`.
  - Style: pure engines unit-tested against hand-worked cases; services/APIs integration-tested against the DB with fakeredis (or real Redis in the Postgres job) and dependency-overridden ports (no broker SDK/network in CI).
- **Frontend:** **2 test files / 6 tests** (Vitest) — `utils` and `diagnostics/api`. **This is thin** and the biggest testing gap; grows with the UI build-out.
- **Well-covered:** indicators, strategies, scoring, committee synthesis, backtest stats, paper engine + cash accounting, analytics metrics, diagnostics.
- **Under-covered:** frontend components/pages, the feed supervisor loops, the report scheduler loop wrapper, WebSocket gateway edges.

---

## 15. CI/CD Pipeline

`.github/workflows/ci.yml` — runs on every push and PRs to `master`/`main`/`develop`; concurrency-cancels superseded runs. **Four jobs:**

1. **Backend — lint, type, test:** Ruff → Black `--check` → MyPy `--strict` → Pytest (SQLite + coverage).
2. **Backend — Postgres + TimescaleDB integration:** spins TimescaleDB + Redis services; **migration test = `alembic upgrade head → downgrade base → upgrade head`** (proves reversibility) → Pytest against Postgres + **real Redis**.
3. **Frontend — lint, type, test, build:** Prettier → ESLint (`--max-warnings 0`) → tsc → Vitest → `next build`.
4. **Docker — build images:** buildx builds backend + frontend images (no push), gated on the three test jobs, with GHA layer caching.

**Status:** all four green on `master` @ `79199b9c` (CI run #50). **CD:** no auto-deploy; `scripts/deploy.sh` performs a manual/SSH prod rollout (pull → migrate → rolling restart → health-check → rollback). Pre-commit hooks mirror the lint/format gates locally.

---

### Appendix — codebase size (indicative)

| | LOC |
|---|---:|
| Backend Python (app) | ~14,900 |
| Frontend TS/TSX (src) | ~1,420 |
| Largest modules | market_data 1961 · committee 1614 · strategy 1330 · paper_trading 1223 · broker 1192 · scanner 1027 |
| Tests | 227 backend + 6 frontend |
| Migrations | 5 (14 tables) |
| REST routers | 11 + WebSocket |

_Advisory-only platform. No live broker order placement exists anywhere in the codebase._
