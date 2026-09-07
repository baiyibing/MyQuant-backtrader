# -*- coding: utf-8 -*-
"""Read-only parquet metadata helpers."""
from __future__ import annotations

from pathlib import Path
from typing import Optional, cast

import pandas as pd


def get_parquet_latest_date(file_path: Path) -> Optional[pd.Timestamp]:
    """Return the latest date in a hive parquet via pyarrow metadata, or None."""
    try:
        import pyarrow.parquet as pq

        meta = pq.read_metadata(file_path)
        max_ts: Optional[pd.Timestamp] = None
        for rg_idx in range(meta.num_row_groups):
            rg = meta.row_group(rg_idx)
            for col_idx in range(rg.num_columns):
                col = rg.column(col_idx)
                stats = col.statistics
                if stats is None or stats.max is None:
                    continue
                col_name = col.path_in_schema
                if "index_level" in col_name:
                    candidate = pd.Timestamp(stats.max)
                    if not bool(pd.isna(candidate)) and (
                        max_ts is None or candidate > max_ts
                    ):
                        max_ts = cast(pd.Timestamp, candidate)
                elif col_name == "time":
                    ts = pd.Timestamp(stats.max, unit="ms")
                    if not bool(pd.isna(ts)) and (max_ts is None or ts > max_ts):
                        max_ts = cast(pd.Timestamp, ts)
        if max_ts is not None:
            return max_ts.normalize()
    except Exception:
        pass
    return None
