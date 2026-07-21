"""Brief factories for committee tests — build a full CommitteeBrief cheaply."""

from __future__ import annotations

from dataclasses import replace

from app.modules.ai_engine.scoring import ScoringEngine
from app.modules.committee.base import CommitteeBrief, PortfolioState
from app.modules.scanner.explain import build_explanation
from app.modules.scanner.opportunity import Opportunity, rank_opportunities
from app.modules.scanner.regime import RegimeEngine, RegimeState
from app.modules.strategy.base import Direction, OptionContext, StrategyContext
from app.modules.strategy.registry import registry

from tests.unit.alpha.factories import ctx as make_ctx
from tests.unit.alpha.factories import series, trending_index


def leader_ctx(
    *,
    symbol: str = "TCS",
    instrument_id: int = 1,
    sector: str = "IT",
    relative_strength: float = 6.0,
    options: OptionContext | None = None,
    news_score: float | None = None,
) -> StrategyContext:
    closes = [100 + i * 0.6 for i in range(60)]
    ind = {
        "ema_9": closes[-1] - 1,
        "ema_21": closes[-1] - 3,
        "ema_50": closes[-1] - 8,
        "atr_14": 1.0,
        "adx_14": 30,
        "rsi_14": 62,
    }
    daily = series("1d", closes, indicators=ind, volumes=[200_000] * 60)
    return make_ctx(
        symbol=symbol,
        instrument_id=instrument_id,
        series_map={"1d": daily},
        sector=sector,
        relative_strength=relative_strength,
        index_trend=Direction.LONG,
        options=options,
        news_score=news_score,
    )


def make_brief(
    *,
    context: StrategyContext | None = None,
    strategy_key: str = "ema_trend",
    regime: RegimeState | None = None,
    portfolio: PortfolioState | None = None,
    extra_opps: list[Opportunity] | None = None,
) -> CommitteeBrief:
    context = context or leader_ctx()
    regime = regime or RegimeEngine().detect(trending_index(Direction.LONG))
    strat = registry.get(strategy_key)
    ctx_r = replace(context, regimes=regime.regimes, index_trend=regime.index_trend)
    sig = strat.evaluate(ctx_r)
    assert sig is not None, f"{strategy_key} did not fire on the leader context"
    card = ScoringEngine().score(sig, ctx_r, regime)
    expl = build_explanation(sig, ctx_r, regime, card, strat.name)
    opp = Opportunity(
        symbol=context.symbol,
        instrument_id=context.instrument_id,
        strategy_key=strat.key,
        strategy_name=strat.name,
        signal=sig,
        scorecard=card,
        explanation=expl,
    )
    # The ranked book is only for the alternatives listing; the committee reviews
    # the constructed opportunity directly (a hostile-regime book is empty by
    # design, but the committee can still be asked to review a candidate).
    book = rank_opportunities(
        [opp, *(extra_opps or [])], regime, universe_size=1, scanned_strategies=13
    )
    chosen = replace(opp, rank=1)
    return CommitteeBrief(
        opportunity=chosen,
        context=context,
        regime=regime,
        book=book,
        portfolio=portfolio or PortfolioState(),
    )
