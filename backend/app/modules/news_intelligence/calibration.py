"""News Intelligence — continuous self-calibration (Sprint 11 pt.3).

For every closed trade, ask: was the news that preceded entry *right*? We match
each :class:`JournalEntry` to the most recent news assessment for its symbol at or
before entry, compare the news sentiment against the realized price move, and
aggregate accuracy + performance stats. This is the learning loop — it improves
the agent's calibration over time **without** changing any trading strategy.

Read-only analytics: it never mutates trades. Consumed by the Analytics UI
(performance by sentiment, avg return after positive vs negative news, accuracy).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.journal.orm import JournalEntry
from app.modules.news_intelligence.orm import NewsAssessmentRow

# A news score below this magnitude is treated as "no directional call".
_MIN_SIGNIFICANT = 10


@dataclass
class _Bucket:
    trades: int = 0
    wins: int = 0
    r_sum: float = 0.0

    def add(self, r: float, win: bool) -> None:
        self.trades += 1
        self.wins += int(win)
        self.r_sum += r

    def as_dict(self) -> dict[str, float]:
        return {
            "trades": self.trades,
            "win_rate": round(self.wins / self.trades, 4) if self.trades else 0.0,
            "avg_r": round(self.r_sum / self.trades, 4) if self.trades else 0.0,
        }


@dataclass
class _Accumulator:
    matched: int = 0
    correct: int = 0
    positive: _Bucket = field(default_factory=_Bucket)
    negative: _Bucket = field(default_factory=_Bucket)
    by_sentiment: dict[str, _Bucket] = field(default_factory=dict)


class NewsCalibrationService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _assessments_by_symbol(self) -> dict[str, list[NewsAssessmentRow]]:
        rows = (await self._session.execute(select(NewsAssessmentRow))).scalars().all()
        by_symbol: dict[str, list[NewsAssessmentRow]] = {}
        for r in rows:
            by_symbol.setdefault(r.symbol.upper(), []).append(r)
        for lst in by_symbol.values():
            lst.sort(key=lambda a: a.generated_at)
        return by_symbol

    @staticmethod
    def _news_at_entry(rows: list[NewsAssessmentRow], entry_ts: object) -> NewsAssessmentRow | None:
        """Latest assessment generated at or before the trade's entry."""
        chosen: NewsAssessmentRow | None = None
        for r in rows:
            if r.generated_at <= entry_ts:  # type: ignore[operator]
                chosen = r
            else:
                break
        return chosen

    async def accuracy(self) -> dict[str, object]:
        """Aggregate news calibration across all closed trades that had news."""
        by_symbol = await self._assessments_by_symbol()
        entries = (await self._session.execute(select(JournalEntry))).scalars().all()
        acc = _Accumulator()

        for e in entries:
            rows = by_symbol.get(e.symbol.upper())
            if not rows:
                continue
            row = self._news_at_entry(rows, e.entry_ts)
            if row is None or abs(row.news_score) < _MIN_SIGNIFICANT:
                continue

            r = float(e.r_multiple)
            win = e.outcome == "win"
            # Realized price move: for a short, a positive r means price fell.
            price_up = (e.direction == "long") == (r >= 0)
            news_up = row.news_score > 0

            acc.matched += 1
            acc.correct += int(news_up == price_up)
            (acc.positive if news_up else acc.negative).add(r, win)
            acc.by_sentiment.setdefault(row.sentiment, _Bucket()).add(r, win)

        return {
            "trades_with_news": acc.matched,
            "accuracy": round(acc.correct / acc.matched, 4) if acc.matched else 0.0,
            "avg_r_after_positive_news": acc.positive.as_dict()["avg_r"],
            "avg_r_after_negative_news": acc.negative.as_dict()["avg_r"],
            "positive_news": acc.positive.as_dict(),
            "negative_news": acc.negative.as_dict(),
            "by_sentiment": {k: v.as_dict() for k, v in sorted(acc.by_sentiment.items())},
        }
