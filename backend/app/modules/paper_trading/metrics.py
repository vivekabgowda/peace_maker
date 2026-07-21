"""Prometheus metrics for the paper-trading engine (Sprint 7)."""

from __future__ import annotations

from prometheus_client import Counter, Gauge

PAPER_ORDERS = Counter(
    "bkn_paper_orders_total", "Paper orders submitted", ["status"]
)  # status: filled | rejected
PAPER_TRADES_CLOSED = Counter(
    "bkn_paper_trades_closed_total", "Paper positions closed", ["reason"]
)  # reason: stop | target | manual | eod
PAPER_POSITIONS_OPEN = Gauge("bkn_paper_positions_open", "Currently open paper positions")
PAPER_REALIZED_PNL = Gauge(
    "bkn_paper_realized_pnl", "Latest realized P&L of the last account to trade"
)
