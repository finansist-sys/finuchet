import logging
import time

from app.db.models import Account, Category, Transaction, User
from sqlalchemy import select, text

from tests.conftest import TG_A, TG_B, auth, onboard


async def balance(client, tg, name):
    accs = (await client.get("/api/accounts", headers=auth(tg))).json()
    return next(a["balance"] for a in accs if a["name"] == name)


async def test_onboarding_creates_accounts_and_categories(client):
    data = await onboard(client, TG_A)
    assert set(data["accounts"]) == {"Карта", "Наличные", "Наличные $"}
    assert ("Продукты", "expense") in data["categories"]
    me = (await client.get("/api/me", headers=auth(TG_A))).json()
    assert me["onboarded"] is True and me["base_currency"] == "RUB"
    assert str(TG_A) not in str(me)
    assert (
        await client.post(
            "/api/onboarding",
            json={
                "base_currency": "RUB",
                "accounts": [{"type": "card", "name": "x", "currency": "RUB", "balance": 0}],
            },
            headers=auth(TG_A),
        )
    ).status_code == 409


async def test_expense_income_delete_and_balances(client):
    d = await onboard(client, TG_A)
    cash = d["accounts"]["Наличные"]["id"]
    cafe = d["categories"][("Кафе", "expense")]["id"]
    r = await client.post(
        "/api/transactions",
        headers=auth(TG_A),
        json={"kind": "expense", "account_id": cash, "amount": 300_00, "category_id": cafe, "note": "кофе"},
    )
    assert r.status_code == 201
    tx_id = r.json()["transaction"]["id"]
    assert await balance(client, TG_A, "Наличные") == 1_700_00

    salary = d["categories"][("Зарплата", "income")]["id"]
    card = d["accounts"]["Карта"]["id"]
    await client.post(
        "/api/transactions",
        headers=auth(TG_A),
        json={"kind": "income", "account_id": card, "amount": 50_000_00, "category_id": salary},
    )
    assert await balance(client, TG_A, "Карта") == 60_000_00

    assert (await client.delete(f"/api/transactions/{tx_id}", headers=auth(TG_A))).status_code == 204
    assert await balance(client, TG_A, "Наличные") == 2_000_00


async def test_update_moves_money_between_accounts(client):
    d = await onboard(client, TG_A)
    cash, card = d["accounts"]["Наличные"]["id"], d["accounts"]["Карта"]["id"]
    tx = (
        await client.post(
            "/api/transactions",
            headers=auth(TG_A),
            json={"kind": "expense", "account_id": cash, "amount": 500_00},
        )
    ).json()["transaction"]
    r = await client.patch(
        f"/api/transactions/{tx['id']}",
        headers=auth(TG_A),
        json={"kind": "expense", "account_id": card, "amount": 700_00},
    )
    assert r.status_code == 200
    assert await balance(client, TG_A, "Наличные") == 2_000_00
    assert await balance(client, TG_A, "Карта") == 9_300_00


async def test_category_kind_must_match(client):
    d = await onboard(client, TG_A)
    r = await client.post(
        "/api/transactions",
        headers=auth(TG_A),
        json={
            "kind": "expense",
            "account_id": d["accounts"]["Карта"]["id"],
            "amount": 100,
            "category_id": d["categories"][("Зарплата", "income")]["id"],
        },
    )
    assert r.status_code == 422


async def test_transfer_same_and_cross_currency(client):
    d = await onboard(client, TG_A)
    card, cash, usd = (d["accounts"][n]["id"] for n in ("Карта", "Наличные", "Наличные $"))
    r = await client.post(
        "/api/transactions",
        headers=auth(TG_A),
        json={"kind": "transfer", "account_id": card, "to_account_id": cash, "amount": 1_000_00},
    )
    assert r.status_code == 201
    assert await balance(client, TG_A, "Карта") == 9_000_00
    assert await balance(client, TG_A, "Наличные") == 3_000_00

    r = await client.post(
        "/api/transactions",
        headers=auth(TG_A),
        json={"kind": "transfer", "account_id": card, "to_account_id": usd, "amount": 9_000_00},
    )
    assert r.status_code == 422 and r.json()["detail"] == "to_amount_required"
    r = await client.post(
        "/api/transactions",
        headers=auth(TG_A),
        json={
            "kind": "transfer",
            "account_id": card,
            "to_account_id": usd,
            "amount": 9_000_00,
            "to_amount": 100_00,
        },
    )
    assert r.status_code == 201
    assert await balance(client, TG_A, "Карта") == 0
    assert await balance(client, TG_A, "Наличные $") == 200_00


async def test_reconcile(client):
    d = await onboard(client, TG_A)
    cash = d["accounts"]["Наличные"]["id"]
    r = await client.post(f"/api/accounts/{cash}/reconcile", headers=auth(TG_A), json={"balance": 1_234_00})
    assert r.status_code == 200
    assert r.json()["adjustment"]["amount"] == -766_00
    assert await balance(client, TG_A, "Наличные") == 1_234_00
    adj_id = r.json()["adjustment"]["id"]
    assert (await client.delete(f"/api/transactions/{adj_id}", headers=auth(TG_A))).status_code == 204
    assert await balance(client, TG_A, "Наличные") == 2_000_00


