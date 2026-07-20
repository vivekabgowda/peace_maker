# 02 — Folder Structure

A **monorepo** keeps the frontend, backend, infra, and docs versioned together
and makes cross-cutting changes atomic.

## 1. Top-Level Layout

```
peace_maker/
├── README.md
├── docs/                        # Architecture & design (this set)
│   ├── 00-overview.md … 12-security-compliance.md
│   ├── adr/                     # Architecture Decision Records
│   └── diagrams/
├── backend/                     # Python / FastAPI application
├── frontend/                    # Next.js / TypeScript application
├── automation/                  # n8n workflow exports
├── infra/                       # Docker, compose, deployment, IaC
├── scripts/                     # Dev & ops scripts (seed, migrate, lint)
├── .github/                     # CI/CD workflows, PR templates
├── docker-compose.yml           # Local full-stack topology
├── Makefile                     # Common developer commands
└── .env.example
```

## 2. Backend (`backend/`) — Clean Architecture

The backend follows **Clean Architecture**: dependencies point *inward*. The
`domain` layer knows nothing about FastAPI, SQLAlchemy, or Redis. Each core
module is a self-contained package with the same internal shape.

```
backend/
├── pyproject.toml               # deps, tool config (ruff, mypy, pytest)
├── app/
│   ├── main.py                  # FastAPI app factory, router mounting
│   ├── core/                    # Cross-cutting infrastructure
│   │   ├── config.py            # Pydantic Settings (12-factor)
│   │   ├── logging.py           # Structured logging setup
│   │   ├── security.py          # JWT, hashing, RBAC
│   │   ├── database.py          # Engine, session, unit-of-work
│   │   ├── redis.py             # Redis client, pub/sub helpers
│   │   ├── di.py                # Dependency-injection container/providers
│   │   ├── errors.py            # Domain error types + API envelope
│   │   └── telemetry.py         # OTel, metrics, correlation IDs
│   │
│   ├── modules/                 # One package per bounded context
│   │   ├── auth/
│   │   │   ├── domain/          # Entities, value objects, interfaces (ports)
│   │   │   ├── application/     # Use cases / services (business logic)
│   │   │   ├── infrastructure/  # Repos (SQLAlchemy), adapters
│   │   │   ├── api/             # FastAPI routers + schemas (DTOs)
│   │   │   └── tests/
│   │   ├── users/
│   │   ├── market_data/
│   │   ├── scanner/
│   │   ├── strategy/
│   │   ├── ai_engine/
│   │   │   ├── domain/
│   │   │   ├── agents/          # Specialist agent implementations
│   │   │   ├── orchestration/   # Fusion, ranking, prompt templates
│   │   │   ├── application/
│   │   │   ├── infrastructure/  # LLM client adapters, caching
│   │   │   └── api/
│   │   ├── risk/
│   │   ├── portfolio/
│   │   ├── journal/
│   │   ├── backtesting/
│   │   ├── notifications/
│   │   ├── analytics/
│   │   └── admin/
│   │
│   ├── workers/                 # Celery app + task definitions
│   │   ├── celery_app.py
│   │   ├── scanner_tasks.py
│   │   ├── ai_tasks.py
│   │   ├── backtest_tasks.py
│   │   └── schedules.py         # Beat schedule (market-hours aware)
│   │
│   ├── websocket/               # WS gateway, connection manager
│   │   ├── gateway.py
│   │   └── channels.py
│   │
│   └── shared/                  # Reusable domain-neutral helpers
│       ├── indicators/          # EMA, RSI, MACD, ATR, VWAP, Supertrend…
│       ├── market_calendar/     # NSE holidays, session windows
│       ├── types/               # Shared value objects (Money, Percent…)
│       └── pagination.py
│
├── migrations/                  # Alembic migrations
│   ├── env.py
│   └── versions/
├── tests/                       # Cross-module integration & e2e tests
│   ├── integration/
│   ├── contract/                # API contract tests vs OpenAPI
│   └── conftest.py
└── Dockerfile
```

