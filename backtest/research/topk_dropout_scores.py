"""Load TopkDropout cross-section scores (no qlib).

``--scores-dir``: ``YYYYMMDD.csv`` filename = buy day; columns bare code + score.
``--pred-csv``: multi-day prediction file; buy day T uses pred[T-1] (pred_minus_one).
Codes normalized to ``XXXXXX.SH|SZ|BJ``.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Mapping, Optional

import pandas as pd

from oskh_core.a_share_symbol_normalize import canonical_from_bare_code

_BARE_RE = re.compile(r"(\d{6})")
_SCORE_COL_CANDIDATES = ("score", "pred", "prediction", "y_pred", "pred_score")
_CODE_COL_CANDIDATES = (
    "code",
    "instrument",
    "symbol",
    "stock_code",
    "ticker",
    "证券代码",
    "代码",
)
_DATE_COL_CANDIDATES = ("datetime", "date", "pred_date", "trade_date", "dt")


def _bare_or_canon(raw: str) -> Optional[str]:
    text = str(raw or "").strip().strip('"').strip("'").upper()
    if not text:
        return None
    # pandas read_csv turns 000048 into int 48; pad so SZ/BJ leading zeros survive.
    if re.fullmatch(r"\d{1,6}", text):
        text = text.zfill(6)
    # Already canonical?
    if re.fullmatch(r"\d{6}\.(SH|SZ|BJ)", text):
        return text
    # QLib SH600000 / SZ000001
    if re.fullmatch(r"(SH|SZ|BJ)\d{6}", text):
        prefix, digits = text[:2], text[2:]
        return f"{digits}.{prefix}"
    m = _BARE_RE.search(text)
    if not m:
        return None
    return canonical_from_bare_code(m.group(1))


def _pick_col(columns, candidates: tuple[str, ...]) -> Optional[str]:
    lower = {str(c).strip().lower(): c for c in columns}
    for name in candidates:
        if name.lower() in lower:
            return lower[name.lower()]
    return None


def _frame_to_score_map(df: pd.DataFrame) -> dict[str, float]:
    if df.empty:
        return {}
    code_col = _pick_col(df.columns, _CODE_COL_CANDIDATES)
    score_col = _pick_col(df.columns, _SCORE_COL_CANDIDATES)
    if code_col is None or score_col is None:
        # Fallback: first two columns
        if len(df.columns) < 2:
            raise ValueError("scores CSV needs code + score columns")
        code_col = df.columns[0]
        score_col = df.columns[1]
    out: dict[str, float] = {}
    for raw_code, raw_score in zip(df[code_col], df[score_col]):
        code = _bare_or_canon(raw_code)
        if code is None:
            continue
        try:
            if pd.isna(raw_score):
                continue
            out[code] = float(raw_score)
        except (TypeError, ValueError):
            continue
    return out


def load_scores_dir(path: Path | str) -> dict[str, dict[str, float]]:
    """Map buy-day YYYYMMDD → {canonical_code: score}."""
    root = Path(path)
    if not root.is_dir():
        raise FileNotFoundError(f"scores-dir not found: {root}")
    by_day: dict[str, dict[str, float]] = {}
    for csv_path in sorted(root.glob("*.csv")):
        stem = csv_path.stem
        digits = "".join(ch for ch in stem if ch.isdigit())
        if len(digits) < 8:
            continue
        ds = digits[:8]
        df = pd.read_csv(csv_path, dtype=str)
        by_day[ds] = _frame_to_score_map(df)
    if not by_day:
        raise FileNotFoundError(f"no YYYYMMDD.csv scores under {root}")
    return by_day


def load_pred_csv(path: Path | str) -> dict[str, dict[str, float]]:
    """Load multi-day pred CSV → buy-day scores via pred_minus_one.

    For sorted unique pred dates D0 < D1 < …, scores for buy day Di (i≥1)
    come from pred day D{i-1}. Also exposes lookup by exact pred day under the
    same keys when only one mapping is needed for tests: buy_day == next pred.
    """
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"pred-csv not found: {p}")
    df = pd.read_csv(p, dtype=str)
    date_col = _pick_col(df.columns, _DATE_COL_CANDIDATES)
    if date_col is None:
        raise ValueError(f"pred-csv missing date column: {p}")
    code_col = _pick_col(df.columns, _CODE_COL_CANDIDATES)
    score_col = _pick_col(df.columns, _SCORE_COL_CANDIDATES)
    if code_col is None or score_col is None:
        raise ValueError(f"pred-csv missing code/score columns: {p}")

    work = df[[date_col, code_col, score_col]].copy()
    work["_ds"] = pd.to_datetime(work[date_col]).dt.strftime("%Y%m%d")
    pred_by_day: dict[str, dict[str, float]] = {}
    for ds, sub in work.groupby("_ds", sort=True):
        pred_by_day[str(ds)] = _frame_to_score_map(
            sub.rename(columns={code_col: "code", score_col: "score"})[["code", "score"]]
        )
    pred_days = sorted(pred_by_day)
    # buy day = next pred calendar date in the file (pred_minus_one within file)
    by_buy: dict[str, dict[str, float]] = {}
    for i in range(len(pred_days) - 1):
        by_buy[pred_days[i + 1]] = pred_by_day[pred_days[i]]
    if not by_buy and len(pred_days) == 1:
        # Single pred day: allow explicit buy-day override only via scores-dir.
        # Keep empty so fail-closed surfaces unless caller remaps.
        pass
    return by_buy


def load_scores_from_args(
    *,
    pred_csv: Path | str | None = None,
    scores_dir: Path | str | None = None,
) -> dict[str, dict[str, float]]:
    """Fail-closed: require exactly one of pred-csv / scores-dir."""
    has_pred = pred_csv is not None and str(pred_csv).strip() != ""
    has_dir = scores_dir is not None and str(scores_dir).strip() != ""
    if has_pred and has_dir:
        raise SystemExit("pass only one of --pred-csv / --scores-dir")
    if has_dir:
        return load_scores_dir(scores_dir)
    if has_pred:
        return load_pred_csv(pred_csv)
    raise SystemExit(
        "topk_dropout requires --pred-csv or --scores-dir (fail-closed; no silent pool-only)"
    )


def codes_from_scores(
    scores_by_day: Mapping[str, Mapping[str, float]] | None,
) -> set[str]:
    """Union of canonical codes across score days (for lake load, not just TopK pool)."""
    if not scores_by_day:
        return set()
    out: set[str] = set()
    for day_map in scores_by_day.values():
        out.update(day_map)
    return out


def require_day_scores(
    scores_by_day: Mapping[str, Mapping[str, float]], ds: str
) -> Mapping[str, float]:
    scores = scores_by_day.get(ds)
    if scores is None:
        raise RuntimeError(f"topk_dropout fail-closed: missing scores for buy-day {ds}")
    return scores
