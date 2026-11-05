"""Host root selection for infra's persisted offline L2 research aggregates."""
from __future__ import annotations

from pathlib import Path

from l2_analytics._infra import require_l2
from l2_analytics.paths import cluster_agg_path, daily_metrics_path


def build_aggregates_for_date(con, *, date: str, out_root: str | Path, force: bool = False):
    return require_l2("aggregates").build_aggregates_for_date(
        con, date=date, out_root=out_root, force=force,
    )


def build_all_aggregates(
    parquet_root: str | Path | None = None, *, dates: list[str] | None = None,
    force: bool = False, memory_limit: str = "18GB",
):
    implementation = require_l2("aggregates")
    if parquet_root:
        root = Path(parquet_root).resolve()
    else:
        from common.infra.data_root import resolve_l2_parquet_root

        root = resolve_l2_parquet_root()
    return implementation.build_all_aggregates(
        root, dates=dates, force=force, memory_limit=memory_limit,
    )


def __getattr__(name: str):
    if name in ("DAILY_METRICS_SQL", "CLUSTER_AGG_SQL"):
        return getattr(require_l2("aggregates"), name)
    raise AttributeError(name)
