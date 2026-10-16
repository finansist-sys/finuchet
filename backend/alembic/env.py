"""Alembic environment.

Two ways in:
- CLI (`alembic upgrade head`, Docker): URL from the DATABASE_URL environment variable;
- programmatic (serverless, app/db/session.py:ensure_schema): a live connection is passed in
  ``config.attributes["connection"]``; logging is left untouched so the app's redaction stays active.
"""

from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig

from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context
from app.db.models import Base
from app.db.session import normalize_db_url

config = context.config
target_metadata = Base.metadata
_given_connection = config.attributes.get("connection")

if _given_connection is None and config.config_file_name is not None:
    fileConfig(config.config_file_name)


def _url() -> tuple[str, dict]:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    return normalize_db_url(url)


def run_migrations_offline() -> None:
    url, _ = _url()
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


def _run(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    url, connect_args = _url()
    engine = create_async_engine(url, connect_args=connect_args)
    async with engine.connect() as connection:
        await connection.run_sync(_run)
    await engine.dispose()


if _given_connection is not None:
    _run(_given_connection)
elif context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
