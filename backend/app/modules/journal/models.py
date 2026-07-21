"""Journal domain types (Sprint 7)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class Outcome(StrEnum):
    WIN = "win"
    LOSS = "loss"
    BREAKEVEN = "breakeven"

    @classmethod
    def of(cls, net_pnl: float) -> Outcome:
        if net_pnl > 0:
            return cls.WIN
        if net_pnl < 0:
            return cls.LOSS
        return cls.BREAKEVEN


@dataclass(frozen=True, slots=True)
class ClosedTrade:
    """The minimal, source-agnostic description of a closed round-trip that the
    journal records. Produced by the paper-trading service on position close."""

    position_id: int | None
    account_id: int | None
    symbol: str
    direction: str  # "long" | "short"
    quantity: int
    strategy_key: str | None
    source: str
    entry_price: float
    entry_ts: datetime
    exit_price: float
    exit_ts: datetime
    exit_reason: str | None
    gross_pnl: float
    fees: float
    net_pnl: float
    r_multiple: float
    holding_seconds: int

    @property
    def outcome(self) -> Outcome:
        return Outcome.of(self.net_pnl)


@dataclass(frozen=True, slots=True)
class JournalRecord:
    """A persisted journal entry projected back into the domain (read side)."""

    id: int
    symbol: str
    direction: str
    quantity: int
    strategy_key: str | None
    source: str
    entry_price: float
    entry_ts: datetime
    exit_price: float
    exit_ts: datetime
    exit_reason: str | None
    gross_pnl: float
    fees: float
    net_pnl: float
    r_multiple: float
    holding_seconds: int
    outcome: str
    notes: str | None = None
    tags: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "symbol": self.symbol,
            "direction": self.direction,
            "quantity": self.quantity,
            "strategy_key": self.strategy_key,
            "source": self.source,
            "entry_price": round(self.entry_price, 4),
            "entry_ts": self.entry_ts.isoformat(),
            "exit_price": round(self.exit_price, 4),
            "exit_ts": self.exit_ts.isoformat(),
            "exit_reason": self.exit_reason,
            "gross_pnl": round(self.gross_pnl, 2),
            "fees": round(self.fees, 2),
            "net_pnl": round(self.net_pnl, 2),
            "r_multiple": round(self.r_multiple, 4),
            "holding_seconds": self.holding_seconds,
            "outcome": self.outcome,
            "notes": self.notes,
            "tags": self.tags,
        }
