"""True-core X6 · lake END / loader boundary differential (read-only).

tool_id is tooling identity only — NOT a backend_id. Reuses research contract
v0 (L2-S0) / minute_orders_research_v1 identity labels only for documentation;
does not run MatchCore, does not call load_minute_orders_source, does not write
the lake, and does not unlock CLI --evidence-level=lake. Lake boundary
attestation != host PASS / lake PASS / green R; forever opt-in; never BOOKS
default.

See docs/backtest/note-true-core-x6-lake-boundary-2026-10-02.md.
"""

from .differential import (
    BACKEND_ID,
    CONTRACT,
    DIFFERENTIAL_ROOT_NAME,
    DIFFERENTIAL_STATUS,
    FORBIDDEN_SUMMARY_NAME,
    LAKE_BOUNDARY_NOTICE,
    REPORT_FILENAME,
    REPORT_SCHEMA,
    TOOL_ID,
    LakeDifferentialError,
    LakeDifferentialOutcome,
    run_x6_lake_differential,
    write_differential_report,
)
from .ingest import (
    BOUNDARY_META_SCHEMA,
    LakeBoundaryIngestError,
    LakeBoundaryMeta,
    load_lake_boundary_meta,
    meta_from_mapping,
)

__all__ = [
    "BACKEND_ID",
    "BOUNDARY_META_SCHEMA",
    "CONTRACT",
    "DIFFERENTIAL_ROOT_NAME",
    "DIFFERENTIAL_STATUS",
    "FORBIDDEN_SUMMARY_NAME",
    "LAKE_BOUNDARY_NOTICE",
    "REPORT_FILENAME",
    "REPORT_SCHEMA",
    "TOOL_ID",
    "LakeBoundaryIngestError",
    "LakeBoundaryMeta",
    "LakeDifferentialError",
    "LakeDifferentialOutcome",
    "load_lake_boundary_meta",
    "meta_from_mapping",
    "run_x6_lake_differential",
    "write_differential_report",
]
