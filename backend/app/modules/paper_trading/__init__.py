"""Paper-trading engine (Sprint 7).

Simulates order execution against live, read-only market prices and records every
round-trip to the trade journal. There is no live broker order path anywhere in
this module — by design.
"""

from __future__ import annotations

from app.modules.paper_trading.models import (
    ExitReason,
    OrderRequest,
    OrderSide,
    OrderType,
    Position,
)
from app.modules.paper_trading.service import PaperTradingService

__all__ = [
    "ExitReason",
    "OrderRequest",
    "OrderSide",
    "OrderType",
    "PaperTradingService",
    "Position",
]
