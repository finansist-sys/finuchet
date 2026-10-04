"""Bot lifecycle and the Telegram webhook endpoint."""

from __future__ import annotations

import asyncio
import contextlib
import hmac
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, MenuButtonWebApp, Update, WebAppInfo
from fastapi import APIRouter, FastAPI, Request, Response
from pydantic import ValidationError

from app.bot import handlers
from app.bot.middlewares import ContextMiddleware
from app.config import Settings
from app.security.ratelimit import RateLimiter

log = logging.getLogger(__name__)
webhook_router = APIRouter()

COMMANDS = {
    "ru": [
        ("start", "Начать"),
        ("help", "Как записывать траты"),
        ("privacy", "Какие данные хранятся"),
        ("delete_me", "Удалить мои данные"),
    ],
    "en": [
        ("start", "Start"),
        ("help", "How to log expenses"),
        ("privacy", "What data is stored"),
        ("delete_me", "Delete my data"),
    ],
}


def build_dispatcher(settings: Settings, sessionmaker) -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())
    mw = ContextMiddleware(settings, sessionmaker, RateLimiter(limit=20, window_seconds=10))
    dp.message.outer_middleware(mw)
    dp.callback_query.outer_middleware(mw)
    dp.include_router(handlers.router)
    return dp


async def _configure(bot: Bot, settings: Settings) -> None:
    url = handlers.app_url(settings)
    await bot.set_chat_menu_button(menu_button=MenuButtonWebApp(text="Финучёт", web_app=WebAppInfo(url=url)))
    for lang, cmds in COMMANDS.items():
        await bot.set_my_commands(
            [BotCommand(command=c, description=d) for c, d in cmds],
            language_code=None if lang == "ru" else lang,
        )


async def start_bot(app: FastAPI) -> None:
    settings: Settings = app.state.settings
    app.state.bot = None
    app.state.dp = None
    app.state.polling_task = None
    if settings.bot_mode == "off":
        return

    bot = Bot(
        settings.bot_token.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML, link_preview_is_disabled=True),
    )
    dp = build_dispatcher(settings, app.state.sessionmaker)
    app.state.bot, app.state.dp = bot, dp
    await _configure(bot, settings)

    if settings.bot_mode == "webhook":
        await bot.set_webhook(
            url=f"{settings.public_url.rstrip('/')}/tg/{settings.webhook_path_token.get_secret_value()}",
            secret_token=settings.webhook_secret.get_secret_value(),
            allowed_updates=dp.resolve_used_update_types(),
            drop_pending_updates=False,  # entries typed during a restart are still recorded
        )
    else:
        await bot.delete_webhook(drop_pending_updates=True)
        app.state.polling_task = asyncio.create_task(dp.start_polling(bot, handle_signals=False))


async def stop_bot(app: FastAPI) -> None:
    task = getattr(app.state, "polling_task", None)
    if task is not None:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
    bot: Bot | None = getattr(app.state, "bot", None)
    if bot is not None:
        await bot.session.close()


@webhook_router.post("/tg/{path_token}", include_in_schema=False)
async def telegram_webhook(path_token: str, request: Request) -> Response:
    settings: Settings = request.app.state.settings
    bot: Bot | None = request.app.state.bot
    dp: Dispatcher | None = request.app.state.dp
    if (
        bot is None
        or dp is None
        or not hmac.compare_digest(path_token, settings.webhook_path_token.get_secret_value())
    ):
        return Response(status_code=404)
    secret = request.headers.get("x-telegram-bot-api-secret-token", "")
    if not hmac.compare_digest(secret, settings.webhook_secret.get_secret_value()):
        return Response(status_code=403)
    try:
        update = Update.model_validate(await request.json(), context={"bot": bot})
    except (ValidationError, ValueError):
        return Response(status_code=400)
    try:
        await dp.feed_update(bot, update)
    except Exception as exc:  # never make Telegram retry the same update forever
        log.error("update handling failed: %s", type(exc).__name__)
    return Response(status_code=200)
