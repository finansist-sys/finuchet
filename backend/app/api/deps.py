"""Request dependencies: DB session, Telegram authentication, current user."""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db.models import User
from app.db.session import app_sessionmaker
from app.security.identity import tg_hash
from app.security.ratelimit import RateLimiter
from app.security.telegram_auth import InitDataError, TelegramIdentity, validate_init_data
from app.services.users import find_user, lang_of


def settings_of(request: Request) -> Settings:
    return request.app.state.settings


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    maker = await app_sessionmaker(request.app)
    async with maker() as session:
        yield session


@dataclass(frozen=True, slots=True)
class Auth:
    tg_hash: bytes
    lang: str
    auth_date: int


def authenticate(request: Request, authorization: Annotated[str | None, Header()] = None) -> Auth:
    settings: Settings = request.app.state.settings
    if not authorization or not authorization.startswith("tma "):
        raise HTTPException(401, "unauthorized")
    raw = authorization[4:].strip()

    identity: TelegramIdentity
    if settings.env == "dev" and settings.dev_fake_tg_id and raw == "dev":
        identity = TelegramIdentity(settings.dev_fake_tg_id, "ru", int(time.time()))
    else:
        try:
            identity = validate_init_data(
                raw, settings.bot_token.get_secret_value(), settings.init_data_ttl_seconds
            )
        except InitDataError:
            raise HTTPException(401, "unauthorized") from None

    h = tg_hash(identity.tg_id, settings.id_pepper.get_secret_value())
    limiter: RateLimiter = request.app.state.api_limiter
    if not limiter.allow(h):
        raise HTTPException(429, "too_many_requests")
    return Auth(tg_hash=h, lang=lang_of(identity.language_code), auth_date=identity.auth_date)


AuthDep = Annotated[Auth, Depends(authenticate)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def current_user(auth: AuthDep, session: SessionDep) -> User:
    user = await find_user(session, auth.tg_hash)
    if user is None:
        raise HTTPException(409, "onboarding_required")
    return user


UserDep = Annotated[User, Depends(current_user)]


def require_fresh(auth: Auth, settings: Settings) -> None:
    """Destructive actions need initData signed within the last few minutes."""
    if time.time() - auth.auth_date > settings.destructive_ttl_seconds:
        raise HTTPException(401, "reauth_required")
