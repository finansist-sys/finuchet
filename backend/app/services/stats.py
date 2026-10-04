"""Read-only aggregates for the Mini App and the bot's «Баланс» card.

Periods are computed in the user's time zone. Sums are kept per currency:
currencies are never converted into each other.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Account, Category, Transaction, User


@dataclass(slots=True)
class Period:
    start: date  # inclusive, local
    end: date  # exclusive, local

    def utc_bounds(self, tz: ZoneInfo) -> tuple[datetime, datetime]:
        s = datetime.combine(self.start, datetime.min.time(), tz).astimezone(UTC)
        e = datetime.combine(self.end, datetime.min.time(), tz).astimezone(UTC)
        return s, e


def local_today(user: User, now: datetime | None = None) -> date:
    return (now or datetime.now(UTC)).astimezone(ZoneInfo(user.tz)).date()


def period_for(kind: str, today: date, offset: int = 0) -> Period:
    """kind: week | month | year; offset: 0 = current, -1 = previous, ..."""
    if kind == "week":
        start = today - timedelta(days=today.weekday()) + timedelta(weeks=offset)
        return Period(start, start + timedelta(days=7))
    if kind == "year":
        y = today.year + offset
        return Period(date(y, 1, 1), date(y + 1, 1, 1))
    m = today.year * 12 + (today.month - 1) + offset
    y, mo = divmod(m, 12)
    start = date(y, mo + 1, 1)
    ny, nm = divmod(m + 1, 12)
    return Period(start, date(ny, nm + 1, 1))


def _utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt


async def _rows(session: AsyncSession, user: User, period: Period):
    s, e = period.utc_bounds(ZoneInfo(user.tz))
    q = (
        select(Transaction, Account.currency)
        .join(Account, Account.id == Transaction.account_id)
        .where(
            Transaction.user_id == user.id,
            Transaction.kind.in_(("expense", "income")),
            Transaction.occurred_at >= s,
            Transaction.occurred_at < e,
        )
    )
    return (await session.execute(q)).all()


@dataclass(slots=True)
class Totals:
    income: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    expense: dict[str, int] = field(default_factory=lambda: defaultdict(int))


async def totals(session: AsyncSession, user: User, period: Period) -> Totals:
    t = Totals()
    for tx, cur in await _rows(session, user, period):
        (t.income if tx.kind == "income" else t.expense)[cur] += tx.amount
    return t


async def balances(session: AsyncSession, user: User) -> dict[str, int]:
    rows = await session.scalars(
        select(Account).where(Account.user_id == user.id, Account.archived.is_(False))
    )
    out: dict[str, int] = defaultdict(int)
    for a in rows:
        out[a.currency] += a.balance
    return dict(out)


async def daily_expenses(session: AsyncSession, user: User, period: Period, currency: str) -> list[int]:
    tz = ZoneInfo(user.tz)
    days = (period.end - period.start).days
    out = [0] * days
    for tx, cur in await _rows(session, user, period):
        if tx.kind != "expense" or cur != currency:
            continue
        idx = (_utc(tx.occurred_at).astimezone(tz).date() - period.start).days
        if 0 <= idx < days:
            out[idx] += tx.amount
    return out


@dataclass(slots=True)
class CategorySum:
    category_id: uuid.UUID | None
    amount: int


async def by_category(
    session: AsyncSession, user: User, period: Period, currency: str, kind: str = "expense"
) -> list[CategorySum]:
    sums: dict[uuid.UUID | None, int] = defaultdict(int)
    for tx, cur in await _rows(session, user, period):
        if tx.kind == kind and cur == currency:
            sums[tx.category_id] += tx.amount
    return sorted((CategorySum(k, v) for k, v in sums.items()), key=lambda c: c.amount, reverse=True)


async def recent(session: AsyncSession, user: User, limit: int = 5) -> list[Transaction]:
    rows = await session.scalars(
        select(Transaction)
        .where(Transaction.user_id == user.id)
        .order_by(Transaction.occurred_at.desc(), Transaction.created_at.desc())
        .limit(limit)
    )
    return list(rows)


async def categories_map(session: AsyncSession, user: User) -> dict[uuid.UUID, Category]:
    rows = await session.scalars(select(Category).where(Category.user_id == user.id))
    return {c.id: c for c in rows}
