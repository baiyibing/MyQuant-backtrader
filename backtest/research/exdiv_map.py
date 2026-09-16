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

import math
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, Mapping, MutableMapping, Optional, Sequence, Union

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
) -> tuple[float, bool]:
    """Return (prev_close_ref, did_map). Empty/missing map → (raw, False)."""
    if not exdiv:
        return float(raw_prev), False
    k = exdiv.get(code, {}).get(ymd)
    if k is None:
        return float(raw_prev), False
    k_f = float(k)
    if k_f <= 0 or math.isnan(k_f):
        return float(raw_prev), False
    return float(raw_prev) * k_f, True


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


def _read_parquet_cols(
    path: Path, columns: Sequence[str], *, code_filter: Optional[set[str]] = None
) -> list[dict]:
    """Read selected columns; optional stock_code pushdown via pyarrow."""
    import pyarrow.parquet as pq

    schema_names = set(pq.ParquetFile(path).schema_arrow.names)
    # Tolerate alternate column spellings.
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
            raise KeyError(f"{path.name} missing column {col!r}; have {sorted(schema_names)}")
        wanted.append(alt)

    filters = None
    code_col = next((c for c in wanted if c.lower() in {"stock_code", "code"}), None)
    if code_filter is not None and code_col is not None:
        # Include both raw and normalized forms when possible.
        filters = [(code_col, "in", sorted(code_filter))]

    try:
        table = pq.read_table(path, columns=wanted, filters=filters)
    except Exception:
        # filters may fail on some writers; fall back to full column read.
        table = pq.read_table(path, columns=wanted)
    # Normalize column names to requested logical names.
    rename = {got: want for got, want in zip(wanted, columns)}
    frame_cols = {rename.get(name, name): table.column(name) for name in table.column_names}
    import pandas as pd

    frame = pd.DataFrame({k: v.to_pylist() for k, v in frame_cols.items()})
    if code_filter is not None and "stock_code" in frame.columns:
        # Post-filter after normalize.
        pass
    return frame.to_dict(orient="records")


def _load_ex_events(
    path: Path, *, start: str, end: str, codes: Optional[set[str]]
) -> dict[str, set[str]]:
    rows = _read_parquet_cols(path, ["stock_code", "ex_date"], code_filter=codes)
    by_code: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        try:
            ds = normalize_date(row["ex_date"])
        except ValueError:
            continue
        if not start <= ds <= end:
            continue
        code = normalize_a_share_code(str(row["stock_code"]).strip())
        if codes is not None and code not in codes:
            continue
        by_code[code].add(ds)
    return by_code


def _load_factor_series(
    path: Path, *, start: str, end: str, codes: Optional[set[str]]
) -> tuple[dict[str, list[tuple[str, float]]], dict[str, dict[str, Optional[float]]]]:
    rows = _read_parquet_cols(
        path,
        ["date", "stock_code", "cumulative_adj_factor"],
        code_filter=codes,
    )
    series: dict[str, list[tuple[str, Optional[float]]]] = defaultdict(list)
    for row in rows:
        try:
            ds = normalize_date(row["date"])
        except ValueError:
            continue
        if not start <= ds <= end:
            continue
        code = normalize_a_share_code(str(row["stock_code"]).strip())
        if codes is not None and code not in codes:
            continue
        series[code].append((ds, _as_float(row["cumulative_adj_factor"])))
    cleaned: dict[str, list[tuple[str, float]]] = {}
    raw_by_date: dict[str, dict[str, Optional[float]]] = {}
    for code, points in series.items():
        points.sort(key=lambda x: x[0])
        raw_by_date[code] = {ds: val for ds, val in points}
        cleaned[code] = [(ds, val) for ds, val in points if val is not None]
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

    adj_path = Path(adj_factor_path) if adj_factor_path else resolve_source_parquet(
        "adj_factor.parquet"
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
            ex_by_code = _load_ex_events(
                ex_path, start=start_n, end=end_n, codes=code_set
            )
        except Exception as exc:  # noqa: BLE001
            _warn_missing_once(
                f"ex_date_index read failed: {ex_path} ({exc!r}); factor-jump fallback only"
            )
    else:
        _warn_missing_once(
            f"ex_date_index missing: {ex_path} (factor-jump fallback only)"
        )

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
