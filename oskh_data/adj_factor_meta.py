"""adj_factor.parquet freshness sidecar (adj_factor.meta.json)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Union

import pandas as pd

from oskh_data.pandas_typing import as_timestamp, normalize_timestamp

PathLike = Union[str, Path]


def adj_factor_meta_path(parquet_path: PathLike) -> Path:
    """``adj_factor.parquet`` → ``adj_factor.meta.json`` (same directory)."""
    p = Path(parquet_path)
    return p.with_name(f"{p.stem}.meta.json")


def write_adj_factor_meta(
    parquet_path: PathLike,
    df: Optional[pd.DataFrame] = None,
    *,
    source: str,
    build_time: Optional[str] = None,
    data_max_date: Optional[str] = None,
    stock_count: Optional[int] = None,
) -> Path:
    """Write freshness sidecar after parquet save."""
    meta_path = adj_factor_meta_path(parquet_path)
    if data_max_date is None and df is not None and not df.empty and "date" in df.columns:
        max_ts = pd.to_datetime(df["date"], errors="coerce").max()
        data_max_date = (
            None if pd.isna(max_ts) else as_timestamp(max_ts).strftime("%Y-%m-%d")
        )
    if stock_count is None and df is not None and not df.empty and "stock_code" in df.columns:
        stock_count = int(df["stock_code"].nunique())
    if stock_count is None:
        stock_count = 0
    if build_time is None:
        build_time = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    payload: dict[str, Any] = {
        "data_max_date": data_max_date,
        "build_time": build_time,
        "source": str(source),
        "stock_count": stock_count,
    }
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta_path


def read_adj_factor_data_max_date(parquet_path: PathLike) -> Optional[pd.Timestamp]:
    """Read ``data_max_date`` from sidecar; return None if missing/invalid."""
    meta_path = adj_factor_meta_path(parquet_path)
    if not meta_path.is_file():
        return None
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        raw = meta.get("data_max_date")
        if not raw:
            return None
        ts = pd.Timestamp(str(raw))
        return None if bool(pd.isna(ts)) else normalize_timestamp(ts)
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None


__all__ = [
    "adj_factor_meta_path",
    "read_adj_factor_data_max_date",
    "write_adj_factor_meta",
]
