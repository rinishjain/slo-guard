"""Unit tests for model/events.py — parser and event types."""
import json
from datetime import datetime, timezone

import pytest

from slo_guard.model.events import HTTPMinute, NAVPublish, parse_event


# ── HTTPMinute ────────────────────────────────────────────────────────────────

BASE_HTTP = {
    "type": "http_minute",
    "ts": "2026-05-15T12:00:00+00:00",
    "service": "xyz_web",
    "region": "HK",
    "total": 10000,
    "http_5xx": 50,
    "latency_buckets_ms": {"500": 6500, "1000": 8200, "2000": 10000},
}


def test_http_minute_parses_correctly():
    e = HTTPMinute.from_dict(BASE_HTTP)
    assert e.service == "xyz_web"
    assert e.region  == "HK"
    assert e.total   == 10000
    assert e.http_5xx == 50


def test_http_minute_ts_is_timezone_aware():
    e = HTTPMinute.from_dict(BASE_HTTP)
    assert e.ts.tzinfo is not None


def test_slow_requests_derived_correctly():
    # slow = total - requests_within_500ms = 10000 - 6500 = 3500
    e = HTTPMinute.from_dict(BASE_HTTP)
    assert e.slow_requests == 3500


def test_slow_requests_all_fast():
    d = {**BASE_HTTP, "total": 1000, "latency_buckets_ms": {"500": 1000}}
    e = HTTPMinute.from_dict(d)
    assert e.slow_requests == 0


def test_slow_requests_all_slow():
    d = {**BASE_HTTP, "total": 1000, "latency_buckets_ms": {"500": 0}}
    e = HTTPMinute.from_dict(d)
    assert e.slow_requests == 1000


def test_slow_requests_missing_500_bucket():
    # If the 500ms bucket is absent, treat all requests as slow
    d = {**BASE_HTTP, "total": 500, "latency_buckets_ms": {"1000": 400, "2000": 500}}
    e = HTTPMinute.from_dict(d)
    assert e.slow_requests == 500


def test_availability_error_rate():
    e = HTTPMinute.from_dict(BASE_HTTP)
    assert abs(e.availability_error_rate - 0.005) < 1e-9


def test_latency_error_rate():
    e = HTTPMinute.from_dict(BASE_HTTP)
    assert abs(e.latency_error_rate - 0.35) < 1e-9


def test_zero_total_returns_zero_rates():
    d = {**BASE_HTTP, "total": 0, "http_5xx": 0, "latency_buckets_ms": {}}
    e = HTTPMinute.from_dict(d)
    assert e.availability_error_rate == 0.0
    assert e.latency_error_rate      == 0.0


def test_naive_ts_gets_utc_attached():
    d = {**BASE_HTTP, "ts": "2026-05-15T12:00:00"}  # no timezone
    e = HTTPMinute.from_dict(d)
    assert e.ts.tzinfo is not None


# ── NAVPublish ────────────────────────────────────────────────────────────────

BASE_NAV = {
    "type": "nav_publish",
    "ts": "2026-05-15T17:00:00+08:00",
    "fund": "ABC_FUND",
    "region": "HK",
    "nav_date": "2026-05-15",
    "status": "published",
}


def test_nav_publish_parses_correctly():
    e = NAVPublish.from_dict(BASE_NAV)
    assert e.fund    == "ABC_FUND"
    assert e.region  == "HK"
    assert e.status  == "published"
    assert e.nav_date == "2026-05-15"


def test_nav_publish_ts_is_timezone_aware():
    e = NAVPublish.from_dict(BASE_NAV)
    assert e.ts.tzinfo is not None


# ── parse_event ───────────────────────────────────────────────────────────────

def test_parse_event_http_minute():
    line = json.dumps(BASE_HTTP)
    e = parse_event(line)
    assert isinstance(e, HTTPMinute)


def test_parse_event_nav_publish():
    line = json.dumps(BASE_NAV)
    e = parse_event(line)
    assert isinstance(e, NAVPublish)


def test_parse_event_unknown_type_returns_none():
    line = json.dumps({"type": "unknown_event", "ts": "2026-01-01T00:00:00Z"})
    assert parse_event(line) is None


def test_parse_event_blank_line_returns_none():
    assert parse_event("") is None
    assert parse_event("   \n") is None


def test_parse_event_invalid_json_raises():
    with pytest.raises(ValueError):
        parse_event("{not valid json")
