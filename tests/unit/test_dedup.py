"""Unit tests for dedup/store.py — 30-minute alert suppression."""
from datetime import UTC, datetime, timedelta

from slo_guard.dedup.store import SUPPRESSION_WINDOW, DeduplicationStore
from slo_guard.model.alert import Alert, AlertType, Severity, SLOType

BASE_TS = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)


def make_alert(
    alert_type: AlertType = AlertType.PAGE,
    slo: SLOType = SLOType.AVAILABILITY,
    service: str = "xyz_web",
    region: str = "HK",
) -> Alert:
    return Alert(
        alert_type=alert_type,
        slo=slo,
        service=service,
        region=region,
        window_pair="5m+1h",
        start=BASE_TS,
        end=BASE_TS,
        severity=Severity.SEV2,
        routing=["oncall-sre"],
        summary="test alert",
    )


class TestDeduplicationStore:

    def setup_method(self):
        self.store = DeduplicationStore()

    # ── initial state ─────────────────────────────────────────────────────────

    def test_new_alert_not_suppressed(self):
        alert = make_alert()
        assert not self.store.is_suppressed(alert, BASE_TS)

    def test_should_emit_returns_true_for_new_alert(self):
        alert = make_alert()
        assert self.store.should_emit(alert, BASE_TS) is True

    # ── after recording ───────────────────────────────────────────────────────

    def test_recorded_alert_is_suppressed_immediately(self):
        alert = make_alert()
        self.store.record(alert, BASE_TS)
        assert self.store.is_suppressed(alert, BASE_TS) is True

    def test_suppressed_within_window(self):
        alert = make_alert()
        self.store.record(alert, BASE_TS)
        # 19 minutes later — still within 20-minute window
        later = BASE_TS + timedelta(minutes=19)
        assert self.store.is_suppressed(alert, later) is True

    def test_suppression_expires_after_window(self):
        alert = make_alert()
        self.store.record(alert, BASE_TS)
        # 20 minutes + 1 second later — suppression expired
        after = BASE_TS + timedelta(minutes=20, seconds=1)
        assert self.store.is_suppressed(alert, after) is False

    def test_suppression_expires_exactly_at_boundary(self):
        alert = make_alert()
        self.store.record(alert, BASE_TS)
        # Exactly at expiry time — should no longer be suppressed
        at_expiry = BASE_TS + SUPPRESSION_WINDOW
        assert self.store.is_suppressed(alert, at_expiry) is False

    def test_should_emit_suppresses_second_call(self):
        alert = make_alert()
        assert self.store.should_emit(alert, BASE_TS) is True
        # Second call within window → suppressed
        assert self.store.should_emit(alert, BASE_TS + timedelta(minutes=1)) is False

    def test_should_emit_re_emits_after_expiry(self):
        alert = make_alert()
        self.store.should_emit(alert, BASE_TS)
        after = BASE_TS + timedelta(minutes=31)
        assert self.store.should_emit(alert, after) is True

    # ── different dedupe keys ─────────────────────────────────────────────────

    def test_different_service_not_suppressed(self):
        alert_a = make_alert(service="svc_a")
        alert_b = make_alert(service="svc_b")
        self.store.record(alert_a, BASE_TS)
        assert not self.store.is_suppressed(alert_b, BASE_TS)

    def test_different_region_not_suppressed(self):
        alert_hk = make_alert(region="HK")
        alert_sg = make_alert(region="SG")
        self.store.record(alert_hk, BASE_TS)
        assert not self.store.is_suppressed(alert_sg, BASE_TS)

    def test_different_slo_not_suppressed(self):
        alert_avail   = make_alert(slo=SLOType.AVAILABILITY)
        alert_latency = make_alert(slo=SLOType.LATENCY)
        self.store.record(alert_avail, BASE_TS)
        assert not self.store.is_suppressed(alert_latency, BASE_TS)

    def test_different_alert_type_not_suppressed(self):
        alert_page   = make_alert(alert_type=AlertType.PAGE)
        alert_ticket = make_alert(alert_type=AlertType.TICKET)
        self.store.record(alert_page, BASE_TS)
        assert not self.store.is_suppressed(alert_ticket, BASE_TS)

    # ── state management ─────────────────────────────────────────────────────

    def test_clear_removes_all_state(self):
        alert = make_alert()
        self.store.record(alert, BASE_TS)
        self.store.clear()
        assert not self.store.is_suppressed(alert, BASE_TS)

    def test_active_keys_returns_tracked_keys(self):
        alert = make_alert()
        self.store.record(alert, BASE_TS)
        assert alert.dedupe_key in self.store.active_keys

    def test_suppression_window_duration(self):
        assert SUPPRESSION_WINDOW == timedelta(minutes=20)
