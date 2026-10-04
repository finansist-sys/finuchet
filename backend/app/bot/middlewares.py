"""Per-update context: DB session, pseudonymous user, language, throttling.

The raw Telegram id is used only in memory to compute tg_hash; it is never
stored or logged.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from app.config import Settings
from app.security.identity import tg_hash
from app.security.ratelimit import RateLimiter
from app.services.users import find_user, lang_of


class ContextMiddleware(BaseMiddleware):
    def __init__(self, settings: Settings, sessionmaker, limiter: RateLimiter) -> None:
        self.settings = settings
        self.sessionmaker = sessionmaker
        self.limiter = limiter

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if isinstance(event, Message):
            if event.chat.type != "private" or event.from_user is None:
                return None
            from_user = event.from_user
        elif isinstance(event, CallbackQuery):
            if event.message is not None and event.message.chat.type != "private":
                return None
            from_user = event.from_user
        else:
            return None
        if from_user.is_bot:
            return None

        h = tg_hash(from_user.id, self.settings.id_pepper.get_secret_value())
        if not self.limiter.allow(h):
            if isinstance(event, CallbackQuery):
                await event.answer()
            return None

        async with self.sessionmaker() as session:
            user = await find_user(session, h)
            data["session"] = session
            data["user"] = user
            data["tg_hash"] = h
            data["lang"] = user.lang if user else lang_of(from_user.language_code)
            data["settings"] = self.settings
            return await handler(event, data)
