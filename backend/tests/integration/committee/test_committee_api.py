"""Integration tests for the /committee endpoints."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import httpx
import pytest
from app.core.database import async_session_factory
from app.modules.market_data.orm import Instrument
from app.modules.market_data.repository import MarketDataRepository

pytestmark = pytest.mark.integration

_CREDS = {"email": "committee@example.com", "password": "s3cure-passw0rd"}


async def _auth(client: httpx.AsyncClient) -> dict[str, str]:
    resp = await client.post("/api/v1/auth/register", json=_CREDS)
    assert resp.status_code == 201, resp.text
    return {"Authorization": f"Bearer {resp.json()['tokens']['access_token']}"}


async def _seed() -> None:
    base = datetime(2026, 3, 2, tzinfo=UTC)
    async with async_session_factory() as session:
        session.add(Instrument(symbol="NIFTY", exchange="NSE", instrument_type="INDEX"))
        session.add(
            Instrument(
                symbol="TCS", exchange="NSE", instrument_type="EQ", sector="IT", in_nifty500=True
            )
        )
        await session.flush()
        repo = MarketDataRepository(session)
        ids = await repo.symbol_id_map()
        for sym, start in (("NIFTY", 20000.0), ("TCS", 3000.0)):
            iid = ids[sym]
            for i in range(60):
                px = start * (1 + i * 0.004)
                await repo.upsert_candle(
                    iid,
                    "1d",
                    base + timedelta(days=i),
                    Decimal(str(round(px * 0.999, 2))),
                    Decimal(str(round(px * 1.006, 2))),
                    Decimal(str(round(px * 0.994, 2))),
                    Decimal(str(round(px, 2))),
                    1_000_000,
                )
        await session.commit()


async def test_committee_endpoints_require_auth(client: httpx.AsyncClient) -> None:
    for path in ["/api/v1/committee/agents", "/api/v1/committee/review"]:
        resp = await client.get(path)
        assert resp.status_code == 401


async def test_roster_lists_seven_agents(client: httpx.AsyncClient) -> None:
    headers = await _auth(client)
    resp = await client.get("/api/v1/committee/agents", headers=headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 7
    roles = {a["role"] for a in data}
    assert "risk_manager" in roles and "devils_advocate" in roles


async def test_review_convenes_and_returns_full_decision(client: httpx.AsyncClient) -> None:
    headers = await _auth(client)
    await _seed()
    resp = await client.get("/api/v1/committee/review", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    if not body["convened"]:
        # A valid outcome (e.g. no-trade); must still explain itself.
        assert body["reason"]
        return
    decision = body["decision"]
    # Every mandated CIO field is present.
    for key in (
        "recommendation",
        "confidence_breakdown",
        "bull_case",
        "bear_case",
        "invalidation",
        "risk",
        "position",
        "expected_holding",
        "alternatives",
        "rationale",
    ):
        assert key in decision, key
    assert len(body["reports"]) == 7
    # No black box: every report finding carries a citation.
    for report in body["reports"]:
        for finding in report["findings"]:
            assert finding["citation"]
