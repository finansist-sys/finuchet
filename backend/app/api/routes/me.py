from __future__ import annotations

from fastapi import APIRouter, Request, Response

from app.api.deps import AuthDep, SessionDep, UserDep, require_fresh
from app.api.schemas import OnboardingIn, SettingsIn
from app.core.features import enabled_features
from app.core.money import CURRENCIES
from app.services import users

router = APIRouter(prefix="/api", tags=["me"])


def _me(user) -> dict:
    return {
        "onboarded": True,
        "base_currency": user.base_currency,
        "tz": user.tz,
        "lang": user.lang,
        "default_account_id": str(user.default_account_id) if user.default_account_id else None,
        "features": enabled_features(),
    }


@router.get("/me")
async def get_me(auth: AuthDep, session: SessionDep) -> dict:
    # Never returns the Telegram id or anything derived from it.
    user = await users.find_user(session, auth.tg_hash)
    if user is None:
        return {"onboarded": False, "lang": auth.lang, "features": enabled_features()}
    return _me(user)


@router.get("/currencies")
async def currencies() -> list[dict]:
    return [{"code": c, "symbol": s, "exponent": e} for c, (e, s) in CURRENCIES.items()]


@router.post("/onboarding", status_code=201)
async def onboarding(body: OnboardingIn, auth: AuthDep, session: SessionDep) -> dict:
    user = await users.onboard(
        session,
        auth.tg_hash,
        base_currency=body.base_currency,
        tz=body.tz,
        lang=auth.lang,
        accounts=[users.StartAccount(a.type, a.name, a.currency, a.balance) for a in body.accounts],
    )
    return _me(user)


@router.patch("/me")
async def patch_me(body: SettingsIn, user: UserDep, session: SessionDep) -> dict:
    await users.update_settings(
        session,
        user,
        base_currency=body.base_currency,
        tz=body.tz,
        default_account_id=body.default_account_id,
    )
    return _me(user)


@router.delete("/me", status_code=204)
async def delete_me(request: Request, auth: AuthDep, user: UserDep, session: SessionDep) -> Response:
    require_fresh(auth, request.app.state.settings)
    await users.delete_user(session, user)
    return Response(status_code=204)
