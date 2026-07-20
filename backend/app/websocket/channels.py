"""WebSocket channel names and helpers."""

from __future__ import annotations

INDICES = "indices"
QUOTES_ALL = "quotes"
BREADTH = "breadth"
NEWS = "news"


def quote_channel(symbol: str) -> str:
    return f"quotes:{symbol}"


def indicator_channel(symbol: str) -> str:
    return f"indicators:{symbol}"


def option_chain_channel(underlying: str) -> str:
    return f"option_chain:{underlying}"


INDEX_SYMBOLS = {"NIFTY", "BANKNIFTY", "SENSEX", "INDIAVIX"}
