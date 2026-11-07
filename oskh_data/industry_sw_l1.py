# -*- coding: utf-8 -*-
"""BT root-policy facade for infra's read-only Wind / 聚源 SW-L1 readers.

1.3 writes ``vendor_wind_sw_l1/`` (harvest + merge). This fork only reads.
Root: ``resolve_source_parquet("vendor_wind_sw_l1")``. Missing configuration
or a missing map file raises; do not return an empty map.
The optional ``requirements-infra.txt`` dependency loads only when used.
"""
from __future__ import annotations

from pathlib import Path
from typing import Mapping, Optional

from common.infra.data_root import resolve_source_parquet
from oskh_data._infra import require_infra

LAKE_NAME = "vendor_wind_sw_l1"
SW_L1_MAP_NAME = "sw_l1_map.csv"
WIND_L1_MAP_NAME = "wind_l1_map.csv"


def resolve_sw_l1_root() -> Path:
    """Lake root follows OSKH_SOURCE_PARQUET_ROOT. Do not bake drive letters."""
    return Path(resolve_source_parquet(LAKE_NAME))


def normalize_industry(name: str) -> str:
    """Strip spaces and bracket suffixes for cross-source name compare."""
    return require_infra("reference_data.industry.vendor_wind_sw_l1").normalize_industry(name)


def normalize_wind_code(code: str) -> str | None:
    """Upper-case ``dddddd.SH/.SZ/.BJ``; empty or invalid → None."""
    return require_infra("reference_data.industry.vendor_wind_sw_l1").normalize_wind_code(code)


def load_wind_csv(path: Path) -> list[dict[str, str]]:
    """Read a Wind harvest CSV; accept ``申万一级行业`` or ``申万一级行业.行业级别``."""
    return require_infra("reference_data.industry.vendor_wind_sw_l1").load_wind_csv(Path(path))


def _require_map_file(path: Path, *, what: str) -> Path:
    target = Path(path)
    if target.is_file():
        return target
    raise FileNotFoundError(
        f"{what} not found: {target}. Set OSKH_SOURCE_PARQUET_ROOT to the lake "
        f"root (expected {LAKE_NAME}/{target.name}). Do not guess another disk."
    )


def load_sw_l1_map(path: Path | None = None) -> dict[str, str]:
    """``code → sw_l1`` from 聚源 ``sw_l1_map.csv``. Missing file raises."""
    target = Path(path) if path is not None else resolve_sw_l1_root() / SW_L1_MAP_NAME
    target = _require_map_file(target, what="sw_l1_map")
    return require_infra("reference_data.industry.readers").load_sw_l1_map(target)


def load_wind_l1_map(path: Path | None = None) -> dict[str, str]:
    """``code → wind_sw_l1`` from 1.3 ``wind_l1_map.csv``. Missing file raises."""
    target = Path(path) if path is not None else resolve_sw_l1_root() / WIND_L1_MAP_NAME
    target = _require_map_file(target, what="wind_l1_map")
    return require_infra("reference_data.industry.readers").load_wind_l1_map(target)


def load_industry_map() -> dict[str, str]:
    """Lake maps: 聚源 base, then Wind overlay. Both files are required."""
    root = resolve_sw_l1_root()
    _require_map_file(root / SW_L1_MAP_NAME, what="sw_l1_map")
    _require_map_file(root / WIND_L1_MAP_NAME, what="wind_l1_map")
    return require_infra("reference_data.industry.readers").load_industry_map(root)


def lookup_industry(stock: str, mapping: Mapping[str, str]) -> Optional[str]:
    """Resolve 6-digit or canonical ticker against a code→industry map (1.3 semantics)."""
    return require_infra("reference_data.industry.readers").lookup_industry(stock, mapping)


def industry_bucket_for_stock(stock: str, mapping: Mapping[str, str]) -> str:
    return require_infra("reference_data.industry.readers").industry_bucket_for_stock(stock, mapping)
