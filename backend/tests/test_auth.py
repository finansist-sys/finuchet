import json
import time
from urllib.parse import parse_qsl, urlencode

import pytest
from app.security.identity import tg_hash
from app.security.telegram_auth import InitDataError, sign_init_data, validate_init_data

from tests.conftest import BOT_TOKEN, auth, init_data

DAY = 24 * 3600


def test_valid_init_data():
    ident = validate_init_data(init_data(42, lang="en"), BOT_TOKEN, DAY)
    assert ident.tg_id == 42
    assert ident.language_code == "en"


def test_wrong_bot_token_rejected():
    with pytest.raises(InitDataError):
        validate_init_data(init_data(42), "999:OTHER_TOKEN", DAY)


def test_tampered_user_rejected():
    fields = dict(parse_qsl(init_data(42)))
    fields["user"] = json.dumps({"id": 43})
    with pytest.raises(InitDataError):
        validate_init_data(urlencode(fields), BOT_TOKEN, DAY)


def test_missing_hash_rejected():
    fields = dict(parse_qsl(init_data(42)))
    fields.pop("hash")
    with pytest.raises(InitDataError):
        validate_init_data(urlencode(fields), BOT_TOKEN, DAY)


def test_expired_rejected():
    with pytest.raises(InitDataError):
        validate_init_data(init_data(42, auth_date=int(time.time()) - DAY - 10), BOT_TOKEN, DAY)


def test_future_rejected():
    with pytest.raises(InitDataError):
        validate_init_data(init_data(42, auth_date=int(time.time()) + 3600), BOT_TOKEN, DAY)


def test_missing_user_rejected():
    raw = sign_init_data({"auth_date": str(int(time.time()))}, BOT_TOKEN)
    with pytest.raises(InitDataError):
        validate_init_data(raw, BOT_TOKEN, DAY)


def test_duplicate_field_rejected():
    raw = init_data(42) + "&user=" + json.dumps({"id": 1})
    with pytest.raises(InitDataError):
        validate_init_data(raw, BOT_TOKEN, DAY)


def test_too_long_rejected():
    with pytest.raises(InitDataError):
        validate_init_data("a" * 5000, BOT_TOKEN, DAY)


def test_tg_hash_is_stable_and_not_reversible_looking():
    h1 = tg_hash(42, "x" * 40)
    assert h1 == tg_hash(42, "x" * 40)
    assert h1 != tg_hash(42, "y" * 40)
    assert b"42" not in h1 and len(h1) == 32


async def test_api_requires_auth(client):
    assert (await client.get("/api/me")).status_code == 401
    assert (await client.get("/api/me", headers={"Authorization": "tma garbage"})).status_code == 401
    assert (await client.get("/api/me", headers={"Authorization": "Bearer x"})).status_code == 401


async def test_dev_shortcut_disabled_outside_dev(client):
    assert (await client.get("/api/me", headers={"Authorization": "tma dev"})).status_code == 401


async def test_me_before_onboarding(client):
    r = await client.get("/api/me", headers=auth(5))
    assert r.status_code == 200
    assert r.json()["onboarded"] is False
    assert (await client.get("/api/accounts", headers=auth(5))).status_code == 409


def test_prod_refuses_dev_fake_user():
    from app.config import Settings

    with pytest.raises(ValueError):
        Settings(
            env="prod",
            public_url="https://x.org",
            bot_token="1:a",
            webhook_secret="s",
            webhook_path_token="p",
            id_pepper="p" * 40,
            database_url="sqlite+aiosqlite://",
            dev_fake_tg_id=1,
        )