### Why this shape
- **Per-module `domain/application/infrastructure/api`** enforces SOLID and makes
  each module independently testable and extractable into a service later.
- **`shared/indicators`** is pure, deterministic, and heavily unit-tested — the
  quant core must be trustworthy and provider-agnostic.
- **`workers/`** isolates async/heavy work; the request path stays fast.

## 3. Frontend (`frontend/`) — Next.js App Router

```
frontend/
├── package.json
├── tsconfig.json
├── tailwind.config.ts
├── next.config.mjs
├── src/
│   ├── app/                     # App Router (route = folder)
│   │   ├── (auth)/login/
│   │   ├── (app)/
│   │   │   ├── dashboard/
│   │   │   ├── scanner/
│   │   │   ├── live-market/
│   │   │   ├── watchlist/
│   │   │   ├── journal/
│   │   │   ├── portfolio/
│   │   │   ├── analytics/
│   │   │   ├── settings/
│   │   │   └── admin/
│   │   ├── layout.tsx           # Root layout, dark theme, providers
│   │   └── api/                 # Route handlers (BFF proxy if needed)
│   │
│   ├── components/
│   │   ├── ui/                  # Design-system primitives (Button, Card…)
│   │   ├── charts/              # TradingView wrappers, sparklines
│   │   ├── market/              # Quote tiles, option chain, heatmaps
│   │   ├── recommendations/     # Recommendation card, risk panel
│   │   └── layout/              # Sidebar, topbar, command palette
│   │
│   ├── features/                # Feature-scoped logic (mirrors backend)
│   │   ├── scanner/
│   │   ├── portfolio/
│   │   ├── journal/
│   │   └── recommendations/
│   │
│   ├── lib/
│   │   ├── api-client/          # Typed client (generated from OpenAPI)
│   │   ├── websocket/           # WS hooks, reconnection
│   │   ├── auth/                # Token handling, guards
│   │   └── format/              # ₹, %, time (IST) formatters
│   │
│   ├── hooks/                   # useLiveQuote, useRecommendations, …
│   ├── stores/                  # Client state (Zustand)
│   ├── types/                   # Shared TS types (generated + hand-written)
│   └── styles/
├── public/
└── Dockerfile
```

### Frontend conventions
- **Types generated from the backend OpenAPI schema** → the frontend and backend
  never drift on contracts.
- **`features/` mirror backend `modules/`** so a developer reasons about the same
  bounded context on both sides.
- Server Components for data-heavy pages; Client Components for live/interactive
  widgets.

## 4. Infrastructure (`infra/`)

```
infra/
├── docker/
│   ├── backend.Dockerfile
│   ├── frontend.Dockerfile
│   └── nginx/
├── compose/
│   ├── docker-compose.dev.yml
│   ├── docker-compose.staging.yml
│   └── docker-compose.prod.yml
├── env/
│   ├── .env.dev.example
│   ├── .env.staging.example
│   └── .env.prod.example
├── observability/
│   ├── prometheus/
│   ├── grafana/
│   └── loki/
└── db/
    ├── init/                    # Postgres init (extensions: timescaledb)
    └── seed/                    # Seed data (instrument master, calendars)
```

## 5. Automation (`automation/`)

```
automation/
└── n8n/
    ├── workflows/               # Exported n8n workflow JSON
    │   ├── notification-router.json
    │   ├── eod-report.json
    │   └── news-ingest.json
    └── README.md
```

## 6. Naming & Conventions

| Item | Convention |
|------|-----------|
| Python modules/packages | `snake_case` |
| Python classes | `PascalCase` |
| TS components | `PascalCase.tsx` |
| TS hooks | `useCamelCase.ts` |
| API routes | `/api/v1/kebab-or-plural-nouns` |
| DB tables | `snake_case`, plural (`recommendations`) |
| Env vars | `UPPER_SNAKE_CASE`, prefixed `BKN_` |
| Branches | `type/scope-short-desc` |
| Commits | Conventional Commits (`feat:`, `fix:`, `docs:` …) |
