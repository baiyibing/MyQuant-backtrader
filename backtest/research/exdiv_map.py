# -*- coding: utf-8 -*-
"""Ex-dividend reference-price ratios for scoped engine correction (E-R6).

Event gate (survey C2 / X-R2):
  primary = ex_date_index.parquet
  fallback = factor row-jump |Δcum/cum| > 1e-2 when that day has no ex row
  k always = cum[prev_row] / cum[D_row] (LAG; never calendar D-1; never dr)
  noise band |Δcum/cum| <= 5e-3 → do not adjust (even if ex event)

Missing/unreadable parquet → empty map + one-shot stderr (CI data-free).
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

import math
import sys
from collections import defaultdict
from datetime import date as date_cls
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, Mapping, MutableMapping, Optional, Sequence, Union

import pandas as pd

from common.infra.data_root import resolve_source_parquet
from oskh_core.a_share_symbol_normalize import normalize_a_share_code

# Re-export normalize for callers/tests that need date dual-format.
from backtest.research.exdiv_hold_hits import normalize_date  # noqa: F401

NOISE_EPS = 5e-3
FALLBACK_JUMP_EPS = 1e-2
WARMUP_CALENDAR_DAYS = 10

ExdivRatios = dict[str, dict[str, float]]

_MISSING_WARNED = False


def _warn_missing_once(msg: str) -> None:
    global _MISSING_WARNED
    if _MISSING_WARNED:
        return
    _MISSING_WARNED = True
    print(f"[exdiv_map] {msg}", file=sys.stderr, flush=True)


def reset_missing_warn_flag_for_tests() -> None:
    """Test helper: allow one more missing-path stderr tip."""
    global _MISSING_WARNED
    _MISSING_WARNED = False


def _warmup_start(start: str) -> str:
    day = datetime.strptime(normalize_date(start), "%Y%m%d")
    return (day - timedelta(days=WARMUP_CALENDAR_DAYS)).strftime("%Y%m%d")


def _is_nan(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    text = str(value).strip()
    return (not text) or text.lower() in {"nan", "none", "null", "nat"}


def _as_float(value: object) -> Optional[float]:
    if _is_nan(value):
        return None
    try:
        out = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if math.isnan(out) or math.isinf(out) or out <= 0:
        return None
    return out


def mapped_prev_close(
    exdiv: Optional[Mapping[str, Mapping[str, float]]],
    code: str,
    ymd: str,
    raw_prev: float,
    *,
    fen_round: bool = False,
) -> tuple[float, bool]:
    """Return (prev_close_ref, did_map). Empty/missing map → (raw, False), never rounded."""
    if not exdiv:
        return float(raw_prev), False
    k = exdiv.get(code, {}).get(ymd)
    if k is None:
        return float(raw_prev), False
    k_f = float(k)
    if k_f <= 0 or math.isnan(k_f):
        return float(raw_prev), False
    mapped = float(raw_prev) * k_f
    if fen_round:
        mapped = float(Decimal(str(mapped)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    return mapped, True


def k_for(
    exdiv: Optional[Mapping[str, Mapping[str, float]]],
    code: str,
    ymd: str,
) -> Optional[float]:
    if not exdiv:
        return None
    k = exdiv.get(code, {}).get(ymd)
    if k is None:
        return None
    k_f = float(k)
    if k_f <= 0 or math.isnan(k_f):
        return None
    return k_f


def _code_filter_values(codes: set[str]) -> list[str]:
    """Push both suffixed and bare-6 forms so parquet filters still hit."""
    values: set[str] = set()
    for code in codes:
        values.add(code)
        six = code.split(".", 1)[0]
        values.add(six)
        values.add(normalize_a_share_code(code))
    return sorted(values)


def _resolve_columns(schema_names: set[str], columns: Sequence[str]) -> list[str]:
    wanted: list[str] = []
    for col in columns:
        if col in schema_names:
            wanted.append(col)
            continue
        alt = None
        low = col.lower()
        for name in schema_names:
            if name.lower() == low:
                alt = name
                break
        if alt is None and low == "stock_code":
            for name in schema_names:
                if name.lower() == "code":
                    alt = name
                    break
        if alt is None and low in {"ex_date", "date"}:
            for name in schema_names:
                if name.lower() in {"ex_date", "date"}:
                    alt = name
                    break
        if alt is None and low in {"cumulative_adj_factor", "adj_factor"}:
            for name in schema_names:
                if name.lower() in {"cumulative_adj_factor", "adj_factor"}:
                    alt = name
                    break
        if alt is None:
            raise KeyError(f"missing column {col!r}; have {sorted(schema_names)}")
        wanted.append(alt)
    return wanted


def _date_filter_bounds(arrow_type, start: str, end: str):
    import pyarrow as pa

    start_d = datetime.strptime(start, "%Y%m%d")
    end_d = datetime.strptime(end, "%Y%m%d")
    if pa.types.is_date(arrow_type):
        return start_d.date(), end_d.date()
    if pa.types.is_timestamp(arrow_type):
        return start_d, end_d
    return start, end


def _read_parquet_frame(
    path: Path,
    columns: Sequence[str],
    *,
    code_filter: Optional[set[str]] = None,
    date_start: Optional[str] = None,
    date_end: Optional[str] = None,
    date_column: Optional[str] = None,
) -> pd.DataFrame:
    """Read selected columns as a frame. Date/code filters are best-effort pushdown."""
    import pyarrow.parquet as pq

    parquet = pq.ParquetFile(path)
    schema = parquet.schema_arrow
    wanted = _resolve_columns(set(schema.names), columns)
    rename = {got: want for got, want in zip(wanted, columns)}
    filters: list = []
    code_col = next((c for c in wanted if c.lower() in {"stock_code", "code"}), None)
    if code_filter is not None and code_col is not None:
        filters.append((code_col, "in", _code_filter_values(code_filter)))
    date_col = None
    if date_start and date_end:
        date_col = date_column or next(
            (c for c in wanted if c.lower() in {"date", "ex_date"}), None
        )
        if date_col is not None:
            lo, hi = _date_filter_bounds(schema.field(date_col).type, date_start, date_end)
            filters.append((date_col, ">=", lo))
            filters.append((date_col, "<=", hi))

    def _load(use_filters: Optional[list]):
        try:
            return pq.read_table(path, columns=wanted, filters=use_filters or None)
        except Exception:
            return None

    table = _load(filters) if filters else _load(None)
    if table is None or (table.num_rows == 0 and date_col is not None and filters):
        without_date = [item for item in filters if item[0] != date_col]
        retry = _load(without_date)
        if retry is not None:
            table = retry
    if table is None:
        table = pq.read_table(path, columns=wanted)
    frame = table.rename_columns(
        [rename.get(name, name) for name in table.column_names]
    ).to_pandas()
    return frame if isinstance(frame, pd.DataFrame) else pd.DataFrame(frame)


def _normalize_date_series(values: pd.Series) -> pd.Series:
    """Vectorized cousin of ``normalize_date``; invalid cells become NA."""
    if pd.api.types.is_datetime64_any_dtype(values):
        return values.dt.strftime("%Y%m%d")
    if values.dtype == object and values.map(lambda x: isinstance(x, date_cls)).any():
        parsed = pd.to_datetime(values, errors="coerce")
        return parsed.dt.strftime("%Y%m%d")
    text = values.astype(str).str.strip()
    invalid = text.eq("") | text.str.lower().isin({"nan", "none", "nat", "null"})
    ymd = text.str.fullmatch(r"\d{8}")
    iso = text.str.match(r"^\d{4}-\d{2}-\d{2}")
    out = pd.Series(pd.NA, index=values.index, dtype="object")
    out.loc[ymd & ~invalid] = text.loc[ymd & ~invalid]
    out.loc[iso & ~invalid] = (
        text.loc[iso & ~invalid].str.slice(0, 10).str.replace("-", "", n=2, regex=False)
    )
    rest = ~(ymd | iso) & ~invalid
    if rest.any():
        parsed = pd.to_datetime(text.loc[rest], errors="coerce")
        out.loc[rest] = parsed.dt.strftime("%Y%m%d")
    return out


def _load_ex_events(
    path: Path, *, start: str, end: str, codes: Optional[set[str]]
) -> dict[str, set[str]]:
    frame = _read_parquet_frame(
        path,
        ["stock_code", "ex_date"],
        code_filter=codes,
        date_start=start,
        date_end=end,
        date_column="ex_date",
    )
    if frame.empty:
        return {}
    frame = frame.copy()
    frame["ds"] = _normalize_date_series(frame["ex_date"])
    frame = frame[frame["ds"].notna() & (frame["ds"] >= start) & (frame["ds"] <= end)]
    frame["code"] = frame["stock_code"].astype(str).str.strip().map(normalize_a_share_code)
    if codes is not None:
        frame = frame[frame["code"].isin(codes)]
    by_code: dict[str, set[str]] = defaultdict(set)
    for code, ds in zip(frame["code"].tolist(), frame["ds"].tolist()):
        by_code[str(code)].add(str(ds))
    return by_code


def _load_factor_series(
    path: Path, *, start: str, end: str, codes: Optional[set[str]]
) -> tuple[dict[str, list[tuple[str, float]]], dict[str, dict[str, Optional[float]]]]:
    frame = _read_parquet_frame(
        path,
        ["date", "stock_code", "cumulative_adj_factor"],
        code_filter=codes,
        date_start=start,
        date_end=end,
        date_column="date",
    )
    cleaned: dict[str, list[tuple[str, float]]] = {}
    raw_by_date: dict[str, dict[str, Optional[float]]] = {}
    if frame.empty:
        return cleaned, raw_by_date
    frame = frame.copy()
    frame["ds"] = _normalize_date_series(frame["date"])
    frame = frame[frame["ds"].notna() & (frame["ds"] >= start) & (frame["ds"] <= end)]
    frame["code"] = frame["stock_code"].astype(str).str.strip().map(normalize_a_share_code)
    if codes is not None:
        frame = frame[frame["code"].isin(codes)]
    if frame.empty:
        return cleaned, raw_by_date
    frame = frame.sort_values(["code", "ds"], kind="mergesort")
    for code, group in frame.groupby("code", sort=False):
        points = [
            (str(ds), _as_float(val))
            for ds, val in zip(group["ds"].tolist(), group["cumulative_adj_factor"].tolist())
        ]
        raw_by_date[str(code)] = {ds: val for ds, val in points}
        cleaned[str(code)] = [(ds, val) for ds, val in points if val is not None]
    return cleaned, raw_by_date


def load_exdiv_ratios(
    codes: Optional[Iterable[str]],
    start: str,
    end: str,
    *,
    adj_factor_path: Optional[Union[str, Path]] = None,
    ex_date_index_path: Optional[Union[str, Path]] = None,
    noise_eps: float = NOISE_EPS,
    fallback_eps: float = FALLBACK_JUMP_EPS,
    skipped_out: Optional[MutableMapping[str, int]] = None,
) -> ExdivRatios:
    """Build code → {ymd → k} for event days in [start, end].

    Read window for factors includes warmup (start−10 calendar days) so the
    first event day still has a LAG predecessor. Missing files / read errors
    yield ``{}`` plus a one-shot stderr tip (never raise).
    """
    start_n = normalize_date(start)
    end_n = normalize_date(end)
    warm = _warmup_start(start_n)
    code_set: Optional[set[str]]
    if codes is None:
        code_set = None
    else:
        code_set = {normalize_a_share_code(c) for c in codes}

    adj_path = (
        Path(adj_factor_path) if adj_factor_path else resolve_source_parquet("adj_factor.parquet")
    )
    ex_path = (
        Path(ex_date_index_path)
        if ex_date_index_path
        else resolve_source_parquet("ex_date_index.parquet")
    )

    skipped = 0
    ratios: ExdivRatios = {}

    if not adj_path.is_file():
        _warn_missing_once(f"adj_factor missing or unreadable: {adj_path} (empty exdiv map)")
        if skipped_out is not None:
            skipped_out["exdiv_skipped_no_factor"] = skipped
        return ratios

    try:
        factor_clean, raw_by_code_date = _load_factor_series(
            adj_path, start=warm, end=end_n, codes=code_set
        )
    except Exception as exc:  # noqa: BLE001 — X-R2: never raise to callers
        _warn_missing_once(f"adj_factor read failed: {adj_path} ({exc!r}); empty exdiv map")
        if skipped_out is not None:
            skipped_out["exdiv_skipped_no_factor"] = skipped
        return ratios

    ex_by_code: dict[str, set[str]] = {}
    if ex_path.is_file():
        try:
            ex_by_code = _load_ex_events(ex_path, start=start_n, end=end_n, codes=code_set)
        except Exception as exc:  # noqa: BLE001
            _warn_missing_once(
                f"ex_date_index read failed: {ex_path} ({exc!r}); factor-jump fallback only"
            )
    else:
        _warn_missing_once(f"ex_date_index missing: {ex_path} (factor-jump fallback only)")

    for code, points in factor_clean.items():
        if len(points) < 2:
            continue
        ex_days = ex_by_code.get(code, set())
        code_map: dict[str, float] = {}
        for i in range(1, len(points)):
            prev_ds, prev_cum = points[i - 1]
            ds, cum = points[i]
            if not start_n <= ds <= end_n:
                continue
            jump = abs(cum - prev_cum) / prev_cum if prev_cum > 0 else 0.0
            is_ex = ds in ex_days
            if is_ex:
                if jump <= noise_eps:
                    # Noise band: declare event but do not adjust.
                    continue
                k = prev_cum / cum
                if k > 0 and math.isfinite(k):
                    code_map[ds] = float(k)
                else:
                    skipped += 1
            elif jump > fallback_eps:
                # Fallback: large jump with no ex row.
                k = prev_cum / cum
                if k > 0 and math.isfinite(k):
                    code_map[ds] = float(k)
                else:
                    skipped += 1
        # Ex events with no usable factor / no LAG predecessor → skip count.
        # Noise-band suppressions are intentional non-adjusts, not skips.
        raw = raw_by_code_date.get(code, {})
        for ds in ex_days:
            if ds in code_map:
                continue
            if ds not in raw or raw[ds] is None:
                skipped += 1
                continue
            # Factor present: if noise-band, leave alone; if no predecessor, skip.
            prev_candidates = [p for p in points if p[0] < ds]
            if not prev_candidates:
                skipped += 1
            # else: either noise-filtered or already handled in loop
        if code_map:
            ratios[code] = code_map

    # Ex codes with zero factor coverage at all.
    for code, ex_days in ex_by_code.items():
        if code in factor_clean and factor_clean[code]:
            continue
        skipped += len(ex_days)

    if skipped_out is not None:
        skipped_out["exdiv_skipped_no_factor"] = int(skipped)
    return ratios


__all__ = [
    "NOISE_EPS",
    "FALLBACK_JUMP_EPS",
    "ExdivRatios",
    "load_exdiv_ratios",
    "mapped_prev_close",
    "k_for",
    "normalize_date",
    "reset_missing_warn_flag_for_tests",
]
