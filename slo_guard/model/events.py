"""
Input event models for slo-guard.

Two event types are supported:
  - http_minute : per-minute HTTP aggregate metrics per service/region
  - nav_publish : daily NAV publication event per fund/region
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class HTTPMinute:
    """Per-minute HTTP metrics aggregate."""

    ts: datetime
    service: str
    region: str
    total: int
    http_5xx: int
    # Cumulative latency buckets: key = upper-bound ms (str), value = count of requests <= that bound
    latency_buckets_ms: dict[str, int]

    # ── derived fields ──────────────────────────────────────────────────────

    @property
    def slow_requests(self) -> int:
        """Requests that took > 500 ms (i.e. NOT in the <=500 bucket)."""
        within_500 = self.latency_buckets_ms.get("500", 0)
        return max(0, self.total - within_500)

    @property
    def availability_error_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return self.http_5xx / self.total

    @property
    def latency_error_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return self.slow_requests / self.total

    # ── construction ────────────────────────────────────────────────────────

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> HTTPMinute:
        ts_raw = d["ts"]
        if isinstance(ts_raw, str):
            ts = datetime.fromisoformat(ts_raw)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=UTC)
        else:
            ts = ts_raw

        buckets: dict[str, int] = {
            str(k): int(v)
            for k, v in d.get("latency_buckets_ms", {}).items()
        }

        return cls(
            ts=ts,
            service=d["service"],
            region=d["region"],
            total=int(d.get("total", 0)),
            http_5xx=int(d.get("http_5xx", 0)),
            latency_buckets_ms=buckets,
        )


@dataclass(frozen=True)
class NAVPublish:
    """Daily NAV publication event for a fund."""

    ts: datetime          # wall-clock time the event was emitted
    fund: str
    region: str
    nav_date: str         # YYYY-MM-DD  the NAV date being published
    status: str           # e.g. "published"

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> NAVPublish:
        ts_raw = d["ts"]
        if isinstance(ts_raw, str):
            ts = datetime.fromisoformat(ts_raw)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=UTC)
        else:
            ts = ts_raw

        return cls(
            ts=ts,
            fund=d["fund"],
            region=d["region"],
            nav_date=d["nav_date"],
            status=d.get("status", ""),
        )


def parse_event(line: str) -> HTTPMinute | NAVPublish | None:
    """
    Parse a single JSONL line into the appropriate event type.

    Returns None for blank lines or unknown event types.
    Raises ValueError for malformed JSON or missing required fields.
    """
    line = line.strip()
    if not line:
        return None

    try:
        d = json.loads(line)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON: {exc}") from exc

    event_type = d.get("type")
    if event_type == "http_minute":
        return HTTPMinute.from_dict(d)
    if event_type == "nav_publish":
        return NAVPublish.from_dict(d)

    return None  # unknown type — silently ignore
