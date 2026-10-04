"""Logging that never writes personal data or secrets.

We log only what is needed to operate the service: method, route template,
status, timing and error types. A redaction filter is a second line of defence
in case a library logs something sensitive (initData, bot token, ids).
"""

from __future__ import annotations

import logging
import re
import sys

_REDACTIONS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?i)\btma\s+\S+"), "tma [REDACTED]"),
    (re.compile(r"\b\d{6,12}:[A-Za-z0-9_-]{30,}\b"), "[BOT_TOKEN]"),
    (re.compile(r"(?i)(hash|signature|query_id|auth_date|user)=[^&\s]+"), r"\1=[REDACTED]"),
    (re.compile(r"(?i)\"(id|user_id|chat_id|from_id)\"\s*:\s*-?\d+"), r'"\1": [ID]'),
    (re.compile(r"(?i)\b(chat_id|user_id|from_user_id|tg_id)=\s*-?\d+"), r"\1=[ID]"),
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}"), "[EMAIL]"),
]


def redact(text: str) -> str:
    for pattern, repl in _REDACTIONS:
        text = pattern.sub(repl, text)
    return text


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        record.msg = redact(message)
        record.args = None
        if record.exc_info and record.exc_info[1] is not None:
            # Keep the exception type, drop its message (may echo user input).
            exc_type = record.exc_info[0]
            record.msg = f"{record.msg} [{exc_type.__name__ if exc_type else 'Exception'}]"
            record.exc_info = None
            record.exc_text = None
        return True


def setup_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    handler.addFilter(RedactingFilter())
    handler._finuchet = True  # type: ignore[attr-defined]
    root = logging.getLogger()
    root.handlers[:] = [h for h in root.handlers if not getattr(h, "_finuchet", False)]
    root.addHandler(handler)
    root.setLevel(level)
    # uvicorn installs its own handlers (bypassing our filter) and logs full tracebacks of
    # unhandled errors, which may contain SQL parameters. Route everything through root.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        lg = logging.getLogger(name)
        lg.handlers.clear()
        lg.propagate = True
    # Libraries that may log request details: keep them quiet.
    for noisy in ("uvicorn.access", "aiogram.event", "httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
