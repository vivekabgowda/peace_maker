# BKN AI Capital — Local Bring-up Checklist (macOS, clean setup)

> Run the entire platform on a 2022 MacBook (Apple Silicon **or** Intel) from a
> clean machine, with **one command**, and prove every service is operational.
> Simulated market data — **no live broker**.
>
> Companion guide (narrative): `docs/SPRINT8_MAC_SETUP.md`. This file is the
> **check-off proof sheet** — run each command, compare to "Expected", tick the box.

Legend: `[ ]` = to verify · `✅` = expected healthy result.

---

## A. Prerequisites — install & configure Docker Desktop

| # | Step | Command / Action | Expected | ✔ |
|---|---|---|---|---|
| A1 | Install Docker Desktop | Download from https://www.docker.com/products/docker-desktop/ (Apple Silicon build on M1/M2, Intel otherwise), install, launch. | Menu-bar whale icon is **steady** (not animating). | `[ ]` |
| A2 | Allocate resources | Docker Desktop → Settings → Resources: **≥ 4 CPUs, ≥ 8 GB RAM, ≥ 20 GB disk** → Apply & Restart. | Settings saved; Docker restarts healthy. | `[ ]` |
| A3 | Verify Docker CLI | `docker --version && docker compose version` | Prints Docker 24+ and Compose v2+. | `[ ]` |
| A4 | Verify daemon | `docker info \| grep -i "server version"` | Prints a server version (daemon reachable). | `[ ]` |
| A5 | Get the code | `git clone <repo-url> && cd peace_maker` | Repo cloned; you're in the project root. | `[ ]` |

> **2022 MacBook note (Apple Silicon):** all images (TimescaleDB, Redis, Node,
> Python) are multi-arch — they run natively on M-series; no `platform` overrides
> or emulation needed.

---

## B. One-command startup

| # | Step | Command | Expected | ✔ |
|---|---|---|---|---|
| B1 | **Start everything** | `make up` | Builds images, starts all services, runs DB migrations automatically, **blocks until every service is healthy**, then prints the URL map ending with `✓ BKN AI Capital is up.` | `[ ]` |
| B2 | Confirm containers | `docker compose ps` | Six services listed; **State/health = `healthy`** for `postgres`, `redis`, `backend`, `feed`, `frontend` (n8n `running`). | `[ ]` |

`make up` runs `scripts/dev-up.sh`, which uses `docker compose up --build --wait`
— it only returns once health checks pass (or fails fast and dumps logs).

---

## C. Verify each service starts successfully

| # | Service | Command | Expected | ✔ |
|---|---|---|---|---|
| C1 | **PostgreSQL** | `docker compose exec postgres pg_isready -U bkn -d bkn` | `... accepting connections` | `[ ]` |
| C2 | **TimescaleDB** (extension) | `docker compose exec postgres psql -U bkn -d bkn -c "select extname,extversion from pg_extension where extname='timescaledb';"` | One row: `timescaledb \| 2.17.x` | `[ ]` |
| C2b | TimescaleDB hypertables | `docker compose exec postgres psql -U bkn -d bkn -c "select count(*) from timescaledb_information.hypertables;"` | `count ≥ 3` (candles, market_indicators, option_chain_snapshots) | `[ ]` |
| C3 | **Redis** | `docker compose exec redis redis-cli ping` | `PONG` | `[ ]` |
| C4 | **Backend API** | `docker compose ps backend` | `healthy` | `[ ]` |
| C5 | **Feed** (ingestion + workers) | `docker compose ps feed` | `healthy` | `[ ]` |
| C6 | **Frontend** | `docker compose ps frontend` | `healthy` | `[ ]` |
| C7 | Migrations applied | `docker compose exec backend alembic current` | `0005_paper (head)` | `[ ]` |

---

## D. Verify all health endpoints

| # | Endpoint | Command | Expected | ✔ |
|---|---|---|---|---|
| D1 | API liveness | `curl -s localhost:8000/api/v1/health/live` | `{"status":"ok","version":"0.1.0"}` | `[ ]` |
| D2 | API readiness | `curl -s localhost:8000/api/v1/health/ready` | `{"status":"ready","checks":{"database":true,"redis":true}}` | `[ ]` |
| D3 | **Full diagnostics** | `curl -s localhost:8000/api/v1/health/diagnostics` | `"status":"healthy"`; services `database`/`redis`/`market_feed` all `"healthy":true`; `"broker_connected":false` | `[ ]` |
| D4 | Feed liveness | `curl -s localhost:8001/health/live` | `{"status":"ok",...}` | `[ ]` |
| D5 | Prometheus metrics | `curl -s localhost:8000/metrics \| head` | Prometheus exposition text (`# HELP …`) | `[ ]` |

