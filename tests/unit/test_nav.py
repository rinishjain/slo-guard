"""Unit tests for nav/checker.py — NAV freshness SLO."""
from datetime import datetime

from slo_guard.model.alert import AlertType, SLOType
from slo_guard.model.events import NAVPublish
from slo_guard.nav.checker import NAVChecker


def make_nav(ts_iso: str, status: str = "published", region: str = "HK") -> NAVPublish:
    return NAVPublish(
        ts=datetime.fromisoformat(ts_iso),
        fund="TEST_FUND",
        region=region,
        nav_date="2026-05-15",
        status=status,
    )


class TestNAVChecker:

    def setup_method(self):
        self.checker = NAVChecker()

    # ── published before cutoff — no alert ───────────────────────────────────

    def test_published_before_cutoff_no_alert(self):
        # 17:59:59 HKT = 09:59:59 UTC
        event = make_nav("2026-05-15T09:59:59+00:00")
        assert self.checker.evaluate(event) is None

    def test_published_exactly_at_cutoff_no_alert(self):
        # 18:00:00 HKT = 10:00:00 UTC
        event = make_nav("2026-05-15T10:00:00+00:00")
        assert self.checker.evaluate(event) is None

    # ── published after cutoff — alert ───────────────────────────────────────

    def test_published_one_second_late_fires_alert(self):
        # 18:00:01 HKT = 10:00:01 UTC
        event = make_nav("2026-05-15T10:00:01+00:00")
        alert = self.checker.evaluate(event)
        assert alert is not None

    def test_published_well_after_cutoff_fires_alert(self):
        # 20:00 HKT = 12:00 UTC
        event = make_nav("2026-05-15T12:00:00+00:00")
        alert = self.checker.evaluate(event)
        assert alert is not None

    def test_alert_has_nav_freshness_slo(self):
        event = make_nav("2026-05-15T12:00:00+00:00")
        alert = self.checker.evaluate(event)
        assert alert.slo == SLOType.NAV_FRESHNESS

    def test_alert_type_is_ticket(self):
        event = make_nav("2026-05-15T12:00:00+00:00")
        alert = self.checker.evaluate(event)
        assert alert.alert_type == AlertType.TICKET

    def test_alert_severity_is_sev3(self):
        event = make_nav("2026-05-15T12:00:00+00:00")
        alert = self.checker.evaluate(event)
        assert alert.severity.value == "sev3"

    def test_alert_service_is_fund_name(self):
        event = make_nav("2026-05-15T12:00:00+00:00")
        alert = self.checker.evaluate(event)
        assert alert.service == "TEST_FUND"

    def test_alert_contains_nav_date_in_summary(self):
        event = make_nav("2026-05-15T12:00:00+00:00")
        alert = self.checker.evaluate(event)
        assert "2026-05-15" in alert.summary

    # ── non-published status ──────────────────────────────────────────────────

    def test_non_published_status_ignored(self):
        # Even if it's late, a "pending" event should not alert
        event = make_nav("2026-05-15T12:00:00+00:00", status="pending")
        assert self.checker.evaluate(event) is None

    def test_failed_status_ignored(self):
        event = make_nav("2026-05-15T12:00:00+00:00", status="failed")
        assert self.checker.evaluate(event) is None

    # ── unknown region ────────────────────────────────────────────────────────

    def test_unknown_region_returns_none(self):
        event = make_nav("2026-05-15T12:00:00+00:00", region="XX")
        assert self.checker.evaluate(event) is None

    # ── timezone correctness ──────────────────────────────────────────────────

    def test_sg_timezone_cutoff_correct(self):
        # SGT = UTC+8, same as HKT
        # 17:59 SGT = 09:59 UTC → no alert
        event = make_nav("2026-05-15T09:59:00+00:00", region="SG")
        assert self.checker.evaluate(event) is None

    def test_in_timezone_cutoff_correct(self):
        # IST = UTC+5:30
        # 18:00 IST = 12:30 UTC
        # Published at 12:29 UTC = 17:59 IST → no alert
        event = make_nav("2026-05-15T12:29:00+00:00", region="IN")
        assert self.checker.evaluate(event) is None

    def test_in_timezone_late_fires_alert(self):
        # Published at 12:31 UTC = 18:01 IST → alert
        event = make_nav("2026-05-15T12:31:00+00:00", region="IN")
        assert self.checker.evaluate(event) is not None

    def test_event_with_offset_ts_handled_correctly(self):
        # Timestamp supplied in HKT directly (UTC+8)
        # 18:01 HKT supplied as offset-aware → should fire
        event = make_nav("2026-05-15T18:01:00+08:00")
        assert self.checker.evaluate(event) is not None

    def test_event_just_before_cutoff_with_offset_ts(self):
        # 17:59 HKT → no alert
        event = make_nav("2026-05-15T17:59:00+08:00")
        assert self.checker.evaluate(event) is None
