"""Encrypted broker-token storage (Sprint 6).

Access tokens are encrypted with **Fernet** (AES-128-CBC + HMAC) before they touch
the database, using a key from ``BKN_BROKER_ENC_KEY``. Two implementations share
one interface: a DB-backed store (production) and an in-memory store (tests).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.modules.broker.orm import BrokerToken
from app.shared.market_calendar import IST

logger = get_logger("broker.token_store")


@dataclass(frozen=True, slots=True)
class BrokerSession:
    """A decrypted broker session (plaintext — kept only in memory)."""

    broker: str
    access_token: str
    public_token: str | None
    kite_user_id: str | None
    expires_at: datetime

    @property
    def is_valid(self) -> bool:
        # SQLite (test path) returns naive datetimes even for tz-aware columns;
        # treat a naive expiry as UTC so the comparison is dialect-agnostic.
        expiry = self.expires_at
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=UTC)
        return datetime.now(UTC) < expiry


def kite_token_expiry(now: datetime | None = None) -> datetime:
    """Kite access tokens die at ~07:30 IST the next calendar day."""
    now = now or datetime.now(UTC)
    ist_now = now.astimezone(IST)
    expiry_ist = datetime.combine(ist_now.date(), time(7, 30), tzinfo=IST)
    if ist_now >= expiry_ist:
        expiry_ist = expiry_ist + timedelta(days=1)
    return expiry_ist.astimezone(UTC)


class Cipher:
    """Thin Fernet wrapper; validates the configured key early."""

    def __init__(self, key: str) -> None:
        try:
            self._fernet = Fernet(key.encode() if isinstance(key, str) else key)
        except (ValueError, TypeError) as exc:
            raise ValueError(
                "BKN_BROKER_ENC_KEY must be a valid 32-byte url-safe base64 Fernet key. "
                "Generate one with: python -c 'from cryptography.fernet import Fernet; "
                "print(Fernet.generate_key().decode())'"
            ) from exc

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, token: str) -> str:
        try:
            return self._fernet.decrypt(token.encode()).decode()
        except InvalidToken as exc:
            raise ValueError("Failed to decrypt broker token (wrong key?)") from exc


class TokenStore(ABC):
    @abstractmethod
    async def save(self, session: BrokerSession) -> None: ...

    @abstractmethod
    async def load(self, broker: str) -> BrokerSession | None: ...

    @abstractmethod
    async def clear(self, broker: str) -> None: ...


class DbTokenStore(TokenStore):
    """Persists one encrypted token row per broker."""

    def __init__(self, db: AsyncSession, cipher: Cipher) -> None:
        self._db = db
        self._cipher = cipher

    async def save(self, session: BrokerSession) -> None:
        await self._db.execute(delete(BrokerToken).where(BrokerToken.broker == session.broker))
        self._db.add(
            BrokerToken(
                broker=session.broker,
                kite_user_id=session.kite_user_id,
                access_token_enc=self._cipher.encrypt(session.access_token),
                public_token_enc=(
                    self._cipher.encrypt(session.public_token) if session.public_token else None
                ),
                expires_at=session.expires_at,
            )
        )
        await self._db.flush()
        logger.info("broker_token_saved", broker=session.broker, kite_user=session.kite_user_id)

    async def load(self, broker: str) -> BrokerSession | None:
        row = await self._db.scalar(select(BrokerToken).where(BrokerToken.broker == broker))
        if row is None:
            return None
        return BrokerSession(
            broker=row.broker,
            access_token=self._cipher.decrypt(row.access_token_enc),
            public_token=(
                self._cipher.decrypt(row.public_token_enc) if row.public_token_enc else None
            ),
            kite_user_id=row.kite_user_id,
            expires_at=row.expires_at,
        )

    async def clear(self, broker: str) -> None:
        await self._db.execute(delete(BrokerToken).where(BrokerToken.broker == broker))
        await self._db.flush()


class MemoryTokenStore(TokenStore):
    """In-memory store for tests and single-process dev."""

    def __init__(self) -> None:
        self._store: dict[str, BrokerSession] = {}

    async def save(self, session: BrokerSession) -> None:
        self._store[session.broker] = session

    async def load(self, broker: str) -> BrokerSession | None:
        return self._store.get(broker)

    async def clear(self, broker: str) -> None:
        self._store.pop(broker, None)
