"""Broker credential storage (Sprint 6).

Kite Connect issues a per-day ``access_token`` (no OAuth refresh token — it is
re-minted via the daily login flow). We persist exactly one active row per broker,
with the token **encrypted at rest** (Fernet). The plaintext token never touches
the database or the logs.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin

_BigIntPK = BigInteger().with_variant(Integer, "sqlite")


class BrokerToken(Base, TimestampMixin):
    __tablename__ = "broker_tokens"

    id: Mapped[int] = mapped_column(_BigIntPK, primary_key=True, autoincrement=True)
    broker: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    kite_user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Fernet-encrypted token material (base64 text). Never store plaintext.
    access_token_enc: Mapped[str] = mapped_column(Text, nullable=False)
    public_token_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    # When the access token stops being valid (Kite: ~07:30 IST next day).
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
