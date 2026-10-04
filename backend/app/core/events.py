"""Tiny in-process domain event bus.

The ledger publishes events; future features (achievements, reminders, ...)
subscribe without touching the accounting core.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

log = logging.getLogger(__name__)

TRANSACTION_CREATED = "transaction_created"
TRANSACTION_DELETED = "transaction_deleted"
USER_ACTIVE = "user_active"


@dataclass(frozen=True, slots=True)
class Event:
    name: str
    user_id: UUID
    payload: dict[str, Any]


Handler = Callable[[Event], Awaitable[None]]
_handlers: dict[str, list[Handler]] = defaultdict(list)


def subscribe(name: str, handler: Handler) -> None:
    _handlers[name].append(handler)


async def publish(event: Event) -> None:
    for handler in list(_handlers.get(event.name, ())):
        try:
            await handler(event)
        except Exception:
            # A failing optional feature must never break accounting.
            log.exception("event handler failed for %s", event.name)
