"""Feature flags. Future sections are switched on here; the Mini App reads them from /api/me."""

from __future__ import annotations

from enum import StrEnum


class Feature(StrEnum):
    DONATIONS = "donations"
    GAME = "game"
    EXPORT = "export"
    REMINDERS = "reminders"
    ADS = "ads"
    ACADEMY = "academy"
    PAYMENTS = "payments"


# Stage 1: only accounting. Nothing optional is enabled yet.
ENABLED: frozenset[Feature] = frozenset()


def enabled_features() -> list[str]:
    return sorted(f.value for f in ENABLED)
