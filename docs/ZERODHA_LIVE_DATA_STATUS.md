# Zerodha Live Data — Status & Verification Runbook

> **Advisory-only.** The live broker connection is **read-only market data**.
> There is no order-placement path anywhere in the platform — the
> `MarketProvider` port has no order method, and the only fill path is the paper
> engine against live, read-only prices.

## What is already implemented

The end-to-end live-data pipeline was built in Sprints 6 & 8 and hardened here.
Selecting Zerodha is a **configuration + daily-token** operation, not new code:

| Capability | Where | Status |
|---|---|---|
| OAuth login + token exchange | `broker/auth.py`, `GET /broker/zerodha/login-url`, `GET /broker/zerodha/callback` | ✅ |
| Encrypted token store (Fernet) | `broker/token_store.py`, `broker_tokens` (migration 0004) | ✅ |
| Connection/token status | `GET /broker/status`, `BrokerService.status()` | ✅ |
| Live WebSocket ticker + reconnect | `broker/provider.py` (`ZerodhaProvider`), `broker/reconnect.py`, `resilient_ws.py` | ✅ |
| Instrument master sync | `market_data/instrument_master.py` (run on feed start) | ✅ |
| Tick ingestion → quotes | `broker/mappers.py`, feed `_run_quote_stream` → event bus → quote cache | ✅ |
| Candle generation (multi-timeframe) | `market_data/candle_builder.py` (feed) | ✅ |
| TimescaleDB storage | `market_data` hypertables via the feed persistence path | ✅ |
| Historical backfill | `broker/historical.py`, `POST /broker/historical/backfill` | ✅ |
| Feed → Scanner / Analytics / Dashboard | all read the domain layer (cache + candle repo), provider-agnostic | ✅ |
| Supervised loops, reconnect, health | `feed/service.py` (`Supervisor`, `Backoff`), `/health/diagnostics` | ✅ |

### Hardened in this change
- **Graceful degradation:** if `market_provider=zerodha` but no valid daily token
  is stored, the feed now **falls back to the simulated provider** instead of
  crashing on connect. The platform stays fully operational and prompts the
  operator to reconnect.
- **Real broker health:** `/health/diagnostics` `broker_connected` reflects the
  actual stored-token validity (read-only) instead of a hardcoded `false`.

## How to run live (operator steps)

1. Set env: `BKN_MARKET_PROVIDER=zerodha`, `BKN_ZERODHA_API_KEY`,
   `BKN_ZERODHA_API_SECRET`, `BKN_BROKER_ENC_KEY` (Fernet key),
   `BKN_MARKET_FEED_ENABLED=true`.
2. Start the stack; open `GET /api/v1/broker/zerodha/login-url`, complete the
   Kite login (interactive 2FA) — Kite redirects to the callback, which exchanges
   the `request_token` for the **daily** access token and stores it encrypted.
3. The feed attaches the token and connects the ticker; instruments sync, candles
   build, and the Dashboard/Scanner/Analytics show live data.
4. **Daily:** Kite tokens expire each morning — repeat step 2 before the open.
   Until reconnected, the feed serves the simulated provider (no crash).

## Indicator verification against Zerodha charts (credential-gated)

This **cannot be executed in CI or without live Kite credentials + market hours.**
Runbook for a human operator to verify indicator parity:

1. With a live token, let the feed ingest a liquid symbol (e.g. `RELIANCE`) for a
   full session so 1m/5m/15m/1h/1D candles form.
2. In the Kite web/app chart, add the same indicators the engine computes
   (EMA 20/50, RSI 14, ADX 14, ATR 14, VWAP, MACD, Bollinger).
3. For 5–10 timestamps per timeframe, compare the platform's stored indicator
   values (`/market/…` / DB) against Kite's chart readouts.
4. **Acceptance:** values match within rounding (candles use the same OHLCV;
   EMAs/RSI/ATR are standard). Investigate any discrepancy > ~0.1% — the usual
   causes are candle-boundary/timezone alignment (IST session) or a partial
   (still-forming) last candle. The candle builder closes bars on session time,
   so compare only **closed** bars.
5. Record results in an ops log; this is the acceptance gate for "live data is
   trustworthy" before relying on the Scanner/Committee output.

> The platform stays advisory-only throughout: even with a perfect live feed,
> execution is simulated (paper) — there is no live order path to enable.
