"""
Alert output model for slo-guard.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class AlertType(str, Enum):
    PAGE   = "page"
    TICKET = "ticket"


class SLOType(str, Enum):
    AVAILABILITY  = "availability"
    LATENCY       = "latency"
    NAV_FRESHNESS = "nav_freshness"


class Severity(str, Enum):
    SEV1 = "sev1"
    SEV2 = "sev2"
    SEV3 = "sev3"

    @classmethod
    def for_alert_type(cls, alert_type: AlertType) -> "Severity":
        return cls.SEV2 if alert_type == AlertType.PAGE else cls.SEV3


@dataclass
class Alert:
    alert_type:  AlertType
    slo:         SLOType
    service:     str
    region:      str
    window_pair: str          # e.g. "5m+1h" or "30m+6h"
    start:       datetime
    end:         datetime
    severity:    Severity
    routing:     list[str]
    summary:     str

    @property
    def dedupe_key(self) -> str:
        return f"{self.alert_type.value}:{self.slo.value}:{self.service}:{self.region}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "alert_type":  self.alert_type.value,
            "slo":         self.slo.value,
            "service":     self.service,
            "region":      self.region,
            "window_pair": self.window_pair,
            "start":       self.start.isoformat(),
            "end":         self.end.isoformat(),
            "severity":    self.severity.value,
            "dedupe_key":  self.dedupe_key,
            "routing":     self.routing,
            "summary":     self.summary,
        }

    def to_jsonl(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)
