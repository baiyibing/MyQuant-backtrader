# -*- coding: utf-8 -*-
"""topk_app_dropout: new strategy — app pool ∩ qlib TopK.

Strategy 7 is untouched. This book has its own runner
``csv_minute_backtest_topk_app_dropout.py``. Buy names must be on the app
day-list and in that day's qlib TopK (default 50, ``pred_minus_one``).
Not registered in csv_strategy_books (1–10 shared engine).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable, Literal, Mapping, Sequence

import pandas as pd

from backtest.research.csv_pool import (
    is_repo_stock_pool,
    parse_pool_csv_entries,
)

BOOK_TAG = "topk_app_dropout"
DEFAULT_TOPK = 50
ASOF_CHOICES = ("pred_minus_one", "identity")
INSTRUMENT_RE = re.compile(r"^(?:SH|SZ|BJ)?(\d{6})$", re.IGNORECASE)
REQUIRED_PRED_COLUMNS = {"datetime", "instrument", "score"}


def _bare(code: str) -> str:
    text = str(code or "").strip()
    if "." in text:
        text = text.split(".", 1)[0]
    match = INSTRUMENT_RE.fullmatch(text) or re.search(r"(\d{6})", text)
    return match.group(1) if match else ""


def load_pred_frame(path: Path) -> pd.DataFrame:
    """Load a MyQuant pred CSV (datetime, instrument, score). CSV only."""
    frame = pd.read_csv(Path(path), dtype={"instrument": str})
    missing = sorted(REQUIRED_PRED_COLUMNS.difference(frame.columns))
    if missing:
        raise ValueError(f"prediction missing column(s): {', '.join(missing)}")
    out = frame.loc[:, ["datetime", "instrument", "score"]].copy()
    out["datetime"] = pd.to_datetime(out["datetime"], errors="raise").dt.normalize()
    out["instrument"] = out["instrument"].astype(str)
    out["score"] = pd.to_numeric(out["score"], errors="raise")
    return out


def ranked_day_codes(day: pd.DataFrame) -> list[str]:
    """Bare codes, score desc then instrument asc; first row wins ties."""
    ordered = day.sort_values(
        ["score", "instrument"], ascending=[False, True], kind="mergesort"
    )
    out: list[str] = []
    seen: set[str] = set()
    for instrument, _score in zip(ordered["instrument"], ordered["score"], strict=True):
        match = INSTRUMENT_RE.fullmatch(str(instrument))
        if match is None:
            continue
        code = match.group(1)
        if code in seen:
            continue
        seen.add(code)
        out.append(code)
    return out


def qlib_topn_by_buy_day(
    predictions: pd.DataFrame,
    *,
    topk: int = DEFAULT_TOPK,
    asof: Literal["pred_minus_one", "identity"] = "pred_minus_one",
) -> dict[str, list[str]]:
    """Map buy-date YYYYMMDD → qlib TopK bare codes (export_daily_pool asof)."""
    if topk <= 0:
        raise ValueError("topk must be greater than zero")
    if asof not in ASOF_CHOICES:
        raise ValueError(f"unsupported asof: {asof}")
    dates: list[pd.Timestamp] = []
    day_codes: dict[pd.Timestamp, list[str]] = {}
    for pred_date, day in predictions.groupby("datetime", sort=True):
        ts = pd.Timestamp(pred_date)
        dates.append(ts)
        day_codes[ts] = ranked_day_codes(day)[:topk]
    out: dict[str, list[str]] = {}
    for index, pred_date in enumerate(dates):
        if asof == "pred_minus_one":
            if index + 1 == len(dates):
                continue
            buy = dates[index + 1]
        else:
            buy = pred_date
        out[f"{buy:%Y%m%d}"] = list(day_codes[pred_date])
    return out


def _iter_app_ymds(app_dir: Path, start: str, end: str) -> Iterable[str]:
    for path in sorted(Path(app_dir).glob("*.csv")):
        stem = path.stem
        if len(stem) == 8 and stem.isdigit() and start <= stem <= end:
            yield stem


def intersect_app_qlib(
    app_dir: Path,
    qlib_topn: Mapping[str, Sequence[str]],
    *,
    start: str,
    end: str,
) -> dict[str, list[tuple[str, str]]]:
    """Keep app file order; drop names not in that day's qlib TopK.

    Days present in the app window but missing from ``qlib_topn`` are omitted
    (no qlib cross-section → cannot gate). Empty intersection stays as [].
    """
    out: dict[str, list[tuple[str, str]]] = {}
    for ymd in _iter_app_ymds(app_dir, start, end):
        if ymd not in qlib_topn:
            continue
        allowed = { _bare(code) for code in qlib_topn[ymd] }
        kept: list[tuple[str, str]] = []
        seen: set[str] = set()
        for canon, name in parse_pool_csv_entries(Path(app_dir) / f"{ymd}.csv"):
            bare = _bare(canon)
            if not bare or bare not in allowed or bare in seen:
                continue
            seen.add(bare)
            kept.append((canon, name))
        out[ymd] = kept
    return out


def overlap_stats(days: Mapping[str, Sequence[tuple[str, str]]]) -> dict[str, Any]:
    sizes = [len(rows) for rows in days.values()]
    if not sizes:
        return {
            "days": 0,
            "hit_days": 0,
            "empty_days": 0,
            "intersect_min": 0,
            "intersect_median": 0,
            "intersect_max": 0,
            "intersect_mean": 0.0,
        }
    ordered = sorted(sizes)
    hit = sum(1 for n in sizes if n > 0)
    return {
        "days": len(sizes),
        "hit_days": hit,
        "empty_days": len(sizes) - hit,
        "intersect_min": ordered[0],
        "intersect_median": ordered[len(ordered) // 2],
        "intersect_max": ordered[-1],
        "intersect_mean": sum(sizes) / len(sizes),
    }


def write_topk_app_dropout_pool(
    days: Mapping[str, Sequence[tuple[str, str]]],
    out_dir: Path,
    *,
    repo: Path | None = None,
    write_empty: bool = True,
) -> list[Path]:
    """Write headerless ``code[,name]`` CSVs. Never writes repo ``stock_pool/``."""
    root = Path(out_dir)
    if is_repo_stock_pool(root, repo=repo):
        raise ValueError(f"refusing to write into stock_pool/: {root}")
    root.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for ymd in sorted(days):
        rows = list(days[ymd])
        if not rows and not write_empty:
            continue
        lines: list[str] = []
        for canon, name in rows:
            bare = _bare(canon)
            if name:
                lines.append(f"{bare},{name}\n")
            else:
                lines.append(f"{bare}\n")
        dest = root / f"{ymd}.csv"
        dest.write_text("".join(lines), encoding="utf-8", newline="\n")
        written.append(dest)
    return written


def write_overlap_report(path: Path, payload: Mapping[str, Any]) -> None:
    Path(path).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
