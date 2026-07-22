# Sprint 14 — Zerodha Kite Connect Live Integration

> **Advisory-only guarantee (non-negotiable):** This integration adds **live
> market data only**. No code path in this sprint — or anywhere in the platform —
> places a live broker order. Execution remains strictly **paper**, filling
> simulated orders against live, read-only prices.

This document is the integration plan for wiring **live Zerodha Kite Connect
market data** through the full BKN AI Capital pipeline. It builds directly on the
Sprint 6 foundation (provider port, `ZerodhaProvider`, OAuth flow, encrypted
token store, reconnect/backoff, broker API) rather than re-implementing it.

---

## 1. Objectives

1. Serve **real NSE/BSE market data** (quotes, candles, ticks) through the
   existing provider-agnostic domain layer by selecting `market_provider=zerodha`.
2. Productionize the **daily Kite token lifecycle**: an admin-driven login flow,
   encrypted storage, validity checks, and graceful fallback to the simulated
   provider when no valid token is present.
3. **Backfill and maintain historical candles** for the tradable universe within
   Kite's rate limits.
4. Run a **resilient WebSocket tick stream** with reconnection, staleness
   detection, and connection sharding.
5. Feed **Scanner, Alpha Engine, AI Committee, Paper Trading, Journal, and
   Analytics** with live data — with **zero changes** to those consumers, because
   they already depend on the domain layer, not on any broker.
6. Preserve the advisory-only guarantee end to end, provably (startup assertion +
   test).
7. Never regress: when Zerodha is unavailable, the platform runs fully on the
   simulated provider.

### Non-goals
- No live order placement, order management, positions, funds, or margins from
  the broker. The `MarketProvider` port intentionally has no order method.
- No automated headless login (Kite mandates interactive 2FA — see §4).

---

## 2. Architecture

The platform already isolates every consumer from the concrete broker behind the
`MarketProvider` port and a provider registry. Switching to live data is a
configuration + token concern, not a consumer-code concern.

```
                         ┌──────────────────────────────────────────┐
   Zerodha Kite          │              Feed process                │
   ┌───────────┐  ticks  │  ZerodhaProvider ──► normalize ──► Event │
   │  Ticker   │────────►│  (KiteTickerPort)     (mappers)     Bus  │
   │  (WS)     │         │        ▲                              │  │
   └───────────┘         │        │ access_token (daily)         │  │
   ┌───────────┐  REST   │   TokenLifecycle ◄── TokenStore       │  │
   │ Kite HTTP │◄───────►│   (validity/fallback)  (Fernet enc.)  ▼  │
   │ (quote/   │ history │                          Candle builder  │
   │  historical)        │                          Indicator engine│
   └───────────┘         │                          Quote hot-cache │
                         └───────────────┬──────────────────────────┘
                                         │ Redis (cache + streams)
             ┌───────────────────────────┼───────────────────────────┐
             ▼               ▼            ▼            ▼               ▼
        MarketData      Scanner /     AI Committee  Paper Trading   Client
        Repository      Alpha Engine  (deliberation) (paper fills)  WebSocket
        (candles)       (ContextBuilder)             against cache  gateway
                                         │                │
                                         ▼                ▼
                                     Journal  ◄──────  closed trades
                                     Analytics ◄─────  (equity curve, risk)
```

**Already in place (Sprint 6):**
- `app/modules/market_data/providers/` — `base.MarketProvider` port, `registry`,
  `simulated`, `resilient_ws`.
- `app/modules/broker/` — `provider.ZerodhaProvider`, `auth` (OAuth), `token_store`
  (Fernet), `ports` (`KiteHttpPort`, `KiteTickerPort`), `kite/` (SDK adapters),
  `historical`, `reconnect` (`BackoffPolicy`, `ReconnectState`), `mappers`,
  `metrics`, `service`, `api`, `factory` (registers `zerodha` + `paper`).
- `broker_tokens` table (migration `0004`).
- Config: `market_provider`, `zerodha_api_key/secret/redirect_url`,
  `broker_enc_key`, `broker_subscribe_fno`, `broker_watchlist`.

**Sprint 14 adds** the orchestration and operational layer around these pieces:
token lifecycle guard, admin broker panel, rate-limited backfill, unified
degradation policy, and the end-to-end live smoke test.

---

## 3. Zerodha Kite authentication flow

Kite uses interactive OAuth producing a **daily** access token.

1. **Initiate (admin).** Admin opens the Broker panel and clicks *Connect Zerodha*.
   Backend builds the login URL:
   `https://kite.zerodha.com/connect/login?api_key=<KEY>&v=3` and redirects.
2. **Consent + 2FA.** The admin logs into Zerodha (password + TOTP). Kite redirects
   to `zerodha_redirect_url`
   (`/api/v1/broker/zerodha/callback?request_token=<RT>&status=success`).
3. **Exchange.** Backend computes `checksum = SHA256(api_key + request_token +
   api_secret)` and calls `POST /session/token` → receives `access_token`
   (and `public_token`).
