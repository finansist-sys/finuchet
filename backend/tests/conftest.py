from __future__ import annotations

import json
import time

import httpx
import pytest

from app.config import Settings
from app.db.models import Base
from app.db.session import make_engine, make_sessionmaker
from app.main import create_app
from app.security.ratelimit import RateLimiter
from app.security.telegram_auth import sign_init_data

BOT_TOKEN = "123456:" + "TEST_TOKEN_not_real"  # fake, tests only
TG_A = 777000111
TG_B = 777000222


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        env="test",
        public_url="https://example.com",
        bot_token=BOT_TOKEN,
        webhook_secret="test-webhook-secret",
        webhook_path_token="test-path-token",
        id_pepper="p" * 48,
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'test.db').as_posix()}",
        bot_mode="off",
    )


@pytest.fixture
async def app(settings):
    application = create_app(settings)
    engine = make_engine(settings.database_url.get_secret_value())
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    application.state.engine = engine
    application.state.sessionmaker = make_sessionmaker(engine)
    application.state.bot = application.state.dp = None
    application.state.api_limiter = RateLimiter(limit=10_000, window_seconds=60)
    yield application
    await engine.dispose()


@pytest.fixture
async def client(app):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://test") as c:
        yield c


@pytest.fixture
def session_maker(app):
    return app.state.sessionmaker


def init_data(tg_id: int, *, auth_date: int | None = None, lang: str = "ru") -> str:
    fields = {
        "auth_date": str(auth_date if auth_date is not None else int(time.time())),
        "query_id": "AAHtest",
        "user": json.dumps(
            {"id": tg_id, "first_name": "Test", "username": "secret_name", "language_code": lang}
        ),
    }
    return sign_init_data(fields, BOT_TOKEN)


def auth(tg_id: int, **kw) -> dict[str, str]:
    return {"Authorization": f"tma {init_data(tg_id, **kw)}"}


async def onboard(client, tg_id: int, *, extra_usd: bool = True) -> dict:
    accounts = [
        {"type": "card", "name": "Карта", "currency": "RUB", "balance": 10_000_00},
        {"type": "cash", "name": "Наличные", "currency": "RUB", "balance": 2_000_00},
    ]
    if extra_usd:
        accounts.append({"type": "cash", "name": "Наличные $", "currency": "USD", "balance": 100_00})
    r = await client.post(
        "/api/onboarding",
        json={"base_currency": "RUB", "tz": "Europe/Moscow", "accounts": accounts},
        headers=auth(tg_id),
    )
    assert r.status_code == 201, r.text
    accs = (await client.get("/api/accounts", headers=auth(tg_id))).json()
    cats = (await client.get("/api/categories", headers=auth(tg_id))).json()
    return {"accounts": {a["name"]: a for a in accs}, "categories": {(c["name"], c["kind"]): c for c in cats}}
