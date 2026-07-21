"""End-to-end Alpha Engine scan: regime → strategies → score → rank → portfolio."""

from __future__ import annotations

from app.modules.scanner.engine import AlphaScanner, RegimeInputs
from app.modules.strategy.base import Direction

from tests.unit.alpha.factories import ctx, series, trending_index


def _leader_ctx(symbol: str, instrument_id: int, sector: str = "IT"):  # type: ignore[no-untyped-def]
    """A clean EMA-trend + relative-strength long candidate."""
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
    return ctx(
        symbol=symbol,
        instrument_id=instrument_id,
        series_map={"1d": daily},
        sector=sector,
        relative_strength=6.0,
        index_trend=Direction.LONG,
    )


def test_scan_produces_ranked_explained_book() -> None:
    scanner = AlphaScanner()
    contexts = [
        _leader_ctx("TCS", 1, "IT"),
        _leader_ctx("INFY", 2, "IT"),
        _leader_ctx("HDFCBANK", 3, "BANK"),
    ]
    book = scanner.scan(
        trending_index(Direction.LONG),
        contexts,
        regime_inputs=RegimeInputs(),
        top_n=20,
    )
    assert not book.no_trade
    assert book.opportunities
    top = book.opportunities[0]
    assert top.rank == 1
    assert top.explanation.why_this
    assert top.scorecard.composite >= 55
    # Ranks are strictly increasing and unique.
    assert [o.rank for o in book.opportunities] == list(range(1, len(book.opportunities) + 1))


def test_scan_respects_sector_cap_in_portfolio_stage() -> None:
    # Four IT leaders; default sector cap is 3 → at most 3 IT names survive.
    scanner = AlphaScanner()
    contexts = [_leader_ctx(f"IT{i}", i, "IT") for i in range(4)]
    book = scanner.scan(trending_index(Direction.LONG), contexts)
    it_names = [o for o in book.opportunities if o.symbol.startswith("IT")]
    assert len(it_names) <= 3


def test_hostile_regime_returns_no_trade() -> None:
    # A strong global risk-off must veto trading regardless of candidate quality.
    scanner = AlphaScanner()
    contexts = [_leader_ctx("TCS", 1)]
    book = scanner.scan(
        trending_index(Direction.LONG),
        contexts,
        regime_inputs=RegimeInputs(global_risk_off=True),
    )
    assert book.no_trade
    assert book.regime.is_hostile
    assert not book.opportunities


def test_empty_universe_is_no_trade() -> None:
    scanner = AlphaScanner()
    book = scanner.scan(trending_index(Direction.LONG), [])
    assert book.no_trade


def test_scan_serializes_to_dict() -> None:
    scanner = AlphaScanner()
    book = scanner.scan(trending_index(Direction.LONG), [_leader_ctx("TCS", 1)])
    payload = book.as_dict(top_n=5)
    assert "regime" in payload and "top" in payload
    assert payload["regime"]["primary"] == "trending_bull"
    if not book.no_trade:
        first = payload["top"][0]
        assert {"symbol", "direction", "entry", "stop", "explanation", "scores"} <= set(first)
