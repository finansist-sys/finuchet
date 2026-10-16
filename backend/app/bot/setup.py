"""Bot lifecycle and the Telegram webhook endpoint.

- webhook / polling (own server): one long-lived Bot, configured at startup (lifespan).
- serverless (Vercel): nothing lives between invocations — the dispatcher is built lazily, a Bot
  client is opened per webhook call, and Telegram is configured by `ensure_bot_setup`
  (triggered from GET /api/healthz after a deploy; idempotent).
"""

from __future__ import annotations

import asyncio
import contextlib
import hmac
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, MenuButtonWebApp, Update, WebAppInfo
from fastapi import APIRouter, FastAPI, Request, Response
from pydantic import ValidationError

from app.bot import handlers
from app.bot.middlewares import ContextMiddleware
from app.bot.storage import SqlStorage
from app.config import Settings
from app.db.session import app_sessionmaker
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


def new_bot(settings: Settings) -> Bot:
    return Bot(
        settings.bot_token.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML, link_preview_is_disabled=True),
    )


def build_dispatcher(app: FastAPI) -> Dispatcher:
    settings: Settings = app.state.settings

    async def get_maker():
        return await app_sessionmaker(app)

    dp = Dispatcher(storage=SqlStorage(get_maker, settings.id_pepper.get_secret_value()))
    mw = ContextMiddleware(settings, get_maker, RateLimiter(limit=20, window_seconds=10))
    dp.message.outer_middleware(mw)
    dp.callback_query.outer_middleware(mw)
    dp.include_router(handlers.router)
    return dp


def get_dispatcher(app: FastAPI) -> Dispatcher:
    dp = getattr(app.state, "dp", None)
    if dp is None:
        dp = app.state.dp = build_dispatcher(app)
    return dp


def webhook_url(settings: Settings) -> str:
    return f"{settings.public_url.rstrip('/')}/tg/{settings.webhook_path_token.get_secret_value()}"


async def configure_telegram(bot: Bot, settings: Settings, dp: Dispatcher) -> None:
    """Webhook + menu button + command list. Safe to call repeatedly."""
    await bot.set_webhook(
        url=webhook_url(settings),
        secret_token=settings.webhook_secret.get_secret_value(),
        allowed_updates=dp.resolve_used_update_types(),
        drop_pending_updates=False,  # entries typed during a restart/deploy are still recorded
    )
    url = handlers.app_url(settings)
    await bot.set_chat_menu_button(menu_button=MenuButtonWebApp(text="Финучёт", web_app=WebAppInfo(url=url)))
    for lang, cmds in COMMANDS.items():
        await bot.set_my_commands(
            [BotCommand(command=c, description=d) for c, d in cmds],
            language_code=None if lang == "ru" else lang,
        )


async def ensure_bot_setup(app: FastAPI) -> bool:
    """Serverless: configure Telegram if the webhook does not point here yet. Returns True if changed."""
    settings: Settings = app.state.settings
    if not settings.serverless or getattr(app.state, "telegram_checked", False):
        return False
    async with new_bot(settings) as bot:
        info = await bot.get_webhook_info()
        changed = info.url != webhook_url(settings)
        if changed:
            await configure_telegram(bot, settings, get_dispatcher(app))
    app.state.telegram_checked = True
    return changed


async def start_bot(app: FastAPI) -> None:
    settings: Settings = app.state.settings
    app.state.bot = None
    app.state.polling_task = None
    if settings.bot_mode in ("off", "serverless"):
        return

    bot = new_bot(settings)
    dp = get_dispatcher(app)
    app.state.bot = bot
    if settings.bot_mode == "webhook":
        await configure_telegram(bot, settings, dp)
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
    app: FastAPI = request.app
    settings: Settings = app.state.settings
    enabled = settings.bot_mode in ("webhook", "serverless") or getattr(app.state, "bot", None) is not None
    if not enabled or not hmac.compare_digest(path_token, settings.webhook_path_token.get_secret_value()):
        return Response(status_code=404)
    secret = request.headers.get("x-telegram-bot-api-secret-token", "")
    if not hmac.compare_digest(secret, settings.webhook_secret.get_secret_value()):
        return Response(status_code=403)
    try:
        payload = await request.json()
    except ValueError:
        return Response(status_code=400)

    dp = get_dispatcher(app)
    shared: Bot | None = getattr(app.state, "bot", None)
    bot = shared or new_bot(settings)
    try:
        try:
            update = Update.model_validate(payload, context={"bot": bot})
        except ValidationError:
            return Response(status_code=400)
        try:
            await dp.feed_update(bot, update)
        except Exception as exc:  # never make Telegram retry the same update forever
            log.error("update handling failed: %s", type(exc).__name__)
        return Response(status_code=200)
    finally:
        if shared is None:
            await bot.session.close()
