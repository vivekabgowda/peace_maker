"""Prometheus metrics for the market-intelligence layer.

Exposed on the app's existing ``/metrics`` endpoint and scraped by Prometheus
(see infra/observability). Covers throughput, latency, drops, and WS uptime.
"""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

QUOTES_INGESTED = Counter("bkn_quotes_ingested_total", "Quotes ingested from the provider")
CANDLES_BUILT = Counter("bkn_candles_built_total", "Candles closed and persisted", ["timeframe"])
OPTION_CHAINS_UPDATED = Counter(
    "bkn_option_chains_updated_total", "Option-chain refreshes processed"
)
NEWS_INGESTED = Counter(
    "bkn_news_ingested_total", "News articles ingested (after dedup)", ["provider"]
)

QUOTE_LATENCY = Histogram(
    "bkn_quote_processing_seconds",
    "Time to process a single quote through the pipeline",
    buckets=(0.0005, 0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25),
)
INDICATOR_UPDATE_SECONDS = Histogram(
    "bkn_indicator_update_seconds",
    "Time to update the incremental indicator bundle for one candle",
    buckets=(0.0005, 0.001, 0.002, 0.005, 0.01, 0.025, 0.05),
)
MARKET_SESSION_PHASE = Gauge(
    "bkn_market_session_phase",
    "Current session phase (0 closed,1 pre_open,2 open,3 closing,4 muhurat)",
)
FEED_IS_LEADER = Gauge(
    "bkn_feed_is_leader", "Whether this feed instance holds the ingestion lock (1/0)"
)

WS_CONNECTED_CLIENTS = Gauge(
    "bkn_ws_connected_clients", "Currently connected dashboard WebSocket clients"
)
WS_MESSAGES_DROPPED = Counter(
    "bkn_ws_messages_dropped_total", "Outbound WS messages dropped due to backpressure"
)
PROVIDER_CONNECTED = Gauge(
    "bkn_provider_connected", "Whether the market provider is connected (1/0)"
)
DATA_FRESHNESS_SECONDS = Gauge(
    "bkn_data_freshness_seconds", "Age of the latest quote for a symbol", ["symbol"]
)
