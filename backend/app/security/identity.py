"""Pseudonymous user identity.

The Telegram user id is never stored. We keep only HMAC-SHA256(ID_PEPPER, tg_id).
The pepper lives in the environment, separately from the database and its backups,
so a leaked database cannot be mapped back to Telegram accounts.
"""

from __future__ import annotations

import hashlib
import hmac


def tg_hash(tg_id: int, pepper: str) -> bytes:
    if tg_id <= 0:
        raise ValueError("invalid telegram id")
    return hmac.new(pepper.encode(), f"tg:{tg_id}".encode(), hashlib.sha256).digest()
