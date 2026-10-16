"""aiogram FSM storage in the application database.

Needed for serverless hosting, where nothing survives between invocations, and it also keeps
"pick category -> type amount" working across restarts of a normal server. The storage key is
HMAC(pepper, bot/chat/user ids): Telegram ids are never written to the database.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import random
from collections.abc import Awaitable, Callable, Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

from aiogram.fsm.state import State
from aiogram.fsm.storage.base import BaseStorage, StorageKey
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import BotState

TTL = timedelta(days=1)
MAX_DATA_BYTES = 2048

SessionmakerGetter = Callable[[], Awaitable[async_sessionmaker[AsyncSession]]]


def _as_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt


class SqlStorage(BaseStorage):
    def __init__(self, get_sessionmaker: SessionmakerGetter, pepper: str) -> None:
        self._get_sessionmaker = get_sessionmaker
        self._pepper = pepper.encode()

    def _key(self, key: StorageKey) -> bytes:
        raw = (
            f"fsm:{key.bot_id}:{key.chat_id}:{key.user_id}:{key.thread_id}:"
            f"{key.business_connection_id}:{key.destiny}"
        )
        return hmac.new(self._pepper, raw.encode(), hashlib.sha256).digest()

    async def _load(self, session: AsyncSession, key: StorageKey) -> BotState | None:
        row = await session.get(BotState, self._key(key))
        if row is not None and datetime.now(UTC) - _as_utc(row.updated_at) > TTL:
            await session.delete(row)
            await session.commit()
            return None
        return row

    async def _save(self, key: StorageKey, *, state: Any = ..., data: Any = ...) -> None:
        maker = await self._get_sessionmaker()
        async with maker() as session:
            row = await self._load(session, key)
            if row is None:
                row = BotState(key=self._key(key), state=None, data="{}")
                session.add(row)
            if state is not ...:
                row.state = state.state if isinstance(state, State) else state
            if data is not ...:
                encoded = json.dumps(dict(data), ensure_ascii=False, separators=(",", ":"))
                if len(encoded.encode()) > MAX_DATA_BYTES:
                    raise ValueError("FSM data too large")
                row.data = encoded
            row.updated_at = datetime.now(UTC)
            if row.state is None and row.data == "{}":
                await session.delete(row)
            await session.commit()
            if random.random() < 0.02:  # noqa: S311 - housekeeping, not security
                await session.execute(delete(BotState).where(BotState.updated_at < datetime.now(UTC) - TTL))
                await session.commit()

    async def set_state(self, key: StorageKey, state: str | State | None = None) -> None:
        await self._save(key, state=state)

    async def get_state(self, key: StorageKey) -> str | None:
        maker = await self._get_sessionmaker()
        async with maker() as session:
            row = await self._load(session, key)
            return row.state if row else None

    async def set_data(self, key: StorageKey, data: Mapping[str, Any]) -> None:
        await self._save(key, data=data)

    async def get_data(self, key: StorageKey) -> dict[str, Any]:
        maker = await self._get_sessionmaker()
        async with maker() as session:
            row = await self._load(session, key)
            return json.loads(row.data) if row else {}

    async def close(self) -> None:
        return None
