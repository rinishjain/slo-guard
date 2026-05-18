#!/usr/bin/env python3
"""
slo-guard CLI entrypoint.

Usage:
    # Read from stdin, write alerts to stdout
    cat events.jsonl | slo-guard

    # Read from a file
    slo-guard --input events.jsonl

    # Write to a file
    slo-guard --input events.jsonl --output alerts.jsonl

    # Verbose mode (prints stats to stderr)
    slo-guard --input events.jsonl --verbose
"""
from __future__ import annotations

import argparse
import sys
from typing import IO

from slo_guard.pipeline import run


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="slo-guard",
        description="SRE alerting engine: reads telemetry JSONL, emits SLO-based alerts.",
    )
    parser.add_argument(
        "--input", "-i",
        metavar="FILE",
        default=None,
        help="Input JSONL file (default: stdin)",
    )
    parser.add_argument(
        "--output", "-o",
        metavar="FILE",
        default=None,
        help="Output JSONL file (default: stdout)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print processing stats to stderr",
    )

    args = parser.parse_args()

    # ── open streams ──────────────────────────────────────────────────────
    input_stream: IO[str]
    output_stream: IO[str]

    if args.input:
        try:
            input_stream = open(args.input, encoding="utf-8")
        except FileNotFoundError:
            print(f"slo-guard: input file not found: {args.input}", file=sys.stderr)
            sys.exit(1)
    else:
        input_stream = sys.stdin

    if args.output:
        output_stream = open(args.output, "w", encoding="utf-8")
    else:
        output_stream = sys.stdout

    # ── run ───────────────────────────────────────────────────────────────
    try:
        run(input_stream=input_stream, output_stream=output_stream)
    finally:
        if args.input:
            input_stream.close()
        if args.output:
            output_stream.close()


if __name__ == "__main__":
    main()
