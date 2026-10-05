"""TC4 · X8 comparison bridge: pre-match intent snapshot ↔ X1 frozen-batch run.

Red-label diagnostic only. comparison_id is NOT a backend_id; reuses research
contract v0 (L2-S0) / minute_orders_research_v1 via X1. Independent comparison
root; never writes success summary.json; comparison_status always
no_ssot_compare_authorization. Bans fills→intent reconstruction.

See docs/backtest/note-true-core-tc4-x8-compare-bridge-2026-10-02.md.
"""

from .bridge import (
    COMPARISON_ID,
    COMPARISON_ROOT_NAME,
    COMPARISON_STATUS,
    CompareBridgeError,
    ComparisonOutcome,
    run_x8_compare,
    write_comparison_report,
)
from .ingest import (
    PREMATCH_SNAPSHOT_SCHEMA,
    CompareIngestError,
    PrematchSnapshot,
    load_prematch_intent_snapshot,
    snapshot_from_mapping,
)

__all__ = [
    "COMPARISON_ID",
    "COMPARISON_ROOT_NAME",
    "COMPARISON_STATUS",
    "CompareBridgeError",
    "CompareIngestError",
    "ComparisonOutcome",
    "PREMATCH_SNAPSHOT_SCHEMA",
    "PrematchSnapshot",
    "load_prematch_intent_snapshot",
    "run_x8_compare",
    "snapshot_from_mapping",
    "write_comparison_report",
]
