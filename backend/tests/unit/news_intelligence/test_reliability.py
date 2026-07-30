"""Source reliability engine — tiers, scores, and rejection of unknown sources."""

from __future__ import annotations

from app.modules.news_intelligence.reliability import (
    SourceTier,
    is_acceptable,
    reliability_for,
    resolve,
    tier_for,
)


def test_official_sources_are_tier1_and_max_reliability() -> None:
    assert reliability_for("NSE Corporate Announcements") == 100
    assert reliability_for("BSE") == 100
    assert reliability_for("SEBI") == 100
    assert reliability_for("RBI Press Release") == 100
    assert tier_for("nseindia.com") is SourceTier.TIER_1


def test_press_and_major_papers_are_tier2() -> None:
    assert tier_for("Economic Times") is SourceTier.TIER_2
    assert 80 <= (reliability_for("Moneycontrol") or 0) <= 92


def test_unknown_source_is_rejected() -> None:
    assert reliability_for("some-random-rumour-site") is None
    assert resolve("") is None
    assert is_acceptable("some-random-rumour-site") is False


def test_social_media_is_never_acceptable_on_its_own() -> None:
    assert tier_for("twitter") is SourceTier.UNTRUSTED
    assert reliability_for("telegram channel") == 0
    assert is_acceptable("x.com/somebody") is False


def test_longer_alias_wins_over_short_collision() -> None:
    # "national stock exchange" and bare "nse" both resolve to NSE.
    assert resolve("National Stock Exchange filing").key == "nse"
