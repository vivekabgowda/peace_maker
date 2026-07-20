# Sprint 1 — Deployment Readiness Checklist

Status of the foundational infrastructure, and everything that must be true
before the **first production deployment** to the Hostinger VPS.

> **Do not deploy yet.** Sprint 1 delivers deployment *readiness*, not a
> deployment. This checklist is the gate for that first release.

Legend: ✅ done & verified · 🔧 provided, needs environment-specific values ·
⬜ not started (later sprint or a human/ops action).

---

## A. What Sprint 1 delivered (verified)

### Backend
- ✅ FastAPI app factory with lifespan, CORS, metrics, OpenAPI at `/api/v1/openapi.json`.
- ✅ SQLAlchemy 2.x async engine with pooling; `Base` + `TimestampMixin`.
- ✅ Alembic (async env) + initial migration (extensions + identity tables); renders valid Postgres SQL.
- ✅ Pydantic v2 typed settings (12-factor, `BKN_` prefix).
- ✅ Redis client lifecycle + readiness ping.
- ✅ JWT auth: register, login, refresh (with rotation + reuse detection), logout; Argon2id hashing.
- ✅ RBAC (`user`/`admin`) + protected routes (`/me`, `/me/profile`).
- ✅ Structured JSON logging with per-request correlation IDs.
- ✅ Consistent error envelope + typed domain errors.
- ✅ Health endpoints: `/health/live`, `/health/ready`.
- ✅ Prometheus metrics at `/metrics`.
- ✅ Seed mechanism (idempotent admin seed).
- ✅ Quality gates green: **Ruff, Black, MyPy (strict), Pytest — 19 tests, 88% coverage.**

### Frontend
- ✅ Next.js App Router + TypeScript (strict) + Tailwind (dark-first design tokens).
- ✅ Zustand auth store + TanStack Query provider.
- ✅ Auth framework wired to the backend (login/register), route guard, protected app shell.
- ✅ Sidebar + Topbar + navigation; responsive; dark theme.
- ✅ Empty pages for all 9 modules (Dashboard, Scanner, Charts, Recommendations, Portfolio, Journal, Analytics, Settings, Admin).
- ✅ Quality gates green: **ESLint (0 warnings), tsc, Vitest, `next build` (14 routes, standalone).**

### Infrastructure & tooling
- ✅ Backend & frontend multi-stage Dockerfiles (non-root, healthchecks).
- ✅ `docker-compose.yml` (dev) and `infra/compose/docker-compose.prod.yml` (prod) — both validated with `docker compose config`.
- ✅ Nginx production config (TLS termination, WS upgrade, security headers, metrics ACL).
- ✅ Env templates (`infra/env/.env.dev.example`, `.env.prod.example`).
- ✅ DB init (extensions), startup/ops scripts (`dev-up`, `deploy`, `backup`).
- ✅ Quality config: Ruff, Black, MyPy, ESLint, Prettier, pre-commit, Husky + lint-staged.
- ✅ CI (GitHub Actions): backend lint/type/test, frontend lint/type/test/build, Docker image build (no deploy).
- ✅ Documentation: dev guide, coding standards, backend README, this checklist.

> Docker **image builds run in CI** (the sandbox used for development has no
> Docker daemon); Compose files and Dockerfiles are otherwise validated.

---

## B. Required before the FIRST production deploy

### 1. Provisioning (ops)
- ⬜ Hostinger VPS provisioned (KVM), OS updated.
- ⬜ Non-root deploy user; SSH **key-only** auth; password auth disabled.
- ⬜ Firewall (`ufw`): allow **22, 80, 443** only; `fail2ban` enabled.
- ⬜ Docker + Docker Compose plugin installed.
- ⬜ Unattended security updates enabled.
- ⬜ DNS A/AAAA record → VPS IP for the production domain.

### 2. Secrets & configuration
- 🔧 Copy `infra/env/.env.prod.example` → `.env` on the VPS (`chmod 600`).
- ⬜ Generate a strong `BKN_JWT_SECRET_KEY` (`openssl rand -hex 32`).
- ⬜ Set strong, unique `BKN_DB_PASSWORD` and `BKN_REDIS_PASSWORD`.
- ⬜ Set `BKN_CORS_ORIGINS` to the real HTTPS origin.
- ⬜ Set `BKN_BACKEND_IMAGE` / `BKN_FRONTEND_IMAGE` to the released registry tags.

### 3. TLS / Nginx
- ⬜ Replace `bkn.example.com` in `infra/docker/nginx/prod.conf` with the real domain.
- ⬜ Issue Let's Encrypt certs (Certbot webroot) into `infra/certs/` (`fullchain.pem`, `privkey.pem`).
- ⬜ Configure **auto-renewal** (systemd timer / cron) + Nginx reload on renew.

### 4. CI/CD (registry & deploy)
- ⬜ Enable pushing images to a registry (GHCR) on tagged releases (currently build-only).
- ⬜ Add a manual, approval-gated `deploy` workflow that SSHes to the VPS and runs `scripts/deploy.sh`.
- ⬜ Add repo secrets: registry token, VPS host/user, SSH deploy key.

### 5. Database & backups
- ⬜ First `alembic upgrade head` on the prod DB (the `migrate` service runs it).
- ⬜ Verify `timescaledb` + `pgcrypto` extensions present (init script + migration).
- ⬜ Schedule nightly `scripts/backup.sh` via cron.
- ⬜ Configure **off-VPS** backup sync (object storage) and test a **restore** once.

### 6. Observability & operations
- 🔧 Prometheus scrape config provided; ⬜ stand up Prometheus + Grafana (or hosted) and confirm `/metrics` is scraped.
- ⬜ Ship structured logs to a store (Loki/hosted); confirm correlation IDs flow.
- ⬜ Configure uptime/health alerting on `/api/v1/health/ready`.
- ⬜ Author incident runbooks (provider outage, DB restore, emergency stop).

### 7. Security sign-off
- ⬜ Confirm Postgres/Redis are **not** published on the host (prod compose keeps them internal — verify).
- ⬜ Dependency/image/secret scans green.
- ⬜ Rotate the seeded admin password immediately after first login.
- ⬜ Legal/compliance review of disclaimers (advisory-only posture) before public access.

### 8. Smoke test (post-deploy, before announcing)
- ⬜ `https://<domain>/` loads (frontend, valid cert, HSTS present).
- ⬜ `GET /api/v1/health/ready` → `200 {"status":"ready"}` (DB + Redis up).
- ⬜ Register → login → `/me` works end to end over HTTPS.
- ⬜ `/metrics` reachable only from the internal network.

---

## C. Explicitly out of scope for Sprint 1 (later sprints)

Market data, scanners, broker integrations, AI agents, trading logic,
WebSocket live feeds, portfolio/journal/analytics, and backtesting are **not**
part of Sprint 1 and must not be started until Sprint 1 is accepted. See the
[roadmap](11-roadmap.md).

---

## D. Sprint 1 acceptance

Sprint 1 is complete when Section A is verified (✅ — done) and the team has
reviewed this checklist. Production go-live is gated on Section B.
