# Technical Design Review — BKN AI Capital (post Sprint 2)

**Reviewer stance:** Principal Engineer, quantitative trading firm.
**Scope:** architecture & code quality of the current codebase (Sprint 1 + 2).
**Goal:** surface weaknesses before they become expensive. **No new features** —
only architecture/quality remediation.

**Severity:** 🔴 Critical (correctness/data-loss/security, fix before prod) ·
🟠 High · 🟡 Medium · 🟢 Low.
**Effort:** S ≤1d · M 1–3d · L 1–2w · XL >2w.

---

## 0. Executive summary — the findings that matter most

The design is sound and the pure quant core (indicators, options math, candle
builder) is clean and well-tested. The **weaknesses cluster in the runtime
distribution model and a few real correctness bugs** introduced while wiring the
live pipeline. None are hard to fix now; all get expensive later.

| # | 🔴/🟠 Top risk | Area | Effort |
|---|--------------|------|--------|
| A | **Multi-worker duplicate feed**: the runner starts in the web process, so N Gunicorn workers = N duplicate feeds writing the same rows | 25, 19 | M |
| B | **VWAP is not session-anchored** — computed over a rolling 300-bar window → wrong indicator value | 22 | S |
| C | **Synchronous event fan-out blocks ingestion** — `publish()` awaits handlers that do DB writes, so persistence backpressures the quote loop | 6, 16 | M |
| D | **No task supervision** — if a runner loop or `provider.stream()` raises, the feed dies silently with no restart | 29, 15 | M |
| E | **Indicator engine reloads 300 candles from DB on every close** — massive read amplification | 16, 22 | M |
| F | **Celery/workers described but not implemented** — all async work runs in the web process | 19, 5(SDD) | L |
| G | **WS auth token in query string** (logged by proxies) + **no rate limiting** + **refresh token in browser storage** | 7, 12 | M |
| H | **Timeframe write amplification + no retention** — every tick writes 10 timeframes; indicators/option snapshots never expire | 10 | M |

Everything below expands these and the rest of the 30 areas.

---

## 1. Project Architecture
- 🟡 **Layering claim vs. reality.** The SDD promises `domain/application/
  infrastructure/api` per module; the code uses a flatter
  `models/schemas/repository/service/router`. Pragmatic and fine — but the docs
  overstate the purity.
  **Impact:** onboarding confusion; reviewers expect ports that don't exist.
  **Recommendation:** either adopt real ports for the 2–3 modules that will grow
  (market_data, future risk/AI) or soften the SDD wording to match. **Effort: S**
  (docs) / **M** (ports for one module).

## 2. Package Structure
- 🟢 Mostly clean, module-per-context. Two smells:
  - `options_math` and indicators live under `market_data`/`shared` inconsistently;
    options math is reusable and belongs in `shared/`.
  - `news/service.py` imports `market_data.metrics` — a cross-context coupling.
  **Impact:** low now, friction when extracting services.
  **Recommendation:** move option math to `shared/`; give news its own metrics or
  a shared metrics module. **Effort: S.**

## 3. SOLID Compliance
- 🟠 **DIP violated.** Services depend on **concrete** repositories/engines
  (`MarketDataService` news up `MarketDataRepository`; engines `new` their repos),
  not abstractions. The provider registry is the one place DIP is honored.
  **Impact:** hard to unit-test services in isolation; swapping persistence means
  editing callers.
  **Recommendation:** define repository `Protocol`s in the domain layer; inject
  them. **Effort: M.**
- 🟡 **SRP:** `MarketFeedRunner` is a God object (connect, sync, quote loop, candle
  drain, indicator dispatch, option loop). Split into `QuoteIngestor`,
  `CandlePersister`, `OptionPoller`, supervised by a thin runner. **Effort: M.**

