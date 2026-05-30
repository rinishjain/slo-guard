"""
Configuration loader for slo-guard.

Reads a YAML file and produces a Config object that is passed into Pipeline.
Call load_config(path) to load from disk, or use DEFAULT_CONFIG for the
hardcoded defaults that mirror config.yaml.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import time, timedelta
from pathlib import Path
from typing import Any

import yaml

from slo_guard.burnrate.engine import AlertRule
from slo_guard.model.alert import AlertType


@dataclass
class Config:
    slo_availability: float
    slo_latency: float
    nav_cutoff: time
    region_timezones: dict[str, str]
    burnrate_rules: list[AlertRule]
    suppression_window: timedelta
    max_window_minutes: int


def _parse_rules(raw: list[dict[str, Any]]) -> list[AlertRule]:
    rules = []
    for r in raw:
        rules.append(AlertRule(
            alert_type=AlertType[r["alert_type"].upper()],
            short_minutes=int(r["short_minutes"]),
            short_threshold=float(r["short_threshold"]),
            long_minutes=int(r["long_minutes"]),
            long_threshold=float(r["long_threshold"]),
            window_pair=str(r["window_pair"]),
        ))
    return rules


def _parse_time(s: str) -> time:
    parts = s.split(":")
    return time(int(parts[0]), int(parts[1]), 0)


def load_config(path: str | Path) -> Config:
    """Load a Config from a YAML file."""
    with open(path, encoding="utf-8") as f:
        raw: dict[str, Any] = yaml.safe_load(f)

    return Config(
        slo_availability=float(raw["slo"]["availability_target"]),
        slo_latency=float(raw["slo"]["latency_target"]),
        nav_cutoff=_parse_time(raw["nav"]["cutoff"]),
        region_timezones=dict(raw["nav"]["region_timezones"]),
        burnrate_rules=_parse_rules(raw["burnrate"]["rules"]),
        suppression_window=timedelta(minutes=int(raw["dedup"]["suppression_window_minutes"])),
        max_window_minutes=int(raw["window"]["max_window_minutes"]),
    )


DEFAULT_CONFIG = Config(
    slo_availability=0.999,
    slo_latency=0.999,
    nav_cutoff=time(18, 0, 0),
    region_timezones={
        "HK": "Asia/Hong_Kong",
        "SG": "Asia/Singapore",
        "JP": "Asia/Tokyo",
        "AU": "Australia/Sydney",
        "IN": "Asia/Kolkata",
        "UK": "Europe/London",
        "EU": "Europe/Paris",
        "US": "America/New_York",
    },
    burnrate_rules=[
        AlertRule(
            alert_type=AlertType.PAGE,
            short_minutes=3,
            short_threshold=12.0,
            long_minutes=60,
            long_threshold=3.0,
            window_pair="5m+1h",
        ),
        AlertRule(
            alert_type=AlertType.TICKET,
            short_minutes=30,
            short_threshold=3.0,
            long_minutes=360,
            long_threshold=1.0,
            window_pair="60m+6h",
        ),
    ],
    suppression_window=timedelta(minutes=20),
    max_window_minutes=360,
)