4. **Persist.** The access token is encrypted (Fernet, `broker_enc_key`) and stored
   in `broker_tokens` with an issued-at timestamp; the provider is handed the token
   via `set_access_token(...)`.
5. **Activate.** The feed (re)subscribes the universe using the live token.

CSRF is mitigated with a signed `state`/nonce round-tripped through the login URL
and validated on callback. All broker routes are **admin-only** (RBAC).

---

## 4. Token lifecycle and refresh strategy

**Reality:** Kite access tokens are valid only for the current trading day and are
invalidated the following morning (~07:30 IST). There is **no non-interactive
refresh** — Kite requires an interactive 2FA login each day. The strategy is
therefore *semi-automated with graceful degradation*, never silent failure.

- **Storage:** one active token per broker account, **encrypted at rest** (Fernet),
  never logged, never returned to the frontend. The API exposes only
  `{ connected: bool, issued_at, expires_hint }`.
- **`TokenLifecycle` guard (new):** before the feed subscribes and before any
  historical pull, verify a token exists and a cheap authenticated probe (e.g.
  `GET /user/profile` or a single LTP) succeeds. On failure:
  - mark broker **disconnected**,
  - **fall back to the simulated provider** so the whole platform keeps working,
  - raise an Admin banner + structured warning log ("Zerodha token expired —
    reconnect").
- **Daily reminder:** a scheduled routine (existing scheduler mechanism) posts a
  pre-open reminder to reconnect. Reconnection is one click in the Admin panel.
- **Invalidation on logout:** disconnecting clears the stored token and reverts the
  provider to simulated.
- **Clock/session awareness:** the market calendar already known to the platform
  gates "should we be live?" so off-hours token absence is not treated as an error.

---

## 5. Live quotes integration

- `ZerodhaProvider` receives ticker updates, and `mappers.tick_to_quote` normalizes
  them into the domain `Quote` model (symbol, ltp, change %, volume, timestamp).
- Quotes are published on the **event bus** and written to the **Redis quote
  hot-cache** with a TTL (`quote_cache_ttl_seconds`, default 30s) — identical to
  the simulated path, so `GET /market/quotes`, `/market/indices`, the dashboard,
  the header ticker, and paper-trade marking all consume live prices unchanged.
- **Staleness safety:** the TTL guarantees a stalled feed cannot serve stale prices
  as "live"; `/health/diagnostics` and the Admin system-health panel already report
  freshest-quote age.

---

## 6. Historical candles integration

- `broker/historical.py` wraps Kite's `historical_data` endpoint;
  `mappers.kite_candle_to_domain` converts to domain `Candle`s, upserted into the
  TimescaleDB candle hypertables (idempotent — safe to re-run).
- **Backfill job (new):** on first connect (and to fill gaps), a **rate-limited,
  chunked** backfill seeds candles for each instrument × timeframe. Kite caps the
  date range per request per interval, so requests are chunked; results are deduped
  via the existing upsert.
- Runs as a throttled background queue that **never blocks the live tick path**.
- Timeframes come from `market_timeframes` (`1m/5m/15m/1h/1d`).

---

## 7. WebSocket streaming design

- `KiteTickerPort` + `resilient_ws.py` maintain the Kite ticker connection; the app
  subscribes by `instrument_token` (resolved via the instrument master) in
  `full`/`quote` mode as needed for OHLC/volume.
- **Kite limits respected:** ≤ **3000 instruments per connection** and ≤ **3
  connections**. The subscription manager **shards** the universe across
  connections when it exceeds a single connection's cap.
- Ticks fan out through the event bus to: the candle builder, the indicator engine,
  the quote cache, and the app's **own** client WebSocket gateway (which continues
  to authenticate browser clients with short-lived tickets — never the Kite token).
- Heartbeat + last-tick timestamps feed staleness detection.

---

## 8. Rate-limit and retry strategy

Kite quotas (approximate, enforced conservatively):

| Surface | Limit | Handling |
|---|---|---|
| REST general | ~3 req/s | Shared **token-bucket** limiter in front of `KiteHttpPort` |
| Quote REST | ~1 req/s | Prefer the ticker stream; throttle any REST quote fallback |
| Historical | ~3 req/s | Backfill queue paced by the limiter; chunked ranges |
| Ticker instruments | ≤3000/conn, ≤3 conn | Connection sharding |

- Requests are **coalesced** and **jittered**; on `429`/throttle the client honors
  `Retry-After` with exponential backoff.
- The limiter is process-wide (feed) so backfill and live paths share the budget
  without starving the tick stream (tick stream is push-based and not rate-limited
  by REST).

---

## 9. Error handling and recovery

- **Ticker disconnect:** `reconnect.py` (`BackoffPolicy` + `ReconnectState`) reconnects
  with exponential backoff + jitter; last-known cache serves reads within its TTL,
  after which reads report staleness rather than lie.
- **Auth failure / expired token:** provider marks disconnected → **fallback to
  simulated** → Admin alert; no crash, no partial state.
- **Historical 429 / transient REST errors:** retry with backoff honoring
  `Retry-After`; permanent errors are logged and surfaced, backfill continues with
  the next chunk.
