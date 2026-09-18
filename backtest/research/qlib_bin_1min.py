# -*- coding: utf-8 -*-
"""Read qlib ``features/*.1min.bin`` as compact minute frames. Does not import qlib.

These bins were dumped from the none-adjusted 1m lake. Calendar is
``calendars/1min.txt``. Reuses ``read_qlib_bin`` / ``qlib_inst_dir``.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from backtest.research.csv_common import _progress
from backtest.research.qlib_bin_daily import calendar_slice, qlib_inst_dir, read_qlib_bin
from oskh_data.symbol_format import to_canonical_symbol


def load_qlib_1min_calendar(qlib_root: Path | str) -> list[str]:
    path = Path(qlib_root) / "calendars" / "1min.txt"
    if not path.is_file():
        raise FileNotFoundError(f"qlib 1min calendar missing: {path}")
    return [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def _iso_bounds(start: date, end: date) -> tuple[str, str]:
    return f"{start.isoformat()} 00:00:00", f"{end.isoformat()} 23:59:59"


def _read_one(
    code: str,
    feat_root: Path,
    dates: np.ndarray,
    hms: np.ndarray,
    i0: int,
    i1: int,
) -> Optional[pd.DataFrame]:
    inst = qlib_inst_dir(code)
    if inst is None:
        return None
    folder = feat_root / inst
    close = read_qlib_bin(folder / "close.1min.bin", i0, i1)
    if close.empty:
        return None
    cols = {"close": close}
    for name in ("open", "high"):
        series = read_qlib_bin(folder / f"{name}.1min.bin", i0, i1)
        cols[name] = series if not series.empty else close
    frame = pd.DataFrame(cols).replace([np.inf, -np.inf], np.nan).dropna(subset=["close"])
    if frame.empty:
        return None
    idx = frame.index.to_numpy()
    return pd.DataFrame(
        {
            "date": dates[idx],
            "hm": hms[idx],
            "open": frame["open"].to_numpy(dtype=np.float64),
            "high": frame["high"].to_numpy(dtype=np.float64),
            "close": frame["close"].to_numpy(dtype=np.float64),
        }
    )


def daily_closes_from_minutes(minute: dict[str, pd.DataFrame]) -> dict[str, dict[date, float]]:
    daily: dict[str, dict[date, float]] = {}
    for symbol, frame in minute.items():
        if frame is None or frame.empty:
            continue
        last = frame.groupby("date", sort=True)["close"].last()
        daily[symbol] = {day: float(close) for day, close in last.items()}
    return daily


def load_qlib_bin_1min_bars(
    codes: set[str] | list[str],
    start: date,
    end: date,
    *,
    qlib_root: Path | str,
    workers: int = 16,
    preload_days: int = 20,
) -> dict[str, pd.DataFrame]:
    """Load none-adjusted ``$open/$high/$close`` 1min bins as v7 frames."""
    root = Path(qlib_root)
    feat = root / "features"
    if not feat.is_dir():
        raise FileNotFoundError(f"qlib 1min features missing: {feat}")
    cal = load_qlib_1min_calendar(root)
    load_start = start - timedelta(days=max(0, int(preload_days)))
    start_iso, end_iso = _iso_bounds(load_start, end)
    try:
        i0, i1 = calendar_slice(cal, start_iso, end_iso)
    except SystemExit as exc:
        raise SystemExit(f"{exc} under {root}") from exc
    stamps = pd.to_datetime(cal)
    dates = stamps.date
    hms = (stamps.hour * 60 + stamps.minute).to_numpy(dtype=np.int32)
    out: dict[str, pd.DataFrame] = {}
    codes_list = sorted({to_canonical_symbol(str(code)) for code in codes})
    n = max(1, int(workers))
    with ThreadPoolExecutor(max_workers=n) as pool:
        futs = {pool.submit(_read_one, code, feat, dates, hms, i0, i1): code for code in codes_list}
        done = 0
        total = len(futs)
        for fut in as_completed(futs):
            done += 1
            _progress(done, total, "qlib 1min bins")
            code = futs[fut]
            try:
                frame = fut.result()
            except Exception:
                continue
            if frame is not None and not frame.empty:
                out[code] = frame
    return out
