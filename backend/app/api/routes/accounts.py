from __future__ import annotations

import uuid

from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import SessionDep, UserDep
from app.api.schemas import (
    AccountIn,
    AccountPatch,
    CategoryIn,
    CategoryPatch,
    ReconcileIn,
    account_out,
    category_out,
    tx_out,
)
from app.db.models import Account, Category
from app.services import ledger

router = APIRouter(prefix="/api", tags=["accounts"])


@router.get("/accounts")
async def list_accounts(user: UserDep, session: SessionDep) -> list[dict]:
    rows = await session.scalars(select(Account).where(Account.user_id == user.id).order_by(Account.sort))
    return [account_out(a) for a in rows]


@router.post("/accounts", status_code=201)
async def create_account(body: AccountIn, user: UserDep, session: SessionDep) -> dict:
    acc = await ledger.create_account(session, user, body.name, body.type, body.currency, body.balance)
    return account_out(acc)


@router.patch("/accounts/{account_id}")
async def patch_account(
    account_id: uuid.UUID, body: AccountPatch, user: UserDep, session: SessionDep
) -> dict:
    acc = await ledger.update_account(session, user, account_id, name=body.name, archived=body.archived)
    return account_out(acc)


@router.post("/accounts/{account_id}/reconcile")
async def reconcile(account_id: uuid.UUID, body: ReconcileIn, user: UserDep, session: SessionDep) -> dict:
    tx = await ledger.reconcile(session, user, account_id, body.balance)
    acc = await ledger.get_account(session, user.id, account_id)
    return {"account": account_out(acc), "adjustment": tx_out(tx) if tx else None}


@router.get("/categories")
async def list_categories(user: UserDep, session: SessionDep) -> list[dict]:
    rows = await session.scalars(select(Category).where(Category.user_id == user.id).order_by(Category.sort))
    return [category_out(c) for c in rows]


@router.post("/categories", status_code=201)
async def create_category(body: CategoryIn, user: UserDep, session: SessionDep) -> dict:
    cat = await ledger.create_category(
        session, user, name=body.name, kind=body.kind, icon=body.icon, emoji=body.emoji, color=body.color
    )
    return category_out(cat)


@router.patch("/categories/{category_id}")
async def patch_category(
    category_id: uuid.UUID, body: CategoryPatch, user: UserDep, session: SessionDep
) -> dict:
    cat = await ledger.update_category(session, user, category_id, **body.model_dump(exclude_none=True))
    return category_out(cat)
