"""Integration tests for the health endpoints."""

from __future__ import annotations

import httpx
import pytest

pytestmark = pytest.mark.integration


async def test_liveness_ok(client: httpx.AsyncClient) -> None:
    resp = await client.get("/api/v1/health/live")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "version" in body


async def test_readiness_reports_checks(client: httpx.AsyncClient) -> None:
    resp = await client.get("/api/v1/health/ready")
    # Database is reachable (sqlite); Redis is not, so overall may be degraded.
    body = resp.json()
    assert "database" in body["checks"]
    assert body["checks"]["database"] is True
    assert resp.status_code in (200, 503)


async def test_root_and_correlation_header(client: httpx.AsyncClient) -> None:
    resp = await client.get("/")
    assert resp.status_code == 200
    assert "X-Correlation-ID" in resp.headers
