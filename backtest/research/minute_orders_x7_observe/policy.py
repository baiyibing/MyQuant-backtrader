"""A·X7 observation policy constants (new projection entry; not views._FAMILIES)."""

from __future__ import annotations

from typing import Any

# observation_id is tooling identity only — NOT a backend_id / economic contract.
OBSERVATION_ID = "minute_orders_x7_observe"
OBSERVATION_ROOT_NAME = "minute_orders_x7_observe"
OBSERVATION_STATUS = "observation_only_not_green_r"
REPORT_SCHEMA = "minute_orders_x7_observation_report_v0"
REPORT_FILENAME = "observation_report.json"
FORBIDDEN_SUMMARY_NAME = "summary.json"

CONTRACT = "research contract v0 (L2-S0)"
BACKEND_ID = "minute_orders_research_v1"

# New projection family label for THIS package only — never registered into
# backtest.research.run_protocol.views._FAMILIES.
X7_PROJECTION_FAMILY = "minute_orders_x7_observe"

NOTICE = (
    "A·X7 observation surface: projects already-obtained New-core tool reports "
    "into a red-label observation slice. observation ≠ green R; no NAV rewrite; "
    "never stuffs views._FAMILIES; forever opt-in; ≠δ5≠R4; no production write; "
    "no 4090."
)

# Allowed source kinds (already-obtained artifacts). No lake write, no host PASS.
ALLOWED_SOURCE_KINDS = frozenset({
    "x1_named_consumer_report",
    "x6_synthetic_differential_report",
    "x6_lake_boundary_report",
    "x6_lake_e2e_report",
    "x8_comparison_report",
    "write_lake_staging_dry_run_report",
    "synthetic_observation_sketch",
})

BANNED_SOURCE_KEYS = frozenset({
    "fills",
    "trades",
    "nav",
    "equity_curve",
    "summary",
    "green_r",
    "host_pass",
    "write_lake",
    "lake_write",
    "production_write",
})


class ObserveError(ValueError):
    """Observation refused before or during write (not a green research failure)."""


def assert_not_views_families_registration() -> dict[str, Any]:
    """Static guard payload: X7 must never register into views._FAMILIES."""
    return {
        "x7_projection_family": X7_PROJECTION_FAMILY,
        "views_families_touch": "forbidden",
        "rule": "new projection entry only; never append to views._FAMILIES",
    }