- **Provider isolation:** all Kite errors are wrapped as `ProviderError`; a
  misbehaving provider degrades the feed, never the API.
- **Observability:** broker metrics (`broker/metrics.py`), the ring-buffer logs, and
  the Admin system-health/logs panels (Sprint 12) surface connection state, reconnect
  counts, tick age, and backfill progress.

---

## 10. Data flow into the pipeline (live in, paper out)

Every consumer reads the **domain layer**, so live data reaches them with **no
consumer code changes**:

- **Scanner / Alpha Engine** — `ContextBuilder` reads candles/indicators from
  `MarketDataRepository`; live candles → live regime detection, 11-factor scoring,
  and the ranked Opportunity Book.
- **AI Committee** — `/committee/review` deliberates on the live scan's chosen
  opportunity (seven agents + CIO), now reasoning over real market state; the
  Admin-configured committee weights/thresholds still apply.
- **Paper Trading** — the **only** order path. Simulated orders fill against the
  **live, read-only** quote cache; open positions mark-to-market on live prices.
- **Journal** — every closed paper trade is recorded (entry/exit/P&L/R-multiple).
- **Analytics** — equity curve, drawdown, win rate, Sharpe, profit factor computed
  from the live-priced closed trades.

**Paper-only enforcement (unchanged and provable):**
- `ZerodhaProvider` / `MarketProvider` expose **no order method** — there is nothing
  to call to place a live order.
- A **startup assertion** and a **test** fail the build if any order-capable broker
  surface is ever introduced. `broker_connected` stays informational; execution mode
  is always paper.

---

## 11. Security considerations

- **Secrets:** `zerodha_api_secret` and `broker_enc_key` come from env only, never
  committed, never logged, never sent to the client. Access tokens are **Fernet-
  encrypted at rest**.
- **RBAC:** all broker/admin routes are admin-only; connect/disconnect and token
  status are audited (audit trail from Sprint 12).
- **CSRF:** signed `state` nonce on the OAuth round-trip.
- **Token isolation:** the Kite access token is used **only** server-side by the
  feed/provider; browser WebSocket auth continues to use the platform's own
  short-lived tickets.
- **No token leakage:** API responses expose booleans/timestamps only.
- **Least privilege:** Kite app configured for market-data scope; no order scope
  used even if present.

---

## 12. Testing strategy

- **Unit:** mappers (tick/candle/instrument normalization), token lifecycle
  (valid/expired/missing → fallback), rate limiter (bucket math), backoff policy,
  connection sharding math. All against fakes of `KiteHttpPort`/`KiteTickerPort`
  (no network).
- **Integration:** OAuth callback (checksum, state validation, encrypted persistence),
  provider registry selection (`simulated`↔`zerodha`), degradation path (expired
  token → simulated), historical upsert idempotency.
- **Contract/guard:** a test asserting the broker surface exposes **no order method**
  (advisory-only guarantee).
- **End-to-end smoke (gated):** with sandbox/mock Kite adapters, run feed → cache →
  scanner → committee → paper fill → journal → analytics and assert live data
  propagates and execution stays paper.
- **CI:** everything runs with mocked Kite (no live credentials in CI); real-broker
  validation is a manual, documented post-deploy step.
- Maintain the existing gate: Ruff · Black · MyPy(strict) · Pytest;
  frontend ESLint · tsc · Vitest · build.

---

## 13. Rollback plan

Rollback is a **configuration flip**, not a code revert:

1. Set `market_provider=simulated` (or `paper`) and restart the feed → the platform
   immediately runs on the simulated provider; all pages keep working.
2. Disconnect in the Admin Broker panel to clear the stored token.
3. If a code-level issue is found, revert the Sprint 14 PR; because Zerodha wiring is
   additive and provider-gated, master returns to the current known-good state with
   no schema rollback required (no destructive migrations planned; any new table is
   additive with a safe `downgrade`).
4. The advisory-only guarantee holds in every state — there is no live-order path to
   disable.

---

## 14. Sprint 14 implementation milestones

1. **Token lifecycle + Admin Broker panel** — connect/callback/disconnect, encrypted
   storage, validity probe, status endpoint, audit entries, RBAC. Fallback to
   simulated on missing/expired token.
2. **Rate limiter + historical backfill** — shared token bucket; chunked, idempotent
   candle backfill job with progress surfaced in Admin.
3. **Live tick streaming hardening** — subscription/sharding manager, staleness
   detection, reconnect/backoff verification, metrics.
4. **Degradation & recovery policy** — unified fallback, alerts, and `/health`
   reporting; advisory-only startup assertion + guard test.
5. **End-to-end live smoke test** (mocked Kite) — data propagates to Scanner, Alpha,
   Committee, Paper Trading, Journal, Analytics; execution stays paper.
6. **Docs + runbook** — daily login runbook, env setup, and validation checklist.

Each milestone is independently shippable and leaves the platform green and
advisory-only.

---

*BKN AI Capital is a decision-support platform. This integration adds live market
data only and never executes trades. See
[docs/12-security-compliance.md](12-security-compliance.md).*
