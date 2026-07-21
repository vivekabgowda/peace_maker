"""System diagnostics — aggregate the live status of every subsystem (Sprint 8).

Powers `GET /api/v1/health/diagnostics` and the frontend diagnostics page. Each
check is defensive: a failing subsystem yields an unhealthy :class:`ServiceStatus`
rather than raising, so the diagnostics endpoint itself never hard-fails — that is
the whole point of a diagnostics page.

The **market feed** is checked *indirectly* via the live quote cache: if fresh
quotes are present, the ingestion pipeline (feed → event bus → candle builder →
cache) is demonstrably working end to end. With the simulated provider this proves
the complete mock-data pipeline without any broker.
"""

from __future__ import annotations

import contextlib
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import async_session_factory
from app.core.redis import get_redis, ping_redis
from app.modules.market_data import cache


@dataclass(slots=True)
class ServiceStatus:
    name: str
    kind: str
    healthy: bool
    detail: str
    latency_ms: float | None = None
    meta: dict[str, object] = field(default_factory=dict)

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "kind": self.kind,
            "healthy": self.healthy,
            "detail": self.detail,
            "latency_ms": self.latency_ms,
            "meta": self.meta,
        }


async def check_database() -> ServiceStatus:
    settings = get_settings()
    is_sqlite = str(settings.database_url).startswith("sqlite")
    kind = "sqlite" if is_sqlite else "postgresql"
    try:
        start = time.perf_counter()
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
            timescale = False
            hypertables = 0
            if not is_sqlite:
                ext = await session.scalar(
                    text("SELECT 1 FROM pg_extension WHERE extname = 'timescaledb'")
                )
                timescale = ext is not None
                if timescale:
                    hypertables = (
                        await session.scalar(
                            text("SELECT count(*) FROM timescaledb_information.hypertables")
                        )
                    ) or 0
        latency = round((time.perf_counter() - start) * 1000, 2)
        if timescale:
            kind = "postgresql + timescaledb"
        return ServiceStatus(
            name="database",
            kind=kind,
            healthy=True,
            detail="SELECT 1 ok" + (f"; {hypertables} hypertables" if timescale else ""),
            latency_ms=latency,
            meta={"timescaledb": timescale, "hypertables": hypertables},
        )
    except Exception as exc:  # pragma: no cover - exercised via failure injection
        return ServiceStatus(
            name="database", kind=kind, healthy=False, detail=f"unreachable: {exc}"
        )


async def check_redis() -> ServiceStatus:
    try:
        start = time.perf_counter()
        ok = await ping_redis()
        latency = round((time.perf_counter() - start) * 1000, 2)
        info_detail = "PONG"
        with contextlib.suppress(Exception):
            server = await get_redis().info("server")
            if isinstance(server, dict) and server.get("redis_version"):
                info_detail = f"redis {server['redis_version']}"
        return ServiceStatus(
            name="redis",
            kind="cache + streams",
            healthy=bool(ok),
            detail=info_detail if ok else "ping failed",
            latency_ms=latency,
        )
    except Exception as exc:  # pragma: no cover
        return ServiceStatus(name="redis", kind="cache + streams", healthy=False, detail=str(exc))


async def check_market_feed() -> ServiceStatus:
    """Infer feed health from the freshness of the live quote cache."""
    settings = get_settings()
    provider = settings.market_provider
    ttl = settings.quote_cache_ttl_seconds
    try:
        market_status = await cache.get_market_status()
        quotes = await cache.get_all_quotes()
        live_symbols = len(quotes)
        # Freshest quote age across all symbols.
        ages: list[float] = []
        now = time.time()
        for q in quotes:
            symbol = q.get("symbol")
            if not symbol:
                continue
            fresh = await cache.get_freshness(str(symbol))
            if fresh is not None:
                ages.append(now - fresh)
        freshest = round(min(ages), 2) if ages else None
        # Healthy when fresh data is flowing (age within the cache TTL window).
        healthy = live_symbols > 0 and freshest is not None and freshest <= ttl * 2
        if healthy:
            detail = f"{live_symbols} symbols quoted; freshest {freshest}s ago ({provider})"
        elif live_symbols == 0:
            detail = f"no live quotes yet (provider={provider}); is the feed process running?"
        else:
            detail = f"quotes stale (freshest {freshest}s > {ttl * 2}s TTL); feed may be stalled"
        return ServiceStatus(
            name="market_feed",
            kind="ingestion pipeline",
            healthy=healthy,
            detail=detail,
            meta={
                "provider": provider,
                "market_status": market_status,
                "live_symbols": live_symbols,
                "freshest_quote_age_seconds": freshest,
            },
        )
    except Exception as exc:  # pragma: no cover
        return ServiceStatus(
            name="market_feed", kind="ingestion pipeline", healthy=False, detail=str(exc)
        )


def check_event_stream() -> ServiceStatus:
    enabled = get_settings().event_stream_enabled
    return ServiceStatus(
        name="event_stream",
        kind="redis streams (cross-instance fan-out)",
        healthy=True,
        detail="enabled" if enabled else "disabled (single-process bus)",
        meta={"enabled": enabled},
    )


async def gather_diagnostics() -> dict[str, object]:
    settings = get_settings()
    database = await check_database()
    redis = await check_redis()
    feed = await check_market_feed()
    stream = check_event_stream()
    services = [database, redis, feed, stream]

    # Core services whose failure means the platform is degraded. The feed is
    # informational here (it may legitimately have no data outside market hours),
    # so it does not force "degraded", but it is surfaced prominently.
    core_healthy = database.healthy and redis.healthy
    overall = "healthy" if core_healthy else "degraded"

    return {
        "status": overall,
        "version": settings.version,
        "environment": settings.env,
        "timestamp": datetime.now(UTC).isoformat(),
        "market_provider": settings.market_provider,
        "broker_connected": False,  # Sprint 8: no live broker by design.
        "services": [s.as_dict() for s in services],
        "pipeline": feed.meta,
    }
