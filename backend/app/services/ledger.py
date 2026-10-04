"""The accounting core: the only place where balances change.

Every write runs in one DB transaction and locks the affected accounts
(SELECT ... FOR UPDATE, in a stable order to avoid deadlocks), so balances
always equal the sum of their operations. Used by both the bot and the API.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import events
from app.core.money import MAX_AMOUNT, is_currency
from app.db.models import Account, Category, Transaction, User
from app.security.sanitize import clean_text, contains_card_number
from app.services.errors import Conflict, Invalid, NotFound

MAX_ACCOUNTS = 20
MAX_CATEGORIES = 60
MAX_TRANSACTIONS = 100_000
PUBLIC_KINDS = {"expense", "income", "transfer"}
ICONS = {
    "cart",
    "coffee",
    "bus",
    "phone",
    "home",
    "heart",
    "film",
    "shirt",
    "dots",
    "briefcase",
    "gift",
    "car",
    "plane",
    "book",
    "paw",
    "baby",
    "dumbbell",
    "pizza",
    "fuel",
    "card",
    "cash",
    "percent",
}


@dataclass(slots=True)
class TxInput:
    kind: str
    account_id: uuid.UUID
    amount: int
    to_account_id: uuid.UUID | None = None
    to_amount: int | None = None
    category_id: uuid.UUID | None = None
    note: str | None = None
    occurred_at: datetime | None = None
    source: str = "app"


# ---------------------------------------------------------------- helpers


def clean_name(value: str, max_len: int) -> str:
    name = clean_text(value, max_len)
    if not name:
        raise Invalid("name_required")
    if contains_card_number(name):
        raise Invalid("card_number_not_allowed")
    return name


def clean_note(value: str | None) -> str | None:
    if value is None:
        return None
    note = clean_text(value, 140)
    if contains_card_number(note):
        raise Invalid("card_number_not_allowed")
    return note or None


def _check_amount(value: int, *, allow_zero: bool = False) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise Invalid("amount_invalid")
    if value < 0 or (value == 0 and not allow_zero) or value > MAX_AMOUNT:
        raise Invalid("amount_invalid")


def _as_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


async def touch_activity(session: AsyncSession, user: User) -> None:
    today = datetime.now(ZoneInfo(user.tz)).date()
    if user.last_active_date != today:
        user.last_active_date = today


async def get_account(session: AsyncSession, user_id: uuid.UUID, account_id: uuid.UUID) -> Account:
    acc = await session.scalar(select(Account).where(Account.id == account_id, Account.user_id == user_id))
    if acc is None:
        raise NotFound("account_not_found")
    return acc


async def get_category(session: AsyncSession, user_id: uuid.UUID, category_id: uuid.UUID) -> Category:
    cat = await session.scalar(
        select(Category).where(Category.id == category_id, Category.user_id == user_id)
    )
    if cat is None:
        raise NotFound("category_not_found")
    return cat


async def get_transaction(session: AsyncSession, user_id: uuid.UUID, tx_id: uuid.UUID) -> Transaction:
    tx = await session.scalar(
        select(Transaction).where(Transaction.id == tx_id, Transaction.user_id == user_id)
    )
    if tx is None:
        raise NotFound("transaction_not_found")
    return tx


def _effects(tx: Transaction) -> list[tuple[uuid.UUID, int]]:
    if tx.kind == "expense":
        return [(tx.account_id, -tx.amount)]
    if tx.kind in ("income", "adjustment"):
        return [(tx.account_id, tx.amount)]
    assert tx.to_account_id is not None and tx.to_amount is not None  # noqa: S101 - invariant
    return [(tx.account_id, -tx.amount), (tx.to_account_id, tx.to_amount)]


async def _apply(
    session: AsyncSession, user_id: uuid.UUID, effects: list[tuple[uuid.UUID, int]], sign: int
) -> None:
    ids = sorted({acc_id for acc_id, _ in effects})
    rows = await session.scalars(
        select(Account)
        .where(Account.user_id == user_id, Account.id.in_(ids))
        .order_by(Account.id)
        .with_for_update()
    )
    accounts = {a.id: a for a in rows}
    for acc_id, delta in effects:
        acc = accounts.get(acc_id)
        if acc is None:
            raise NotFound("account_not_found")
        new_balance = acc.balance + sign * delta
        if abs(new_balance) > MAX_AMOUNT:
            raise Invalid("balance_out_of_range")
        acc.balance = new_balance


async def _validated(session: AsyncSession, user: User, inp: TxInput) -> Transaction:
    if inp.kind not in PUBLIC_KINDS:
        raise Invalid("kind_invalid")
    _check_amount(inp.amount)
    acc = await get_account(session, user.id, inp.account_id)
    if acc.archived:
        raise Invalid("account_archived")

    to_account_id = to_amount = category_id = None
    if inp.kind == "transfer":
        if inp.to_account_id is None or inp.to_account_id == inp.account_id:
            raise Invalid("transfer_target_invalid")
        to_acc = await get_account(session, user.id, inp.to_account_id)
        if to_acc.archived:
            raise Invalid("account_archived")
        if to_acc.currency == acc.currency:
            to_amount = inp.amount
        else:
            if inp.to_amount is None:
                raise Invalid("to_amount_required")
            _check_amount(inp.to_amount)
            to_amount = inp.to_amount
        to_account_id = to_acc.id
    elif inp.category_id is not None:
        cat = await get_category(session, user.id, inp.category_id)
        if cat.kind != inp.kind:
            raise Invalid("category_kind_mismatch")
        category_id = cat.id

    now = datetime.now(UTC)
    occurred = _as_utc(inp.occurred_at) if inp.occurred_at else now
    if occurred > now + timedelta(days=1) or occurred.year < 2000:
        raise Invalid("date_invalid")
    if inp.source not in ("bot", "app"):
        raise Invalid("source_invalid")

    return Transaction(
        user_id=user.id,
        kind=inp.kind,
        account_id=acc.id,
        to_account_id=to_account_id,
        amount=inp.amount,
        to_amount=to_amount,
        category_id=category_id,
        note=clean_note(inp.note),
        source=inp.source,
        occurred_at=occurred,
    )


# ---------------------------------------------------------------- operations


async def create_transaction(session: AsyncSession, user: User, inp: TxInput) -> Transaction:
    count = await session.scalar(
        select(func.count()).select_from(Transaction).where(Transaction.user_id == user.id)
    )
    if (count or 0) >= MAX_TRANSACTIONS:
        raise Conflict("too_many_transactions")
    tx = await _validated(session, user, inp)
    await _apply(session, user.id, _effects(tx), +1)
    session.add(tx)
    await touch_activity(session, user)
    await session.commit()
    await events.publish(
        events.Event(events.TRANSACTION_CREATED, user.id, {"tx_id": tx.id, "source": tx.source})
    )
    return tx


async def update_transaction(
    session: AsyncSession, user: User, tx_id: uuid.UUID, inp: TxInput
) -> Transaction:
    tx = await get_transaction(session, user.id, tx_id)
    if tx.kind == "adjustment":
        raise Invalid("adjustment_readonly")
    new = await _validated(session, user, inp)
    await _apply(session, user.id, _effects(tx), -1)
    for field in (
        "kind",
        "account_id",
        "to_account_id",
        "amount",
        "to_amount",
        "category_id",
        "note",
        "occurred_at",
    ):
        setattr(tx, field, getattr(new, field))
    await _apply(session, user.id, _effects(tx), +1)
    await session.commit()
    return tx


async def delete_transaction(session: AsyncSession, user: User, tx_id: uuid.UUID) -> None:
    tx = await get_transaction(session, user.id, tx_id)
    await _apply(session, user.id, _effects(tx), -1)
    await session.delete(tx)
    await session.commit()
    await events.publish(events.Event(events.TRANSACTION_DELETED, user.id, {"tx_id": tx_id}))


async def reconcile(
    session: AsyncSession, user: User, account_id: uuid.UUID, actual_balance: int
) -> Transaction | None:
    """Set the account to the real amount by recording the difference as an adjustment."""
    if not isinstance(actual_balance, int) or abs(actual_balance) > MAX_AMOUNT:
        raise Invalid("amount_invalid")
    acc = await session.scalar(
        select(Account).where(Account.id == account_id, Account.user_id == user.id).with_for_update()
    )
    if acc is None:
        raise NotFound("account_not_found")
    delta = actual_balance - acc.balance
    if delta == 0:
        return None
    tx = Transaction(user_id=user.id, kind="adjustment", account_id=acc.id, amount=delta, source="app")
    acc.balance = actual_balance
    session.add(tx)
    await touch_activity(session, user)
    await session.commit()
    return tx


# ---------------------------------------------------------------- accounts & categories


async def create_account(
    session: AsyncSession,
    user: User,
    name: str,
    type_: str,
    currency: str,
    balance: int,
    *,
    commit: bool = True,
) -> Account:
    if type_ not in ("card", "cash"):
        raise Invalid("account_type_invalid")
    if not is_currency(currency):
        raise Invalid("currency_invalid")
    if not isinstance(balance, int) or abs(balance) > MAX_AMOUNT:
        raise Invalid("amount_invalid")
    count = await session.scalar(select(func.count()).select_from(Account).where(Account.user_id == user.id))
    if (count or 0) >= MAX_ACCOUNTS:
        raise Conflict("too_many_accounts")
    acc = Account(
        user_id=user.id,
        name=clean_name(name, 40),
        type=type_,
        currency=currency,
        balance=balance,
        sort=count or 0,
    )
    session.add(acc)
    if commit:
        await session.commit()
    else:
        await session.flush()
    return acc


async def update_account(
    session: AsyncSession, user: User, account_id: uuid.UUID, *, name: str | None, archived: bool | None
) -> Account:
    acc = await get_account(session, user.id, account_id)
    if name is not None:
        acc.name = clean_name(name, 40)
    if archived is not None:
        acc.archived = archived
        if archived and user.default_account_id == acc.id:
            user.default_account_id = None
    await session.commit()
    return acc


async def create_category(
    session: AsyncSession, user: User, *, name: str, kind: str, icon: str, emoji: str, color: int
) -> Category:
    if kind not in ("expense", "income"):
        raise Invalid("kind_invalid")
    if icon not in ICONS:
        raise Invalid("icon_invalid")
    if not -1 <= color <= 7:
        raise Invalid("color_invalid")
    count = await session.scalar(
        select(func.count()).select_from(Category).where(Category.user_id == user.id)
    )
    if (count or 0) >= MAX_CATEGORIES:
        raise Conflict("too_many_categories")
    cat = Category(
        user_id=user.id,
        name=clean_name(name, 32),
        kind=kind,
        icon=icon,
        emoji=clean_text(emoji, 8) or "•",
        color=color,
        sort=count or 0,
    )
    session.add(cat)
    await session.commit()
    return cat


async def update_category(
    session: AsyncSession,
    user: User,
    category_id: uuid.UUID,
    *,
    name: str | None = None,
    icon: str | None = None,
    emoji: str | None = None,
    color: int | None = None,
    archived: bool | None = None,
) -> Category:
    cat = await get_category(session, user.id, category_id)
    if name is not None:
        cat.name = clean_name(name, 32)
    if icon is not None:
        if icon not in ICONS:
            raise Invalid("icon_invalid")
        cat.icon = icon
    if emoji is not None:
        cat.emoji = clean_text(emoji, 8) or "•"
    if color is not None:
        if not -1 <= color <= 7:
            raise Invalid("color_invalid")
        cat.color = color
    if archived is not None:
        cat.archived = archived
    await session.commit()
    return cat