## 4. Clean Architecture
- 🟡 **Domain is not framework-free.** "Domain" objects are Pydantic/ORM types;
  business rules live in services that import infrastructure. This is standard
  FastAPI structure, not Clean Architecture.
  **Impact:** the dependency rule isn't actually enforced; future business logic
  can leak into adapters.
  **Recommendation:** keep pragmatic structure but add an import-linter (or
  `ruff` bans) forbidding `api → infrastructure` and `domain → sqlalchemy`.
  **Effort: S.**

## 5. Dependency Injection
- 🟠 **No DI container** — the SDD's `app/core/di.py` was never built. Wiring is
  hard-coded (`AuthService(session)`, `IndicatorEngine(repo)`).
  **Impact:** every construction site knows concrete types; test doubles require
  monkeypatching; config-driven swaps are impossible.
  **Recommendation:** introduce a lightweight provider/DI module (or
  `dependency-injector`), register factories, resolve in routers/runner via
  FastAPI `Depends` and constructor injection. **Effort: M.**

## 6. Event Bus Design
- 🔴 **Synchronous fan-out couples publisher latency to subscriber work.**
  `publish()` `await`s `asyncio.gather(handlers)`; the `CandleClosed` handler does
  **DB writes + indicator recompute**. So the quote loop blocks on persistence.
  **Impact:** a slow DB stalls ingestion; one heavy subscriber throttles the whole
  feed. This defeats the point of an event bus.
  **Recommendation:** make delivery fire-and-forget onto a bounded per-subscriber
  queue with its own worker task (drop/label on overflow); publisher never awaits
  handler bodies. **Effort: M.**
- 🟠 **Single-process only.** No Redis pub/sub bridge → events don't cross workers
  (WS gateway on another worker sees nothing). Documented, but blocks scale-out.
  **Recommendation:** add a Redis-Streams transport behind the same `EventBus`
  interface. **Effort: M.**
- 🟢 No event schema/versioning or replay; handler errors are swallowed (data
  silently dropped). Add a dead-letter counter + structured error events. **S.**

## 7. WebSocket Architecture
- 🟠 **Auth token in the query string.** `?token=<JWT>` is logged by Nginx, proxies,
  and browser history.
  **Impact:** access-token leakage.
  **Recommendation:** short-lived single-use WS ticket (issued via authenticated
  POST) or the `Sec-WebSocket-Protocol` header. **Effort: S.**
- 🟠 **O(clients) broadcast on the event loop.** Every event iterates all
  connections; at a few thousand clients this blocks the loop.
  **Recommendation:** fan out via Redis pub/sub + per-connection async senders;
  pre-bucket subscriptions by channel. **Effort: M.**
- 🟡 No max-connections, no per-IP limit, no WS message-size cap, no re-auth when
  the access token expires mid-session. **Effort: M.**

## 8. Redis Usage
- 🟡 **No TTLs on quote/indicator keys.** If the feed stops, stale values persist
  forever and the dashboard shows them as "live."
  **Recommendation:** short TTL (e.g. 2× tick interval) + freshness gating in the
  API. **Effort: S.**
- 🟡 **`get_all_quotes` is N+1** (SMEMBERS then N GETs).
  **Recommendation:** `MGET`/pipeline, or store quotes in a single hash. **S.**
- 🟢 Defensive `_safe` hides Redis outages entirely → silent staleness with no
  alert. Emit a metric/log on cache failure. Consider cluster-awareness. **S.**

## 9. PostgreSQL Design
- 🟡 **`upsert_candle` overwrites `high`/`low` with the incoming value** instead of
  `GREATEST/LEAST`. A re-emitted/late bar can shrink a candle's range.
  **Recommendation:** `high = GREATEST(excluded.high, candles.high)` etc. **S.**
- 🟡 **Instrument upsert is SELECT-then-INSERT per row** (N queries).
  **Recommendation:** bulk `INSERT … ON CONFLICT`. **S.**
