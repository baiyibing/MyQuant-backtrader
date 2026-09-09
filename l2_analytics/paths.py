"""Hive layout helpers for ``l2_parquet`` (date=YYYY-MM-DD/…).

Canonical day layout (v5.9+), under the market-data tree (not ``data/`` DBs):
  ``<l2_root>/date=YYYY-MM-DD/main.parquet``
  ``<l2_root>/date=YYYY-MM-DD/order.parquet``
  ``<l2_root>/date=YYYY-MM-DD/daily_metrics.parquet``
  ``<l2_root>/date=YYYY-MM-DD/cluster_agg.parquet``

``<l2_root>`` resolved by ``resolve_l2_parquet_root()``: ``OSKH_L2_PARQUET_ROOT`` env var
(L2-specific override, e.g. ``F:\\stock_data\\l2_parquet``) else ``resolve_data_root()/stock_data/l2_parquet``.

Legacy flat parts (``{date}.part-NNNN.{main,order}.parquet``) remain readable
via ``db.connect`` during migration.
"""

from __future__ import annotations

from pathlib import Path

_DATE_PREFIX = "date="


def day_dir(root: Path, date: str) -> Path:
    return root / f"{_DATE_PREFIX}{date}"


def main_parquet_path(root: Path, date: str) -> Path:
    return day_dir(root, date) / "main.parquet"


def order_parquet_path(root: Path, date: str) -> Path:
    return day_dir(root, date) / "order.parquet"


def daily_metrics_path(root: Path, date: str) -> Path:
    return day_dir(root, date) / "daily_metrics.parquet"


def cluster_agg_path(root: Path, date: str) -> Path:
    return day_dir(root, date) / "cluster_agg.parquet"


def rel_main_part(date: str) -> str:
    return f"{_DATE_PREFIX}{date}/main.parquet"


def rel_order_part(date: str) -> str:
    return f"{_DATE_PREFIX}{date}/order.parquet"


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
    mains = sorted(root.glob(f"{date}.part-*.main.parquet"))
    orders = sorted(root.glob(f"{date}.part-*.order.parquet"))
    return mains, orders
