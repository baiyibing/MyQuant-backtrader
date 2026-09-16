# -*- coding: utf-8 -*-
"""CSV daily bar loader + period-env hygiene for both engines.

三职责：日线湖装载（``load_daily_bars`` / ``_read_one_daily``）、warmup 起点、
以及 ``warn_stale_period_env`` 对残留 ``OSKH_PERIOD_*`` 的告警。本模块不 import
任一引擎文件；常量 ``WARMUP_DAYS`` 等来自 ``csv_common``。
"""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import pyarrow.compute as pc
import pyarrow.parquet as pq

from backtest.research.csv_common import WARMUP_DAYS, _progress
from backtest.research.market_layer import utc_ms_range
from common.infra.data_root import resolve_period_root
from oskh_data.symbol_format import to_partition_key

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

_PERIOD_ENV_KEYS = (
    "OSKH_PERIOD_1D_ROOT",
    "OSKH_PERIOD_1M_ROOT",
    "OSKH_INDEX_DAILY_ROOT",
    "OSKH_ETF_DAILY_ROOT",
    "OSKH_SOURCE_PARQUET_ROOT",
)

def warmup_start(start: str, days: int = WARMUP_DAYS) -> str:
    return (pd.Timestamp(start) - pd.Timedelta(days=int(days))).strftime("%Y%m%d")

def warn_stale_period_env() -> None:
    hit = [k for k in _PERIOD_ENV_KEYS if os.environ.get(k)]
    if hit:
        print(
            f"[warn] {', '.join(hit)} is set; lake may ignore F:\\stock_data\\.authority",
            flush=True,
        )


def _read_one_daily(
    code: str, root: Path, start: str, end: str
) -> Optional[pd.DataFrame]:
    path = root / f"symbol={to_partition_key(code)}" / "data.parquet"
    if not path.is_file():
        return None
    t0, t1 = utc_ms_range(start, end)
    try:
        columns = ["time", "open", "high", "low", "close"]
        has_volume = "volume" in pq.read_schema(path).names
        table = pq.read_table(
            path, columns=columns + (["volume"] if has_volume else [])
        )
        table = table.filter((pc.field("time") >= t0) & (pc.field("time") <= t1))
    except Exception:
        return None
    if table.num_rows == 0:
        return None
    ms = table["time"].to_numpy()
    idx = pd.to_datetime(ms, unit="ms", utc=True).tz_localize(None).normalize()
    out = pd.DataFrame(
        {
            "open": table["open"].to_numpy(),
            "high": table["high"].to_numpy(),
            "low": table["low"].to_numpy(),
            "close": table["close"].to_numpy(),
            **(
                {"_volume": table["volume"].to_numpy()}
                if has_volume
                else {}
            ),
        },
        index=idx,
    ).astype(np.float64)
    out = out[~out.index.duplicated(keep="last")].sort_index()
    if has_volume:
        out = out.loc[out["_volume"] != 0].drop(columns="_volume")
    return out if not out.empty else None

def load_daily_bars(
    codes: set[str], start: str, end: str, *, workers: int = 16
) -> dict[str, pd.DataFrame]:
    """不复权日线（与分钟链 adjust_type='none' 对齐），index=交易日 00:00。"""
    root = resolve_period_root("1d") / "dividend_type=none"
    out: dict[str, pd.DataFrame] = {}
    codes_list = sorted(codes)
    n = max(1, int(workers))
    with ThreadPoolExecutor(max_workers=n) as pool:
        futs = {
            pool.submit(_read_one_daily, c, root, start, end): c for c in codes_list
        }
        done = 0
        total = len(futs)
        for fut in as_completed(futs):
            done += 1
            _progress(done, total, "daily lake")
            code = futs[fut]
            try:
                df = fut.result()
            except Exception:
                continue
            if df is not None and not df.empty:
                out[code] = df
    return out

