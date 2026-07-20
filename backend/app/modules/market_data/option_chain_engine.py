"""Option chain engine.

``summarize_chain`` is a pure function that turns a raw
:class:`OptionChainSnapshot` into an enriched summary (PCR, max pain, per-strike
CE/PE OI + greeks). ``OptionChainEngine`` wires it to the cache, persistence, and
the event bus.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger
from app.modules.market_data import cache
from app.modules.market_data.domain.models import OptionChainSnapshot
from app.modules.market_data.options_math import (
    black_scholes,
    max_pain,
    put_call_ratio,
)
from app.modules.market_data.repository import MarketDataRepository
from app.shared.events import OptionChainUpdated, event_bus

logger = get_logger("option_chain_engine")


def _years_to_expiry(expiry: str) -> float:
    try:
        exp = date.fromisoformat(expiry)
    except ValueError:
        return 7 / 365.0
    days = (exp - datetime.now(UTC).date()).days
    return max(days, 0) / 365.0 + 1e-6


def summarize_chain(snapshot: OptionChainSnapshot, rate: float) -> dict[str, Any]:
    """Aggregate a raw chain into PCR, max pain, totals, and per-strike rows."""
    spot = float(snapshot.spot)
    t = _years_to_expiry(snapshot.expiry)
    by_strike: dict[float, dict[str, Any]] = {}
    oi_map: dict[float, tuple[int, int]] = {}
    total_ce_oi = total_pe_oi = 0

    for q in snapshot.quotes:
        strike = float(q.strike)
        row = by_strike.setdefault(strike, {"strike": strike})
        greeks = black_scholes(spot, strike, t, rate, (q.iv or 15.0) / 100.0, q.option_type)
        side = q.option_type.lower()
        row[f"{side}_ltp"] = float(q.ltp)
        row[f"{side}_oi"] = q.oi
        row[f"{side}_oi_change"] = q.oi_change
        row[f"{side}_iv"] = q.iv
        row[f"{side}_delta"] = round(greeks.delta, 4)
        row[f"{side}_theta"] = round(greeks.theta, 4)
        ce_oi, pe_oi = oi_map.get(strike, (0, 0))
        if q.option_type == "CE":
            total_ce_oi += q.oi
            oi_map[strike] = (q.oi, pe_oi)
        else:
            total_pe_oi += q.oi
            oi_map[strike] = (ce_oi, q.oi)

    pcr = put_call_ratio(total_pe_oi, total_ce_oi)
    mp = max_pain(oi_map)
    return {
        "underlying": snapshot.underlying,
        "expiry": snapshot.expiry,
        "spot": spot,
        "ts": snapshot.ts.isoformat(),
        "pcr": round(pcr, 4) if pcr is not None else None,
        "max_pain": mp,
        "total_ce_oi": total_ce_oi,
        "total_pe_oi": total_pe_oi,
        "strikes": [by_strike[s] for s in sorted(by_strike)],
    }


class OptionChainEngine:
    """Refreshes, enriches, caches, persists, and broadcasts option chains."""

    def __init__(self, repository: MarketDataRepository) -> None:
        self._repo = repository
        self._rate = get_settings().risk_free_rate

    async def process(self, snapshot: OptionChainSnapshot) -> dict[str, Any]:
        summary = summarize_chain(snapshot, self._rate)
        await cache.set_option_summary(snapshot.underlying, summary)
        await self._repo.insert_option_snapshot(
            underlying=snapshot.underlying,
            expiry=snapshot.expiry,
            ts=snapshot.ts,
            spot=snapshot.spot,
            pcr=Decimal(str(summary["pcr"])) if summary["pcr"] is not None else None,
            max_pain=Decimal(str(summary["max_pain"])) if summary["max_pain"] is not None else None,
            total_ce_oi=summary["total_ce_oi"],
            total_pe_oi=summary["total_pe_oi"],
        )
        await event_bus.publish(
            OptionChainUpdated(
                source="option_chain_engine",
                underlying=snapshot.underlying,
                expiry=snapshot.expiry,
                pcr=summary["pcr"],
                max_pain=summary["max_pain"],
                total_ce_oi=summary["total_ce_oi"],
                total_pe_oi=summary["total_pe_oi"],
            )
        )
        return summary
