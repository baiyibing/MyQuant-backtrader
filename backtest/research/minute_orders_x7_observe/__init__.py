"""A·X7 observation surface: NEW projection entry (never views._FAMILIES).

observation_id is tooling identity only — NOT a backend_id. Reuses research
contract v0 (L2-S0) / minute_orders_research_v1 labels only for documentation.

Projects already-obtained New-core tool reports into a red-label observation
slice. Observation ≠ green R; no NAV rewrite; no production write; no 4090.

See docs/backtest/note-true-core-ax7-observe-2026-10-02.md.
"""

from .policy import (
    BACKEND_ID,
    CONTRACT,
    FORBIDDEN_SUMMARY_NAME,
    NOTICE,
    OBSERVATION_ID,
    OBSERVATION_ROOT_NAME,
    OBSERVATION_STATUS,
    REPORT_FILENAME,
    REPORT_SCHEMA,
    X7_PROJECTION_FAMILY,
    ObserveError,
    assert_not_views_families_registration,
)
from .project import (
    REQUEST_SCHEMA,
    ObservationOutcome,
    ObserveRequest,
    load_observe_request,
    project_observation_slice,
    request_from_mapping,
    run_x7_observe,
)

__all__ = [
    "BACKEND_ID",
    "CONTRACT",
    "FORBIDDEN_SUMMARY_NAME",
    "NOTICE",
    "OBSERVATION_ID",
    "OBSERVATION_ROOT_NAME",
    "OBSERVATION_STATUS",
    "REPORT_FILENAME",
    "REPORT_SCHEMA",
    "REQUEST_SCHEMA",
    "X7_PROJECTION_FAMILY",
    "ObservationOutcome",
    "ObserveError",
    "ObserveRequest",
    "assert_not_views_families_registration",
    "load_observe_request",
    "project_observation_slice",
    "request_from_mapping",
    "run_x7_observe",
]
