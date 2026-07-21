"""Aggregate all v1 module routers under a single APIRouter.

New modules add their router here; versioning is handled by mounting this under
``/api/v1`` in the app factory.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.modules.auth.router import router as auth_router
from app.modules.health.router import router as health_router
from app.modules.market_data.api import router as market_router
from app.modules.news.api import router as news_router
from app.modules.scanner.api import router as alpha_router
from app.modules.users.router import router as users_router
from app.websocket.gateway import router as ws_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(market_router)
api_router.include_router(news_router)
api_router.include_router(alpha_router)
api_router.include_router(ws_router)
