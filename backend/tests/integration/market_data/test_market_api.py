"""Integration tests for the market-data + news read endpoints."""

from __future__ import annotations

import httpx
import pytest

pytestmark = pytest.mark.integration

_CREDS = {"email": "md@example.com", "password": "s3cure-passw0rd"}


async def _token(client: httpx.AsyncClient) -> str:
    resp = await client.post("/api/v1/auth/register", json=_CREDS)
    assert resp.status_code == 201, resp.text
    return resp.json()["tokens"]["access_token"]


async def _auth(client: httpx.AsyncClient) -> dict[str, str]:
    return {"Authorization": f"Bearer {await _token(client)}"}


async def test_endpoints_require_auth(client: httpx.AsyncClient) -> None:
    for path in ["/api/v1/market/indices", "/api/v1/market/status", "/api/v1/news"]:
        resp = await client.get(path)
        assert resp.status_code == 401


async def test_providers_endpoint_lists_simulated(client: httpx.AsyncClient) -> None:
    headers = await _auth(client)
    resp = await client.get("/api/v1/market/providers", headers=headers)
    assert resp.status_code == 200
    assert "simulated" in resp.json()["providers"]


async def test_market_reads_return_structure(client: httpx.AsyncClient) -> None:
    headers = await _auth(client)
    # Empty environment (no live feed / redis) — endpoints must still succeed.
    for path in [
        "/api/v1/market/indices",
        "/api/v1/market/quotes",
        "/api/v1/market/instruments",
    ]:
        resp = await client.get(path, headers=headers)
        assert resp.status_code == 200
        assert isinstance(resp.json()["data"], list)


async def test_status_and_breadth(client: httpx.AsyncClient) -> None:
    headers = await _auth(client)
    status = await client.get("/api/v1/market/status", headers=headers)
    assert status.status_code == 200
    assert "status" in status.json()

    breadth = await client.get("/api/v1/market/breadth", headers=headers)
    assert breadth.status_code == 200
    body = breadth.json()
    assert set(body["breadth"]) == {"advances", "declines", "unchanged"}


async def test_news_endpoint(client: httpx.AsyncClient) -> None:
    headers = await _auth(client)
    resp = await client.get("/api/v1/news", headers=headers)
    assert resp.status_code == 200
    assert isinstance(resp.json()["data"], list)
