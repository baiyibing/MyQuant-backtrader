"""Hive layout helpers for ``l2_parquet`` (date=YYYY-MM-DD/…).

Canonical day layout (v5.9+), under the market-data tree (not ``data/`` DBs):
  ``<l2_root>/date=YYYY-MM-DD/main.parquet``
  ``<l2_root>/date=YYYY-MM-DD/order.parquet``
  ``<l2_root>/date=YYYY-MM-DD/daily_metrics.parquet``
  ``<l2_root>/date=YYYY-MM-DD/cluster_agg.parquet``

``<l2_root>`` resolved by ``resolve_l2_parquet_root()``: ``OSKH_L2_PARQUET_ROOT`` env var
(L2-specific override, ``<container>/l2_parquet``) else ``resolve_parquet_container()/l2_parquet``.

Legacy flat parts (``{date}.part-NNNN.{main,order}.parquet``) remain readable
via ``db.connect`` during migration.
"""

from __future__ import annotations

from pathlib import Path

from l2_analytics._infra import require_l2


def day_dir(root: Path, date: str) -> Path:
    return require_l2("ingest.paths").day_dir(root, date)


def main_parquet_path(root: Path, date: str) -> Path:
    return require_l2("ingest.paths").main_parquet_path(root, date)


def order_parquet_path(root: Path, date: str) -> Path:
    return require_l2("ingest.paths").order_parquet_path(root, date)


def daily_metrics_path(root: Path, date: str) -> Path:
    return require_l2("ingest.paths").daily_metrics_path(root, date)


def cluster_agg_path(root: Path, date: str) -> Path:
    return require_l2("ingest.paths").cluster_agg_path(root, date)


def rel_main_part(date: str) -> str:
    return require_l2("ingest.paths").rel_main_part(date)


def rel_order_part(date: str) -> str:
    return require_l2("ingest.paths").rel_order_part(date)


def hive_main_glob(root: Path) -> str:
    return (root / "date=*/main.parquet").as_posix()


def hive_order_glob(root: Path) -> str:
    return (root / "date=*/order.parquet").as_posix()


def hive_daily_metrics_glob(root: Path) -> str:
    return (root / "date=*/daily_metrics.parquet").as_posix()


def hive_cluster_agg_glob(root: Path) -> str:
    return (root / "date=*/cluster_agg.parquet").as_posix()


def legacy_flat_main_glob(root: Path) -> str:
    return (root / "*.main.parquet").as_posix()


def legacy_flat_order_glob(root: Path) -> str:
    return (root / "*.order.parquet").as_posix()


def has_hive_main(root: Path) -> bool:
    return any(root.glob("date=*/main.parquet"))


def has_legacy_flat_main(root: Path) -> bool:
    return any(root.glob("*.main.parquet"))


def list_legacy_flat_parts(root: Path, date: str) -> tuple[list[Path], list[Path]]:
    return require_l2("ingest.paths").list_legacy_flat_parts(root, date)
