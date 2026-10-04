from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Query

from app.api.deps import SessionDep, UserDep
from app.api.schemas import tx_out
from app.core.money import is_currency
from app.services import stats
from app.services.errors import Invalid

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/home")
async def home(user: UserDep, session: SessionDep) -> dict:
    """Everything the main screen needs in one request."""
    today = stats.local_today(user)
    cur = user.base_currency
    month = stats.period_for("month", today)
    week = stats.period_for("week", today)
    totals = await stats.totals(session, user, month)
    return {
        "currency": cur,
        "balances": await stats.balances(session, user),
        "month": {
            "start": month.start.isoformat(),
            "income": totals.income.get(cur, 0),
            "expense": totals.expense.get(cur, 0),
        },
        "week": {
            "start": week.start.isoformat(),
            "today_index": (today - week.start).days,
            "days": await stats.daily_expenses(session, user, week, cur),
        },
        "recent": [tx_out(t) for t in await stats.recent(session, user, 3)],
    }


@router.get("/categories")
async def categories(
    user: UserDep,
    session: SessionDep,
    period: Literal["week", "month", "year"] = "month",
    offset: Annotated[int, Query(ge=-240, le=0)] = 0,
    currency: Annotated[str | None, Query(min_length=3, max_length=3)] = None,
) -> dict:
    cur = currency or user.base_currency
    if not is_currency(cur):
        raise Invalid("currency_invalid")
    p = stats.period_for(period, stats.local_today(user), offset)
    totals = await stats.totals(session, user, p)
    items = await stats.by_category(session, user, p, cur)
    return {
        "currency": cur,
        "start": p.start.isoformat(),
        "end": p.end.isoformat(),
        "income": totals.income.get(cur, 0),
        "expense": totals.expense.get(cur, 0),
        "categories": [
            {"category_id": str(c.category_id) if c.category_id else None, "amount": c.amount} for c in items
        ],
    }
