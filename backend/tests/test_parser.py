import time
from decimal import Decimal

import pytest

from app.bot.keywords import icon_for
from app.bot.parser import parse

CASES = [
    # text, amount, income, currency, account_type, words
    ("300 кофе", "300", False, None, None, ["кофе"]),
    ("кофе 300", "300", False, None, None, ["кофе"]),
    ("Кофе 300", "300", False, None, None, ["Кофе"]),
    ("1.5к такси", "1500", False, None, None, ["такси"]),
    ("1,5к такси", "1500", False, None, None, ["такси"]),
    ("2к продукты", "2000", False, None, None, ["продукты"]),
    ("2 тыс продукты", "2000", False, None, None, ["продукты"]),
    ("2 500,50 продукты", "2500.50", False, None, None, ["продукты"]),
    ("2 500 продукты", "2500", False, None, None, ["продукты"]),
    ("12 345 678 машина", "12345678", False, None, None, ["машина"]),
    ("99.99 подписка", "99.99", False, None, None, ["подписка"]),
    ("+50000 зп", "50000", True, None, None, ["зп"]),
    ("зп 50000", "50000", True, None, None, ["зп"]),
    ("зарплата 85000", "85000", True, None, None, ["зарплата"]),
    ("аванс 30000 карта", "30000", True, None, "card", ["аванс"]),
    ("кэшбэк 450", "450", True, None, None, ["кэшбэк"]),
    ("-300 кофе", "300", False, None, None, ["кофе"]),
    ("300 кофе нал", "300", False, None, "cash", ["кофе"]),
    ("нал 300 кофе", "300", False, None, "cash", ["кофе"]),
    ("300 кофе наличными", "300", False, None, "cash", ["кофе"]),
    ("300 кофе картой", "300", False, None, "card", ["кофе"]),
    ("20$ такси", "20", False, "USD", None, ["такси"]),
    ("20 $ такси", "20", False, "USD", None, ["такси"]),
    ("20 usd такси", "20", False, "USD", None, ["такси"]),
    ("15€ музей", "15", False, "EUR", None, ["музей"]),
    ("15 евро музей", "15", False, "EUR", None, ["музей"]),
    ("500₽ обед", "500", False, "RUB", None, ["обед"]),
    ("500 руб обед", "500", False, "RUB", None, ["обед"]),
    ("1000 тенге обед", "1000", False, "KZT", None, ["обед"]),
    ("300", "300", False, None, None, []),
    ("300 кофе с Машей", "300", False, None, None, ["кофе", "с", "Машей"]),
    ("обед в столовой 450", "450", False, None, None, ["обед", "в", "столовой"]),
    ("300 coffee", "300", False, None, None, ["coffee"]),
    ("+2000 salary card", "2000", True, None, "card", ["salary"]),
    ("12.5k rent", "12500", False, None, None, ["rent"]),
    ("taxi 15 usd cash", "15", False, "USD", "cash", ["taxi"]),
    ("кофе, 300!", "300", False, None, None, ["кофе"]),
    ("такси 0.5к", "500", False, None, None, ["такси"]),
]


@pytest.mark.parametrize(("text", "amount", "income", "currency", "acc", "words"), CASES)
def test_parse_cases(text, amount, income, currency, acc, words):
    e = parse(text)
    assert e is not None, text
    assert e.amount == Decimal(amount)
    assert e.income is income
    assert e.currency == currency
    assert e.account_type == acc
    assert e.words == words


@pytest.mark.parametrize("text", ["", "кофе", "привет как дела", "0 кофе", "/start", "абв123где", "😀"])
def test_parse_rejects(text):
    assert parse(text) is None


def test_parse_is_fast_on_hostile_input():
    hostile = ["1 " * 200, "1" * 5000, " 1,1," * 300, "+" * 1000 + "1", "1 000 " * 400 + "x"]
    start = time.perf_counter()
    for h in hostile:
        parse(h)
    assert time.perf_counter() - start < 0.2


@pytest.mark.parametrize(
    ("words", "icon"),
    [
        (["кофе"], "coffee"),
        (["Пятерочка"], "cart"),
        (["такси"], "bus"),
        (["аренда"], "home"),
        (["аптека"], "heart"),
        (["кино"], "film"),
        (["зп"], "briefcase"),
        (["что-то"], None),
    ],
)
def test_keyword_icons(words, icon):
    assert icon_for(words) == icon
