"""
Regression tests for slo-guard.

Each scenario in testdata/ contains:
  input.jsonl    — fixed input events
  expected.jsonl — expected alert output (golden file)

Run: pytest tests/regression/test_regression.py
Regenerate golden files: python scripts/generate_golden.py
"""
import json
import os

import pytest

from slo_guard.pipeline import Pipeline

TESTDATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "testdata")


def collect_scenarios():
    """Return all scenario dirs that have both input and expected files."""
    scenarios = []
    if not os.path.isdir(TESTDATA_DIR):
        return scenarios
    for name in sorted(os.listdir(TESTDATA_DIR)):
        scenario_dir  = os.path.join(TESTDATA_DIR, name)
        input_path    = os.path.join(scenario_dir, "input.jsonl")
        expected_path = os.path.join(scenario_dir, "expected.jsonl")
        if os.path.isfile(input_path) and os.path.isfile(expected_path):
            scenarios.append(
                pytest.param(name, input_path, expected_path, id=name)
            )
    return scenarios


@pytest.mark.parametrize("name,input_path,expected_path", collect_scenarios())
def test_scenario(name, input_path, expected_path):
    """
    Run the pipeline over input.jsonl and compare to expected.jsonl.

    Comparison is done field-by-field so that irrelevant ordering differences
    in list fields (e.g. routing) don't cause false failures.
    """
    # Run pipeline
    pipeline = Pipeline()
    actual_alerts = []
    with open(input_path, encoding="utf-8") as f:
        for line in f:
            for alert in pipeline.process_line(line):
                actual_alerts.append(alert.to_dict())

    # Load expected
    expected_alerts = []
    with open(expected_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                expected_alerts.append(json.loads(line))

    assert len(actual_alerts) == len(expected_alerts), (
        f"[{name}] Expected {len(expected_alerts)} alert(s), "
        f"got {len(actual_alerts)}.\n"
        f"Actual: {actual_alerts}"
    )

    for i, (actual, expected) in enumerate(zip(actual_alerts, expected_alerts, strict=True)):
        for key in expected:
            assert key in actual, (
                f"[{name}] Alert {i}: missing field '{key}'"
            )
            # Sort lists before comparing (routing order is not guaranteed)
            act_val = sorted(actual[key]) if isinstance(actual[key], list) else actual[key]
            exp_val = sorted(expected[key]) if isinstance(expected[key], list) else expected[key]
            assert act_val == exp_val, (
                f"[{name}] Alert {i}: field '{key}' mismatch.\n"
                f"  Expected: {exp_val}\n"
                f"  Actual:   {act_val}"
            )


def test_no_alert_for_clean_traffic():
    """Sanity check: clean traffic produces zero alerts."""
    pipeline = Pipeline()
    clean_event = json.dumps({
        "type": "http_minute",
        "ts": "2026-05-15T12:00:00+00:00",
        "service": "xyz_web",
        "region": "HK",
        "total": 10000,
        "http_5xx": 0,
        "latency_buckets_ms": {"500": 10000, "1000": 10000, "2000": 10000},
    })
    for _ in range(10):
        alerts = list(pipeline.process_line(clean_event))
        assert alerts == [], f"Expected no alerts for clean traffic, got: {alerts}"


def test_deduplication_scenario():
    """
    Deduplication scenario: 10 minutes of high errors.
    Each dedupe key should appear at most once per 30-minute window.
    """
    input_path = os.path.join(TESTDATA_DIR, "deduplication", "input.jsonl")
    if not os.path.isfile(input_path):
        pytest.skip("deduplication scenario not found")

    pipeline = Pipeline()
    alerts = []
    with open(input_path, encoding="utf-8") as f:
        for line in f:
            alerts.extend(pipeline.process_line(line))

    # Group by dedupe_key — each key should appear exactly once
    seen_keys: dict[str, int] = {}
    for alert in alerts:
        key = alert.dedupe_key
        seen_keys[key] = seen_keys.get(key, 0) + 1

    for key, count in seen_keys.items():
        assert count == 1, (
            f"Alert with dedupe_key '{key}' emitted {count} times "
            f"within a 30-minute window — deduplication failed."
        )
