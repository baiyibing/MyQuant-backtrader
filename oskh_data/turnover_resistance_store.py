# -*- coding: utf-8 -*-
"""Parquet store for canonical turnover-resistance daily series + TR Bollinger Bands."""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Sequence, Union

import pandas as pd
from filelock import FileLock

from backtest.chip_turnover_resistance_bands import compute_tr_bb_columns
from common.infra.quant_logger import get_logger
from common.infra.timekeeping import wall_now_s
from oskh_data.reader import _resolve_data_root

_log = get_logger(__name__)

DEFAULT_WINDOW = 1000
DEFAULT_FREE_FLOAT_POLICY = "warn-zero"
UNIQUE_KEYS = ("stock_code", "trade_date", "window")

# Rust FFI 18 cols (normalized) + TR BB 10 cols + audit 5 cols
SCHEMA_COLUMNS: tuple[str, ...] = (
    "stock_code",
    "trade_date",
    "stock_name",
    "close",
    "cyqk_t",
    "cyqk_t_1",
    "profit_chip_diff",
    "turnover",
    "turnover_resistance",
    "turnover_free",
    "turnover_resistance_free",
    "circulating_capital",
    "free_float_capital",
    "bb_upper",
    "bb_middle",
    "bb_lower",
    "bb_position",
    "bb_width",
    "tr_bb_upper",
    "tr_bb_middle",
    "tr_bb_lower",
    "tr_bb_position",
    "tr_bb_width",
    "tr_bb_free_upper",
    "tr_bb_free_middle",
    "tr_bb_free_lower",
    "tr_bb_free_position",
    "tr_bb_free_width",
    "window",
    "source",
    "free_float_policy",
    "updated_at",
    "bands_computed_at",
)

_FLOAT_COLUMNS = frozenset(
    col
    for col in SCHEMA_COLUMNS
    if col
    not in {
        "stock_code",
        "trade_date",
        "stock_name",
        "source",
        "free_float_policy",
    }
)

_TR_BB_COLUMNS = (
    "tr_bb_upper",
    "tr_bb_middle",
    "tr_bb_lower",
    "tr_bb_position",
    "tr_bb_width",
    "tr_bb_free_upper",
    "tr_bb_free_middle",
    "tr_bb_free_lower",
    "tr_bb_free_position",
    "tr_bb_free_width",
)


def resolve_parquet_path(path: Optional[Union[str, Path]] = None) -> Path:
    """Resolve Parquet path (env ``TURNOVER_RESIST_BANDS_PATH`` overrides default)."""
    if path is not None:
        return Path(path)
    env = os.getenv("TURNOVER_RESIST_BANDS_PATH")
    if env:
        return Path(env)
    root = _resolve_data_root()
    return root / "stock_data" / "turnover_resistance_daily.parquet"


def resolve_staging_dir(staging_dir: Optional[Union[str, Path]] = None) -> Path:
    """Directory for per-year TR staging Parquet files."""
    if staging_dir is not None:
        return Path(staging_dir)
    env = os.getenv("TURNOVER_RESIST_STAGING_DIR")
    if env:
        return Path(env)
    root = _resolve_data_root()
    return root / "stock_data" / "tr_staging"


def resolve_year_staging_path(
    year: int,
    staging_dir: Optional[Union[str, Path]] = None,
) -> Path:
    """Per-year staging file used during backfill before merge into canonical."""
    return resolve_staging_dir(staging_dir) / f"turnover_resistance_daily_{year}.parquet"


def _read_parquet_or_empty(path: Path) -> pd.DataFrame:
    if not path.is_file():
        return _empty_frame()
    return _ensure_schema(pd.read_parquet(path))


