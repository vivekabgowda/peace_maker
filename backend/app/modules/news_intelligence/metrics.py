"""Prometheus metrics for the News Intelligence engine (Sprint 11)."""

from __future__ import annotations

from prometheus_client import Counter, Histogram

ASSESSMENTS = Counter(
    "bkn_news_assessments_total",
    "News Intelligence assessments produced",
    ["result"],  # scored | empty
)

NEWS_SCORE = Histogram(
    "bkn_news_score",
    "Distribution of signed news scores (-100..100)",
    buckets=(-100, -75, -50, -25, -10, 0, 10, 25, 50, 75, 100),
)
