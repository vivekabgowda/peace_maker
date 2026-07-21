#!/usr/bin/env python3
"""BKN AI Capital — end-to-end local validation (Sprint 7).

Drives the *running* local stack through the full advisory + paper-trading loop
and asserts the Sprint 7 success criteria:

  1. The platform is up and healthy.
  2. Live market data is flowing through the system.
  3. A paper trade is executed and recorded (position -> journal).
  4. Performance analytics update and a weekly report is generated.
  5. No live broker orders exist (the API exposes no order-placement path).

Standard library only — runs on a stock macOS/Linux Python 3, no pip installs.
Point it at a different host with BKN_BASE_URL (default http://localhost:8000).
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request

BASE = os.environ.get("BKN_BASE_URL", "http://localhost:8000").rstrip("/")
API = f"{BASE}/api/v1"

_PASS = "\033[32m✓\033[0m"
_FAIL = "\033[31m✗\033[0m"
_INFO = "→"


class ValidationError(Exception):
    pass


def _request(method: str, path: str, *, token: str | None = None, body: dict | None = None) -> dict:
    url = path if path.startswith("http") else f"{API}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode()
        raise ValidationError(f"{method} {path} -> HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise ValidationError(f"{method} {path} -> {exc.reason}") from exc


def step(msg: str) -> None:
    print(f"  {_INFO} {msg}")


def ok(msg: str) -> None:
    print(f"  {_PASS} {msg}")


# -- 1. Health --------------------------------------------------------------
def wait_for_health(timeout: int = 120) -> None:
    step(f"Waiting for the API to become ready at {BASE} …")
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            body = _request("GET", "/health/ready")
            if body.get("status") == "ready":
                ok(f"API ready — checks: {body.get('checks')}")
                return
        except ValidationError:
            pass
        time.sleep(3)
    raise ValidationError(f"API did not become ready within {timeout}s")


# -- Auth -------------------------------------------------------------------
def authenticate() -> str:
    creds = {"email": f"validator+{int(time.time())}@example.com", "password": "Validate!123"}
    body = _request("POST", "/auth/register", body=creds)
    token = body["tokens"]["access_token"]
    ok("Registered a validation user and obtained a JWT")
    return token


# -- 2. Diagnostics ---------------------------------------------------------
def check_diagnostics() -> None:
    step("Fetching system diagnostics …")
    report = _request("GET", "/health/diagnostics")
    for svc in report.get("services", []):
        mark = _PASS if svc.get("healthy") else _FAIL
        print(f"      {mark} {svc.get('name')}: {svc.get('detail')}")
    core = {s["name"]: s["healthy"] for s in report.get("services", [])}
    if not (core.get("database") and core.get("redis")):
        raise ValidationError("A core service (database/redis) is unhealthy")
    if report.get("broker_connected"):
        raise ValidationError("A live broker is connected — Sprint 8 expects simulated data only")
    ok(f"Diagnostics: {report.get('status')} (provider: {report.get('market_provider')})")


# -- 3. Live market data ----------------------------------------------------
def wait_for_live_data(token: str, timeout: int = 90) -> dict:
    step("Checking that live market data is flowing …")
    deadline = time.time() + timeout
    while time.time() < deadline:
        quotes = _request("GET", "/market/quotes", token=token).get("data", [])
        priced = [q for q in quotes if q.get("ltp") not in (None, "", "0")]
        if priced:
            sample = priced[0]
            ok(f"Live data flowing — {len(priced)} symbols quoted (e.g. {sample.get('symbol')} @ {sample.get('ltp')})")
            return sample
        time.sleep(3)
    raise ValidationError(
        "No live quotes appeared. Is the feed running? "
        "(docker compose logs feed) — provider="
        + os.environ.get("BKN_MARKET_PROVIDER", "simulated")
    )


# -- 3. Paper trade ---------------------------------------------------------
def execute_paper_trade(token: str, quote: dict) -> None:
    symbol = quote["symbol"]
    ltp = float(quote["ltp"])
    order = {
        "symbol": symbol,
        "side": "buy",
        "quantity": 1,
        "stop": round(ltp * 0.98, 2),
        "target": round(ltp * 1.02, 2),
        "strategy_key": "validation",
    }
    step(f"Submitting a paper BUY for {symbol} at ~{ltp} …")
    result = _request("POST", "/paper/orders", token=token, body=order)
    if result.get("status") != "filled":
        raise ValidationError(f"Paper order not filled: {result}")
    position_id = result["position"]["id"]
    ok(f"Paper order filled @ {result['fill_price']} (position #{position_id})")

    positions = _request("GET", "/paper/positions", token=token)
    if positions["count"] < 1:
        raise ValidationError("Filled order did not produce an open position")
    ok(f"Open positions visible: {positions['count']}")

    step("Closing the position at the live price …")
    closed = _request("POST", f"/paper/positions/{position_id}/close", token=token)
    ok(f"Position closed — net P&L {closed.get('net_pnl')} (reason: {closed.get('exit_reason')})")

    entries = _request("GET", "/journal/entries", token=token)
    if entries["count"] < 1:
        raise ValidationError("Closed trade was not recorded in the journal")
    ok(f"Trade journal recorded {entries['count']} closed trade(s)")


# -- 4. Analytics + report --------------------------------------------------
def check_analytics_and_report(token: str) -> None:
    summary = _request("GET", "/analytics/summary", token=token)
    if summary["total_trades"] < 1:
        raise ValidationError("Analytics summary shows no trades")
    ok(
        f"Analytics: {summary['total_trades']} trades, "
        f"win rate {summary['win_rate'] * 100:.0f}%, net P&L {summary['net_pnl']}"
    )

    step("Generating a weekly performance report …")
    report = _request("POST", "/analytics/reports/generate?kind=weekly", token=token)
    if report.get("kind") != "weekly" or "Weekly performance report" not in report.get("rendered", ""):
        raise ValidationError("Weekly report was not generated correctly")
    ok("Weekly performance report generated and stored")


# -- 5. No live orders ------------------------------------------------------
def assert_no_live_order_path(token: str) -> None:
    # The app serves its OpenAPI schema under the API prefix (/api/v1/openapi.json).
    openapi = _request("GET", "/openapi.json")
    paths = openapi.get("paths", {})
    offenders = [
        p
        for p in paths
        if ("order" in p.lower() and "paper" not in p.lower())
        or "/broker/orders" in p.lower()
        or p.lower().endswith("/place")
    ]
    if offenders:
        raise ValidationError(f"Unexpected order-placement endpoints found: {offenders}")
    ok("No live broker order-placement endpoints exist (advisory + paper only)")


def main() -> int:
    print("\n=== BKN AI Capital — end-to-end validation ===\n")
    try:
        wait_for_health()
        check_diagnostics()
        token = authenticate()
        quote = wait_for_live_data(token)
        execute_paper_trade(token, quote)
        check_analytics_and_report(token)
        assert_no_live_order_path(token)
    except ValidationError as exc:
        print(f"\n{_FAIL} VALIDATION FAILED: {exc}\n")
        return 1
    print(f"\n{_PASS} ALL CHECKS PASSED — the platform runs locally, live data flows,")
    print("   paper trades are executed and recorded, and reports generate automatically.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