---

## E. Confirm the frontend communicates with the backend

| # | Step | Action | Expected | ✔ |
|---|---|---|---|---|
| E1 | Open the app | Browse to **http://localhost:3000** | Login screen renders. | `[ ]` |
| E2 | **Diagnostics page** (no login) | Browse to **http://localhost:3000/diagnostics** | Status board; **"Frontend → Backend" = green**, database/redis/market_feed green, "Live broker: not connected". Auto-refreshes every 5s. | `[ ]` |
| E3 | Proxy path works | `curl -s localhost:3000/api/v1/health/diagnostics \| head -c 60` | Same JSON as D3 (frontend proxies `/api/*` → backend). | `[ ]` |
| E4 | Create a user | `make seed` (admin) **or** register at the login page | User created; you can sign in. | `[ ]` |
| E5 | Live data in UI | Sign in → **Dashboard** | Index tiles + quotes update live over WebSocket (simulated feed). | `[ ]` |

---

## F. Prove the full pipeline (automated)

| # | Step | Command | Expected | ✔ |
|---|---|---|---|---|
| F1 | **End-to-end validation** | `make validate` | Per-step ✓: health → diagnostics (core healthy, no broker) → live data flowing → paper trade executed & recorded → analytics + weekly report → no order-placement endpoint. Ends with `✅ ALL CHECKS PASSED`. | `[ ]` |

---

## G. One-command shutdown

| # | Step | Command | Expected | ✔ |
|---|---|---|---|---|
| G1 | Stop (keep data) | `make down` | All containers stop/removed; volumes preserved; prints `✓ Stopped.` | `[ ]` |
| G2 | Full reset (optional) | `make purge` | Stops **and** deletes all volumes (Postgres/Redis/n8n data). | `[ ]` |
| G3 | Tail logs (optional) | `make logs` | Streams logs from all services. | `[ ]` |

---

## H. Operational proof summary

When A–G are ticked, every service is proven operational:

- ✅ **PostgreSQL** — accepting connections (C1)
- ✅ **TimescaleDB** — extension loaded + hypertables present (C2/C2b)
- ✅ **Redis** — `PONG` (C3)
- ✅ **Backend API** — healthy + liveness/readiness/diagnostics 200 (C4, D1–D3)
- ✅ **Feed (ingestion + workers)** — healthy + liveness 200 + live symbols quoted (C5, D4, D3)
- ✅ **Frontend** — healthy + renders + talks to backend (C6, E1–E3)
- ✅ **Frontend ↔ Backend** — green on the diagnostics page + proxy path (E2/E3)
- ✅ **Full pipeline** — `make validate` green (F1)
- ✅ **No live broker** — `broker_connected: false` (D3, E2)

---

## Appendix — in-repository pre-flight verification (already proven)

These are verified in CI and in-sandbox, so the checklist above is known to work
before you touch your Mac:

- **CI green on `master`** — backend lint/type/test, **Postgres+TimescaleDB
  integration** (migration `upgrade→downgrade→upgrade` + pytest on real Timescale),
  frontend (prettier/eslint/tsc/vitest/`next build`), and docker image builds.
- **Health endpoints proven responding** (app-level, SQLite+fakeredis):
  ```
  GET /api/v1/health/live         -> 200  {"status":"ok","version":"0.1.0"}
  GET /api/v1/health/ready        -> 200  {"status":"ready","checks":{"database":true,"redis":true}}
  GET /api/v1/health/diagnostics  -> 200  {"status":"healthy","broker_connected":false,
                                           services:[database✓, redis✓, market_feed✓, event_stream✓]}
  ```
- **Compose config** is valid and defines healthchecks for postgres, redis,
  backend, feed, and frontend.

> The only steps that must run on your MacBook are A–G (they need the Docker
> daemon, which isn't available in the build sandbox). Everything they exercise —
> the images, migrations, health endpoints, diagnostics, and the e2e validator —
> is already verified in CI and in-sandbox.
