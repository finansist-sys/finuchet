"""Database engine and sessions.

Works in two environments:
- own server (Docker): one long-lived process with a connection pool;
- serverless (Vercel): every invocation may run in a fresh process, so connections are not
  pooled (NullPool), the engine is created lazily, and the schema is migrated on first use.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

BACKEND_DIR = Path(__file__).resolve().parents[2]
_MIGRATION_LOCK_ID = 4207_2026  # arbitrary constant for pg_advisory_xact_lock


def normalize_db_url(url: str) -> tuple[str, dict]:
    """Turn a provider URL (e.g. Neon's ``postgresql://…?sslmode=require``) into an asyncpg URL.

    asyncpg does not understand libpq's ``sslmode``/``channel_binding`` query options, so they are
    removed from the URL and translated into connect arguments.
    """
    if url.startswith("sqlite"):
        return url, {}
    parts = urlsplit(url)
    scheme = parts.scheme
    if scheme in ("postgres", "postgresql"):
        scheme = "postgresql+asyncpg"
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    sslmode = query.pop("sslmode", None)
    query.pop("channel_binding", None)
    connect_args: dict = {}
    if sslmode and sslmode != "disable":
        connect_args["ssl"] = sslmode
    return urlunsplit((scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)), connect_args


def make_engine(url: str, *, serverless: bool = False) -> AsyncEngine:
    url, connect_args = normalize_db_url(url)
    if url.startswith("sqlite"):
        engine = create_async_engine(url)

        @event.listens_for(engine.sync_engine, "connect")
        def _fk_on(dbapi_conn, _record):  # pragma: no cover - trivial
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()

        return engine
    if serverless:
        # No pooling across invocations; safe with connection poolers (PgBouncer transaction mode):
        # disable both asyncpg's and SQLAlchemy's prepared-statement caches (the latter is a URL option).
        connect_args["statement_cache_size"] = 0
        url += ("&" if "?" in url else "?") + "prepared_statement_cache_size=0"
        return create_async_engine(url, poolclass=NullPool, connect_args=connect_args)
    return create_async_engine(url, pool_pre_ping=True, connect_args=connect_args)


def make_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def session_scope(maker: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncSession]:
    async with maker() as session:
        yield session


# ---------------------------------------------------------------- lazy app wiring

_init_lock = asyncio.Lock()


async def app_sessionmaker(app) -> async_sessionmaker[AsyncSession]:
    """Engine + sessionmaker for this process, created on first use (and schema migrated if serverless)."""
    maker = getattr(app.state, "sessionmaker", None)
    if maker is not None:
        return maker
    async with _init_lock:
        maker = getattr(app.state, "sessionmaker", None)
        if maker is not None:
            return maker
        settings = app.state.settings
        engine = make_engine(settings.database_url.get_secret_value(), serverless=settings.serverless)
        if settings.serverless:
            await ensure_schema(engine)
        app.state.engine = engine
        app.state.sessionmaker = make_sessionmaker(engine)
        return app.state.sessionmaker


def _alembic_config():
    from alembic.config import Config

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    return cfg


async def ensure_schema(engine: AsyncEngine) -> None:
    """Apply pending Alembic migrations. Cheap no-op when the schema is already current."""
    from alembic.runtime.migration import MigrationContext
    from alembic.script import ScriptDirectory

    from alembic import command

    cfg = _alembic_config()
    head = ScriptDirectory.from_config(cfg).get_current_head()

    async with engine.connect() as conn:
        current = await conn.run_sync(lambda c: MigrationContext.configure(c).get_current_revision())
    if current == head:
        return

    async with engine.begin() as conn:
        if engine.dialect.name == "postgresql":
            # Only one cold-starting instance migrates; others wait, then see the new head.
            await conn.execute(text("SELECT pg_advisory_xact_lock(:id)"), {"id": _MIGRATION_LOCK_ID})

        def _upgrade(sync_conn) -> None:
            if MigrationContext.configure(sync_conn).get_current_revision() == head:
                return
            cfg.attributes["connection"] = sync_conn
            command.upgrade(cfg, "head")

        await conn.run_sync(_upgrade)
