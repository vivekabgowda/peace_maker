"""Integration: the /paper, /journal and /analytics REST endpoints.

Seeds the live-quote cache (fakeredis under test) so the API can price fills.
"""

from __future__ import annotations

import httpx
import pytest
from app.modules.market_data import cache

pytestmark = pytest.mark.integration

_CREDS = {"email": "paper@example.com", "password": "s3cure-passw0rd"}


async def _auth(client: httpx.AsyncClient) -> dict[str, str]:
    resp = await client.post("/api/v1/auth/register", json=_CREDS)
    assert resp.status_code == 201, resp.text
    return {"Authorization": f"Bearer {resp.json()['tokens']['access_token']}"}


async def _seed_quote(symbol: str, ltp: float) -> None:
    await cache.set_quote(
        symbol,
        {
            "symbol": symbol,
            "ltp": str(ltp),
            "volume": 0,
            "vwap": str(ltp),
            "bid": str(ltp),
            "ask": str(ltp),
        },
    )


async def test_paper_endpoints_require_auth(client: httpx.AsyncClient) -> None:
    for path in ["/api/v1/paper/account", "/api/v1/paper/positions", "/api/v1/analytics/summary"]:
        resp = await client.get(path)
        assert resp.status_code == 401


async def test_submit_order_requires_live_price(client: httpx.AsyncClient) -> None:
    headers = await _auth(client)
    resp = await client.post(
        "/api/v1/paper/orders",
        headers=headers,
        json={"symbol": "NOPRICE", "side": "buy", "quantity": 1},
    )
    assert resp.status_code == 409  # no live price


async def test_full_paper_to_analytics_flow(client: httpx.AsyncClient) -> None:
    headers = await _auth(client)
    await _seed_quote("TCS", 100.0)

    # Submit a paper order (filled at the live price).
    submit = await client.post(
        "/api/v1/paper/orders",
        headers=headers,
        json={"symbol": "TCS", "side": "buy", "quantity": 10, "stop": 95.0, "target": 130.0},
    )
    assert submit.status_code == 200, submit.text
    body = submit.json()
    assert body["status"] == "filled"
    position_id = body["position"]["id"]

    # It shows up as an open position with a live mark.
    positions = await client.get("/api/v1/paper/positions", headers=headers)
    assert positions.json()["count"] == 1
    assert positions.json()["positions"][0]["symbol"] == "TCS"

    # Account reserved the notional.
    account = await client.get("/api/v1/paper/account", headers=headers)
    assert account.json()["open_positions"] == 1

    # Price moves up; close the position manually at the new live price.
    await _seed_quote("TCS", 108.0)
    close = await client.post(f"/api/v1/paper/positions/{position_id}/close", headers=headers)
    assert close.status_code == 200, close.text
    assert close.json()["net_pnl"] > 0

    # Journal recorded the closed trade.
    journal = await client.get("/api/v1/journal/entries", headers=headers)
    assert journal.json()["count"] == 1
    entry = journal.json()["entries"][0]
    assert entry["symbol"] == "TCS" and entry["outcome"] == "win"

    # Annotate it.
    patched = await client.patch(
        f"/api/v1/journal/entries/{entry['id']}",
        headers=headers,
        json={"notes": "clean breakout", "tags": ["breakout"]},
    )
    assert patched.status_code == 200
    assert patched.json()["notes"] == "clean breakout"

    # Analytics summary reflects the trade.
    summary = await client.get("/api/v1/analytics/summary", headers=headers)
    assert summary.json()["total_trades"] == 1
    assert summary.json()["win_rate"] == 1.0

    # A weekly report can be generated on demand and retrieved.
    gen = await client.post("/api/v1/analytics/reports/generate?kind=weekly", headers=headers)
    assert gen.status_code == 200, gen.text
    assert gen.json()["kind"] == "weekly"
    latest = await client.get("/api/v1/analytics/reports/latest?kind=weekly", headers=headers)
    assert latest.status_code == 200
    assert "Weekly performance report" in latest.json()["rendered"]
