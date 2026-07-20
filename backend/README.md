# BKN AI Capital — Backend

Production FastAPI backend. Clean Architecture, async SQLAlchemy 2.x, Alembic,
Pydantic v2, JWT auth, structured logging, and Prometheus metrics.

> Sprint 1 scope: foundational infrastructure + authentication only. No trading,
> scanning, or AI logic yet.

## Layout

```
app/
├── main.py            # app factory (middleware, handlers, router, lifespan)
├── core/              # config, logging, security, database, redis, errors, DI
├── api/v1/router.py   # aggregates module routers under /api/v1
├── modules/           # bounded contexts (auth, users, health today; more later)
│   └── <module>/      # models · schemas · repository · service · router
├── shared/            # pure, reusable helpers (indicators, calendar — later)
├── workers/           # Celery app (later sprints)
└── websocket/         # WS gateway (later sprints)
migrations/            # Alembic (async env, versioned migrations)
tests/                 # unit + integration (pytest, async)
scripts/seed.py        # idempotent seed
```

Each module maps to Clean Architecture layers: `service.py` = application,
`repository.py`/`models.py` = infrastructure, `schemas.py`/`router.py` = delivery.

## Local development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Run against the compose Postgres/Redis (see infra/), or export BKN_* vars.
alembic upgrade head          # apply migrations
python -m scripts.seed        # seed the initial admin
uvicorn app.main:app --reload # http://localhost:8000/docs
```

## Configuration

All settings come from environment variables prefixed `BKN_` (see
`infra/env/.env.dev.example`). Key ones: `BKN_ENV`, `BKN_DATABASE_URL`,
`BKN_REDIS_URL`, `BKN_JWT_SECRET_KEY`.

## Quality gates

```bash
ruff check app tests scripts     # lint
black --check app tests scripts  # format
mypy app                         # strict typing
pytest                           # tests + coverage
```

## Endpoints (Sprint 1)

| Method | Path | Auth |
|--------|------|------|
| GET | `/api/v1/health/live` | — |
| GET | `/api/v1/health/ready` | — |
| POST | `/api/v1/auth/register` | — |
| POST | `/api/v1/auth/login` | — |
| POST | `/api/v1/auth/refresh` | — |
| POST | `/api/v1/auth/logout` | — |
| GET | `/api/v1/me` | Bearer |
| PATCH | `/api/v1/me/profile` | Bearer |
| GET | `/metrics` | — (Prometheus) |

Interactive docs at `/docs`; OpenAPI at `/api/v1/openapi.json`.
