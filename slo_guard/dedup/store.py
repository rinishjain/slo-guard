"""
Alert deduplication for slo-guard.

Suppresses repeated alerts for the same (alert_type, slo, service, region)
combination for 30 minutes after the first emission.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from slo_guard.model.alert import Alert

SUPPRESSION_WINDOW = timedelta(minutes=20)


class DeduplicationStore:
    """
    In-memory dedup store keyed by Alert.dedupe_key.

    Thread-safety: NOT thread-safe. Single-threaded use only.
    """

    def __init__(self, suppression_window: timedelta = SUPPRESSION_WINDOW) -> None:
        self._suppression_window = suppression_window
        # Maps dedupe_key -> expiry datetime (wall clock, UTC)
        self._expiry: dict[str, datetime] = {}

    def is_suppressed(self, alert: Alert, now: datetime) -> bool:
        """
        Return True if this alert should be suppressed.

        An alert is suppressed if its dedupe_key was seen within the last
        SUPPRESSION_WINDOW.
        """
        key = alert.dedupe_key
        expiry = self._expiry.get(key)
        if expiry is None:
            return False
        return now < expiry

    def record(self, alert: Alert, now: datetime) -> None:
        """
        Record that an alert was emitted at `now`.

        Sets the suppression expiry to now + SUPPRESSION_WINDOW.
        """
        self._expiry[alert.dedupe_key] = now + self._suppression_window

    def should_emit(self, alert: Alert, now: datetime) -> bool:
        """
        Convenience: returns True and records the alert if it should be emitted,
        returns False (and does NOT record) if it should be suppressed.
        """
        if self.is_suppressed(alert, now):
            return False
        self.record(alert, now)
        return True

    def clear(self) -> None:
        """Reset all state (useful in tests)."""
        self._expiry.clear()

    @property
    def active_keys(self) -> list[str]:
        """Return all currently tracked dedupe keys (for debugging/testing)."""
        return list(self._expiry.keys())
