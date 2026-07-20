# BKN AI Capital

> Institutional-grade, AI-assisted trading platform for the Indian stock market.
> **The Bloomberg Terminal for retail traders in India.**

BKN AI Capital continuously analyzes the Indian market (NSE/BSE), ranks trading
opportunities, explains its reasoning in plain language, and enforces strict,
non-negotiable risk management. **In Version 1 the platform never places trades
automatically** — every output is a transparent, reviewable *recommendation*.

---

## 📦 Project Status — Sprint 1 (Foundations) implemented

The architecture is approved and **Sprint 1 (foundational infrastructure) is
implemented and verified**: backend (FastAPI, async SQLAlchemy, Alembic, JWT
auth), frontend (Next.js App Router shell), Docker/Compose, Nginx, CI/CD, and
tooling. No market/scanner/AI/trading logic yet — that follows the roadmap.

- **Run it locally:** [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) → `make up`
- **What's done / what's left for prod:** [docs/DEPLOYMENT_CHECKLIST.md](docs/DEPLOYMENT_CHECKLIST.md)
- **Coding standards:** [docs/CODING_STANDARDS.md](docs/CODING_STANDARDS.md)

Verified gates: backend **Ruff · Black · MyPy(strict) · Pytest (19 tests, 88%)**;
frontend **ESLint · tsc · Vitest · `next build`**; Compose files validated.

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
└── docs/              ← all architecture & design deliverables
    ├── 00-overview.md
    ├── 01-architecture.md
    ├── ...
    └── diagrams/
```

---

*BKN AI Capital is a decision-support platform. It does not provide investment
advice under any regulatory definition, and it does not execute trades in V1.
See [docs/12-security-compliance.md](docs/12-security-compliance.md).*