def merge_parquet_into_canonical(
    *sources: Union[str, Path],
    canonical_path: Optional[Union[str, Path]] = None,
) -> dict[str, int]:
    """Merge staging Parquet file(s) into the canonical store (dedupe by UNIQUE_KEYS)."""
    source_paths = [Path(s) for s in sources]
    frames = [_read_parquet_or_empty(path) for path in source_paths]
    frames = [frame for frame in frames if not frame.empty]
    if not frames:
        store = TurnoverResistanceStore(canonical_path)
        existing = store._read()
        return {
            "source_rows": 0,
            "total_before": len(existing),
            "total_after": len(existing),
            "keys_updated": 0,
        }

    incoming = pd.concat(frames, ignore_index=True)
    incoming = incoming.drop_duplicates(subset=list(UNIQUE_KEYS), keep="last")
    store = TurnoverResistanceStore(canonical_path)

    with store._locked():
        existing = store._read()
        before = len(existing)
        merged = pd.concat([existing, incoming], ignore_index=True)
        merged = merged.drop_duplicates(subset=list(UNIQUE_KEYS), keep="last")
        store._write_atomic(merged)

    keys_updated = len(merged) - before
    stats = {
        "source_rows": len(incoming),
        "total_before": before,
        "total_after": len(merged),
        "keys_updated": max(keys_updated, 0),
    }
    _log.info("merge_parquet_into_canonical complete", context={**stats, "sources": [str(p) for p in source_paths]})
    return stats


def normalize_ffi_row(
    row: Dict[str, Any],
    *,
    trade_date: str,
    window: int = DEFAULT_WINDOW,
    source: str = "canonical_rust",
    free_float_policy: str = DEFAULT_FREE_FLOAT_POLICY,
) -> Dict[str, Any]:
    """Map Rust FFI / CSV dict keys to store schema columns."""
    code = row.get("stock_code") or row.get("code")
    if not code:
        raise ValueError("FFI row missing stock_code")

    date_val = trade_date or row.get("trade_date") or row.get("date")
    if not date_val:
        raise ValueError("FFI row missing trade_date/date")
    trade_date_str = str(date_val)

    def _f(key: str, *aliases: str) -> float:
        for name in (key, *aliases):
            val = row.get(name)
            if val is None or val == "":
                continue
            try:
                return float(val)
            except (TypeError, ValueError):
                continue
        return float("nan")

    now = wall_now_s()
    out: Dict[str, Any] = {
        "stock_code": str(code),
        "trade_date": trade_date_str,
        "stock_name": str(row.get("stock_name") or ""),
        "close": _f("close"),
        "cyqk_t": _f("cyqk_t", "cyqk_T"),
        "cyqk_t_1": _f("cyqk_t_1", "cyqk_T_1"),
        "profit_chip_diff": _f("profit_chip_diff"),
        "turnover": _f("turnover"),
        "turnover_resistance": _f("turnover_resistance"),
        "turnover_free": _f("turnover_free"),
        "turnover_resistance_free": _f("turnover_resistance_free"),
        "circulating_capital": _f("circulating_capital"),
        "free_float_capital": _f("free_float_capital", "freeFloatCapital"),
        "bb_upper": _f("bb_upper"),
        "bb_middle": _f("bb_middle"),
        "bb_lower": _f("bb_lower"),
        "bb_position": _f("bb_position"),
        "bb_width": _f("bb_width"),
        "window": int(window),
        "source": str(source),
        "free_float_policy": str(free_float_policy),
        "updated_at": now,
        "bands_computed_at": float("nan"),
    }
    for col in _TR_BB_COLUMNS:
        out[col] = float("nan")
    return out


def _empty_frame() -> pd.DataFrame:
    return pd.DataFrame({col: pd.Series(dtype="float64") for col in SCHEMA_COLUMNS})


