"""Short-lived, single-use WebSocket auth tickets (R1 security).

Removes the JWT from the WebSocket URL. The client obtains a ticket from an
authenticated REST call; the ticket is stored in Redis with a short TTL and is
consumed (deleted) on WS connect, so it cannot be replayed or leaked via logs.
"""

from __future__ import annotations

import secrets

from app.core.redis import get_redis

_TICKET_PREFIX = "ws:ticket:"
_TTL_SECONDS = 30


async def issue_ticket(user_id: str) -> str:
    ticket = secrets.token_urlsafe(32)
    await get_redis().set(f"{_TICKET_PREFIX}{ticket}", user_id, ex=_TTL_SECONDS)
    return ticket


async def consume_ticket(ticket: str) -> str | None:
    """Atomically validate + invalidate a ticket. Returns the user_id or None."""
    key = f"{_TICKET_PREFIX}{ticket}"
    try:
        user_id = await get_redis().getdel(key)
    except Exception:
        return None
    return user_id if isinstance(user_id, str) else None
