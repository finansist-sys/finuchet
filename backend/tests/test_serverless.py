"""Serverless (Vercel + Neon) specifics: lazy wiring, migrations on first use, DB-backed bot state."""

from datetime import UTC, datetime, timedelta

import httpx
import pytest
from aiogram.fsm.storage.base import StorageKey
from sqlalchemy import select, text

from app.bot.storage import SqlStorage
from app.config import Settings
from app.db.models import BotState
from app.db.session import app_sessionmaker, ensure_schema, make_engine, make_sessionmaker, normalize_db_url
from app.main import create_app
from tests.conftest import BOT_TOKEN, TG_A, auth


def test_neon_url_is_converted_for_asyncpg():
    host = "user:pw" + "@" + "ep-x-pooler.eu-central-1.aws.neon.tech/neondb"  # fake, built from parts
    url, args = normalize_db_url(f"postgresql://{host}?sslmode=require&channel_binding=require")
    assert url == f"postgresql+asyncpg://{host}"
    assert args == {"ssl": "require"}
    assert normalize_db_url("postgres://u:p@h/db")[0].startswith("postgresql+asyncpg://")
    assert normalize_db_url("sqlite+aiosqlite:///x.db") == ("sqlite+aiosqlite:///x.db", {})


async def test_ensure_schema_creates_and_is_idempotent(tmp_path):
    engine = make_engine(f"sqlite+aiosqlite:///{(tmp_path / 'fresh.db').as_posix()}")
    await ensure_schema(engine)
    await ensure_schema(engine)  # second call: no-op
    async with engine.connect() as conn:
        version = (await conn.execute(text("SELECT version_num FROM alembic_version"))).scalar_one()
        tables = {r[0] for r in await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))}
    await engine.dispose()
    assert version == "0002"
    assert {"users", "accounts", "categories", "transactions", "category_hints", "bot_states"} <= tables


async def test_serverless_app_migrates_on_first_request(tmp_path):
    settings = Settings(
        env="test",
        bot_token=BOT_TOKEN,
        webhook_secret="test-webhook-secret",
        webhook_path_token="test-path-token",
        id_pepper="p" * 48,
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'lazy.db').as_posix()}",
        bot_mode="serverless",
        vercel_project_production_url="finuchet.vercel.app",
    )
    assert settings.public_url == "https://finuchet.vercel.app"
    app = create_app(settings)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://t") as c:
        r = await c.get("/api/me", headers=auth(TG_A))
        assert r.status_code == 200 and r.json()["onboarded"] is False
        assert (await c.post("/tg/wrong", json={})).status_code == 404
        r = await c.post("/tg/test-path-token", json={}, headers={"X-Telegram-Bot-Api-Secret-Token": "bad"})
        assert r.status_code == 403
    await app.state.engine.dispose()


@pytest.fixture
async def storage(tmp_path):
    engine = make_engine(f"sqlite+aiosqlite:///{(tmp_path / 's.db').as_posix()}")
    await ensure_schema(engine)
    maker = make_sessionmaker(engine)

    async def get_maker():
        return maker

    yield SqlStorage(get_maker, "p" * 48), maker
    await engine.dispose()


async def test_fsm_state_roundtrip_without_telegram_ids(storage):
    st, maker = storage
    key = StorageKey(bot_id=42, chat_id=TG_A, user_id=TG_A)
    assert await st.get_state(key) is None and await st.get_data(key) == {}
    await st.set_state(key, "NewEntry:amount")
    await st.set_data(key, {"kind": "expense", "category_id": "c0ffee"})
    assert await st.get_state(key) == "NewEntry:amount"
    assert await st.get_data(key) == {"kind": "expense", "category_id": "c0ffee"}
    async with maker() as s:
        rows = (await s.scalars(select(BotState))).all()
        dump = repr([(r.key, r.state, r.data) for r in rows])
    assert len(rows) == 1 and str(TG_A) not in dump
    other = StorageKey(bot_id=42, chat_id=TG_A + 1, user_id=TG_A + 1)
    assert await st.get_state(other) is None
    await st.set_state(key, None)
    await st.set_data(key, {})
    async with maker() as s:
        assert (await s.scalars(select(BotState))).all() == []


async def test_fsm_state_expires(storage):
    st, maker = storage
    key = StorageKey(bot_id=1, chat_id=2, user_id=2)
    await st.set_state(key, "NewEntry:amount")
    async with maker() as s:
        row = (await s.scalars(select(BotState))).one()
        row.updated_at = datetime.now(UTC) - timedelta(days=2)
        await s.commit()
    assert await st.get_state(key) is None


async def test_lazy_sessionmaker_reused(app):
    assert await app_sessionmaker(app) is await app_sessionmaker(app)


def test_postgres_engine_options_are_accepted():
    """Creating the engine does not connect, but validates every option (regression: TypeError on deploy)."""
    host = "u:p" + "@" + "db.example.org/app"
    for serverless in (True, False):
        engine = make_engine(f"postgresql://{host}?sslmode=require", serverless=serverless)
        assert engine.dialect.name == "postgresql"
