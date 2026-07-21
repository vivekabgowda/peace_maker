"""Feed Service ASGI app — health endpoints + supervised pipeline lifespan.

Run as its own container/process: ``python -m app.feed`` (uvicorn). It exposes
``/health/live`` and ``/health/ready`` for Docker/orchestration and ``/metrics``
for Prometheus. Ingestion starts only after the single-instance lock is acquired.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response, status
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.core.config import get_settings
from app.core.database import dispose_engine
from app.core.logging import configure_logging, get_logger
from app.core.redis import close_redis
from app.feed.lock import SingleInstanceLock
from app.feed.service import FeedService
from app.shared.events import event_bus

logger = get_logger("feed_app")

_state: dict[str, object] = {}


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(level=settings.log_level, json_logs=settings.log_json)
    logger.info("feed_startup", provider=settings.market_provider)

    await event_bus.start()
    lock = SingleInstanceLock()
    service = FeedService()
    _state["lock"] = lock
    _state["service"] = service

    # Acquire leadership (standby instances block here), then start ingestion.
    await lock.acquire_blocking()
    await service.start()

    try:
        yield
    finally:
        await service.stop()
        await lock.release()
        await event_bus.stop()
        await dispose_engine()
        await close_redis()
        logger.info("feed_shutdown")


app = FastAPI(title="BKN Feed Service", lifespan=lifespan, docs_url=None, redoc_url=None)


@app.get("/health/live")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready")
async def ready(response: Response) -> dict[str, object]:
    lock: SingleInstanceLock | None = _state.get("lock")  # type: ignore[assignment]
    service: FeedService | None = _state.get("service")  # type: ignore[assignment]
    is_leader = bool(lock and lock.is_leader)
    health = service.health() if service else {"started": False}
    supervisor = health.get("supervisor", {}) if isinstance(health, dict) else {}
    healthy = (
        is_leader and bool(supervisor.get("healthy", False))
        if isinstance(supervisor, dict)
        else False
    )
    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"leader": is_leader, "health": health}


@app.get("/metrics", include_in_schema=False)
async def metrics_endpoint() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
