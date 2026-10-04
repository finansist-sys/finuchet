"""Bot conversation: quick text entries, button entries, entry card, balance, data deletion."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta
from html import escape

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import keyboards as kb
from app.bot.keywords import icon_for
from app.bot.parser import Entry, parse
from app.bot.texts import TEXTS, t
from app.config import Settings
from app.core.money import format_amount, to_minor
from app.db.models import Account, Category, Transaction, User
from app.services import hints, ledger, stats, users
from app.services.errors import DomainError, NotFound

log = logging.getLogger(__name__)
router = Router(name="finuchet")

EXPENSE_LABELS = {TEXTS[lang]["btn_expense"] for lang in TEXTS}
INCOME_LABELS = {TEXTS[lang]["btn_income"] for lang in TEXTS}
BALANCE_LABELS = {TEXTS[lang]["btn_balance"] for lang in TEXTS}


class NewEntry(StatesGroup):
    amount = State()


def app_url(settings: Settings) -> str:
    return settings.public_url.rstrip("/") + "/"


# ---------------------------------------------------------------- data helpers


async def active_accounts(session: AsyncSession, user: User) -> list[Account]:
    rows = await session.scalars(
        select(Account).where(Account.user_id == user.id, Account.archived.is_(False)).order_by(Account.sort)
    )
    return list(rows)


async def frequent_categories(session: AsyncSession, user: User, kind: str) -> list[Category]:
    since = datetime.now(UTC) - timedelta(days=90)
    counts = dict(
        (
            await session.execute(
                select(Transaction.category_id, func.count())
                .where(
                    Transaction.user_id == user.id,
                    Transaction.occurred_at >= since,
                    Transaction.category_id.is_not(None),
                )
                .group_by(Transaction.category_id)
            )
        ).all()
    )
    cats = await session.scalars(
        select(Category).where(
            Category.user_id == user.id, Category.kind == kind, Category.archived.is_(False)
        )
    )
    return sorted(cats, key=lambda c: (-counts.get(c.id, 0), c.sort))


def pick_account(accounts: list[Account], user: User, entry: Entry) -> Account | None:
    candidates = [a for a in accounts if a.currency == entry.currency] if entry.currency else accounts
    if entry.account_type:
        typed = [a for a in candidates if a.type == entry.account_type]
        candidates = typed or candidates
    if not candidates:
        return None
    for a in candidates:
        if a.id == user.default_account_id:
            return a
    base = [a for a in candidates if a.currency == user.base_currency]
    return (base or candidates)[0]


async def guess_category(session: AsyncSession, user: User, kind: str, words: list[str]) -> uuid.UUID | None:
    remembered = await hints.suggest(session, user.id, hints.keywords(" ".join(words)))
    if remembered is not None:
        cat = await session.get(Category, remembered)
        if cat and cat.user_id == user.id and cat.kind == kind and not cat.archived:
            return cat.id
    icon = icon_for(words)
    if icon:
        cat = await session.scalar(
            select(Category)
            .where(
                Category.user_id == user.id,
                Category.kind == kind,
                Category.icon == icon,
                Category.archived.is_(False),
            )
            .order_by(Category.sort)
            .limit(1)
        )
        if cat:
            return cat.id
    return None


async def card_text(session: AsyncSession, user: User, tx: Transaction) -> str:
    acc = await session.get(Account, tx.account_id)
    cat = await session.get(Category, tx.category_id) if tx.category_id else None
    sign = -tx.amount if tx.kind == "expense" else tx.amount
    amount = format_amount(sign, acc.currency, signed=True) if acc else str(tx.amount)
    category = f"{escape(cat.emoji)} {escape(cat.name)}" if cat else t(user.lang, "no_category")
    text = t(user.lang, "saved", amount=amount, category=category, account=escape(acc.name) if acc else "—")
    if tx.note:
        text += f"\n<i>{escape(tx.note)}</i>"
    return text


async def safe_edit(message, text: str, reply_markup=None) -> None:
    try:
        await message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest:
        pass  # "message is not modified" or too old to edit


async def record(
    session: AsyncSession, user: User, entry: Entry, *, kind: str, category_id: uuid.UUID | None
) -> tuple[Transaction | None, str | None]:
    accounts = await active_accounts(session, user)
    if not accounts:
        return None, t(user.lang, "no_accounts")
    acc = pick_account(accounts, user, entry)
    if acc is None:
        return None, t(user.lang, "no_account_currency", currency=escape(entry.currency or ""))
    amount = to_minor(entry.amount, acc.currency)
    if amount <= 0:
        return None, t(user.lang, "not_understood")
    if category_id is None:
        category_id = await guess_category(session, user, kind, entry.words)
    note = " ".join(entry.words) or None
    tx = await ledger.create_transaction(
        session,
        user,
        ledger.TxInput(
            kind=kind, account_id=acc.id, amount=amount, category_id=category_id, note=note, source="bot"
        ),
    )
    if category_id and entry.words:
        await hints.learn(session, user.id, hints.keywords(note or ""), category_id)
        await session.commit()
    return tx, None


async def send_card(message: Message, session: AsyncSession, user: User, tx: Transaction) -> None:
    text = await card_text(session, user, tx)
    if tx.category_id is None:
        cats = await frequent_categories(session, user, tx.kind)
        await message.answer(
            f"{text}\n{t(user.lang, 'pick_category')}", reply_markup=kb.tx_categories(user.lang, tx.id, cats)
        )
    else:
        await message.answer(text, reply_markup=kb.tx_card(user.lang, tx.id))


# ---------------------------------------------------------------- commands


@router.message(CommandStart())
async def cmd_start(
    message: Message, user: User | None, lang: str, settings: Settings, state: FSMContext
) -> None:
    await state.clear()
    if user is None:
        await message.answer(t(lang, "start_new"), reply_markup=kb.open_app_keyboard(lang, app_url(settings)))
    else:
        await message.answer(t(lang, "start_back"), reply_markup=kb.main_keyboard(lang))


@router.message(Command("help"))
async def cmd_help(message: Message, lang: str) -> None:
    await message.answer(t(lang, "help"))


@router.message(Command("privacy"))
async def cmd_privacy(message: Message, lang: str) -> None:
    await message.answer(t(lang, "privacy"))


@router.message(Command("delete_me"))
async def cmd_delete(message: Message, user: User | None, lang: str) -> None:
    if user is None:
        await message.answer(t(lang, "nothing_to_delete"))
        return
    await message.answer(t(lang, "delete_confirm"), reply_markup=kb.delete_confirm(lang))


# ---------------------------------------------------------------- buttons


@router.message(F.text.in_(EXPENSE_LABELS | INCOME_LABELS))
async def btn_new_entry(
    message: Message,
    session: AsyncSession,
    user: User | None,
    lang: str,
    settings: Settings,
    state: FSMContext,
) -> None:
    await state.clear()
    if user is None:
        await message.answer(
            t(lang, "need_onboarding"), reply_markup=kb.open_app_keyboard(lang, app_url(settings))
        )
        return
    kind = "expense" if message.text in EXPENSE_LABELS else "income"
    cats = await frequent_categories(session, user, kind)
    await message.answer(t(lang, "pick_category"), reply_markup=kb.new_entry_categories(kind, cats))


@router.message(F.text.in_(BALANCE_LABELS))
async def btn_balance(
    message: Message, session: AsyncSession, user: User | None, lang: str, settings: Settings
) -> None:
    if user is None:
        await message.answer(
            t(lang, "need_onboarding"), reply_markup=kb.open_app_keyboard(lang, app_url(settings))
        )
        return
    lines = [t(lang, "balance_title")]
    for a in await active_accounts(session, user):
        icon = "💳" if a.type == "card" else "💵"
        lines.append(f"{icon} {escape(a.name)} — {format_amount(a.balance, a.currency)}")
    bal = await stats.balances(session, user)
    if len(bal) > 0:
        lines.append(t(lang, "balance_total", total=", ".join(format_amount(v, c) for c, v in bal.items())))

    cur = user.base_currency
    today = stats.local_today(user)
    day = stats.Period(today, today + timedelta(days=1))
    month = stats.period_for("month", today)
    spent_today = (await stats.totals(session, user, day)).expense.get(cur, 0)
    m = await stats.totals(session, user, month)
    lines += [
        "",
        t(lang, "balance_today", amount=format_amount(spent_today, cur)),
        t(
            lang,
            "balance_month",
            expense=format_amount(m.expense.get(cur, 0), cur),
            income=format_amount(m.income.get(cur, 0), cur),
        ),
    ]
    top = (await stats.by_category(session, user, month, cur))[:3]
    if top:
        cats = await stats.categories_map(session, user)
        total = sum(c.amount for c in await stats.by_category(session, user, month, cur)) or 1
        lines += ["", t(lang, "balance_top")]
        for c in top:
            cat = cats.get(c.category_id) if c.category_id else None
            name = f"{escape(cat.emoji)} {escape(cat.name)}" if cat else t(lang, "no_category")
            filled = max(1, round(c.amount / total * 8))
            lines.append(f"{'▇' * filled}{'▁' * (8 - filled)} {name} — {format_amount(c.amount, cur)}")
    await message.answer("\n".join(lines), reply_markup=kb.open_app_keyboard(lang, app_url(settings)))


@router.message(StateFilter(NewEntry.amount), F.text)
async def entry_amount(
    message: Message, session: AsyncSession, user: User | None, lang: str, state: FSMContext
) -> None:
    data = await state.get_data()
    entry = parse(message.text or "")
    if user is None or entry is None:
        await message.answer(t(lang, "not_understood"))
        return
    await state.clear()
    category_id = uuid.UUID(data["category_id"])
    try:
        tx, error = await record(session, user, entry, kind=data["kind"], category_id=category_id)
    except DomainError:
        await message.answer(t(lang, "not_understood"))
        return
    if error or tx is None:
        await message.answer(error or t(lang, "not_understood"))
        return
    await send_card(message, session, user, tx)


@router.message(F.text)
async def quick_entry(
    message: Message, session: AsyncSession, user: User | None, lang: str, settings: Settings
) -> None:
    if user is None:
        await message.answer(
            t(lang, "need_onboarding"), reply_markup=kb.open_app_keyboard(lang, app_url(settings))
        )
        return
    entry = parse(message.text or "")
    if entry is None:
        await message.answer(t(lang, "not_understood"))
        return
    try:
        tx, error = await record(
            session, user, entry, kind="income" if entry.income else "expense", category_id=None
        )
    except DomainError:
        await message.answer(t(lang, "not_understood"))
        return
    if error or tx is None:
        await message.answer(error or t(lang, "not_understood"))
        return
    await send_card(message, session, user, tx)


# ---------------------------------------------------------------- inline callbacks


@router.callback_query(F.data.startswith("f:"))
async def on_callback(
    query: CallbackQuery, session: AsyncSession, user: User | None, lang: str, state: FSMContext
) -> None:
    parts = (query.data or "").split(":")
    action = parts[1] if len(parts) > 1 else ""
    message = query.message
    if user is None or message is None:
        await query.answer()
        return

    if action == "dy":
        await state.clear()
        await users.delete_user(session, user)
        await safe_edit(message, t(lang, "deleted"))
        await query.answer()
        return
    if action == "dn":
        await safe_edit(message, t(lang, "cancelled"))
        await query.answer()
        return

    if action == "n" and len(parts) == 4:
        kind = {"e": "expense", "i": "income"}.get(parts[2])
        cat_id = kb.unpack(parts[3])
        cat = await session.get(Category, cat_id) if cat_id and kind else None
        if cat is None or cat.user_id != user.id or cat.kind != kind or cat.archived:
            await query.answer()
            return
        await state.set_state(NewEntry.amount)
        await state.update_data(kind=kind, category_id=str(cat.id))
        await safe_edit(message, t(lang, "ask_amount", emoji=escape(cat.emoji), name=escape(cat.name)))
        await query.answer()
        return

    tx_id = kb.unpack(parts[2]) if len(parts) > 2 else None
    if tx_id is None:
        await query.answer()
        return
    try:
        tx = await ledger.get_transaction(session, user.id, tx_id)  # ownership check
    except NotFound:
        await safe_edit(message, t(lang, "gone"))
        await query.answer()
        return

    try:
        if action == "u":
            await ledger.delete_transaction(session, user, tx.id)
            await safe_edit(message, t(lang, "undone"))
        elif action == "c" and tx.kind in ("expense", "income"):
            cats = await frequent_categories(session, user, tx.kind)
            await safe_edit(message, await card_text(session, user, tx), kb.tx_categories(lang, tx.id, cats))
        elif action == "a":
            src = await session.get(Account, tx.account_id)
            accounts = [a for a in await active_accounts(session, user) if src and a.currency == src.currency]
            await safe_edit(message, t(lang, "pick_account"), kb.tx_accounts(lang, tx.id, accounts))
        elif action in ("sc", "sa") and len(parts) == 4 and tx.kind in ("expense", "income"):
            target = kb.unpack(parts[3])
            if target is None:
                await query.answer()
                return
            inp = ledger.TxInput(
                kind=tx.kind,
                account_id=tx.account_id,
                amount=tx.amount,
                category_id=tx.category_id,
                note=tx.note,
                occurred_at=tx.occurred_at,
                source=tx.source,
            )
            if action == "sc":
                inp.category_id = target
            else:
                acc = await ledger.get_account(session, user.id, target)
                src = await session.get(Account, tx.account_id)
                if src is None or acc.currency != src.currency:
                    await query.answer()
                    return
                inp.account_id = acc.id
            tx = await ledger.update_transaction(session, user, tx.id, inp)
            if action == "sc" and tx.note:
                await hints.learn(session, user.id, hints.keywords(tx.note), target)
                await session.commit()
            await safe_edit(message, await card_text(session, user, tx), kb.tx_card(lang, tx.id))
        elif action == "b":
            await safe_edit(message, await card_text(session, user, tx), kb.tx_card(lang, tx.id))
    except DomainError:
        pass
    await query.answer()
