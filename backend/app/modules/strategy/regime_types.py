"""Market regime taxonomy shared by the regime engine and every strategy.

Kept in the ``strategy`` package (not ``scanner``) so strategies can declare
their ``compatible_regimes`` without importing the scanner — the regime *engine*
lives in ``app.modules.scanner.regime`` and imports these names.
"""

from __future__ import annotations

from enum import StrEnum


class MarketRegime(StrEnum):
    """The market states the engine classifies (Sprint 3, Step 1).

    A single snapshot can be described by one *primary* trend/structure regime
    plus any number of *overlay* regimes (volatility, event, gap). Strategies
    gate on the whole active set, not just the primary.
    """

    # Primary trend / structure
    TRENDING_BULL = "trending_bull"
    TRENDING_BEAR = "trending_bear"
    RANGE = "range"
    ACCUMULATION = "accumulation"
    DISTRIBUTION = "distribution"
    # Volatility overlays
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"
    # Event overlays (from the calendar / macro feed)
    EXPIRY_DAY = "expiry_day"
    RBI_DAY = "rbi_day"
    BUDGET_DAY = "budget_day"
    ELECTION_EVENT = "election_event"
    GLOBAL_RISK_OFF = "global_risk_off"
    # Open / gap overlays
    GAP_UP_TREND = "gap_up_trend"
    GAP_DOWN_PANIC = "gap_down_panic"


# Regimes in which taking fresh directional risk is discouraged platform-wide.
# The scanner still ranks, but the opportunity book flags these and biases
# toward NO-TRADE unless a strategy explicitly opts in.
HOSTILE_REGIMES: frozenset[MarketRegime] = frozenset(
    {
        MarketRegime.GLOBAL_RISK_OFF,
        MarketRegime.GAP_DOWN_PANIC,
    }
)

# Overlays that describe *conditions* rather than a tradable trend. Strategies
# compatible with a trend regime are not auto-rejected just because one of these
# is also active; they are surfaced to scoring instead.
OVERLAY_REGIMES: frozenset[MarketRegime] = frozenset(
    {
        MarketRegime.HIGH_VOLATILITY,
        MarketRegime.LOW_VOLATILITY,
        MarketRegime.EXPIRY_DAY,
        MarketRegime.RBI_DAY,
        MarketRegime.BUDGET_DAY,
        MarketRegime.ELECTION_EVENT,
        MarketRegime.GLOBAL_RISK_OFF,
        MarketRegime.GAP_UP_TREND,
        MarketRegime.GAP_DOWN_PANIC,
    }
)

PRIMARY_REGIMES: frozenset[MarketRegime] = frozenset(
    {
        MarketRegime.TRENDING_BULL,
        MarketRegime.TRENDING_BEAR,
        MarketRegime.RANGE,
        MarketRegime.ACCUMULATION,
        MarketRegime.DISTRIBUTION,
    }
)
