"""Prometheus metrics for the broker connection (Sprint 6 observability)."""

from __future__ import annotations

from prometheus_client import Counter, Gauge

BROKER_CONNECTED = Gauge(
    "bkn_broker_connected", "Whether the broker ticker is connected (1/0)", ["broker"]
)
BROKER_TOKEN_VALID = Gauge(
    "bkn_broker_token_valid", "Whether a valid broker access token is present (1/0)", ["broker"]
)
BROKER_RECONNECTS = Counter("bkn_broker_reconnects_total", "Broker ticker reconnects", ["broker"])
BROKER_TICKS = Counter("bkn_broker_ticks_total", "Ticks received from the broker", ["broker"])
BROKER_SUBSCRIPTIONS = Gauge(
    "bkn_broker_subscriptions", "Currently subscribed instrument count", ["broker"]
)
