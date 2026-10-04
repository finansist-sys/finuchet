"""Cleaning of user-provided text (account/category names, notes)."""

from __future__ import annotations

import re
import unicodedata

# Bidi overrides/isolates and zero-width characters used for spoofing (Trojan Source, CVE-2021-42574).
_INVISIBLE = re.compile("[​-‏‪-‮⁠-⁩﻿]")
_DIGITS_ONLY = re.compile(r"\D")
_CARD_CANDIDATE = re.compile(r"(?:\d[ \-]?){12,19}")


def clean_text(value: str, max_len: int) -> str:
    """NFKC-normalise, drop control/invisible characters, collapse whitespace, trim."""
    value = unicodedata.normalize("NFKC", value)
    value = _INVISIBLE.sub("", value)
    value = "".join(ch for ch in value if unicodedata.category(ch)[0] != "C" or ch == " ")
    value = re.sub(r"\s+", " ", value).strip()
    return value[:max_len]


def _luhn_ok(number: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(number)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def contains_card_number(value: str) -> bool:
    """True if the text looks like it contains a payment card number (PAN)."""
    for match in _CARD_CANDIDATE.finditer(value):
        digits = _DIGITS_ONLY.sub("", match.group())
        if 12 <= len(digits) <= 19 and _luhn_ok(digits):
            return True
    return False
