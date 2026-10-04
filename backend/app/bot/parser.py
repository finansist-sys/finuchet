"""Parsing of quick entries typed in the chat.

Examples: "300 кофе", "кофе 300", "1.5к такси", "2 500,50 продукты", "+50000 зп",
"300 кофе нал", "20$ такси". The regex has no ambiguous nested repetition and
input is capped, so matching is linear (no ReDoS).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

from app.core.money import CURRENCY_ALIASES

MAX_INPUT = 200

_NUMBER = re.compile(
    r"(?<![\w.,])(?P<sign>[+\-−])?\s?"
    r"(?P<int>\d{1,3}(?:[   ]\d{3})+|\d{1,13})"
    r"(?:[.,](?P<frac>\d{1,3}))?"
    r"\s?(?P<mult>тыс\.?|к|k)?"
    r"(?P<cur>[₽$€₸₴₺₾֏¥£])?"
    r"(?![\w])",
    re.IGNORECASE,
)
_WORD = re.compile(r"[^\s]+")

CASH_WORDS = {"нал", "налом", "наличка", "наличкой", "наличные", "наличными", "кэш", "кеш", "cash"}
CARD_WORDS = {"карта", "картой", "карты", "карт", "безнал", "card"}
INCOME_WORDS = (
    "зп",
    "зарплат",
    "аванс",
    "доход",
    "премия",
    "премию",
    "кешбэк",
    "кэшбэк",
    "кешбек",
    "кэшбек",
    "возврат",
    "salary",
    "income",
    "bonus",
    "refund",
    "cashback",
)


@dataclass(slots=True)
class Entry:
    amount: Decimal
    income: bool
    currency: str | None
    account_type: str | None  # "cash" | "card" | None
    words: list[str]  # the rest of the text, original case


def parse(text: str) -> Entry | None:
    text = text.strip()[:MAX_INPUT]
    m = _NUMBER.search(text)
    if not m:
        return None

    digits = re.sub(r"\D", "", m.group("int"))
    value = Decimal(digits)
    if m.group("frac"):
        value += Decimal(m.group("frac")) / (Decimal(10) ** len(m.group("frac")))
    if m.group("mult"):
        value *= 1000
    if value <= 0 or value > Decimal(10) ** 13:
        return None

    currency = CURRENCY_ALIASES.get(m.group("cur") or "")
    income = m.group("sign") == "+"
    account_type: str | None = None
    words: list[str] = []

    rest = (text[: m.start()] + " " + text[m.end() :]).strip()
    for raw in _WORD.findall(rest):
        w = raw.lower().strip(".,!?;:()\"'«»")
        if not w:
            continue
        if currency is None and w in CURRENCY_ALIASES:
            currency = CURRENCY_ALIASES[w]
            continue
        if w in CASH_WORDS:
            account_type = "cash"
            continue
        if w in CARD_WORDS:
            account_type = "card"
            continue
        if not income and m.group("sign") is None and w.startswith(INCOME_WORDS):
            income = True
        words.append(raw.strip(".,!?;:\"'«»"))

    return Entry(
        amount=value,
        income=income,
        currency=currency,
        account_type=account_type,
        words=[w for w in words if w],
    )
