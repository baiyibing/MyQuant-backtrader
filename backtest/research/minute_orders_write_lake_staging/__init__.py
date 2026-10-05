"""True-core residual R2 · write-lake staging dry-run (NOT production write).

tool_id is tooling identity only — NOT a backend_id. Reuses research contract
v0 (L2-S0) / minute_orders_research_v1 labels only for documentation.

This knife does NOT write the lake. It plans an independent staging dry-run
and publishes MUST Human cuts required before any production Phase4 write
can be separately authorized. Prefer existing vendor Phase2 staging /
Phase4 host ownership over blind write from this fork (AGENTS.md consume-only).

See docs/backtest/note-true-core-write-lake-residual-2026-10-02.md.
"""

from .policy import (
    BACKEND_ID,
    CONTRACT,
    FORBIDDEN_SUMMARY_NAME,
    MUST_HUMAN_CUTS,
    NOTICE,
    PLAN_FILENAME,
    REPORT_FILENAME,
    REPORT_SCHEMA,
    STAGING_ROOT_NAME,
    STAGING_STATUS,
    TOOL_ID,
    WriteLakeStagingError,
    assert_not_production_target,
    assert_staging_out_dir,
    must_human_cuts_payload,
)
from .staging import (
    ALLOWED_MODE,
    REQUEST_SCHEMA,
    StagingOutcome,
    StagingRequest,
    load_staging_request,
    request_from_mapping,
    run_write_lake_staging_dry_run,
)

__all__ = [
    "ALLOWED_MODE",
    "BACKEND_ID",
    "CONTRACT",
    "FORBIDDEN_SUMMARY_NAME",
    "MUST_HUMAN_CUTS",
    "NOTICE",
    "PLAN_FILENAME",
    "REPORT_FILENAME",
    "REPORT_SCHEMA",
    "REQUEST_SCHEMA",
    "STAGING_ROOT_NAME",
    "STAGING_STATUS",
    "TOOL_ID",
    "StagingOutcome",
    "StagingRequest",
    "WriteLakeStagingError",
    "assert_not_production_target",
    "assert_staging_out_dir",
    "load_staging_request",
    "must_human_cuts_payload",
    "request_from_mapping",
    "run_write_lake_staging_dry_run",
]
