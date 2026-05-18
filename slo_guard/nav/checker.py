"""
NAV freshness checker for slo-guard.

Alerts if a fund's NAV is published after 18:00 local time for its region.
"""
from __future__ import annotations

from datetime import time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from slo_guard.model.alert import Alert, AlertType, Severity, SLOType
from slo_guard.model.events import NAVPublish
from slo_guard.router.rules import route

# ── Region → timezone mapping ─────────────────────────────────────────────────

REGION_TIMEZONES: dict[str, str] = {
    "HK":  "Asia/Hong_Kong",
    "SG":  "Asia/Singapore",
    "JP":  "Asia/Tokyo",
    "AU":  "Australia/Sydney",
    "IN":  "Asia/Kolkata",
    "UK":  "Europe/London",
    "EU":  "Europe/Paris",
    "US":  "America/New_York",
}

NAV_CUTOFF = time(18, 0, 0)   # 18:00:00 local time


class NAVChecker:
    """
    Evaluates NAV freshness SLO for each nav_publish event.

    Yields an Alert if the event's local publish time exceeds the 18:00 cutoff.
    Only events with status == "published" are evaluated.
    """

    def evaluate(self, event: NAVPublish) -> Alert | None:
        if event.status != "published":
            return None

        tz_name = REGION_TIMEZONES.get(event.region.upper())
        if tz_name is None:
            # Unknown region — cannot determine local time; skip safely
            return None

        try:
            tz = ZoneInfo(tz_name)
        except ZoneInfoNotFoundError:
            return None

        local_ts = event.ts.astimezone(tz)
        local_time = local_ts.time()

        if local_time > NAV_CUTOFF:
            return self._make_alert(event)

        return None

    def _make_alert(self, event: NAVPublish) -> Alert:
        return Alert(
            alert_type=AlertType.TICKET,
            slo=SLOType.NAV_FRESHNESS,
            service=event.fund,
            region=event.region,
            window_pair="nav_cutoff",
            start=event.ts,
            end=event.ts,
            severity=Severity.SEV3,
            routing=route(event.fund, AlertType.TICKET),
            summary=(
                f"NAV for fund {event.fund} in {event.region} "
                f"published after 18:00 local time on {event.nav_date}"
            ),
        )
