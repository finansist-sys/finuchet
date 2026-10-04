"""Request/response models. Requests reject unknown fields (no mass assignment)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.money import MAX_AMOUNT
from app.db.models import Account, Category, Transaction

Amount = Field(gt=0, le=MAX_AMOUNT)
Balance = Field(ge=-MAX_AMOUNT, le=MAX_AMOUNT)


class In(BaseModel):
    model_config = ConfigDict(extra="forbid", str_max_length=200)


# ---------------------------------------------------------------- requests


class StartAccountIn(In):
    type: Literal["card", "cash"]
    name: str = Field(min_length=1, max_length=40)
    currency: str = Field(min_length=3, max_length=3)
    balance: int = Balance


class OnboardingIn(In):
    base_currency: str = Field(min_length=3, max_length=3)
    tz: str = Field(default="UTC", max_length=64)
    accounts: list[StartAccountIn] = Field(min_length=1, max_length=10)


class SettingsIn(In):
    base_currency: str | None = Field(default=None, min_length=3, max_length=3)
    tz: str | None = Field(default=None, max_length=64)
    default_account_id: uuid.UUID | None = None


class AccountIn(In):
    type: Literal["card", "cash"]
    name: str = Field(min_length=1, max_length=40)
    currency: str = Field(min_length=3, max_length=3)
    balance: int = Balance


class AccountPatch(In):
    name: str | None = Field(default=None, min_length=1, max_length=40)
    archived: bool | None = None


class ReconcileIn(In):
    balance: int = Balance


class CategoryIn(In):
    name: str = Field(min_length=1, max_length=32)
    kind: Literal["expense", "income"]
    icon: str = Field(default="dots", max_length=24)
    emoji: str = Field(default="•", max_length=8)
    color: int = Field(default=-1, ge=-1, le=7)


class CategoryPatch(In):
    name: str | None = Field(default=None, min_length=1, max_length=32)
    icon: str | None = Field(default=None, max_length=24)
    emoji: str | None = Field(default=None, max_length=8)
    color: int | None = Field(default=None, ge=-1, le=7)
    archived: bool | None = None


class TransactionIn(In):
    kind: Literal["expense", "income", "transfer"]
    account_id: uuid.UUID
    amount: int = Amount
    to_account_id: uuid.UUID | None = None
    to_amount: int | None = Field(default=None, gt=0, le=MAX_AMOUNT)
    category_id: uuid.UUID | None = None
    note: str | None = Field(default=None, max_length=140)
    occurred_at: datetime | None = None


# ---------------------------------------------------------------- responses


def account_out(a: Account) -> dict:
    return {
        "id": str(a.id),
        "name": a.name,
        "type": a.type,
        "currency": a.currency,
        "balance": a.balance,
        "archived": a.archived,
    }


def category_out(c: Category) -> dict:
    return {
        "id": str(c.id),
        "name": c.name,
        "kind": c.kind,
        "icon": c.icon,
        "emoji": c.emoji,
        "color": c.color,
        "archived": c.archived,
    }


def tx_out(t: Transaction) -> dict:
    return {
        "id": str(t.id),
        "kind": t.kind,
        "account_id": str(t.account_id),
        "to_account_id": str(t.to_account_id) if t.to_account_id else None,
        "amount": t.amount,
        "to_amount": t.to_amount,
        "category_id": str(t.category_id) if t.category_id else None,
        "note": t.note,
        "source": t.source,
        "occurred_at": as_utc(t.occurred_at).isoformat(),
    }


def as_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)
