"""Alembic async migration environment.

Uses the application's async engine/URL and the shared declarative ``Base``
metadata so ``--autogenerate`` stays in sync with the ORM models.
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.engine import Connection

from app.core.config import get_settings
from app.core.database import Base, engine

# Import model modules so their tables register on Base.metadata.
from app.modules.admin import orm as _admin_orm  # noqa: F401
from app.modules.analytics import orm as _analytics_orm  # noqa: F401
from app.modules.auth import models as _auth_models  # noqa: F401
from app.modules.broker import orm as _broker_orm  # noqa: F401
from app.modules.journal import orm as _journal_orm  # noqa: F401
from app.modules.market_data import orm as _market_orm  # noqa: F401
from app.modules.news import orm as _news_orm  # noqa: F401
from app.modules.paper_trading import orm as _paper_orm  # noqa: F401
from app.modules.users import models as _users_models  # noqa: F401
from app.modules.validation import orm as _validation_orm  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
config.set_main_option("sqlalchemy.url", str(get_settings().database_url))


def run_migrations_offline() -> None:
    """Emit SQL to a script without a live DB connection."""
    context.configure(
        url=str(get_settings().database_url),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def _do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations against the async engine."""
    async with engine.connect() as connection:
        await connection.run_sync(_do_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
