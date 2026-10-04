"""Per-user memory of which category a word belongs to (used by the bot)."""

from __future__ import annotations

import re
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CategoryHint

_WORD = re.compile(r"[^\W\d_]{2,32}", re.UNICODE)
MAX_HINTS_PER_USER = 2000


def keywords(text: str) -> list[str]:
    """Lower-cased words (letters only, 2..32 chars), in order, without duplicates."""
    seen: list[str] = []
    for w in _WORD.findall(text.lower().replace("ё", "е")):
        if w not in seen:
            seen.append(w)
    return seen[:5]


async def suggest(session: AsyncSession, user_id: uuid.UUID, words: list[str]) -> uuid.UUID | None:
    if not words:
        return None
    rows = await session.scalars(
        select(CategoryHint)
        .where(CategoryHint.user_id == user_id, CategoryHint.keyword.in_(words))
        .order_by(CategoryHint.hits.desc())
        .limit(1)
    )
    hint = rows.first()
    return hint.category_id if hint else None


async def learn(session: AsyncSession, user_id: uuid.UUID, words: list[str], category_id: uuid.UUID) -> None:
    """Remember the first keyword of an entry. Caller commits."""
    if not words:
        return
    word = words[0]
    hint = await session.scalar(
        select(CategoryHint).where(CategoryHint.user_id == user_id, CategoryHint.keyword == word)
    )
    if hint is None:
        count = await session.scalar(
            select(func.count()).select_from(CategoryHint).where(CategoryHint.user_id == user_id)
        )
        if (count or 0) >= MAX_HINTS_PER_USER:
            return
        session.add(CategoryHint(user_id=user_id, keyword=word, category_id=category_id, hits=1))
    elif hint.category_id == category_id:
        hint.hits = min(hint.hits + 1, 1_000_000)
    else:
        hint.category_id, hint.hits = category_id, 1
