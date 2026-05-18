#!/usr/bin/env python3
"""
Generate golden regression output files from testdata inputs.

Run this script whenever intentional output format changes are made:
    python scripts/generate_golden.py

This will overwrite all expected.jsonl files in testdata/.
Commit the updated files along with your code change.
"""
import os
import sys

# Ensure the project root is on the path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from io import StringIO
from slo_guard.pipeline import Pipeline

TESTDATA_DIR = os.path.join(ROOT, "testdata")


def generate(scenario: str) -> None:
    input_path    = os.path.join(TESTDATA_DIR, scenario, "input.jsonl")
    expected_path = os.path.join(TESTDATA_DIR, scenario, "expected.jsonl")

    if not os.path.exists(input_path):
        print(f"  SKIP {scenario}: no input.jsonl found")
        return

    pipeline = Pipeline()
    alerts = []
    with open(input_path, encoding="utf-8") as f:
        for line in f:
            for alert in pipeline.process_line(line):
                alerts.append(alert.to_jsonl())

    with open(expected_path, "w", encoding="utf-8") as f:
        for line in alerts:
            f.write(line + "\n")

    print(f"  OK  {scenario}: {len(alerts)} alert(s) written to expected.jsonl")


def main():
    scenarios = sorted(
        d for d in os.listdir(TESTDATA_DIR)
        if os.path.isdir(os.path.join(TESTDATA_DIR, d))
    )
    print(f"Generating golden files for {len(scenarios)} scenario(s)...")
    for scenario in scenarios:
        generate(scenario)
    print("Done.")


if __name__ == "__main__":
    main()
