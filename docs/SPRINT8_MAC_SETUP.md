# Sprint 8 — Local Environment Bring-up (macOS, from a clean machine)

> Goal: get the **entire** BKN AI Capital platform running on a MacBook with **one
> command**, and prove the complete pipeline works end-to-end on **simulated
> market data** — **no live broker**. This guide assumes a brand-new Mac.

---

## 0. What runs

One `docker compose` brings up six services + all workers:

| Service | Container | Port | Role |
|---|---|---|---|
| PostgreSQL + **TimescaleDB** | `postgres` | 5432 | Relational + time-series store |
| Redis | `redis` | 6379 | Live quote cache + event streams |
| Backend API | `backend` | 8000 | FastAPI (auth, market, paper, analytics, health) |
| Market **feed** (+ workers) | `feed` | 8001 | Ingestion + candle/indicator + paper manager + report scheduler |
| Frontend | `frontend` | 3000 | Next.js UI (incl. the diagnostics page) |
| n8n | `n8n` | 5678 | Automation (scheduled reports) |

The **feed** container runs all supervised workers: quote stream, option poll,
session watch, news poll, the paper-trading position manager, and the report
scheduler.

---

## 1. Prerequisites (clean machine)

1. **Docker Desktop for Mac** — the only hard requirement.
   - Download: <https://www.docker.com/products/docker-desktop/> (choose **Apple
     Silicon** on M-series, **Intel** otherwise).
   - Install, launch it, and wait until the whale icon in the menu bar is steady.
   - Recommended resources (Docker Desktop → Settings → Resources): **≥ 4 CPUs,
     ≥ 8 GB RAM, ≥ 20 GB disk**.
2. **Git** — to get the code. macOS prompts to install the Command Line Tools the
   first time you run `git`; accept it. (Or `brew install git` if you use
   [Homebrew](https://brew.sh).)

Verify:
```bash
docker --version          # Docker version 24+.
docker compose version    # Docker Compose v2+.
git --version
```

> You do **not** need Python, Node, Postgres, or Redis installed on the Mac —
> everything runs in containers.

---

## 2. Get the code

```bash
git clone <repo-url>
cd peace_maker
```

---

## 3. Start everything — one command

```bash
make up
```

That runs `scripts/dev-up.sh`, which:
1. checks Docker is running,
2. creates `.env` from `infra/env/.env.dev.example` if it's missing,
3. builds the images and starts all services,
4. **blocks until every service is healthy** (`docker compose up --wait`),
5. prints the URL map.

First run pulls base images and builds — expect a few minutes. Subsequent runs are
seconds. When it returns, you'll see:

```
✓ BKN AI Capital is up.
  Frontend            http://localhost:3000
  API (docs)          http://localhost:8000/docs
  Diagnostics page    http://localhost:3000/diagnostics
  ...
```

Migrations run **automatically** inside the backend container on startup
(`alembic upgrade head`), so the schema is ready before the API serves traffic.

---

## 4. Verify every service is healthy

**A. The diagnostics page (easiest).** Open <http://localhost:3000/diagnostics>.
It needs **no login** and shows a live status board:

- **Frontend → Backend** — green proves the browser reached the API (Requirement:
  "verify frontend can communicate with backend").
- **database** — green proves PostgreSQL/TimescaleDB connectivity (and shows the
  TimescaleDB hypertable count).
- **redis** — green proves Redis connectivity.
- **market_feed** — green proves the simulated data pipeline is flowing (symbol
  count + freshest-quote age).
- **event_stream** — cross-instance fan-out status.
- **Live broker** — intentionally **not connected**; the panel says so.

The page auto-refreshes every 5 seconds.

**B. The health endpoints (scriptable):**
```bash
curl -s http://localhost:8000/api/v1/health/ready | jq          # {"status":"ready", ...}
curl -s http://localhost:8000/api/v1/health/diagnostics | jq    # full report
curl -s http://localhost:8001/health/live                       # feed liveness
```

**C. Container health:**
```bash
docker compose ps    # every service shows "healthy"
```

---

## 5. Prove the full pipeline end-to-end (simulated data)

```bash
make validate        # or ./scripts/validate.sh
```

`scripts/validate.py` (Python standard-library only — already on macOS) asserts:

1. the API is **ready** (DB + Redis healthy),
2. **diagnostics** reports all core services healthy and **no broker connected**,
3. a user can register/authenticate,
4. **simulated market data is flowing** (`/market/quotes` returns priced symbols),
5. a **paper trade executes and is recorded** (order → position → close → journal),
6. **analytics update** and a **weekly report generates**,
7. **no live order-placement endpoint exists** (OpenAPI introspection).

A green run is the deliverable: the whole platform up with one command, showing
simulated market data end-to-end.

You can also watch live prices in the UI: register at
<http://localhost:3000> (or `make seed` to create the admin user) and open the
Dashboard — index tiles and quotes update over WebSocket from the simulated feed.

---

## 6. Stop / reset

```bash
make down            # stop containers, keep data
make purge           # stop AND delete all volumes (fresh slate)
make logs            # tail all logs
```

---

## 7. Troubleshooting

| Symptom | Fix |
|---|---|
| `✗ Docker is not running` | Launch Docker Desktop; wait for the steady whale icon. |
| `make up` times out waiting for health | `docker compose logs backend feed` — usually the first build; re-run `make up`. |
| Port already in use (5432/6379/8000/3000) | Stop the conflicting local service, or change the host port in `docker-compose.yml`. |
| Diagnostics shows **market_feed** red | The feed needs a few seconds to warm up; wait one refresh. Still red → `docker compose logs feed`. |
| Diagnostics shows **database/redis** red | `docker compose ps` — ensure `postgres`/`redis` are healthy; `make down && make up`. |
| "No space left on device" | `docker system prune` to reclaim space, then `make up`. |
| Apple Silicon image warnings | All images are multi-arch; no action needed. |

---

## 8. What's intentionally NOT here

**No live broker.** This environment runs entirely on the **simulated** market
provider. Connecting Zerodha (live, read-only market data) is a later step
(`docs/SPRINT6_ZERODHA.md`), and live order placement does not exist anywhere in
the platform by design. The diagnostics page and the validation script both assert
`broker_connected = false`.
