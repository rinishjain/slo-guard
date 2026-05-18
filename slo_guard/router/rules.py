"""
Alert routing rules for slo-guard.

Maps (service, alert_type) → list of routing targets.
PAGE alerts always include "oncall-sre". TICKET alerts go to the team only.

Extend SERVICE_TEAMS to add new service → team mappings.
"""
from __future__ import annotations

from slo_guard.model.alert import AlertType

# Map service/fund name prefixes to owning teams
SERVICE_TEAMS: dict[str, str] = {
    "xyz_web":      "web-platform",
    "xyz-web":      "web-platform",
    "payments":     "payments-team",
    "auth":         "identity-team",
    "nav":          "fund-ops",
}

DEFAULT_TEAM = "sre-general"


def _team_for(service: str) -> str:
    """Look up the owning team for a service, falling back to DEFAULT_TEAM."""
    service_lower = service.lower()
    for prefix, team in SERVICE_TEAMS.items():
        if service_lower.startswith(prefix):
            return team
    return DEFAULT_TEAM


def route(service: str, alert_type: AlertType) -> list[str]:
    """
    Return the routing list for an alert.

    PAGE  → ["oncall-sre", "<team>"]
    TICKET → ["<team>"]
    """
    team = _team_for(service)
    if alert_type == AlertType.PAGE:
        return ["oncall-sre", team]
    return [team]
