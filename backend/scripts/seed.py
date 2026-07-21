"""Idempotent database seed mechanism.

Sprint 1 seeds only an initial admin user (from environment variables) so a
fresh environment has a way in. Domain seeds (instrument master, market
calendar) arrive in later sprints under this same, re-runnable pattern.

Usage::

    python -m scripts.seed
"""

from __future__ import annotations

import asyncio
import os

from app.core.database import async_session_factory
from app.core.logging import configure_logging, get_logger
from app.core.security import hash_password
from app.modules.users.models import User, UserRole, UserStatus
from app.modules.users.repository import UserRepository

logger = get_logger("seed")


async def seed_admin() -> None:
    email = os.getenv("BKN_SEED_ADMIN_EMAIL", "admin@example.com")
    password = os.getenv("BKN_SEED_ADMIN_PASSWORD", "ChangeMe!123")

    async with async_session_factory() as session:
        repo = UserRepository(session)
        if await repo.get_by_email(email) is not None:
            logger.info("seed_admin_exists", email=email)
            return
        user = User(
            email=email.lower(),
            password_hash=hash_password(password),
            role=UserRole.ADMIN.value,
            status=UserStatus.ACTIVE.value,
        )
        session.add(user)
        await session.commit()
        logger.info("seed_admin_created", email=email)


async def main() -> None:
    configure_logging(json_logs=False)
    await seed_admin()


if __name__ == "__main__":
    asyncio.run(main())
