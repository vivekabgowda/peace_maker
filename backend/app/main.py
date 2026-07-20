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

    # Bridge market events → dashboard WebSocket clients.
    from app.websocket.gateway import register_ws_bridge

    register_ws_bridge()

    # Optionally start the live market feed (off by default; enabled in envs
    # that have a provider configured).
    runner = None
    if settings.market_feed_enabled:
        from app.modules.market_data.runner import MarketFeedRunner

        runner = MarketFeedRunner()
        await runner.start()
        logger.info("market_feed_enabled", provider=settings.market_provider)

    try:
        yield
    finally:
        if runner is not None:
            await runner.stop()
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
