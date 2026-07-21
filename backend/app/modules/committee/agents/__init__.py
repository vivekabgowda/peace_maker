"""The seven committee agents, in review order."""

from __future__ import annotations

from app.modules.committee.agents.devils_advocate import DevilsAdvocate
from app.modules.committee.agents.news import NewsAnalyst
from app.modules.committee.agents.options import OptionsAnalyst
from app.modules.committee.agents.portfolio_manager import PortfolioManager
from app.modules.committee.agents.risk import RiskManager
from app.modules.committee.agents.strategist import ChiefMarketStrategist
from app.modules.committee.agents.technical import TechnicalAnalyst
from app.modules.committee.base import Agent

# Canonical committee roster and order (specialists first, PM last before CIO).
DEFAULT_AGENTS: tuple[type[Agent], ...] = (
    ChiefMarketStrategist,
    TechnicalAnalyst,
    OptionsAnalyst,
    NewsAnalyst,
    RiskManager,
    DevilsAdvocate,
    PortfolioManager,
)

__all__ = [
    "DEFAULT_AGENTS",
    "ChiefMarketStrategist",
    "DevilsAdvocate",
    "NewsAnalyst",
    "OptionsAnalyst",
    "PortfolioManager",
    "RiskManager",
    "TechnicalAnalyst",
]
