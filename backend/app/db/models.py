"""Database schema.

Privacy: no Telegram id, name, username, e-mail or phone is stored anywhere.
A user is identified only by tg_hash = HMAC(pepper, telegram_id).
Amounts are integers in the account currency's minor units.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    SmallInteger,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tg_hash: Mapped[bytes] = mapped_column(LargeBinary(32), unique=True, nullable=False)
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    tz: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
    lang: Mapped[str] = mapped_column(String(2), nullable=False, default="ru")
    default_account_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    last_active_date: Mapped[date | None] = mapped_column(Date, nullable=True)


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = (
        CheckConstraint("type IN ('card', 'cash')", name="ck_account_type"),
        Index("ix_accounts_user", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(40), nullable=False)
    type: Mapped[str] = mapped_column(String(8), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    balance: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    sort: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    archived: Mapped[bool] = mapped_column(default=False, nullable=False)


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (
        CheckConstraint("kind IN ('expense', 'income')", name="ck_category_kind"),
        Index("ix_categories_user", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(32), nullable=False)
    kind: Mapped[str] = mapped_column(String(8), nullable=False)
    icon: Mapped[str] = mapped_column(String(24), nullable=False, default="dots")
    emoji: Mapped[str] = mapped_column(String(8), nullable=False, default="•")
    color: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=-1
    )  # palette slot 0..7, -1 = grey
    sort: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    archived: Mapped[bool] = mapped_column(default=False, nullable=False)


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint("kind IN ('expense', 'income', 'transfer', 'adjustment')", name="ck_tx_kind"),
        CheckConstraint("amount > 0 OR (kind = 'adjustment' AND amount <> 0)", name="ck_tx_amount"),
        CheckConstraint("source IN ('bot', 'app')", name="ck_tx_source"),
        Index("ix_tx_user_time", "user_id", "occurred_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    kind: Mapped[str] = mapped_column(String(10), nullable=False)
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    to_account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), nullable=True
    )
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    to_amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"), nullable=True
    )
    note: Mapped[str | None] = mapped_column(String(140), nullable=True)
    source: Mapped[str] = mapped_column(String(3), nullable=False, default="app")
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class CategoryHint(Base):
    """Bot memory: which category a word was last filed under ("кофе" -> Кафе)."""

    __tablename__ = "category_hints"
    __table_args__ = (UniqueConstraint("user_id", "keyword", name="uq_hint_user_keyword"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    keyword: Mapped[str] = mapped_column(String(32), nullable=False)
    category_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("categories.id", ondelete="CASCADE"), nullable=False
    )
    hits: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
