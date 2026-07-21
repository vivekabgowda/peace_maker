"""Portfolio awareness (Sprint 3, Step 7).

Turns a ranked list of independent opportunities into a *portfolio-coherent*
short-list: it de-duplicates correlated ideas, caps sector concentration, and
enforces gross-exposure and daily-risk budgets. Runs greedily from best to worst
so the highest-conviction ideas claim the budget first.

Advisory-only in V1: 'positions' are the ideas the book is about to recommend,
plus any the caller passes in as already held.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from app.modules.scanner.opportunity import Opportunity
from app.modules.strategy.base import Direction


@dataclass(frozen=True, slots=True)
class PortfolioConstraints:
    """Risk/concentration budget for a single recommendation set."""

    max_positions: int = 10
    max_per_sector: int = 3
    max_total_risk_pct: float = 6.0  # sum of per-idea risk (% of capital)
    per_trade_risk_pct: float = 1.0  # assumed risk budget per idea
    correlation_threshold: float = 0.7


@dataclass(frozen=True, slots=True)
class Held:
    """An existing position the new book must stay coherent with."""

    symbol: str
    sector: str | None
    direction: Direction


@dataclass
class PortfolioResult:
    """Outcome of applying constraints to a ranked book."""

    accepted: list[Opportunity] = field(default_factory=list)
    dropped: list[tuple[Opportunity, str]] = field(default_factory=list)
    sector_counts: dict[str, int] = field(default_factory=dict)
    total_risk_pct: float = 0.0


# A correlation oracle maps an unordered pair of symbols to a 0..1 correlation.
Correlation = Callable[[str, str], float]


def _default_correlation(sector_of: dict[str, str | None]) -> Correlation:
    """Fallback correlation proxy: same sector ⇒ 0.8, else 0.2."""

    def corr(a: str, b: str) -> float:
        return 0.8 if sector_of.get(a) and sector_of.get(a) == sector_of.get(b) else 0.2

    return corr


class PortfolioManager:
    """Applies portfolio constraints to a ranked opportunity list."""

    def __init__(self, constraints: PortfolioConstraints | None = None) -> None:
        self.constraints = constraints or PortfolioConstraints()

    def apply(
        self,
        ranked: Sequence[Opportunity],
        *,
        held: Sequence[Held] = (),
        correlation: Correlation | None = None,
    ) -> PortfolioResult:
        c = self.constraints
        sector_of = {o.symbol: _sector(o) for o in ranked}
        corr = correlation or _default_correlation(sector_of)

        result = PortfolioResult()
        # Seed sector counts / accepted symbols with existing holdings.
        for h in held:
            if h.sector:
                result.sector_counts[h.sector] = result.sector_counts.get(h.sector, 0) + 1
        accepted_syms: list[tuple[str, Direction]] = [(h.symbol, h.direction) for h in held]

        for opp in ranked:
            if len(result.accepted) >= c.max_positions:
                result.dropped.append((opp, "position count cap reached"))
                continue
            if result.total_risk_pct + c.per_trade_risk_pct > c.max_total_risk_pct:
                result.dropped.append((opp, "total risk budget exhausted"))
                continue
            sector = _sector(opp)
            if sector and result.sector_counts.get(sector, 0) >= c.max_per_sector:
                result.dropped.append((opp, f"sector cap for {sector} reached"))
                continue
            dupe = _correlated_conflict(opp, accepted_syms, corr, c.correlation_threshold)
            if dupe is not None:
                result.dropped.append((opp, f"correlated with {dupe} already selected"))
                continue

            result.accepted.append(opp)
            accepted_syms.append((opp.symbol, opp.direction))
            if sector:
                result.sector_counts[sector] = result.sector_counts.get(sector, 0) + 1
            result.total_risk_pct += c.per_trade_risk_pct

        return result


def _sector(opp: Opportunity) -> str | None:
    """Sector is carried as a ``sector:<name>`` tag the scanner attaches."""
    for tag in opp.signal.tags:
        if tag.startswith("sector:"):
            return tag.split(":", 1)[1]
    return None


def _correlated_conflict(
    opp: Opportunity,
    accepted: Sequence[tuple[str, Direction]],
    corr: Correlation,
    threshold: float,
) -> str | None:
    """Return the symbol this opp is too correlated with (same direction), else None."""
    for sym, direction in accepted:
        if sym == opp.symbol:
            return sym
        if direction is opp.direction and corr(opp.symbol, sym) >= threshold:
            return sym
    return None
