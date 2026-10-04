"""Validation of Telegram Mini App initData.

Algorithm: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
secret_key = HMAC_SHA256(key="WebAppData", msg=bot_token)
hash       = hex(HMAC_SHA256(key=secret_key, msg=data_check_string))
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode

MAX_INIT_DATA_LEN = 4096
CLOCK_SKEW_SECONDS = 60


class InitDataError(Exception):
    """initData is missing, malformed, forged or expired. Message is safe to log."""


@dataclass(frozen=True, slots=True)
class TelegramIdentity:
    tg_id: int
    language_code: str | None
    auth_date: int


def _secret_key(bot_token: str) -> bytes:
    return hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()


def sign_init_data(fields: dict[str, str], bot_token: str) -> str:
    """Build a signed initData string. Used by tests and the dev tooling only."""
    check = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    digest = hmac.new(_secret_key(bot_token), check.encode(), hashlib.sha256).hexdigest()
    return urlencode({**fields, "hash": digest})


def validate_init_data(
    init_data: str, bot_token: str, max_age_seconds: int, now: float | None = None
) -> TelegramIdentity:
    if not init_data or len(init_data) > MAX_INIT_DATA_LEN:
        raise InitDataError("initData missing or too long")

    pairs = parse_qsl(init_data, keep_blank_values=True, strict_parsing=False)
    fields: dict[str, str] = {}
    for key, value in pairs:
        if key in fields:
            raise InitDataError("duplicate initData field")
        fields[key] = value

    received_hash = fields.pop("hash", "")
    if not received_hash:
        raise InitDataError("initData hash missing")

    check = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    expected = hmac.new(_secret_key(bot_token), check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received_hash.lower()):
        raise InitDataError("initData signature mismatch")

    try:
        auth_date = int(fields.get("auth_date", ""))
    except ValueError as exc:
        raise InitDataError("initData auth_date invalid") from exc
    current = time.time() if now is None else now
    if auth_date > current + CLOCK_SKEW_SECONDS:
        raise InitDataError("initData auth_date in the future")
    if current - auth_date > max_age_seconds:
        raise InitDataError("initData expired")

    try:
        user = json.loads(fields.get("user", ""))
        tg_id = int(user["id"])
    except (ValueError, KeyError, TypeError) as exc:
        raise InitDataError("initData user missing") from exc
    if tg_id <= 0:
        raise InitDataError("initData user invalid")

    lang = user.get("language_code") if isinstance(user, dict) else None
    lang = lang if isinstance(lang, str) and len(lang) <= 10 else None
    # Name, username and photo are intentionally ignored and never stored.
    return TelegramIdentity(tg_id=tg_id, language_code=lang, auth_date=auth_date)
