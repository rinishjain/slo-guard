# slo-guard

SRE alerting engine that reads telemetry (JSONL) and emits SLO-based alerts using burn-rate alerting, deduplication, and routing.

## Features

- **Burn-rate alerting** — PAGE and TICKET tiers across dual rolling windows (5m+1h, 30m+6h)
- **Availability SLO** — 99.9% target; error rate = HTTP 5xx / total
- **Latency SLO** — treats requests > 500 ms as errors
- **NAV freshness SLO** — alerts if a fund NAV is published after 18:00 local time
- **Deduplication** — 30-minute suppression per (alert_type, slo, service, region)
- **Structured output** — JSONL alerts with severity, routing, dedupe key, and summary
- **Zero runtime dependencies** — Python 3.11+ standard library only

---
Assumptions
- Input JSONL arrives in chronological order; out-of-order event handling is out of scope for v1.
- The tool runs in-process with in-memory state; persistence across restarts is not required.
- Region-to-timezone mapping (e.g. HK → Asia/Hong_Kong) is provided as a static config; dynamic mapping is out of scope.
- Alert routing (team names per service) is defined in a simple config file; complex routing logic is out of scope.
- NAV freshness SLO applies only to events with status = “published”; other statuses are ignored.
- SLO targets (99.9% availability, 500 ms latency threshold) are fixed constants, not runtime-configurable in v1.
- The CI environment has outbound internet access for downloading vulnerability databases.
- NAV is a business term (Net Asset Value) referring to a scheduled daily publication event; it has no special SRE-standard meaning.

## Quick start

```bash
# Install
pip install -e .

# Run from stdin
cat events.jsonl | slo-guard

# Run from file
slo-guard --input events.jsonl --output alerts.jsonl
```

---

## Input format

Two event types are accepted, one per line:

### `http_minute`
Per-minute HTTP aggregate metrics:
```json
{
  "type": "http_minute",
  "ts": "2026-05-15T09:50:00+00:00",
  "service": "xyz_web",
  "region": "HK",
  "total": 10000,
  "http_5xx": 50,
  "latency_buckets_ms": {
    "500": 6500,
    "1000": 8200,
    "2000": 10000
  }
}
```
Latency buckets are **cumulative** (≤ bucket ms). `slow_requests = total - bucket["500"]`.

### `nav_publish`
Daily NAV publication event:
```json
{
  "type": "nav_publish",
  "ts": "2026-05-15T10:05:00+00:00",
  "fund": "ABC_FUND",
  "region": "HK",
  "nav_date": "2026-05-15",
  "status": "published"
}
```

---

## Output format

Each alert is a single JSON line:
```json
{
  "alert_type": "page",
  "slo": "availability",
  "service": "xyz_web",
  "region": "HK",
  "window_pair": "5m+1h",
  "start": "2026-05-15T09:50:00+00:00",
  "end": "2026-05-15T09:54:00+00:00",
  "severity": "sev2",
  "dedupe_key": "page:availability:xyz_web:HK",
  "routing": ["oncall-sre", "web-platform"],
  "summary": "High error rate causing availability burn-rate breach for xyz_web in HK"
}
```

---

## SLOs and alerting rules

### Burn-rate formula
```
burn_rate = observed_error_rate / (1 - SLO_target)
```

### Alert tiers

| Alert | Short window | Short threshold | Long window | Long threshold | Severity |
|-------|-------------|-----------------|-------------|----------------|----------|
| PAGE  | 5 m         | burn rate > 14  | 1 h         | burn rate > 6  | sev2     |
| TICKET| 30 m        | burn rate > 3   | 6 h         | burn rate > 1  | sev3     |

Both conditions must be true simultaneously.

### NAV freshness
- Alert fires if `status == "published"` and publish time > 18:00 local time for the fund's region
- Severity: sev3 / TICKET

---

## Architecture

```
JSONL input
    │
    ▼
┌─────────┐     ┌──────────────┐     ┌─────────────────┐
│  Parser  │────▶│ Rolling       │────▶│ Burn-rate engine│
│          │     │ window store  │     │ (PAGE / TICKET) │
└─────────┘     └──────────────┘     └────────┬────────┘
    │                                          │
    │ nav_publish                              │
    ▼                                          ▼
┌─────────────┐                      ┌──────────────────┐
│ NAV checker │                      │  Deduplicator    │
│             │─────────────────────▶│  (30-min window) │
└─────────────┘                      └────────┬─────────┘
                                              │
                                              ▼
                                       JSONL alerts
```

---

## Running tests

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Unit tests
pytest tests/unit/ -v

# Regression tests (generate golden files first)
python scripts/generate_golden.py
pytest tests/regression/ -v

# All tests with coverage
pytest --cov=slo_guard --cov-report=term-missing
```

---

## Adding a new service team

Edit `slo_guard/router/rules.py`:
```python
SERVICE_TEAMS: dict[str, str] = {
    "xyz_web":   "web-platform",
    "payments":  "payments-team",
    "my_new_svc": "my-team",   # ← add here
}
```

## Adding a new region timezone

Edit `slo_guard/nav/checker.py`:
```python
REGION_TIMEZONES: dict[str, str] = {
    "HK": "Asia/Hong_Kong",
    "MY": "Asia/Kuala_Lumpur",  # ← add here
}
```

---

## Project structure

```
slo-guard/
├── slo_guard/
│   ├── model/          # Input event types + Alert output type
│   ├── window/         # Rolling window ring buffer
│   ├── burnrate/       # Burn-rate engine and alert rules
│   ├── nav/            # NAV freshness checker
│   ├── dedup/          # 30-minute deduplication store
│   ├── router/         # Alert routing rules
│   ├── pipeline.py     # Wires all components together
│   └── cli.py          # CLI entrypoint
├── tests/
│   ├── unit/           # Unit tests (TDD, per-module)
│   └── regression/     # Golden file regression tests
├── testdata/           # Fixed input/output fixtures
├── scripts/
│   └── generate_golden.py  # Regenerate golden files
├── .github/workflows/
│   └── ci.yml          # GitHub Actions CI pipeline
└── pyproject.toml
```
# slo-guard
# AIOPS-Project
# AIOPS-Project