- 🟢 Solid otherwise: constraint naming convention, partial indexes, immutable
  audit intent (audit table exists but isn't wired — see §14).

## 10. TimescaleDB Performance
- 🟠 **Timeframe write amplification.** Every tick updates 10 timeframes and each
  close writes a `candles` row per timeframe → 10× write volume, and indicators
  another row per (symbol, timeframe, close).
  **Recommendation:** persist the **1m base** hypertable + **continuous
  aggregates** for higher timeframes; compute indicators from the base or cache
  only. **Effort: L.**
- 🟠 **No retention/compression on `market_indicators` and `option_chain_snapshots`**
  (only `candles` is compressed). These grow fastest.
  **Recommendation:** compression + `add_retention_policy` on all hypertables. **S.**

## 11. API Design
- 🟡 **Inconsistent response envelopes** — `{data:[…]}`, `{breadth,sectors}`, raw
  objects. No pagination on `instruments`/`quotes`. Response models are
  `dict[str, Any]` → OpenAPI loses schema (breaks the "typed client from OpenAPI"
  promise).
  **Recommendation:** one envelope + typed Pydantic response models everywhere;
  cursor pagination on lists. **Effort: M.**
- 🟡 **Rate limiting described but not implemented.** **Effort: M.**

## 12. Security
- 🔴 **Refresh token stored in browser (Zustand `persist` → localStorage).**
  XSS-exfiltratable; the SDD itself mandates httpOnly cookies.
  **Recommendation:** move refresh to an httpOnly, Secure, SameSite cookie; keep
  only the access token in memory. **Effort: M.**
- 🟠 **No auth rate limiting / lockout** → credential stuffing & brute force.
  **Effort: M.**
- 🟠 WS token in query string (see §7). Weak default JWT secret in config (dev
  convenience, but easy to ship by accident — fail fast if default in prod).
  **Effort: S.**
- 🟢 No app-level security headers when hit directly (Nginx has them); no request
  body-size limits on some routes. **S.**

## 13. Authentication
- 🟡 **No refresh-reuse family revocation.** Rotation rejects a reused token but
  doesn't revoke the whole session family on detected theft.
  **Recommendation:** on reuse detection, revoke all of the user's refresh tokens.
  **Effort: S.**
- 🟡 **Access tokens can't be revoked before expiry** (no jti denylist). Acceptable
  with 15-min TTL; document the tradeoff or add a denylist for logout-all. **M.**
- 🟢 MFA is schema-only (not implemented) — fine for now; don't advertise it as done.

## 14. Logging
- 🟡 **Correlation IDs stop at HTTP.** The market pipeline (quote→candle→indicator)
  has no trace id, so you can't follow one tick through the system.
  **Recommendation:** carry a correlation/trace id on events; bind it in handlers.
  **Effort: M.**
- 🟡 **`audit_log` table exists but nothing writes to it** — auth events, risk-limit
  changes (later) must be audited. Wire it now while the surface is small. **S.**
- 🟢 Risk of log floods from the quote loop; add sampling. Emails appear in some
  logs (minor PII). **S.**

## 15. Error Handling
- 🔴 **`provider.stream()` failure kills the quote loop permanently.** The runner's
  `_quote_loop` has no try/reconnect; the resilient client isn't used on this path.
  **Impact:** a transient provider hiccup silently stops the entire feed until a
  restart.
  **Recommendation:** wrap the stream in supervised reconnect (reuse
  `ResilientWebSocketClient` semantics); restart loop tasks on failure. **M.**
- 🟠 **Broad `except Exception` swallowing** in `cache._safe` and `_option_loop`
  hides real faults (only a debug log). Emit metrics + rate-limited error logs.
  **S.**
- 🟠 **Lost candles on DB failure** in `_drain_closed` (no retry/DLQ). **M.**

## 16. Performance
- 🔴 **Indicator engine reloads 300 candles from Postgres on every candle close**,
  for every (symbol, timeframe). At the target universe that is thousands of
  300-row reads per minute.
  **Recommendation:** maintain a rolling in-memory OHLCV window per (symbol,
  timeframe) and compute incrementally; DB is the durable store, not the compute
  source. **Effort: M.**
- 🟠 Synchronous fan-out (see §6) and per-tick JSON+Redis round trips on the hot
  path. Batch cache writes; pipeline Redis. **M.**

## 17. Memory Usage
- 🟢 Bounded overall (universe-sized dicts, per-conn queues capped). Watch: candle
  aggregators and `_last_volume` are never evicted for delisted symbols; add
  lifecycle cleanup. **Effort: S.**

## 18. CPU Usage
- 🟡 **Full indicator recompute each bar** in pure Python (O(n) per indicator).
  Fine at current scale (benchmarked ~1.2 ms/bundle) but scales linearly with
  universe × timeframes.
  **Recommendation:** incremental indicator state (Wilder smoothers are already
  recursive) or vectorize with numpy/TA-Lib behind the same interface. **L.**

## 19. Scalability
- 🔴 **The realtime path is single-process and not shardable.** The runner is a
  singleton in the web process; the event bus and WS gateway are in-memory. You
  cannot add web workers without duplicating the feed (§25) or losing events
  across workers (§6).
  **Recommendation:** (1) move the feed to a **dedicated worker process**, not the
  API; (2) Redis-Streams event transport; (3) shard the universe across feed
  workers by symbol hash. **Effort: L.**
- 🟠 **Celery (in the SDD) is not implemented** — there is no task queue; the
  "workers" package is empty. Either implement it or update the SDD. **L.**

## 20. Broker Provider Abstraction
- 🟠 **The resilient WebSocket client is unused by the streaming path.** The
  simulated provider exposes `stream()` as an async generator, so the reconnect/
  heartbeat/backpressure machinery is only unit-tested in isolation, never on the
  real ingestion path. A real broker will need bespoke wiring.
  **Recommendation:** define the live-feed contract in terms of the resilient
  client (provider supplies connect/encode/decode callbacks); make the simulator
  drive it too, so the same path is exercised end-to-end. **Effort: M.**
- 🟡 Generic `ProviderError` only — no taxonomy for auth/rate-limit/stale; no
  rate-limit backoff contract; `fetch_instruments` returns the whole list (no
  paging for 50k-row masters). **M.**

## 21. Market Data Pipeline
- 🔴 **No market-calendar / session awareness.** The runner streams and builds
  candles 24/7; there's no NSE session gating, holiday handling, or session
  VWAP/OHLC reset. The SDD's `shared/market_calendar` was not built.
  **Impact:** off-hours synthetic bars, wrong session opens, VWAP that never
  resets (see §22).
  **Recommendation:** implement the market calendar; gate ingestion and reset
  session state at open. **Effort: M.**
- 🟡 **Volume-delta from cumulative is fragile** — on provider reset/restart the
  cumulative drops, delta clamps to 0, and volume is lost/mis-attributed.
  **Recommendation:** prefer per-tick traded qty where the provider gives it;
  persist last cumulative per session. **S.**
- 🟢 No out-of-order/late-tick handling; gap-fill can't distinguish "halt" from
  "no data." Document assumptions. **S.**

## 22. Technical Indicator Pipeline
- 🔴 **VWAP is wrong.** `vwap()` accumulates over whatever window is passed (the
  last 300 bars), but VWAP must be **anchored to the session open**. A rolling
  300-bar VWAP is a different, misleading number traders will not trust.
  **Recommendation:** compute session VWAP from session-start bars (needs the
  market calendar, §21); reset daily. **Effort: S** (given calendar).
- 🟠 **Indicators are computed over candles that include synthetic gap-fill bars**,
  which biases RSI/ATR/etc. Flag or exclude synthetic bars from indicator input.
  **M.**
- 🟢 Full-series recompute (perf, §16); warm-up handled via NULLs (fine).

## 23. Option Chain Engine
- 🟡 **Greeks use the provider's IV as ground truth** rather than solving IV from
  the option's market price; if a real provider gives price-only, greeks will be
  inconsistent. Time-to-expiry uses **calendar** days (no trading-day/holiday
  adjustment, no intraday theta).
  **Recommendation:** solve IV from LTP (the `implied_volatility` solver exists),
  use a trading-day year fraction. **Effort: M.**
- 🟡 **Snapshots grow unbounded** (insert per poll, no retention/dedup). Add
  retention + skip-if-unchanged. **S.**

## 24. News Engine
- 🟠 **Ingestion is never scheduled.** `NewsService.ingest()` exists but nothing
  calls it — no poller/worker wires the news provider into the runtime, so the
  news pipeline is dormant in practice.
  **Recommendation:** add a supervised news poll loop (or n8n/Celery schedule).
  **Effort: S.**
- 🟡 Dedup by exact-headline hash misses reworded near-duplicates; regex symbol
  mapping (`\bIT\b`, sector keyword `' it '`) risks false positives; no
  source-trust weighting. Baseline is acceptable but document limits. **M.**

## 25. Deployment Readiness
- 🔴 **Multi-worker duplicate feed.** The prod backend runs Gunicorn with 4
  Uvicorn workers, and the feed starts in `lifespan` — so **4 independent runners**
  connect, ingest, and write the same candles/snapshots concurrently (duplicate
  writes, contention, quadrupled provider load / rate-limit risk).
  **Recommendation:** run the feed as a **single dedicated process/service**
  (separate compose service, `--workers 1` or a leader-election lock), never in
  the API workers. **Effort: M.**
- 🟡 No graceful WS drain on shutdown; no feed healthcheck/readiness. **S.**

## 26. Testing Coverage
- 🟠 **The orchestrator (`runner.py`) has ~0% coverage** — the most failure-prone
  integration point is untested; WS gateway behavior is untested.
  **Recommendation:** integration test the runner against the simulated provider
  with an in-memory DB + fake clock; drive the WS gateway with a test client. **M.**
- 🟠 **Integration tests run on SQLite**, so Postgres/Timescale-specific paths
  (`ON CONFLICT`, hypertables, partial indexes) are **never executed in CI**.
  **Recommendation:** add a Postgres+Timescale service (testcontainers) job.
  **Effort: M.**
- 🟢 No coverage threshold gate; no provider contract tests; no load test in CI. **M.**

## 27. Docker Configuration
- 🟡 Dev backend uses the `builder` stage (build tools present) — fine for dev but
  don't ship it. No CPU/memory limits in compose; images not pinned by digest; no
  feed healthcheck.
  **Recommendation:** resource limits, digest pinning, a dedicated `worker`/`feed`
  service in prod compose. **Effort: S–M.**

## 28. CI/CD
- 🟠 **No real-DB test job** (SQLite only) → migrations/Timescale untested in CI
  (§26). No coverage gate; Docker images build-only (no scan/push described);
  no e2e; SAST limited to ruff's `S` rules.
  **Recommendation:** add Postgres/Timescale integration job, migration-apply
  check, coverage floor, image scan (Trivy), and a Playwright smoke e2e. **L.**

## 29. Failure Recovery
- 🔴 **No task supervision.** The runner creates `asyncio` tasks (`_quote_loop`,
  `_option_loop`) with no done-callbacks; if one raises, it dies silently and is
  never restarted — the feed degrades with no signal.
  **Recommendation:** supervise tasks (restart with backoff, emit a health metric);
  add a watchdog on data freshness that trips the emergency-stop and alerts.
  **Effort: M.**
- 🟠 Redis/DB outages are swallowed (§8, §15) rather than surfaced with alerts.
  DB-write failures drop candles with no retry/DLQ. **M.**

## 30. Disaster Recovery
- 🟡 Backups are **scripted but not automated or tested**; no PITR (WAL archiving)
  configured; TimescaleDB hypertable backup/restore isn't documented (needs care);
  no restore drill; single-VPS (no replica).
  **Recommendation:** automate nightly backup + off-site sync (cron), enable WAL
  archiving/PITR, document + rehearse a restore, and validate RPO/RTO. Acceptable
  for a V1 single-VPS *if* documented and drilled. **Effort: M.**

---

## Remediation Roadmap (quality only — no new features)

Sequenced so each phase leaves the system releasable. Nothing here adds product
scope; it hardens what exists.

### Phase R0 — Correctness & data integrity (must fix before any live feed) — ~1 wk
1. 🔴 **Single feed process** (§25): move the runner out of API workers into a
   dedicated service / leader lock. *(A)*
2. 🔴 **Session-anchored VWAP** + exclude synthetic bars from indicator input
   (§22). *(B)*
3. 🔴 **Task supervision + stream reconnect** (§29, §15): restart loops with
   backoff; wrap `provider.stream()`. *(D)*
4. 🔴 **Async event fan-out** (§6): decouple publisher from subscriber work. *(C)*
5. 🟡 `GREATEST/LEAST` candle upsert (§9). *(S)*

### Phase R1 — Realtime performance & correctness — ~1 wk
6. 🔴 **In-memory rolling window for indicators** (§16) — stop reloading candles.
7. 🟠 **Market calendar** (§21) — session gating, holiday handling (unblocks VWAP).
8. 🟠 **Redis TTLs + freshness gating + MGET** (§8); freshness watchdog (§29).
9. 🟠 **Timescale retention/compression on all hypertables** (§10).

### Phase R2 — Security & auth hardening — ~1 wk
10. 🔴 **Refresh token → httpOnly cookie** (§12).
11. 🟠 **Auth rate limiting/lockout** + **WS ticket auth** (§7, §12).
12. 🟡 **Refresh-reuse family revocation** + wire the **audit log** (§13, §14).
13. 🟠 **API rate limiting** middleware (§11).

### Phase R3 — Architecture & DI cleanup — ~1–2 wk
14. 🟠 **DI container** + **repository Protocols** (§3, §5) for market_data + auth.
15. 🟡 **Split the runner** into ingestor/persister/pollers (§3).
16. 🟠 **Provider live-feed contract via the resilient client** (§20); make the
    simulator drive it.
17. 🟡 **Uniform API envelope + typed response models + pagination** (§11).
18. 🟡 **Import-linter** enforcing the dependency rule (§4).

### Phase R4 — Scale-out & platform — ~2 wk
19. 🟠 **Redis-Streams event transport** + WS fan-out across workers (§6, §7, §19).
20. 🟠 **Implement the task queue** (Celery/arq) or update the SDD to drop it (§19).
21. 🔴/🟠 **Continuous aggregates** for higher timeframes; persist 1m base only
    (§10) — removes write amplification.
22. 🟠 **Wire the news poll loop** (§24).

### Phase R5 — Testing, CI/CD, DR — ~1–2 wk
23. 🟠 **Postgres+Timescale integration CI job** + migration-apply test (§26, §28).
24. 🟠 **Runner + WS integration tests**; coverage floor; provider contract tests
    (§26).
25. 🟡 **Image scan + Playwright smoke e2e** (§28).
26. 🟡 **Automate + rehearse backups, enable PITR, document Timescale DR** (§30).
27. 🟡 **Compose resource limits + digest pinning + feed healthcheck** (§27).

### What is already good (keep)
- Pure, deterministic, golden-tested quant core (indicators, options math, candle
  builder) — the highest-value code and the best-tested.
- Provider & news **abstractions** (the seams are in the right places).
- Typed settings, structured logging, error envelope, migration discipline,
  green CI across ruff/black/mypy(strict)/pytest.

---

## One-line verdict
**The bones are right; the runtime distribution model and a handful of
correctness bugs are the debt.** Phase R0 (≈1 week) removes the items that would
corrupt data or silently stop the feed in production — do that before any live
broker is connected. The rest is standard hardening that can proceed in parallel
with later product sprints.
