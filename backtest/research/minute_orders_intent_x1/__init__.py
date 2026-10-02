"""TC2 narrow X1: out-of-core a-priori frozen LIMIT batch + named consumer.

Adapter identity only. Reuses research contract v0 (L2-S0) and backend
minute_orders_research_v1 unchanged — does not mint a new economic contract
or backend_id. See docs/backtest/note-true-core-tc2-x1-intent-adapter-2026-10-02.md.
"""

from .builders import (
    ADAPTER_ID,
    CancelIntent,
    IntentBuildError,
    LimitIntent,
    build_cancel_order,
    build_submit_order,
    freeze_command_batch,
)
from .consumer import (
    FrozenBatchArtifacts,
    FrozenBatchRun,
    assemble_run_input,
    run_x1_frozen_batch,
    run_x1_frozen_batch_with_artifacts,
)

__all__ = [
    "ADAPTER_ID",
    "CancelIntent",
    "FrozenBatchArtifacts",
    "FrozenBatchRun",
    "IntentBuildError",
    "LimitIntent",
    "assemble_run_input",
    "build_cancel_order",
    "build_submit_order",
    "freeze_command_batch",
    "run_x1_frozen_batch",
    "run_x1_frozen_batch_with_artifacts",
]
