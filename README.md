# BKN AI Capital

> Institutional-grade, AI-assisted trading platform for the Indian stock market.
> **The Bloomberg Terminal for retail traders in India.**

BKN AI Capital continuously analyzes the Indian market (NSE/BSE), ranks trading
opportunities, explains its reasoning in plain language, and enforces strict,
non-negotiable risk management. **In Version 1 the platform never places trades
automatically** — every output is a transparent, reviewable *recommendation*.

---

## 📦 Project Status — V1 advisory platform, production-hardened

The full V1 advisory stack is implemented, tested, and hardened. The backend
(FastAPI, async SQLAlchemy, Alembic, JWT/Argon2id auth) and the Next.js
(App Router) frontend are wired end to end against real APIs — **no mock data
in the UI** — with Docker/Compose, CI/CD, and a strict quality gate.

- **Run it locally:** [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) → `make up` (see [Quick start](#quick-start))
- **What's done / what's left for prod:** [docs/DEPLOYMENT_CHECKLIST.md](docs/DEPLOYMENT_CHECKLIST.md)
- **Coding standards:** [docs/CODING_STANDARDS.md](docs/CODING_STANDARDS.md)

**Backend capabilities (Sprints 1–8):**
- **1 — Foundations:** FastAPI, async SQLAlchemy, Alembic, JWT + refresh-cookie auth, Docker/Compose, CI/CD.
- **2 — Market Intelligence:** provider abstraction (+ simulated reference feed), event bus, instrument master, live quote cache, multi-timeframe candle builder, 14-indicator engine, option-chain engine (PCR/max-pain/greeks), news engine, WebSocket gateway. [docs/SPRINT2_MARKET_INTELLIGENCE.md](docs/SPRINT2_MARKET_INTELLIGENCE.md)
- **3 — Alpha Engine:** strategy plugins, regime engine, 11-factor scoring, scanner + Opportunity Book. [docs/SPRINT3_ALPHA_ENGINE.md](docs/SPRINT3_ALPHA_ENGINE.md)
- **4 — AI Committee:** seven specialist agents + CIO synthesis. [docs/SPRINT4_AI_COMMITTEE.md](docs/SPRINT4_AI_COMMITTEE.md)
- **5 — Backtesting:** bar-by-bar replay, trade simulator, earned strategy stats. [docs/SPRINT5_BACKTESTING.md](docs/SPRINT5_BACKTESTING.md)
- **6 — Zerodha Kite Connect:** live market data + OAuth + historical ingestion, **no order placement**. [docs/SPRINT6_ZERODHA.md](docs/SPRINT6_ZERODHA.md)
- **7 — Paper Trading & Analytics:** `make up`/`make down`, health checks, **paper-trading engine**, trade journal, performance analytics, daily/weekly reports — advisory-only. [docs/SPRINT7_LOCAL_DEPLOYMENT.md](docs/SPRINT7_LOCAL_DEPLOYMENT.md)
- **8 — Bring-up & Diagnostics:** clean-machine macOS guide, `/health/diagnostics` endpoint and page. [docs/SPRINT8_MAC_SETUP.md](docs/SPRINT8_MAC_SETUP.md)

**Application pages (Sprints 9–12) — all wired to real APIs:**
- **Dashboard** (live market), **Scanner** (opportunity book), **Charts** (candles/EMA/volume + paper-trade markers).
- **Recommendations** — ranked opportunities with the AI committee's vote and reasoning; filters by strategy/confidence/sector/direction.
- **Portfolio** — paper account summary, positions, equity curve, allocation, risk metrics.
- **Journal / Analytics** — closed-trade book and performance analytics.
- **Settings** — profile, trading defaults, notifications, appearance (accent theming), security.
- **Admin** — RBAC-guarded system health, user/role management, AI-committee configuration, logs, and audit trail.

**Sprint 13 — Production hardening:** app-wide error boundaries, request
timeouts + smart query retries, resilient WebSocket reconnection, mobile/tablet
navigation, lazy-loaded chart bundle, defence-in-depth admin guard, and full
input validation. No new features — polish, reliability, and security only.

Verified gates: backend **Ruff · Black · MyPy(strict) · Pytest (244 tests, 84%)**;
frontend **ESLint · tsc(strict) · Vitest (15 tests) · `next build`**; Compose files validated.

### Quick start
```bash
cp infra/env/.env.dev.example .env
make up          # Postgres+TimescaleDB, Redis, backend, frontend, n8n
make seed        # create the initial admin user
# Frontend → http://localhost:3000   API docs → http://localhost:8000/docs
```

## 📚 Documentation Index

> **⭐ Start here: [docs/SOFTWARE_DESIGN_DOCUMENT.md](docs/SOFTWARE_DESIGN_DOCUMENT.md)**
> — the consolidated, review-ready architecture document (all 12 objectives in one
> place). The numbered docs below are its deep-dive companions.

Read the docs in order — each builds on the previous.

| # | Document | Purpose |
|---|----------|---------|
| 00 | [Overview & Principles](docs/00-overview.md) | Vision, scope, guiding principles, non-negotiables |
| 01 | [System Architecture](docs/01-architecture.md) | High-level topology, C4 views, tech stack rationale |
| 02 | [Folder Structure](docs/02-folder-structure.md) | Monorepo layout for backend, frontend, infra |
| 03 | [Database Schema](docs/03-database-schema.md) | PostgreSQL schema, tables, relationships, indexing |
| 04 | [API Design](docs/04-api-design.md) | REST + WebSocket contracts, auth, versioning |
| 05 | [Service Architecture](docs/05-service-architecture.md) | Module boundaries, Clean Architecture, DI |
| 06 | [AI Agent System](docs/06-ai-agents.md) | Multi-agent design, orchestration, recommendation fusion |
| 07 | [Scanner Engine](docs/07-scanner-engine.md) | Real-time market scanning pipeline and indicators |
| 08 | [Risk Management](docs/08-risk-management.md) | Position sizing, risk limits, invalidation rules |
| 09 | [Frontend & UI/UX](docs/09-frontend-ui.md) | Pages, wireframes, component system, real-time UX |
| 10 | [Deployment & DevOps](docs/10-deployment.md) | Docker, CI/CD, environments, observability |
| 11 | [Roadmap & Sprint Plan](docs/11-roadmap.md) | Phases, milestones, sprint-by-sprint plan |
| 12 | [Security & Compliance](docs/12-security-compliance.md) | AuthZ, secrets, SEBI/regulatory posture, auditing |

## 🧱 Tech Stack (summary)

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js (App Router), TypeScript, Tailwind CSS, TradingView charts |
| Backend | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.x |
| AI/Agents | LLM orchestration layer + deterministic quant engine |
| Database | PostgreSQL 16 (+ TimescaleDB for time-series) |
| Cache / Streams | Redis 7 (cache, pub/sub, rate limiting) |
| Message/Task | Celery + Redis (or n8n for orchestration workflows) |
| Automation | n8n (alerting, scheduled workflows, integrations) |
| Auth | JWT (access + refresh), OAuth-ready |
| Deploy | Docker + Docker Compose (dev), container orchestration (prod) |
| VCS/CI | GitHub + GitHub Actions |

## 🔌 API usage examples

All routes are under `/api/v1`. Auth uses a short-lived **access token**
(returned in the JSON body) plus a rotating **httpOnly refresh cookie** — so a
CLI client keeps a cookie jar and sends the access token as a bearer header.
Interactive docs: `http://localhost:8000/docs`.

```bash
API=http://localhost:8000/api/v1

# 1) Register (sets the refresh cookie in cookies.txt; returns an access token)
curl -s -c cookies.txt -X POST "$API/auth/register" \
  -H 'Content-Type: application/json' \
  -d '{"email":"trader@example.com","password":"s3cure-passw0rd"}'

# 2) Log in later and capture the access token into a shell variable
TOKEN=$(curl -s -c cookies.txt -X POST "$API/auth/login" \
  -H 'Content-Type: application/json' \
  -d '{"email":"trader@example.com","password":"s3cure-passw0rd"}' \
  | python -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')
AUTH="Authorization: Bearer $TOKEN"

# 3) Who am I (profile + preferences)
curl -s "$API/me" -H "$AUTH"

# 4) Ranked opportunity book (advisory)
curl -s "$API/alpha/opportunities?top=10" -H "$AUTH"

# 5) Convene the AI committee on one symbol
curl -s "$API/committee/review?symbol=RELIANCE" -H "$AUTH"

# 6) Submit a PAPER order (simulated fill at the live price — never a broker)
curl -s -X POST "$API/paper/orders" -H "$AUTH" -H 'Content-Type: application/json' \
  -d '{"symbol":"RELIANCE","side":"buy","quantity":10}'

# 7) Refresh the access token using the cookie (no body)
curl -s -b cookies.txt -X POST "$API/auth/refresh"
```

> There is **no** endpoint anywhere that places a live broker order — order
> routes fill against live, read-only prices in the paper-trading engine only.

## 🛡️ The Non-Negotiables

1. **No auto-execution in V1.** Recommendations only.
2. **Risk management is a hard gate**, not a suggestion. A recommendation that
   violates risk limits is never surfaced.
3. **Every recommendation is explainable** — context, technicals, risks, and
   invalidation conditions are always attached.
4. **AI predictions never substitute for sound risk management.**
5. **Never increase exposure after losses. Never chase. Always size positions.**

## 🗺️ How to Navigate This Repo (today)

```
peace_maker/
├── README.md          ← you are here
├── Makefile           ← make up / down / seed / validate / logs
├── docker-compose.yml ← Postgres+TimescaleDB, Redis, backend, frontend
├── backend/           ← FastAPI app (app/), Alembic migrations, tests
│   └── app/modules/   ← auth, market_data, scanner, committee, paper_trading,
│                        analytics, journal, admin, … (one module per domain)
├── frontend/          ← Next.js App Router (src/app, src/features, src/lib)
├── infra/             ← env templates, nginx, deployment assets
└── docs/              ← architecture & design deliverables (00–12 + sprints)
```

---

*BKN AI Capital is a decision-support platform. It does not provide investment
advice under any regulatory definition, and it does not execute trades in V1.
See [docs/12-security-compliance.md](docs/12-security-compliance.md).*
