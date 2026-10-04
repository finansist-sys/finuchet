"""User lifecycle: onboarding, settings, full deletion."""

from __future__ import annotations

from dataclasses import dataclass
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.money import is_currency
from app.db.models import Account, Category, CategoryHint, Transaction, User
from app.services import ledger
from app.services.default_categories import DEFAULTS
from app.services.errors import Conflict, Invalid


@dataclass(slots=True)
class StartAccount:
    type: str
    name: str
    currency: str
    balance: int


def valid_tz(tz: str) -> str:
    if not tz or len(tz) > 64:
        return "UTC"
    try:
        ZoneInfo(tz)
    except (ZoneInfoNotFoundError, ValueError):
        return "UTC"
    return tz


def lang_of(code: str | None) -> str:
    return "ru" if not code or code.lower().startswith(("ru", "uk", "be", "kk")) else "en"


async def find_user(session: AsyncSession, tg_hash: bytes) -> User | None:
    return await session.scalar(select(User).where(User.tg_hash == tg_hash))


async def onboard(
    session: AsyncSession,
    tg_hash: bytes,
    *,
    base_currency: str,
    tz: str,
    lang: str,
    accounts: list[StartAccount],
) -> User:
    if await find_user(session, tg_hash) is not None:
        raise Conflict("already_onboarded")
    if not is_currency(base_currency):
        raise Invalid("currency_invalid")
    if not 1 <= len(accounts) <= 10:
        raise Invalid("accounts_invalid")

    user = User(
        tg_hash=tg_hash,
        base_currency=base_currency,
        tz=valid_tz(tz),
        lang=lang if lang in ("ru", "en") else "ru",
    )
    session.add(user)
    await session.flush()

    for i, (_key, ru, en, kind, icon, emoji, color) in enumerate(DEFAULTS):
        session.add(
            Category(
                user_id=user.id,
                name=ru if user.lang == "ru" else en,
                kind=kind,
                icon=icon,
                emoji=emoji,
                color=color,
                sort=i,
            )
        )

    created = [
        await ledger.create_account(session, user, a.name, a.type, a.currency, a.balance, commit=False)
        for a in accounts
    ]
    user.default_account_id = created[0].id
    await ledger.touch_activity(session, user)
    await session.commit()
    return user


async def update_settings(
    session: AsyncSession,
    user: User,
    *,
    base_currency: str | None,
    tz: str | None,
    default_account_id=None,
) -> User:
    if base_currency is not None:
        if not is_currency(base_currency):
            raise Invalid("currency_invalid")
        user.base_currency = base_currency
    if tz is not None:
        user.tz = valid_tz(tz)
    if default_account_id is not None:
        acc = await ledger.get_account(session, user.id, default_account_id)
        user.default_account_id = acc.id
    await session.commit()
    return user


async def delete_user(session: AsyncSession, user: User) -> None:
    """Erase every row that belongs to the user. Explicit order works without FK cascades too."""
    uid = user.id
    for model in (CategoryHint, Transaction, Category, Account):
        await session.execute(delete(model).where(model.user_id == uid))
    await session.execute(delete(User).where(User.id == uid))
    await session.commit()
