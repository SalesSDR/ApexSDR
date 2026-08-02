import asyncio
import logging
import os
import sys
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from app.config import settings  # noqa: E402
from app.models.base import Base  # noqa: E402
from app.models import schemas  # noqa: E402,F401  (registers all tables on Base.metadata)

config = context.config
config.set_main_option("sqlalchemy.url", settings.DATABASE_ASYNC_URL)

# This module also runs in-process (main.py calls alembic's command.upgrade()
# on startup), where fileConfig() would otherwise permanently reset the host
# app's logging: disable_existing_loggers=True (its default) disables every
# logger the app already configured, and even with that off it still resets
# the root logger's level/handlers per alembic.ini's [logger_root] section.
# Snapshot and restore both around the whole migration run so CLI usage still
# gets alembic's own formatted output, but the host app's logging is intact
# once this module finishes.
_root_logger = logging.getLogger()
_original_level = _root_logger.level
_original_handlers = _root_logger.handlers[:]

if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


try:
    if context.is_offline_mode():
        run_migrations_offline()
    else:
        asyncio.run(run_migrations_online())
finally:
    _root_logger.setLevel(_original_level)
    _root_logger.handlers[:] = _original_handlers