async def test_other_users_data_is_invisible(client):
    """BOLA/IDOR: user B must not read or change anything of user A."""
    a = await onboard(client, TG_A)
    await onboard(client, TG_B)
    a_cash = a["accounts"]["Наличные"]["id"]
    a_cat = a["categories"][("Кафе", "expense")]["id"]
    tx = (
        await client.post(
            "/api/transactions",
            headers=auth(TG_A),
            json={"kind": "expense", "account_id": a_cash, "amount": 100},
        )
    ).json()["transaction"]

    hb = auth(TG_B)
    assert (await client.delete(f"/api/transactions/{tx['id']}", headers=hb)).status_code == 404
    assert (
        await client.patch(
            f"/api/transactions/{tx['id']}",
            headers=hb,
            json={"kind": "expense", "account_id": a_cash, "amount": 1},
        )
    ).status_code == 404
    assert (
        await client.post(
            "/api/transactions", headers=hb, json={"kind": "expense", "account_id": a_cash, "amount": 1}
        )
    ).status_code == 404
    assert (
        await client.patch(f"/api/accounts/{a_cash}", headers=hb, json={"name": "hacked"})
    ).status_code == 404
    assert (
        await client.post(f"/api/accounts/{a_cash}/reconcile", headers=hb, json={"balance": 0})
    ).status_code == 404
    assert (
        await client.patch(f"/api/categories/{a_cat}", headers=hb, json={"name": "hacked"})
    ).status_code == 404
    listed = (await client.get("/api/transactions", headers=hb, params={"account_id": a_cash})).json()
    assert listed["items"] == []
    assert await balance(client, TG_A, "Наличные") == 2_000_00 - 100


async def test_unknown_fields_rejected_and_input_not_echoed(client):
    d = await onboard(client, TG_A)
    r = await client.post(
        "/api/transactions",
        headers=auth(TG_A),
        json={
            "kind": "expense",
            "account_id": d["accounts"]["Карта"]["id"],
            "amount": -5,
            "note": "very private note",
            "user_id": "x",
        },
    )
    assert r.status_code == 422
    assert "very private note" not in r.text


async def test_card_number_in_names_rejected(client):
    d = await onboard(client, TG_A)
    r = await client.patch(
        f"/api/accounts/{d['accounts']['Карта']['id']}",
        headers=auth(TG_A),
        json={"name": "4111 1111 1111 1111"},
    )
    assert r.status_code == 422 and r.json()["detail"] == "card_number_not_allowed"


async def test_stats_home_and_categories(client):
    d = await onboard(client, TG_A)
    card = d["accounts"]["Карта"]["id"]
    food = d["categories"][("Продукты", "expense")]["id"]
    await client.post(
        "/api/transactions",
        headers=auth(TG_A),
        json={"kind": "expense", "account_id": card, "amount": 1_000_00, "category_id": food},
    )
    await client.post(
        "/api/transactions",
        headers=auth(TG_A),
        json={"kind": "expense", "account_id": d["accounts"]["Наличные $"]["id"], "amount": 5_00},
    )
    home = (await client.get("/api/stats/home", headers=auth(TG_A))).json()
    assert home["month"]["expense"] == 1_000_00
    assert home["balances"] == {"RUB": 11_000_00, "USD": 95_00}
    assert sum(home["week"]["days"]) == 1_000_00 and len(home["week"]["days"]) == 7
    cats = (await client.get("/api/stats/categories", headers=auth(TG_A), params={"currency": "USD"})).json()
    assert cats["expense"] == 5_00 and cats["categories"][0]["category_id"] is None


async def test_delete_me_requires_fresh_auth_and_erases_everything(client, session_maker):
    await onboard(client, TG_A)
    await onboard(client, TG_B)
    stale = auth(TG_A, auth_date=int(time.time()) - 3600)
    assert (await client.delete("/api/me", headers=stale)).status_code == 401
    assert (await client.delete("/api/me", headers=auth(TG_A))).status_code == 204
    async with session_maker() as s:
        assert len((await s.scalars(select(User))).all()) == 1
        users_left = (await s.scalars(select(User))).all()
        uid = users_left[0].id
        for model in (Account, Category, Transaction):
            rows = (await s.scalars(select(model))).all()
            assert all(r.user_id == uid for r in rows)


async def test_database_never_contains_telegram_id(client, session_maker):
    d = await onboard(client, TG_A)
    await client.post(
        "/api/transactions",
        headers=auth(TG_A),
        json={"kind": "expense", "account_id": d["accounts"]["Карта"]["id"], "amount": 100, "note": "обед"},
    )
    async with session_maker() as s:
        tables = ["users", "accounts", "categories", "transactions", "category_hints"]
        dump = ""
        for table in tables:
            rows = (await s.execute(text(f"SELECT * FROM {table}"))).all()  # noqa: S608 - fixed names
            dump += repr(rows)
    assert str(TG_A) not in dump
    assert "secret_name" not in dump  # Telegram username from initData is never stored


async def test_logs_contain_no_identifiers(client, caplog):
    caplog.set_level(logging.INFO)
    await onboard(client, TG_A)
    joined = " ".join(r.getMessage() for r in caplog.records)
    assert str(TG_A) not in joined
    assert "hash=" not in joined and "tma " not in joined
