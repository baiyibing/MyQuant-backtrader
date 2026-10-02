"""True-core X6 · synthetic_fixture / attestation differential (NOT true lake).

tool_id is tooling identity only — NOT a backend_id. Reuses research contract
v0 (L2-S0) / minute_orders_research_v1 identity labels only for documentation;
does not run MatchCore or mint new economic semantics. Fixture PASS != lake
PASS; forever opt-in; never BOOKS default.

See docs/backtest/note-true-core-x6-synthetic-attestation-2026-10-02.md.
"""

from .differential import (
    BACKEND_ID,
    CONTRACT,
    DIFFERENTIAL_ROOT_NAME,
    DIFFERENTIAL_STATUS,
    FIXTURE_NOTICE,
    FORBIDDEN_SUMMARY_NAME,
    REPORT_FILENAME,
    REPORT_SCHEMA,
    TOOL_ID,
    DifferentialError,
    DifferentialOutcome,
    run_x6_synthetic_differential,
    write_differential_report,
)
from .ingest import (
    BOUNDARY_META_SCHEMA,
    DifferentialIngestError,
    SyntheticBoundaryMeta,
    load_synthetic_boundary_meta,
    meta_from_mapping,
)

__all__ = [
    "BACKEND_ID",
    "BOUNDARY_META_SCHEMA",
    "CONTRACT",
    "DIFFERENTIAL_ROOT_NAME",
    "DIFFERENTIAL_STATUS",
    "FIXTURE_NOTICE",
    "FORBIDDEN_SUMMARY_NAME",
    "REPORT_FILENAME",
    "REPORT_SCHEMA",
    "TOOL_ID",
    "DifferentialError",
    "DifferentialIngestError",
    "DifferentialOutcome",
    "SyntheticBoundaryMeta",
    "load_synthetic_boundary_meta",
    "meta_from_mapping",
    "run_x6_synthetic_differential",
    "write_differential_report",
]
