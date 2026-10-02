"""True-core X6 · lake END / loader boundary + recipe e2e (read-only).

tool_id is tooling identity only — NOT a backend_id. Reuses research contract
v0 (L2-S0) / minute_orders_research_v1 identity labels only for documentation.

Boundary knife (#309): does not call load_minute_orders_source.
Recipe e2e knife (this residual GO): calls load_minute_orders_source only;
does not write the lake; does not unlock CLI --evidence-level=lake; does not
run MatchCore fills / research_v1 success summary. Lake load != host PASS /
lake PASS / green R; forever opt-in; never BOOKS default.

See docs/backtest/note-true-core-x6-lake-boundary-2026-10-02.md
and docs/backtest/note-true-core-x6-lake-recipe-e2e-2026-10-02.md.
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
from .e2e import (
    E2E_REPORT_FILENAME,
    E2E_REPORT_SCHEMA,
    E2E_STATUS,
    LAKE_E2E_NOTICE,
    LakeRecipeE2EError,
    LakeRecipeE2EOutcome,
    run_x6_lake_recipe_e2e,
    write_e2e_report,
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
    "E2E_REPORT_FILENAME",
    "E2E_REPORT_SCHEMA",
    "E2E_STATUS",
    "FORBIDDEN_SUMMARY_NAME",
    "LAKE_BOUNDARY_NOTICE",
    "LAKE_E2E_NOTICE",
    "REPORT_FILENAME",
    "REPORT_SCHEMA",
    "TOOL_ID",
    "LakeBoundaryIngestError",
    "LakeBoundaryMeta",
    "LakeDifferentialError",
    "LakeDifferentialOutcome",
    "LakeRecipeE2EError",
    "LakeRecipeE2EOutcome",
    "load_lake_boundary_meta",
    "meta_from_mapping",
    "run_x6_lake_differential",
    "run_x6_lake_recipe_e2e",
    "write_differential_report",
    "write_e2e_report",
]
