"""
Core pipeline for slo-guard.

Wires together: parser → window store → burn-rate engine
                                      → NAV checker
                                      → deduplicator → output
"""
from __future__ import annotations

import sys
from collections.abc import Iterator
from typing import IO

from slo_guard.burnrate.engine import BurnRateEngine
from slo_guard.config import DEFAULT_CONFIG, Config
from slo_guard.dedup.store import DeduplicationStore
from slo_guard.model.alert import Alert
from slo_guard.model.events import HTTPMinute, NAVPublish, parse_event
from slo_guard.nav.checker import NAVChecker
from slo_guard.window.store import WindowStore


class Pipeline:
    """
    Stateful pipeline that processes a stream of JSONL events and emits alerts.

    Usage:
        pipeline = Pipeline()
        for alert in pipeline.process_line(line):
            print(alert.to_jsonl())
    """

    def __init__(self, config: Config = DEFAULT_CONFIG) -> None:
        self._window_store = WindowStore(config.max_window_minutes)
        self._burn_engine  = BurnRateEngine(
            self._window_store,
            rules=config.burnrate_rules,
            slo_availability=config.slo_availability,
            slo_latency=config.slo_latency,
        )
        self._nav_checker  = NAVChecker(
            cutoff=config.nav_cutoff,
            region_timezones=config.region_timezones,
        )
        self._dedup        = DeduplicationStore(config.suppression_window)

    def process_line(self, line: str) -> Iterator[Alert]:
        """Parse one JSONL line and yield any alerts that should be emitted."""
        try:
            event = parse_event(line)
        except ValueError:
            # Malformed JSON — skip silently in production, log if needed
            return

        if event is None:
            return

        if isinstance(event, HTTPMinute):
            now = event.ts
            for alert in self._burn_engine.evaluate(event):
                if self._dedup.should_emit(alert, now):
                    yield alert

        elif isinstance(event, NAVPublish):
            now = event.ts
            nav_alert = self._nav_checker.evaluate(event)
            if nav_alert and self._dedup.should_emit(nav_alert, now):
                yield nav_alert

    def process_stream(self, stream: IO[str]) -> Iterator[Alert]:
        """Process all lines from a text stream."""
        for line in stream:
            yield from self.process_line(line)


def run(
    input_stream: IO[str] = sys.stdin,
    output_stream: IO[str] = sys.stdout,
    config: Config = DEFAULT_CONFIG,
) -> None:
    """Main entry point: read JSONL from input, write alerts to output."""
    pipeline = Pipeline(config)
    for alert in pipeline.process_stream(input_stream):
        output_stream.write(alert.to_jsonl() + "\n")
        output_stream.flush()
