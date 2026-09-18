# -*- coding: utf-8 -*-
"""Consume 1.3 Wind / 聚源 申万一级行业 maps from the parquet lake.

1.3 writes ``vendor_wind_sw_l1/`` (harvest + merge). This fork only reads.
Root: ``resolve_source_parquet("vendor_wind_sw_l1")``. Missing configuration
or a missing map file raises; do not return an empty map.
"""
from __future__ import annotations

import csv
import re
import unicodedata
from pathlib import Path
from typing import Mapping, Optional

from common.infra.data_root import resolve_source_parquet
from oskh_data.symbol_format import to_canonical_symbol

LAKE_NAME = "vendor_wind_sw_l1"
SW_L1_MAP_NAME = "sw_l1_map.csv"
WIND_L1_MAP_NAME = "wind_l1_map.csv"


def resolve_sw_l1_root() -> Path:
    """Lake root follows OSKH_SOURCE_PARQUET_ROOT. Do not bake drive letters."""
    return Path(resolve_source_parquet(LAKE_NAME))


def normalize_industry(name: str) -> str:
    """Strip spaces and bracket suffixes for cross-source name compare."""
    text = unicodedata.normalize("NFKC", name)
    text = re.sub(r"[\s（）\(\)]+", "", text)
    return text.strip()


def normalize_wind_code(code: str) -> str | None:
    """Upper-case ``dddddd.SH/.SZ/.BJ``; empty or invalid → None."""
    if not code:
        return None
    text = code.strip().upper()
    if not re.match(r"^\d{6}\.(SH|SZ|BJ)$", text):
        return None
    return text


def _code_key(raw: str) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""
    canon = to_canonical_symbol(text)
    return canon if canon else (normalize_wind_code(text) or text.upper())


def load_wind_csv(path: Path) -> list[dict[str, str]]:
    """Read a Wind harvest CSV; accept ``申万一级行业`` or ``申万一级行业.行业级别``."""
    with Path(path).open(encoding="utf-8", newline="") as fh:
        rows: list[dict[str, str]] = []
        for row in csv.DictReader(fh):
            code = name = industry = None
            for key, value in row.items():
                if value is None:
                    continue
                header = (key or "").strip()
                if header.startswith("Wind") or header.startswith("代码"):
                    code = value.strip() or None
                elif "简称" in header:
                    name = value.strip() or None
                elif header == "申万一级行业" or header.startswith("申万一级行业"):
                    industry = value.strip() or None
                elif "申万" in header and "行业" in header and "级别" not in header:
                    industry = value.strip() or None
            if code and industry:
                rows.append(
                    {"Wind代码": code, "证券简称": name or "", "申万一级行业": industry}
                )
        return rows


def _load_map_csv(path: Path, industry_col: str) -> dict[str, str]:
    out: dict[str, str] = {}
    with Path(path).open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            code = _code_key(row.get("code_gildata") or row.get("Wind代码") or "")
            industry = str(row.get(industry_col) or "").strip()
            if code and industry:
                out[code] = industry
    return out


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
    return _load_map_csv(_require_map_file(target, what="sw_l1_map"), "sw_l1")


def load_wind_l1_map(path: Path | None = None) -> dict[str, str]:
    """``code → wind_sw_l1`` from 1.3 ``wind_l1_map.csv``. Missing file raises."""
    target = Path(path) if path is not None else resolve_sw_l1_root() / WIND_L1_MAP_NAME
    return _load_map_csv(_require_map_file(target, what="wind_l1_map"), "wind_sw_l1")


def load_industry_map() -> dict[str, str]:
    """Lake maps: 聚源 base, then Wind overlay. Both files are required."""
    out = dict(load_sw_l1_map())
    out.update(load_wind_l1_map())
    return out


def lookup_industry(stock: str, mapping: Mapping[str, str]) -> Optional[str]:
    """Resolve 6-digit or canonical ticker against a code→industry map (1.3 semantics)."""
    text = (stock or "").strip()
    if not text or not mapping:
        return None
    if text in mapping:
        return mapping[text]
    key6 = text[:6] if len(text) >= 6 else text
    if key6 in mapping:
        return mapping[key6]
    if len(text) >= 6:
        tail = text[-6:]
        if tail in mapping:
            return mapping[tail]
    if len(key6) == 6:
        for map_key, value in mapping.items():
            item = str(map_key).strip()
            if len(item) >= 6 and item[:6] == key6:
                return str(value).strip()
    return None


def industry_bucket_for_stock(stock: str, mapping: Mapping[str, str]) -> str:
    return lookup_industry(stock, mapping) or "_UNMAPPED_"
