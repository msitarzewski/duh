"""Alembic environment configuration."""

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.ext.asyncio import async_engine_from_config

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

from duh.memory.models import Base

target_metadata = Base.metadata

# Async drivers that require async_engine_from_config.
_ASYNC_DRIVERS = {"aiosqlite", "asyncpg", "aiomysql"}


def _is_async_url(url: str) -> bool:
    """Return True if the URL uses an async driver."""
    return any(f"+{d}" in url for d in _ASYNC_DRIVERS)


def _expand_url(section: dict[str, str]) -> dict[str, str]:
    """Expand ``~`` in the database URL to the user home directory."""
    url = section.get("sqlalchemy.url", "")
    if ":///" in url:
        prefix, path = url.split(":///", 1)
        section["sqlalchemy.url"] = prefix + ":///" + os.path.expanduser(path)
    return section


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:  # type: ignore[no-untyped-def]
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with async engine."""
    section = _expand_url(config.get_section(config.config_ini_section, {}))
    connectable = async_engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (sync or async)."""
    section = _expand_url(config.get_section(config.config_ini_section, {}))
    url = section.get("sqlalchemy.url", "")

    if _is_async_url(url):
        asyncio.run(run_async_migrations())
    else:
        connectable = engine_from_config(
            section,
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
        )

        with connectable.connect() as connection:
            do_run_migrations(connection)

        connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
