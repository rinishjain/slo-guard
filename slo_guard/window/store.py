"""
Rolling window ring buffer for slo-guard.

Maintains per-(service, region) sliding windows of HTTP minute metrics.
Supports querying any sub-window up to the maximum retention period.
"""
from __future__ import annotations

from collections import deque
from datetime import datetime, timedelta
from typing import NamedTuple

# Maximum window we ever need is 6 hours
MAX_WINDOW_MINUTES = 360


class WindowSlot(NamedTuple):
    """One minute's worth of aggregated metrics."""
    ts:     datetime
    total:  int
    errors: int   # meaning depends on SLO (5xx count OR slow_requests count)


class WindowState:
    """
    Sliding window state for a single (service, region, slo) combination.

    Internally stores individual minute slots in a deque ordered oldest→newest.
    Eviction happens lazily on every insert: slots older than max_window_minutes
    are discarded before the new slot is appended.
    """

    def __init__(self, max_window_minutes: int = MAX_WINDOW_MINUTES) -> None:
        self._max_window_minutes = max_window_minutes
        self._slots: deque[WindowSlot] = deque()

    def add(self, slot: WindowSlot) -> None:
        """Append a new slot, evicting any data older than max_window_minutes."""
        cutoff = slot.ts - timedelta(minutes=self._max_window_minutes)
        while self._slots and self._slots[0].ts <= cutoff:
            self._slots.popleft()
        self._slots.append(slot)

    def query(self, minutes: int, reference_ts: datetime) -> tuple[int, int]:
        """
        Return (total_requests, total_errors) over the most recent `minutes`
        of data relative to `reference_ts`.

        Only slots with ts > (reference_ts - minutes) AND ts <= reference_ts
        are included.
        """
        cutoff = reference_ts - timedelta(minutes=minutes)
        total  = 0
        errors = 0
        for slot in self._slots:
            if slot.ts <= cutoff:
                continue
            if slot.ts > reference_ts:
                break
            total  += slot.total
            errors += slot.errors
        return total, errors

    def error_rate(self, minutes: int, reference_ts: datetime) -> float:
        """Return the observed error rate over the window, or 0.0 if no data."""
        total, errors = self.query(minutes, reference_ts)
        if total == 0:
            return 0.0
        return errors / total

    def __len__(self) -> int:
        return len(self._slots)


class WindowStore:
    """
    Collection of WindowState objects keyed by (service, region, slo_label).

    slo_label is a short string like "availability" or "latency" that
    determines which error counter is tracked.
    """

    def __init__(self, max_window_minutes: int = MAX_WINDOW_MINUTES) -> None:
        self._max_window_minutes = max_window_minutes
        self._store: dict[tuple[str, str, str], WindowState] = {}

    def _key(self, service: str, region: str, slo: str) -> tuple[str, str, str]:
        return (service, region, slo)

    def _get_or_create(self, service: str, region: str, slo: str) -> WindowState:
        key = self._key(service, region, slo)
        if key not in self._store:
            self._store[key] = WindowState(self._max_window_minutes)
        return self._store[key]

    def record(
        self,
        service: str,
        region:  str,
        slo:     str,
        ts:      datetime,
        total:   int,
        errors:  int,
    ) -> None:
        """Insert a new data point into the appropriate window."""
        state = self._get_or_create(service, region, slo)
        state.add(WindowSlot(ts=ts, total=total, errors=errors))

    def error_rate(
        self,
        service:      str,
        region:       str,
        slo:          str,
        minutes:      int,
        reference_ts: datetime,
    ) -> float:
        """Return the error rate for a given window width."""
        key = self._key(service, region, slo)
        if key not in self._store:
            return 0.0
        return self._store[key].error_rate(minutes, reference_ts)

    def all_keys(self) -> list[tuple[str, str, str]]:
        return list(self._store.keys())
