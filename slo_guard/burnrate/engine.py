"""
Burn-rate alerting engine for slo-guard.

burn_rate = observed_error_rate / (1 - SLO_target)

Alert tiers:
  PAGE   — 5m burn rate > 14  AND  1h  burn rate > 6
  TICKET — 30m burn rate > 3  AND  6h  burn rate > 1
"""
from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from slo_guard.model.alert import Alert, AlertType, Severity, SLOType
from slo_guard.model.events import HTTPMinute
from slo_guard.router.rules import route
from slo_guard.window.store import WindowStore

# ── SLO targets ─────────────────────────────────────────────────────────────

SLO_AVAILABILITY = 0.999   # 99.9 %
SLO_LATENCY      = 0.999   # treat >500ms the same as 5xx for burn-rate math

# ── Alert thresholds ─────────────────────────────────────────────────────────

@dataclass(frozen=True)
class AlertRule:
    alert_type:    AlertType
    short_minutes: int
    short_threshold: float
    long_minutes:  int
    long_threshold: float
    window_pair:   str


RULES: list[AlertRule] = [
    AlertRule(
        alert_type=AlertType.PAGE,
        short_minutes=5,  short_threshold=14.0,
        long_minutes=60,  long_threshold=6.0,
        window_pair="5m+1h",
    ),
    AlertRule(
        alert_type=AlertType.TICKET,
        short_minutes=30, short_threshold=3.0,
        long_minutes=360, long_threshold=1.0,
        window_pair="30m+6h",
    ),
]


# ── Burn-rate calculation ────────────────────────────────────────────────────

def burn_rate(observed_error_rate: float, slo_target: float) -> float:
    """
    Calculate burn rate.

    A burn rate of 1.0 means the budget is being consumed at exactly the
    rate that will exhaust it over the SLO window. > 1.0 means faster.
    """
    budget = 1.0 - slo_target
    if budget <= 0:
        return 0.0
    return observed_error_rate / budget


# ── Engine ───────────────────────────────────────────────────────────────────

class BurnRateEngine:
    """
    Evaluates burn-rate alert rules against a WindowStore.

    Called once per HTTPMinute event; yields zero or more Alert objects
    for any rules that are currently breaching.
    """

    def __init__(self, store: WindowStore) -> None:
        self._store = store

    def evaluate(
        self,
        event: HTTPMinute,
    ) -> Iterator[Alert]:
        """
        Ingest one HTTPMinute event and yield any alerts that should fire.

        Evaluates all (SLO × rule) combinations for the event's
        (service, region).
        """
        # Record the new data point for both SLOs
        self._store.record(
            service=event.service,
            region=event.region,
            slo="availability",
            ts=event.ts,
            total=event.total,
            errors=event.http_5xx,
        )
        self._store.record(
            service=event.service,
            region=event.region,
            slo="latency",
            ts=event.ts,
            total=event.total,
            errors=event.slow_requests,
        )

        for slo_label, slo_target, slo_type in [
            ("availability", SLO_AVAILABILITY, SLOType.AVAILABILITY),
            ("latency",      SLO_LATENCY,      SLOType.LATENCY),
        ]:
            for rule in RULES:
                short_rate = self._store.error_rate(
                    event.service, event.region, slo_label,
                    rule.short_minutes, event.ts,
                )
                long_rate = self._store.error_rate(
                    event.service, event.region, slo_label,
                    rule.long_minutes, event.ts,
                )

                short_br = burn_rate(short_rate, slo_target)
                long_br  = burn_rate(long_rate,  slo_target)

                if short_br > rule.short_threshold and long_br > rule.long_threshold:
                    yield self._make_alert(event, rule, slo_type)

    def _make_alert(
        self,
        event: HTTPMinute,
        rule:  AlertRule,
        slo:   SLOType,
    ) -> Alert:
        start_ts = event.ts
        end_ts   = event.ts

        return Alert(
            alert_type=rule.alert_type,
            slo=slo,
            service=event.service,
            region=event.region,
            window_pair=rule.window_pair,
            start=start_ts,
            end=end_ts,
            severity=Severity.for_alert_type(rule.alert_type),
            routing=route(event.service, rule.alert_type),
            summary=(
                f"High error rate causing {slo.value} burn-rate breach "
                f"for {event.service} in {event.region}"
            ),
        )
