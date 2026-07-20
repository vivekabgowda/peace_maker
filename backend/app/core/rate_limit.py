"""Redis-backed rate limiting and login protection (R1 security).

- ``TokenBucket`` — generic per-key fixed-window limiter.
- ``LoginGuard`` — progressive lockout on failed logins, keyed by email *and*
  client IP, plus lightweight IP-reputation blocking for abusive sources.

All checks fail **open** on a Redis outage (availability over strictness for a
cache dependency), but every decision is metered.
"""

from __future__ import annotations

from app.core.logging import get_logger
from app.core.redis import get_redis

logger = get_logger("rate_limit")


class TokenBucket:
    """Fixed-window counter: at most ``limit`` events per ``window`` seconds/key."""

    def __init__(self, *, limit: int, window_seconds: int, prefix: str) -> None:
        self._limit = limit
        self._window = window_seconds
        self._prefix = prefix

    async def allow(self, key: str) -> bool:
        redis_key = f"rl:{self._prefix}:{key}"
        try:
            count = await get_redis().incr(redis_key)
            if count == 1:
                await get_redis().expire(redis_key, self._window)
            return bool(count <= self._limit)
        except Exception:
            logger.warning("rate_limit_unavailable", prefix=self._prefix)
            return True


class LoginGuard:
    """Progressive lockout + IP reputation for the login endpoint."""

    def __init__(
        self,
        *,
        max_failures: int = 5,
        base_lock_seconds: int = 30,
        ip_failure_limit: int = 50,
        ip_window_seconds: int = 900,
    ) -> None:
        self._max_failures = max_failures
        self._base_lock = base_lock_seconds
        self._ip_limit = ip_failure_limit
        self._ip_window = ip_window_seconds

    async def is_locked(self, email: str, ip: str) -> tuple[bool, int]:
        """Return (locked, retry_after_seconds)."""
        try:
            r = get_redis()
            if await r.get(f"lock:acct:{email.lower()}"):
                ttl = await r.ttl(f"lock:acct:{email.lower()}")
                return True, max(0, int(ttl))
            if await r.get(f"lock:ip:{ip}"):
                ttl = await r.ttl(f"lock:ip:{ip}")
                return True, max(0, int(ttl))
        except Exception:
            return False, 0
        return False, 0

    async def record_failure(self, email: str, ip: str) -> None:
        """Count a failed attempt; apply progressive account + IP lockouts."""
        try:
            r = get_redis()
            acct_key = f"fail:acct:{email.lower()}"
            fails = await r.incr(acct_key)
            if fails == 1:
                await r.expire(acct_key, self._ip_window)
            if fails >= self._max_failures:
                # Progressive: lock doubles each extra failure over the threshold.
                lock = self._base_lock * (2 ** (fails - self._max_failures))
                await r.set(f"lock:acct:{email.lower()}", "1", ex=min(lock, 3600))
                logger.warning("account_locked", email=email, seconds=min(lock, 3600))

            ip_key = f"fail:ip:{ip}"
            ip_fails = await r.incr(ip_key)
            if ip_fails == 1:
                await r.expire(ip_key, self._ip_window)
            if ip_fails >= self._ip_limit:
                await r.set(f"lock:ip:{ip}", "1", ex=self._ip_window)
                logger.warning("ip_blocked", ip=ip, failures=ip_fails)
        except Exception:
            logger.warning("login_guard_unavailable")

    async def record_success(self, email: str) -> None:
        try:
            r = get_redis()
            await r.delete(f"fail:acct:{email.lower()}", f"lock:acct:{email.lower()}")
        except Exception:
            logger.debug("login_guard_clear_failed")


login_guard = LoginGuard()
login_rate_limit = TokenBucket(limit=20, window_seconds=60, prefix="login")
