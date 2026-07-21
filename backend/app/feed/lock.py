"""Single-instance lock for the market feed (Technical Design Review R0 #1).

Only one feed instance may ingest at a time. A Redis lock (SET NX PX) is
acquired and periodically renewed; if this instance loses/omits renewal (crash,
network partition), the lock expires and another instance can take over. This
gives leader election without a heavyweight coordinator.
"""

from __future__ import annotations

import asyncio
import contextlib
import socket
import uuid

from app.core.logging import get_logger
from app.core.redis import get_redis
from app.modules.market_data import metrics

logger = get_logger("feed_lock")

_LOCK_KEY = "bkn:feed:leader"
# Lua: release only if we still own the lock (compare-and-delete).
_RELEASE_LUA = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('del', KEYS[1])
else
    return 0
end
"""


class SingleInstanceLock:
    def __init__(self, *, ttl_seconds: int = 15, renew_seconds: float = 5.0) -> None:
        self._token = f"{socket.gethostname()}:{uuid.uuid4()}"
        self._ttl = ttl_seconds
        self._renew = renew_seconds
        self._is_leader = False
        self._renew_task: asyncio.Task[None] | None = None

    @property
    def is_leader(self) -> bool:
        return self._is_leader

    async def acquire(self) -> bool:
        """Try to become leader once. Returns True if acquired."""
        acquired = await get_redis().set(_LOCK_KEY, self._token, nx=True, px=self._ttl * 1000)
        self._is_leader = bool(acquired)
        metrics.FEED_IS_LEADER.set(1 if self._is_leader else 0)
        if self._is_leader:
            logger.info("feed_leader_acquired", token=self._token)
            self._renew_task = asyncio.create_task(self._renew_loop())
        return self._is_leader

    async def acquire_blocking(self, poll_seconds: float = 3.0) -> None:
        """Block until leadership is acquired (standby instances wait here)."""
        while not await self.acquire():
            logger.info("feed_standby_waiting")
            await asyncio.sleep(poll_seconds)

    async def _renew_loop(self) -> None:
        while self._is_leader:
            await asyncio.sleep(self._renew)
            try:
                # Refresh TTL only if we still own it.
                ok = await get_redis().set(_LOCK_KEY, self._token, xx=True, px=self._ttl * 1000)
                if not ok:
                    self._is_leader = False
                    metrics.FEED_IS_LEADER.set(0)
                    logger.error("feed_leadership_lost")
            except Exception:
                logger.exception("feed_lock_renew_error")

    async def release(self) -> None:
        if self._renew_task is not None:
            self._renew_task.cancel()
            with contextlib.suppress(Exception):
                await self._renew_task
        with contextlib.suppress(Exception):
            await get_redis().eval(_RELEASE_LUA, 1, _LOCK_KEY, self._token)  # type: ignore[misc]
        self._is_leader = False
        metrics.FEED_IS_LEADER.set(0)
        logger.info("feed_leader_released")
