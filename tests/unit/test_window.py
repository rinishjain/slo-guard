"""Unit tests for window/store.py — rolling window ring buffer."""
from datetime import datetime, timedelta, timezone

import pytest

from slo_guard.window.store import WindowSlot, WindowState, WindowStore

# ── helpers ───────────────────────────────────────────────────────────────────

def ts(offset_minutes: int = 0) -> datetime:
    """Return a timezone-aware UTC datetime at a fixed base + offset."""
    base = datetime(2026, 5, 15, 12, 0, 0, tzinfo=timezone.utc)
    return base + timedelta(minutes=offset_minutes)


def make_slot(offset_minutes: int, total: int, errors: int) -> WindowSlot:
    return WindowSlot(ts=ts(offset_minutes), total=total, errors=errors)


# ── WindowState ───────────────────────────────────────────────────────────────

class TestWindowState:

    def test_empty_window_returns_zeros(self):
        w = WindowState()
        total, errors = w.query(5, ts(0))
        assert total  == 0
        assert errors == 0

    def test_empty_window_error_rate_is_zero(self):
        w = WindowState()
        assert w.error_rate(5, ts(0)) == 0.0

    def test_single_slot_within_window(self):
        w = WindowState()
        w.add(make_slot(0, total=1000, errors=10))
        total, errors = w.query(5, ts(1))
        assert total  == 1000
        assert errors == 10

    def test_slot_outside_window_excluded(self):
        w = WindowState()
        w.add(make_slot(0, total=1000, errors=10))
        # Query a 5-minute window starting at t=10 — the slot at t=0 is outside
        total, errors = w.query(5, ts(10))
        assert total  == 0
        assert errors == 0

    def test_multiple_slots_summed_correctly(self):
        w = WindowState()
        w.add(make_slot(0,  total=1000, errors=5))
        w.add(make_slot(1,  total=2000, errors=15))
        w.add(make_slot(2,  total=500,  errors=2))
        total, errors = w.query(5, ts(3))
        assert total  == 3500
        assert errors == 22

    def test_eviction_discards_old_slots(self):
        w = WindowState()
        # Add a slot at t=0 and another 361 minutes later (> MAX 360)
        w.add(make_slot(0,   total=1000, errors=10))
        w.add(make_slot(361, total=500,  errors=5))
        # The slot at t=0 should be evicted
        assert len(w) == 1

    def test_eviction_boundary_exactly_max_window(self):
        w = WindowState()
        w.add(make_slot(0,   total=100, errors=1))
        w.add(make_slot(360, total=200, errors=2))
        # Slot at t=0 is exactly at the 360-minute boundary — should be evicted
        assert len(w) == 1

    def test_error_rate_calculated_correctly(self):
        w = WindowState()
        w.add(make_slot(0, total=1000, errors=100))
        rate = w.error_rate(5, ts(1))
        assert abs(rate - 0.1) < 1e-9

    def test_slots_at_reference_ts_boundary_included(self):
        # A slot whose ts == reference_ts should be INCLUDED
        w = WindowState()
        w.add(make_slot(5, total=500, errors=25))
        total, errors = w.query(5, ts(5))
        assert total  == 500
        assert errors == 25

    def test_multiple_windows_independent(self):
        w = WindowState()
        for i in range(10):
            w.add(make_slot(i, total=100, errors=i))  # increasing errors

        # 5-minute window from t=10: slots at t=6..10 (but t=10 doesn't exist, t=5..9)
        total_5m, errors_5m = w.query(5, ts(10))
        # 60-minute window: all 10 slots
        total_1h, errors_1h = w.query(60, ts(10))
        assert total_5m  < total_1h
        assert errors_5m < errors_1h


# ── WindowStore ───────────────────────────────────────────────────────────────

class TestWindowStore:

    def test_unknown_key_returns_zero_error_rate(self):
        store = WindowStore()
        rate = store.error_rate("unknown_svc", "US", "availability", 5, ts(0))
        assert rate == 0.0

    def test_record_and_query(self):
        store = WindowStore()
        store.record("xyz_web", "HK", "availability", ts(0), total=1000, errors=50)
        rate = store.error_rate("xyz_web", "HK", "availability", 5, ts(1))
        assert abs(rate - 0.05) < 1e-9

    def test_different_services_are_independent(self):
        store = WindowStore()
        store.record("svc_a", "HK", "availability", ts(0), total=1000, errors=100)
        store.record("svc_b", "HK", "availability", ts(0), total=1000, errors=0)
        assert store.error_rate("svc_a", "HK", "availability", 5, ts(1)) > 0
        assert store.error_rate("svc_b", "HK", "availability", 5, ts(1)) == 0.0

    def test_different_regions_are_independent(self):
        store = WindowStore()
        store.record("xyz_web", "HK", "availability", ts(0), total=1000, errors=100)
        store.record("xyz_web", "SG", "availability", ts(0), total=1000, errors=0)
        assert store.error_rate("xyz_web", "HK", "availability", 5, ts(1)) > 0
        assert store.error_rate("xyz_web", "SG", "availability", 5, ts(1)) == 0.0

    def test_different_slos_are_independent(self):
        store = WindowStore()
        store.record("xyz_web", "HK", "availability", ts(0), total=1000, errors=100)
        store.record("xyz_web", "HK", "latency",      ts(0), total=1000, errors=0)
        assert store.error_rate("xyz_web", "HK", "availability", 5, ts(1)) > 0
        assert store.error_rate("xyz_web", "HK", "latency",      5, ts(1)) == 0.0

    def test_all_keys_returns_inserted_keys(self):
        store = WindowStore()
        store.record("svc_a", "HK", "availability", ts(0), total=100, errors=1)
        store.record("svc_b", "SG", "latency",      ts(0), total=100, errors=1)
        keys = store.all_keys()
        assert ("svc_a", "HK", "availability") in keys
        assert ("svc_b", "SG", "latency")      in keys
