from decimal import Decimal

from sqlalchemy import select

from app.bot.handlers import card_text, guess_category, pick_account, record
from app.bot.keyboards import cb, pack, unpack
from app.bot.parser import Entry, parse
from app.db.models import Account, Category, Transaction
from app.security.identity import tg_hash
from app.services import users
from tests.conftest import TG_A, onboard


async def _user(session_maker, settings):
    async with session_maker() as s:
        return await users.find_user(s, tg_hash(TG_A, settings.id_pepper.get_secret_value()))


async def test_quick_entry_records_and_learns(client, session_maker, settings):
    await onboard(client, TG_A)
    async with session_maker() as s:
        user = await users.find_user(s, tg_hash(TG_A, settings.id_pepper.get_secret_value()))
        tx, err = await record(s, user, parse("300 кофе нал"), kind="expense", category_id=None)
        assert err is None and tx.amount == 300_00 and tx.source == "bot"
        acc = await s.get(Account, tx.account_id)
        assert acc.name == "Наличные" and acc.balance == 1_700_00
        cat = await s.get(Category, tx.category_id)
        assert cat.name == "Кафе"

        # Unknown word -> no category; user picks one -> remembered next time.
        tx2, _ = await record(s, user, parse("450 Шаверма"), kind="expense", category_id=None)
        assert tx2.category_id is None
        food = await s.scalar(
            select(Category).where(Category.user_id == user.id, Category.name == "Продукты")
        )
        tx3, _ = await record(s, user, parse("450 Шаверма"), kind="expense", category_id=food.id)
        assert tx3.category_id == food.id
        assert await guess_category(s, user, "expense", ["шаверма"]) == food.id


async def test_currency_picks_matching_account(client, session_maker, settings):
    await onboard(client, TG_A)
    async with session_maker() as s:
        user = await users.find_user(s, tg_hash(TG_A, settings.id_pepper.get_secret_value()))
        tx, err = await record(s, user, parse("20$ такси"), kind="expense", category_id=None)
        assert err is None
        assert (await s.get(Account, tx.account_id)).currency == "USD"
        tx, err = await record(s, user, parse("20 евро такси"), kind="expense", category_id=None)
        assert tx is None and "EUR" in err


async def test_default_account_preferred(client, session_maker, settings):
    await onboard(client, TG_A)
    async with session_maker() as s:
        user = await users.find_user(s, tg_hash(TG_A, settings.id_pepper.get_secret_value()))
        accounts = list(await s.scalars(select(Account).where(Account.user_id == user.id)))
        chosen = pick_account(accounts, user, Entry(Decimal(1), False, None, None, []))
        assert chosen.id == user.default_account_id


async def test_card_text_escapes_html(client, session_maker, settings):
    await onboard(client, TG_A)
    async with session_maker() as s:
        user = await users.find_user(s, tg_hash(TG_A, settings.id_pepper.get_secret_value()))
        cat = await s.scalar(select(Category).where(Category.user_id == user.id, Category.name == "Кафе"))
        cat.name = '<a href="https://evil">x</a>'
        await s.commit()
        tx, _ = await record(s, user, parse("100 <b>note</b>"), kind="expense", category_id=cat.id)
        text = await card_text(s, user, tx)
        assert "<a href" not in text and "&lt;a href" in text
        assert "<b>note</b>" not in text


async def test_callback_ids_cannot_reach_other_users(client, session_maker, settings):
    """Forged callback data: ledger lookups are always scoped to the sender."""
    from app.services import ledger
    from app.services.errors import NotFound

    await onboard(client, TG_A)
    from tests.conftest import TG_B

    await onboard(client, TG_B)
    async with session_maker() as s:
        pepper = settings.id_pepper.get_secret_value()
        a = await users.find_user(s, tg_hash(TG_A, pepper))
        b = await users.find_user(s, tg_hash(TG_B, pepper))
        tx, _ = await record(s, a, parse("100 кофе"), kind="expense", category_id=None)
        try:
            await ledger.get_transaction(s, b.id, tx.id)
            raise AssertionError("BOLA")
        except NotFound:
            pass
        assert (await s.get(Transaction, tx.id)) is not None


def test_callback_packing_fits_limit():
    import uuid

    u1, u2 = uuid.uuid4(), uuid.uuid4()
    assert unpack(pack(u1)) == u1
    assert len(cb("sc", u1, u2).encode()) <= 64
    assert unpack("not-base64!!") is None
    assert unpack(pack(u1)[:-2]) is None


async def test_webhook_rejects_wrong_token_and_secret(client, app, settings):
    from aiogram import Bot

    from app.bot.setup import build_dispatcher

    app.state.bot = Bot("123456:TEST")
    app.state.dp = build_dispatcher(settings, app.state.sessionmaker)
    try:
        assert (await client.post("/tg/wrong", json={})).status_code == 404
        r = await client.post(
            "/tg/test-path-token", json={}, headers={"X-Telegram-Bot-Api-Secret-Token": "bad"}
        )
        assert r.status_code == 403
        r = await client.post(
            "/tg/test-path-token",
            content=b"not json",
            headers={"X-Telegram-Bot-Api-Secret-Token": "test-webhook-secret"},
        )
        assert r.status_code == 400
    finally:
        await app.state.bot.session.close()