def _ensure_schema(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in SCHEMA_COLUMNS:
        if col not in out.columns:
            out[col] = float("nan") if col in _FLOAT_COLUMNS else None
    out = out[list(SCHEMA_COLUMNS)]
    out["stock_code"] = out["stock_code"].astype(str)
    out["trade_date"] = out["trade_date"].astype(str)
    out["stock_name"] = out["stock_name"].fillna("").astype(str)
    out["source"] = out["source"].fillna("canonical_rust").astype(str)
    out["free_float_policy"] = out["free_float_policy"].fillna(DEFAULT_FREE_FLOAT_POLICY).astype(str)
    out["window"] = pd.to_numeric(out["window"], errors="coerce").fillna(DEFAULT_WINDOW).astype("int64")
    for col in _FLOAT_COLUMNS:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    return out


def _validate_audit_columns(df: pd.DataFrame, *, strict: bool) -> None:
    if df.empty:
        return
    for col in ("window", "source", "free_float_policy"):
        nunique = df[col].nunique(dropna=False)
        if nunique > 1:
            msg = f"口径不一致 ({col}): {df[col].unique().tolist()}"
            if strict:
                raise ValueError(msg)
            _log.warning(msg, context={"column": col})


class TurnoverResistanceStore:
    """Read/write ``stock_data/turnover_resistance_daily.parquet`` with file locking."""

    def __init__(self, path: Optional[Union[str, Path]] = None) -> None:
        self.path = resolve_parquet_path(path)
        self._lock_path = self.path.with_suffix(self.path.suffix + ".lock")

    @contextmanager
    def _locked(self) -> Iterator[None]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock = FileLock(str(self._lock_path), timeout=120)
        with lock:
            yield

    def _read(self) -> pd.DataFrame:
        if not self.path.is_file():
            return _empty_frame()
        df = pd.read_parquet(self.path)
        return _ensure_schema(df)

    def _write_atomic(self, df: pd.DataFrame) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        staging = self.path.with_suffix(".staging.parquet")
        frame = _ensure_schema(df)
        frame = frame.sort_values(list(UNIQUE_KEYS)).reset_index(drop=True)
        frame.to_parquet(staging, index=False)
        staging.replace(self.path)

    def upsert_daily(
        self,
        trade_date: str,
        rows: Sequence[Dict[str, Any]],
        *,
        window: int = DEFAULT_WINDOW,
        source: str = "canonical_rust",
        free_float_policy: str = DEFAULT_FREE_FLOAT_POLICY,
    ) -> dict[str, int]:
        """Append/replace one trading-day cross-section."""
        trade_date = str(trade_date)
        normalized = [
            normalize_ffi_row(
                row,
                trade_date=trade_date,
                window=window,
                source=source,
                free_float_policy=free_float_policy,
            )
            for row in rows
        ]
        if not normalized:
            return {"existing": 0, "inserted": 0, "replaced": 0}

        new_df = _ensure_schema(pd.DataFrame(normalized))

        with self._locked():
            existing = self._read()
            same_day = existing[existing["trade_date"] == trade_date]
            if not same_day.empty:
                for code in new_df["stock_code"].unique():
                    prev = same_day[same_day["stock_code"] == code]
                    if prev.empty:
                        continue
                    prev_windows = prev["window"].unique()
                    if len(prev_windows) != 1 or int(prev_windows[0]) != int(window):
                        raise ValueError(
                            f"window 冲突: {code} @ {trade_date} "
                            f"已有 window={prev_windows.tolist()}，本次 window={window}"
                        )

            before = len(existing)
            before_keys = set(
                zip(
                    existing["stock_code"].astype(str),
                    existing["trade_date"].astype(str),
                    existing["window"].astype(int),
                )
            )
            new_keys = set(
                zip(
                    new_df["stock_code"].astype(str),
                    new_df["trade_date"].astype(str),
                    new_df["window"].astype(int),
                )
            )
            replaced = len(before_keys & new_keys)
            merged = pd.concat([existing, new_df], ignore_index=True)
            merged = merged.drop_duplicates(subset=list(UNIQUE_KEYS), keep="last")
            total_after = len(merged)
            self._write_atomic(merged)

        inserted = len(new_df) - replaced
        stats = {
            "existing_before": before,
            "inserted": max(inserted, 0),
            "replaced": replaced,
            "total_after": total_after,
        }
        _log.info(
            "upsert_daily complete",
            context={"trade_date": trade_date, "window": window, **stats},
        )
        return stats

    def load_series(
        self,
        stock_code: str,
        *,
        end_date: Optional[str] = None,
        n: int = 60,
        window: int = DEFAULT_WINDOW,
        strict: bool = True,
    ) -> pd.DataFrame:
        """Load last *n* trading rows for one stock (sparse series, ascending)."""
        df = self._read()
        if df.empty:
            return df

        sub = df[(df["stock_code"] == stock_code) & (df["window"] == int(window))]
        if end_date:
            sub = sub[sub["trade_date"] <= str(end_date)]
        sub = sub.sort_values("trade_date")
        if n > 0:
            sub = sub.tail(n)

        if strict:
            _validate_audit_columns(sub, strict=True)
        elif sub.empty:
            _log.warning(
                "load_series empty",
                context={"stock_code": stock_code, "end_date": end_date},
            )
        return sub.reset_index(drop=True)

    def load_cross_section(
        self,
        trade_date: str,
        *,
        window: int = DEFAULT_WINDOW,
        require_bands: bool = False,
    ) -> pd.DataFrame:
        df = self._read()
        sub = df[(df["trade_date"] == str(trade_date)) & (df["window"] == int(window))]
        if require_bands:
            sub = sub[sub["bands_computed_at"].notna()]
        return sub.sort_values("stock_code").reset_index(drop=True)

    def load_bb_breakout(
        self,
        trade_date: str,
        *,
        band: str = "upper",
        window: int = DEFAULT_WINDOW,
    ) -> pd.DataFrame:
        df = self.load_cross_section(trade_date, window=window, require_bands=True)
        if df.empty:
            return df
        if band == "upper":
            return df[df["turnover_resistance"] > df["tr_bb_upper"]].reset_index(drop=True)
        if band == "lower":
            return df[df["turnover_resistance"] < df["tr_bb_lower"]].reset_index(drop=True)
        raise ValueError(f"unsupported band={band!r}; use 'upper' or 'lower'")

    def load_recent_history(
        self,
        *,
        n_trading_days: int = 60,
        end_date: Optional[str] = None,
        window: int = DEFAULT_WINDOW,
    ) -> pd.DataFrame:
        """Load all rows with trade_date in the last *n_trading_days* distinct dates."""
        df = self._read()
        if df.empty:
            return df
        sub = df[df["window"] == int(window)]
        if end_date:
            sub = sub[sub["trade_date"] <= str(end_date)]
        if sub.empty:
            return sub
        dates = sorted(sub["trade_date"].unique())
        keep = set(dates[-n_trading_days:])
        return sub[sub["trade_date"].isin(keep)].reset_index(drop=True)

    def compute_and_update_bands(
        self,
        trade_dates: Optional[Sequence[str]] = None,
        *,
        n_history: int = 60,
        period: int = 20,
        nbdev: float = 2.0,
        ddof: int = 1,
        window: int = DEFAULT_WINDOW,
        only_missing: bool = False,
    ) -> dict[str, int]:
        """Batch TR BB for given trade dates (default: all dates missing bands)."""
        with self._locked():
            df = self._read()
            if df.empty:
                return {"updated_rows": 0, "trade_dates": 0}

            sub = df[df["window"] == int(window)].copy()
            if trade_dates is not None:
                want = {str(d) for d in trade_dates}
                sub_target = sub[sub["trade_date"].isin(want)]
            elif only_missing:
                sub_target = sub[sub["bands_computed_at"].isna()]
            else:
                sub_target = sub

            if sub_target.empty:
                return {"updated_rows": 0, "trade_dates": 0}

            target_dates = sorted(sub_target["trade_date"].unique())
            all_dates = sorted(sub["trade_date"].unique())
            date_to_idx = {d: i for i, d in enumerate(all_dates)}

            updated = 0
            now = wall_now_s()
            for td in target_dates:
                idx_pos = date_to_idx[td]
                start = max(0, idx_pos - n_history + 1)
                hist_dates = set(all_dates[start : idx_pos + 1])
                hist = sub[sub["trade_date"].isin(hist_dates)]
                _validate_audit_columns(hist, strict=True)
                computed = compute_tr_bb_columns(
                    hist,
                    period=period,
                    nbdev=nbdev,
                    ddof=ddof,
                )
                day_rows = computed[computed["trade_date"] == td]
                if day_rows.empty:
                    continue
                for _, row in day_rows.iterrows():
                    mask = (
                        (df["stock_code"] == row["stock_code"])
                        & (df["trade_date"] == row["trade_date"])
                        & (df["window"] == int(window))
                    )
                    hit = df.index[mask]
                    if len(hit) == 0:
                        continue
                    for idx in hit:
                        for col in _TR_BB_COLUMNS:
                            val = row[col]
                            df.at[idx, col] = float(val) if pd.notna(val) else float("nan")
                        df.at[idx, "bands_computed_at"] = now
                        updated += 1

            self._write_atomic(df)
            return {"updated_rows": updated, "trade_dates": len(target_dates)}

    def compute_all_bands_vectorized(
        self,
        *,
        period: int = 20,
        nbdev: float = 2.0,
        ddof: int = 1,
        window: int = DEFAULT_WINDOW,
    ) -> dict[str, int]:
        """Recompute TR BB for all rows in one vectorized pass (full-history backfill)."""
        with self._locked():
            df = self._read()
            if df.empty:
                return {"updated_rows": 0, "total_rows": 0}

            sub_mask = df["window"] == int(window)
            sub = df.loc[sub_mask].sort_values(["stock_code", "trade_date"])
            if sub.empty:
                return {"updated_rows": 0, "total_rows": 0}

            computed = compute_tr_bb_columns(
                sub,
                period=period,
                nbdev=nbdev,
                ddof=ddof,
            )
            now = wall_now_s()
            for col in _TR_BB_COLUMNS:
                df.loc[sub_mask, col] = computed[col].to_numpy()
            sub_indices = df.index[sub_mask]
            ready = computed["tr_bb_middle"].notna().to_numpy()
            df.loc[sub_indices[ready], "bands_computed_at"] = now
            df.loc[sub_indices[~ready], "bands_computed_at"] = float("nan")
            self._write_atomic(df)
            return {
                "updated_rows": int(ready.sum()),
                "total_rows": int(len(sub)),
            }

    def list_trade_dates(self, *, window: int = DEFAULT_WINDOW) -> List[str]:
        df = self._read()
        if df.empty:
            return []
        sub = df[df["window"] == int(window)]
        return sorted(sub["trade_date"].unique())

    def has_trade_date(self, trade_date: str, *, window: int = DEFAULT_WINDOW) -> bool:
        df = self._read()
        if df.empty:
            return False
        mask = (df["trade_date"] == str(trade_date)) & (df["window"] == int(window))
        return bool(mask.any())

    def distribution_stats(
        self,
        trade_date: Optional[str] = None,
        *,
        window: int = DEFAULT_WINDOW,
    ) -> dict[str, float]:
        """Summary stats for TR distribution (§8 P2-2 acceptance helper)."""
        df = self._read()
        if df.empty:
            return {}
        sub = df[df["window"] == int(window)]
        if trade_date:
            sub = sub[sub["trade_date"] == str(trade_date)]
        if sub.empty:
            return {}
        tr = sub["turnover_resistance"].dropna()
        if tr.empty:
            return {}
        abs_tr = tr.abs()
        return {
            "count": float(len(tr)),
            "p50": float(tr.quantile(0.5)),
            "p90": float(tr.quantile(0.9)),
            "p95": float(tr.quantile(0.95)),
            "p99": float(tr.quantile(0.99)),
            "abs_gt_20_pct": float((abs_tr > 20).mean() * 100.0),
        }
