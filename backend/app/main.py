"""FastAPI application factory.

Wires configuration, logging, middleware, exception handlers, metrics, the
versioned API router, and lifecycle hooks. No business logic lives here.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.responses import Response

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.database import dispose_engine
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.core.middleware import CorrelationMiddleware
from app.core.redis import close_redis

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    logger.info("startup", env=settings.env, version=settings.version)

    # Start the event bus workers and bridge market events → WebSocket clients.
    from app.shared.events import event_bus
    from app.websocket.gateway import register_ws_bridge

    await event_bus.start()
    register_ws_bridge()

    # NOTE: the live market feed no longer runs in the API process. It runs as a
    # dedicated Feed Service (app.feed) with a single-instance lock — see R0 #1.
    # The API only consumes events (for WebSocket fan-out) via the bus/Redis.
    if settings.market_feed_enabled:
        logger.warning(
            "market_feed_enabled_in_api_ignored",
            detail="Run the dedicated feed service (python -m app.feed); the API never ingests.",
        )

    try:
        yield
    finally:
        await event_bus.stop()
        await dispose_engine()
        await close_redis()
        logger.info("shutdown")


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(level=settings.log_level, json_logs=settings.log_json)

    app = FastAPI(
        title=settings.project_name,
        version=settings.version,
        description="BKN AI Capital — API. Advisory only; no trade execution in V1.",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url=f"{settings.api_v1_prefix}/openapi.json",
        lifespan=lifespan,
    )

    app.add_middleware(CorrelationMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Correlation-ID"],
    )

    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    @app.get("/", include_in_schema=False)
    async def root() -> dict[str, str]:
        return {
            "name": settings.project_name,
            "version": settings.version,
            "docs": "/docs",
        }

    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return app


app = create_app()
