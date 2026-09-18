# -*- coding: utf-8 -*-
"""Read qlib ``features/*.day.bin`` as daily OHLCV frames. Does not import qlib.

Bin layout matches ``qlib.utils.read_bin``: little-endian float32 header
(ref start index) then one float32 per calendar day. Calendar is
``calendars/day.txt``. ``$close`` in this dump is 后复权; ``$adjclose`` is none.
"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from backtest.research.csv_common import _progress
from oskh_data.symbol_format import to_canonical_symbol

_CANON = re.compile(r"^(\d{6})\.(SH|SZ|BJ)$", re.IGNORECASE)
_QLIB = re.compile(r"^(SH|SZ|BJ)(\d{6})$", re.IGNORECASE)


def qlib_inst_dir(code: str) -> Optional[str]:
    """``600519.SH`` / ``SH600519`` → ``sh600519`` feature folder name."""
    text = str(code or "").strip()
    if not text:
        return None
    if "_" in text:
        text = to_canonical_symbol(text)
    m = _CANON.fullmatch(text)
    if m:
        return f"{m.group(2).lower()}{m.group(1)}"
    m = _QLIB.fullmatch(text)
    if m:
        return f"{m.group(1).lower()}{m.group(2)}"
    return None


def read_qlib_bin(path: Path, start_index: int, end_index: int) -> pd.Series:
    if not path.is_file():
        return pd.Series(dtype=np.float32)
    with path.open("rb") as f:
        raw = f.read(4)
        if len(raw) < 4:
            return pd.Series(dtype=np.float32)
        ref = int(np.frombuffer(raw, dtype="<f")[0])
        si = max(ref, start_index)
        if si > end_index:
            return pd.Series(dtype=np.float32)
        f.seek(4 * (si - ref) + 4)
        data = np.frombuffer(f.read(4 * (end_index - si + 1)), dtype="<f")
    return pd.Series(data, index=range(si, si + len(data)))


def load_qlib_calendar(qlib_root: Path | str) -> list[str]:
    path = Path(qlib_root) / "calendars" / "day.txt"
    if not path.is_file():
        raise FileNotFoundError(f"qlib calendar missing: {path}")
    return [
        ln.strip() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()
    ]


def _ymd_to_iso(ymd: str) -> str:
    digits = "".join(ch for ch in str(ymd) if ch.isdigit())
    if len(digits) < 8:
        raise ValueError(f"cannot parse YYYYMMDD: {ymd!r}")
    return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}"


def calendar_slice(cal: list[str], start_iso: str, end_iso: str) -> tuple[int, int]:
    """Clamp ``[start, end]`` onto trading days: first ``>= start``, last ``<= end``."""
    i0 = next((i for i, d in enumerate(cal) if d >= start_iso), None)
    i1 = None
    for i in range(len(cal) - 1, -1, -1):
        if cal[i] <= end_iso:
            i1 = i
            break
    if i0 is None or i1 is None or i0 > i1:
        raise SystemExit(f"qlib calendar missing {start_iso} or {end_iso}")
    return i0, i1


def _read_one(
    code: str, feat_root: Path, cal: list[str], i0: int, i1: int
) -> Optional[pd.DataFrame]:
    inst = qlib_inst_dir(code)
    if inst is None:
        return None
    folder = feat_root / inst
    close = read_qlib_bin(folder / "close.day.bin", i0, i1)
    if close.empty:
        return None
    cols = {"close": close}
    for name in ("open", "high", "low"):
        s = read_qlib_bin(folder / f"{name}.day.bin", i0, i1)
        cols[name] = s if not s.empty else close
    df = pd.DataFrame(cols).sort_index()
    df = df.replace([np.inf, -np.inf], np.nan).dropna(subset=["close"])
    if df.empty:
        return None
    idx = pd.to_datetime([cal[int(i)] for i in df.index]).normalize()
    out = pd.DataFrame(
        {
            "open": df["open"].to_numpy(dtype=np.float64),
            "high": df["high"].to_numpy(dtype=np.float64),
            "low": df["low"].to_numpy(dtype=np.float64),
            "close": df["close"].to_numpy(dtype=np.float64),
        },
        index=idx,
    )
    return out[~out.index.duplicated(keep="last")].sort_index()


def load_qlib_bin_daily_bars(
    codes: set[str],
    start: str,
    end: str,
    *,
    qlib_root: Path | str,
    workers: int = 16,
) -> dict[str, pd.DataFrame]:
    """Load ``$open/$high/$low/$close`` (后复权) from a qlib data root."""
    root = Path(qlib_root)
    feat = root / "features"
    if not feat.is_dir():
        raise FileNotFoundError(f"qlib features missing: {feat}")
    cal = load_qlib_calendar(root)
    start_iso, end_iso = _ymd_to_iso(start), _ymd_to_iso(end)
    try:
        i0, i1 = calendar_slice(cal, start_iso, end_iso)
    except SystemExit as exc:
        raise SystemExit(f"{exc} under {root}") from exc
    out: dict[str, pd.DataFrame] = {}
    codes_list = sorted(codes)
    n = max(1, int(workers))
    with ThreadPoolExecutor(max_workers=n) as pool:
        futs = {pool.submit(_read_one, c, feat, cal, i0, i1): c for c in codes_list}
        done = 0
        total = len(futs)
        for fut in as_completed(futs):
            done += 1
            _progress(done, total, "qlib bins")
            code = futs[fut]
            try:
                df = fut.result()
            except Exception:
                continue
            if df is not None and not df.empty:
                out[code] = df
    return out
