from __future__ import annotations

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Query, Response
from sqlalchemy import or_, select

from app.api.deps import SessionDep, UserDep
from app.api.schemas import TransactionIn, account_out, tx_out
from app.db.models import Account, Transaction
from app.services import ledger

router = APIRouter(prefix="/api", tags=["transactions"])


def _input(body: TransactionIn) -> ledger.TxInput:
    return ledger.TxInput(
        kind=body.kind,
        account_id=body.account_id,
        amount=body.amount,
        to_account_id=body.to_account_id,
        to_amount=body.to_amount,
        category_id=body.category_id,
        note=body.note,
        occurred_at=body.occurred_at,
    )


async def _touched_accounts(session, user, tx) -> list[dict]:
    ids = [tx.account_id] + ([tx.to_account_id] if tx.to_account_id else [])
    rows = await session.scalars(select(Account).where(Account.user_id == user.id, Account.id.in_(ids)))
    return [account_out(a) for a in rows]


@router.get("/transactions")
async def list_transactions(
    user: UserDep,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0, le=100_000)] = 0,
    kind: Literal["expense", "income", "transfer", "adjustment"] | None = None,
    account_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
) -> dict:
    q = select(Transaction).where(Transaction.user_id == user.id)
    if kind:
        q = q.where(Transaction.kind == kind)
    if account_id:
        q = q.where(or_(Transaction.account_id == account_id, Transaction.to_account_id == account_id))
    if category_id:
        q = q.where(Transaction.category_id == category_id)
    q = (
        q.order_by(Transaction.occurred_at.desc(), Transaction.created_at.desc())
        .offset(offset)
        .limit(limit + 1)
    )
    rows = list(await session.scalars(q))
    return {"items": [tx_out(t) for t in rows[:limit]], "has_more": len(rows) > limit}


@router.post("/transactions", status_code=201)
async def create_transaction(body: TransactionIn, user: UserDep, session: SessionDep) -> dict:
    tx = await ledger.create_transaction(session, user, _input(body))
    return {"transaction": tx_out(tx), "accounts": await _touched_accounts(session, user, tx)}


@router.patch("/transactions/{tx_id}")
async def update_transaction(
    tx_id: uuid.UUID, body: TransactionIn, user: UserDep, session: SessionDep
) -> dict:
    tx = await ledger.update_transaction(session, user, tx_id, _input(body))
    return {"transaction": tx_out(tx)}


@router.delete("/transactions/{tx_id}", status_code=204)
async def delete_transaction(tx_id: uuid.UUID, user: UserDep, session: SessionDep) -> Response:
    await ledger.delete_transaction(session, user, tx_id)
    return Response(status_code=204)
