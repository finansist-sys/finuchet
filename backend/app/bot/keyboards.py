"""Keyboards and compact callback data.

callback_data is limited to 64 bytes, so UUIDs are packed as 22-char base64url.
Callback data comes from the client and can be forged: handlers always re-check
that every referenced object belongs to the sender.
"""

from __future__ import annotations

import base64
import uuid

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    WebAppInfo,
)

from app.bot.texts import t
from app.db.models import Account, Category


def pack(u: uuid.UUID) -> str:
    return base64.urlsafe_b64encode(u.bytes).decode().rstrip("=")


def unpack(s: str) -> uuid.UUID | None:
    try:
        raw = base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))
        return uuid.UUID(bytes=raw) if len(raw) == 16 else None
    except (ValueError, TypeError):
        return None


def cb(action: str, *parts: uuid.UUID | str) -> str:
    packed = [pack(p) if isinstance(p, uuid.UUID) else p for p in parts]
    data = ":".join(["f", action, *packed])
    assert len(data.encode()) <= 64  # noqa: S101 - programming error guard
    return data


def main_keyboard(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=t(lang, "btn_expense")),
                KeyboardButton(text=t(lang, "btn_income")),
                KeyboardButton(text=t(lang, "btn_balance")),
            ]
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def open_app_keyboard(lang: str, url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=t(lang, "open_app"), web_app=WebAppInfo(url=url))]]
    )


def _grid(buttons: list[InlineKeyboardButton], per_row: int) -> list[list[InlineKeyboardButton]]:
    return [buttons[i : i + per_row] for i in range(0, len(buttons), per_row)]


def tx_card(lang: str, tx_id: uuid.UUID) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=t(lang, "btn_category"), callback_data=cb("c", tx_id)),
                InlineKeyboardButton(text=t(lang, "btn_account"), callback_data=cb("a", tx_id)),
                InlineKeyboardButton(text=t(lang, "btn_undo"), callback_data=cb("u", tx_id)),
            ]
        ]
    )


def tx_categories(lang: str, tx_id: uuid.UUID, cats: list[Category]) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(text=f"{c.emoji} {c.name}", callback_data=cb("sc", tx_id, c.id))
        for c in cats[:12]
    ]
    rows = _grid(buttons, 3)
    rows.append(
        [
            InlineKeyboardButton(text=t(lang, "btn_back"), callback_data=cb("b", tx_id)),
            InlineKeyboardButton(text=t(lang, "btn_undo"), callback_data=cb("u", tx_id)),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def tx_accounts(lang: str, tx_id: uuid.UUID, accounts: list[Account]) -> InlineKeyboardMarkup:
    buttons = [InlineKeyboardButton(text=a.name, callback_data=cb("sa", tx_id, a.id)) for a in accounts[:10]]
    rows = _grid(buttons, 2)
    rows.append([InlineKeyboardButton(text=t(lang, "btn_back"), callback_data=cb("b", tx_id))])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def new_entry_categories(kind: str, cats: list[Category]) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(text=f"{c.emoji} {c.name}", callback_data=cb("n", kind[0], c.id))
        for c in cats[:12]
    ]
    return InlineKeyboardMarkup(inline_keyboard=_grid(buttons, 3))


def delete_confirm(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=t(lang, "btn_delete_yes"), callback_data=cb("dy")),
                InlineKeyboardButton(text=t(lang, "btn_cancel"), callback_data=cb("dn")),
            ]
        ]
    )
