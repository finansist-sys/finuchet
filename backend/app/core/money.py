"""Currencies and amounts. Amounts are integers in minor units (kopecks, cents)."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

# ISO 4217 code -> (minor-unit exponent, symbol). Popular ones first.
CURRENCIES: dict[str, tuple[int, str]] = {
    "RUB": (2, "₽"),
    "USD": (2, "$"),
    "EUR": (2, "€"),
    "KZT": (2, "₸"),
    "BYN": (2, "Br"),
    "UAH": (2, "₴"),
    "AMD": (2, "֏"),
    "GEL": (2, "₾"),
    "UZS": (2, "сўм"),
    "KGS": (2, "сом"),
    "TJS": (2, "смн"),
    "AZN": (2, "₼"),
    "MDL": (2, "L"),
    "TRY": (2, "₺"),
    "AED": (2, "AED"),
    "CNY": (2, "¥"),
    "GBP": (2, "£"),
    "CHF": (2, "CHF"),
    "PLN": (2, "zł"),
    "CZK": (2, "Kč"),
    "SEK": (2, "kr"),
    "NOK": (2, "kr"),
    "DKK": (2, "kr"),
    "CAD": (2, "C$"),
    "AUD": (2, "A$"),
    "INR": (2, "₹"),
    "THB": (2, "฿"),
    "IDR": (2, "Rp"),
    "ILS": (2, "₪"),
    "RSD": (2, "дин"),
    "MNT": (2, "₮"),
    "HKD": (2, "HK$"),
    "SGD": (2, "S$"),
    "BRL": (2, "R$"),
    "MXN": (2, "MX$"),
    "JPY": (0, "¥"),
    "KRW": (0, "₩"),
    "VND": (0, "₫"),
    "KWD": (3, "KD"),
    "BHD": (3, "BD"),
}

# Absolute limit for a single amount or balance, in minor units.
MAX_AMOUNT = 10**15

# Symbols/words the bot recognises after a number ("20$", "300 руб").
CURRENCY_ALIASES: dict[str, str] = {
    "₽": "RUB",
    "р": "RUB",
    "р.": "RUB",
    "руб": "RUB",
    "руб.": "RUB",
    "rub": "RUB",
    "$": "USD",
    "usd": "USD",
    "долл": "USD",
    "доллар": "USD",
    "долларов": "USD",
    "€": "EUR",
    "eur": "EUR",
    "евро": "EUR",
    "₸": "KZT",
    "тенге": "KZT",
    "kzt": "KZT",
    "₴": "UAH",
    "грн": "UAH",
    "uah": "UAH",
    "byn": "BYN",
    "br": "BYN",
    "₺": "TRY",
    "лир": "TRY",
    "try": "TRY",
    "₾": "GEL",
    "лари": "GEL",
    "gel": "GEL",
    "֏": "AMD",
    "драм": "AMD",
    "amd": "AMD",
    "¥": "CNY",
    "юань": "CNY",
    "cny": "CNY",
    "£": "GBP",
    "gbp": "GBP",
}
for _code in CURRENCIES:
    CURRENCY_ALIASES.setdefault(_code.lower(), _code)


def is_currency(code: str) -> bool:
    return code in CURRENCIES


def exponent(code: str) -> int:
    return CURRENCIES[code][0]


def symbol(code: str) -> str:
    return CURRENCIES[code][1]


def to_minor(value: Decimal | str, code: str) -> int:
    """Convert a decimal amount to minor units, rounding half up."""
    try:
        d = Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("invalid amount") from exc
    q = Decimal(1).scaleb(-exponent(code))
    return int((d.quantize(q, rounding=ROUND_HALF_UP) * (10 ** exponent(code))).to_integral_value())


def format_amount(minor: int, code: str, *, signed: bool = False) -> str:
    """'148 320,50 ₽' style formatting for bot messages (thin no-break spaces)."""
    exp = exponent(code)
    sign = "−" if minor < 0 else ("+" if signed and minor > 0 else "")
    whole, frac = divmod(abs(minor), 10**exp) if exp else (abs(minor), 0)
    whole_s = f"{whole:,}".replace(",", " ")
    frac_s = f",{frac:0{exp}d}" if exp and frac else ""
    return f"{sign}{whole_s}{frac_s} {symbol(code)}"
