"""Daily 1d parquet merge-write helpers (none bulk write + front mirror / path B).

**All parquet writes use PyArrow** (``pq.write_table`` / Arrow merge). DuckDB is
never used to write hive files.

Write modes (``OSKH_DAILY_PARQUET_WRITE_MODE``; default ``batch``):

- ``batch`` — **default**. PyArrow parallel write; when path-B reads none from
  disk, uses DuckDB glob batch-**read** first (2026-07-17 bench: path_b n=200
  batch 1.81s < parallel 4.55s). Daily mirror in-memory path ≡ ``parallel``.
- ``parallel`` — ThreadPool + pyarrow only (no DuckDB read)
- ``legacy`` — serial pandas read/concat/write (baseline)

Deprecated alias: ``duckdb`` → ``batch`` (old name implied DuckDB writes parquet; it does not).

Phase B: ``mirror_none_tail_to_front`` appends only ``t > max(front.time)``.
"""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Literal, Optional, Sequence, Set, Tuple, cast

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from common.infra.quant_logger import get_logger
from common.infra.timekeeping import mono_now
from oskh_data.pandas_typing import as_series, normalize_timestamp, to_numeric_series
from oskh_data.symbol_format import to_canonical_symbol, to_partition_key

logger = get_logger(__name__)

WriteMode = Literal["parallel", "batch", "legacy"]

STANDARD_COLUMNS = ["time", "open", "high", "low", "close", "volume", "amount"]

# Canonical Arrow/pandas dtypes for 1d hive (rebuild schema gate uses the same contract).
# QMT / pandas often emit volume as float64 ("double"); DuckDB rebuild fail-closes on drift.
CANONICAL_ARROW_TYPES: dict[str, pa.DataType] = {
    "time": pa.int64(),
    "open": pa.float64(),
    "high": pa.float64(),
    "low": pa.float64(),
    "close": pa.float64(),
    "volume": pa.int64(),
    "amount": pa.float64(),
}

_DEFAULT_WORKERS = max(4, min(16, (os.cpu_count() or 8)))
_MS_PER_DAY = 86_400_000

# Old env value ``duckdb`` meant "DuckDB batch-read for path B"; rename to ``batch``.
_MODE_ALIASES = {"duckdb": "batch"}


def utc_midnight_ms_from_time_ms(time_ms: pd.Series) -> pd.Series:
    """Map epoch-ms (CST-as-UTC or UTC midnight) → Shanghai calendar day's UTC midnight ms.

    Same formula as ``shanghai_day`` in
    ``scripts/data/_repair_daily_cst_utc_double_rows.py``, then epoch ms —
    not string-date normalize.

    Pandas 2.2+/3 may yield ``datetime64[us]`` (or ``[ms]``) from
    ``to_datetime``/``normalize``; ``astype("int64") // 10**6`` assumed ns and
    produced bogus epoch-seconds. Cast to ``datetime64[ms]`` first so int64 is
    always milliseconds.
    """
    ts = pd.to_datetime(time_ms.astype("int64"), unit="ms")
    sh = (ts + pd.Timedelta(hours=8)).dt.normalize()
    return sh.astype("datetime64[ms]").astype("int64")


def normalize_daily_times_to_utc_midnight(df: pd.DataFrame) -> pd.DataFrame:
    """Rewrite ``time`` to UTC midnight of Shanghai day; fail-closed if remainder nonzero."""
    out = df.copy()
    out["time"] = utc_midnight_ms_from_time_ms(cast(pd.Series, out["time"]))
    rem_sum = int((out["time"].astype("int64") % _MS_PER_DAY).sum())
    if rem_sum != 0:
        raise ValueError(
            f"daily time normalize failed: (time % 86400000).sum() == {rem_sum} (expected 0)"
        )
    return out


@dataclass
class MirrorStats:
    """Counters for ``mirror_none_tail_to_front``."""

    mirrored: int = 0
    days_mirrored: int = 0
    skipped_ex: int = 0
    missing_front: int = 0
    missing_front_codes: List[str] = field(default_factory=list)
    empty_tail: int = 0
    skipped_empty: int = 0
    errors: List[str] = field(default_factory=list)


def resolve_write_mode(raw: str | None = None) -> WriteMode:
    """Default ``batch``. Alias ``duckdb`` → ``batch``."""
    text = (
        (
            raw
            if raw is not None
            else os.environ.get("OSKH_DAILY_PARQUET_WRITE_MODE", "")
        )
        .strip()
        .lower()
    )
    text = _MODE_ALIASES.get(text, text)
    if text == "parallel":
        return "parallel"
    if text == "batch":
        return "batch"
    if text == "legacy":
        return "legacy"
    return "batch"


def _normalize_new_frame(df_new: pd.DataFrame) -> pd.DataFrame:
    out = df_new.copy()
    if "time" not in out.columns:
        out["time"] = (pd.to_datetime(out.index).astype("int64") // 10**6).astype(
            "int64"
        )
    for col in STANDARD_COLUMNS:
        if col not in out.columns:
            if col in ("volume", "amount"):
                out[col] = 0
            else:
                raise ValueError(f"missing column {col}")
    out = cast(pd.DataFrame, out[STANDARD_COLUMNS]).copy()
    out["time"] = (
        to_numeric_series(out["time"], errors="coerce").fillna(0).astype("int64")
    )
    for col in ("open", "high", "low", "close", "amount"):
        out[col] = to_numeric_series(out[col], errors="coerce").astype("float64")
    # volume must be int64 on disk (lesson 41 / 2026-08-02): float64 → double poisons rebuild
    vol = to_numeric_series(out["volume"], errors="coerce").fillna(0.0)
    out["volume"] = vol.round().astype("int64")
    return out


def canonicalize_arrow_daily_table(table: pa.Table) -> pa.Table:
    """Cast a daily hive table to ``CANONICAL_ARROW_TYPES`` (volume→int64, etc.)."""
    cols: List[pa.Array] = []
    names: List[str] = []
    for name in STANDARD_COLUMNS:
        if name not in table.column_names:
            continue
        col = table.column(name)
        target = CANONICAL_ARROW_TYPES[name]
        if col.type.equals(target):
            cols.append(col)
            names.append(name)
            continue
        if name == "volume":
            s = (
                to_numeric_series(col.to_pandas(), errors="coerce")
                .fillna(0.0)
                .round()
                .astype("int64")
            )
            cols.append(pa.array(s, type=pa.int64()))
        elif name == "time":
            s = (
                to_numeric_series(col.to_pandas(), errors="coerce")
                .fillna(0)
                .astype("int64")
            )
            cols.append(pa.array(s, type=pa.int64()))
        else:
            cols.append(col.cast(target, safe=False))
        names.append(name)
    return pa.Table.from_arrays(cols, names=names)


def _file_path(
    base_dir: Path,
    adjust_type: str,
    stock_code: str,
    *,
    ensure_dir: bool = True,
) -> Path:
    from common.infra.data_root import resolve_period_root

    part = to_partition_key(to_canonical_symbol(stock_code))
    # path-SSOT D2 写侧契约：周期根经 resolve_period_root（env 胜 base——
    # 写后路径 == 读路径；base_dir 保持容器语义，禁传 period 根（双后缀陷阱））
    d = resolve_period_root("1d", base=base_dir) / f"dividend_type={adjust_type}" / f"symbol={part}"
    if ensure_dir:
        d.mkdir(parents=True, exist_ok=True)
    return d / "data.parquet"


def _read_single_parquet(
    path: Path,
    columns: Optional[Sequence[str]] = None,
) -> pa.Table:
    """Read one hive file via ``ParquetFile`` (not ``pq.read_table``).

    ``pq.read_table(path)`` may open a Dataset over the parent hive tree and
    fail unifying sibling schemas when dictionary index widths differ
    (int8 vs int32 on ``period`` / ``symbol``). Single-file reads must not
    merge the partition tree.
    """
    pf = pq.ParquetFile(path)
    if columns is None:
        return pf.read()
    return pf.read(columns=list(columns))


def _max_time_ms(path: Path) -> Optional[int]:
    """Return max ``time`` in daily parquet, or None if unreadable/empty."""
    if not path.is_file() or path.stat().st_size == 0:
        return None
    try:
        table = _read_single_parquet(path, columns=["time"])
    except Exception:
        return None
    if table.num_rows == 0:
        return None
    times_col = table.column("time")
    if times_col.length == 0 or times_col.null_count == times_col.length:
        return None
    mx_val = max(v for v in times_col.to_pylist() if v is not None)
    return int(mx_val)


def mirror_none_tail_to_front(
    base_dir: Path | str,
    processed: Dict[str, pd.DataFrame],
    *,
    ex_set: Optional[Set[str]] = None,
    mode: str | None = None,
    max_workers: int | None = None,
) -> MirrorStats:
    """Mirror none ``processed`` bars into front for dates after existing front max.

    Invariant (plan v2): ``D_mirror = {t in processed.time | t > max(front.time)}``.

    - Skips codes in ``ex_set`` (canonical symbols; leave to QMT front full refresh).
    - Does **not** create front files when missing (fail-closed).
    - Does **not** fill mid-history holes (``t < max(front)`` missing days).
    - Never overlays pre-ex front history with full none frames.
    """
    stats = MirrorStats()
    if not processed:
        return stats

    base = Path(base_dir)
    ex_canon = {to_canonical_symbol(c) for c in (ex_set or set())}
    m = resolve_write_mode(mode)
    items: List[Tuple[Path, pd.DataFrame]] = []
    days_per_item: List[int] = []

    n_processed = len(processed)
    logger.info(f"mirror_front prepare: scanning {n_processed} none frames (mode={m})")
    last_prep = mono_now()
    scanned = 0
    for code, df in processed.items():
        scanned += 1
        if (mono_now() - last_prep) >= 10.0 or scanned == n_processed:
            logger.info(f"mirror_front prepare: progress {scanned}/{n_processed}")
            last_prep = mono_now()
        if not isinstance(df, pd.DataFrame) or df.empty:
            stats.skipped_empty += 1
            continue
        canon = to_canonical_symbol(code)
        if canon in ex_canon:
            stats.skipped_ex += 1
            continue

        front_path = _file_path(base, "front", canon, ensure_dir=False)
        max_front = _max_time_ms(front_path)
        if max_front is None:
            stats.missing_front += 1
            stats.missing_front_codes.append(canon)
            continue

        try:
            norm = _normalize_new_frame(df)
        except Exception as exc:  # noqa: BLE001
            stats.errors.append(f"{canon}: normalize: {type(exc).__name__}: {exc}")
            continue

        tail = norm.loc[norm["time"].astype("int64") > max_front].copy()
        if tail.empty:
            stats.empty_tail += 1
            continue
        tail = tail.dropna(subset=["close"])
        if tail.empty:
            stats.empty_tail += 1
            continue

        # ensure_dir for write target
        write_path = _file_path(base, "front", canon, ensure_dir=True)
        items.append((write_path, tail))
        days_per_item.append(int(len(tail)))

    if not items:
        return stats

    if m == "legacy":
        ok = 0
        for (path, df_tail), n_days in zip(items, days_per_item):
            try:
                _legacy_merge_write(path, df_tail)
                ok += 1
                stats.days_mirrored += n_days
            except Exception as exc:  # noqa: BLE001
                stats.errors.append(f"{path}: {type(exc).__name__}: {exc}")
        stats.mirrored = ok
        return stats

    ok, errors = merge_write_many_parallel(
        items,
        max_workers=max_workers,
        progress_label="mirror_front write",
    )
    stats.mirrored = ok
    stats.errors.extend(errors)
    # Days submitted for mirror (not reduced on partial write failure).
    stats.days_mirrored = int(sum(days_per_item))
    return stats


def merge_write_one_daily(
    file_path: Path,
    df_new: pd.DataFrame,
    *,
    engine: str = "pyarrow",
) -> None:
    """Merge ``df_new`` into one daily parquet (Shanghai-day dedupe, keep last).

    Both append-fast and overlap paths collapse on Shanghai calendar day so
    CST-as-UTC vs UTC-midnight for the same session cannot stack (plan A / lesson
    34 clarification: incremental tip dedupe ≠ full-history unify).

    Incoming ``time`` is normalized to UTC midnight before write; fail-closed if
    ``(time % 86400000).sum() != 0``.
    """
    del engine  # reserved; always pyarrow
    df_new = normalize_daily_times_to_utc_midnight(_normalize_new_frame(df_new))
    new_table = canonicalize_arrow_daily_table(
        pa.Table.from_pandas(df_new, preserve_index=False)
    )

    if not file_path.exists() or file_path.stat().st_size == 0:
        pq.write_table(new_table, file_path, compression="snappy")
        return

    existing = canonicalize_arrow_daily_table(
        _read_single_parquet(file_path, columns=STANDARD_COLUMNS)
    )
    if existing.num_rows == 0:
        pq.write_table(new_table, file_path, compression="snappy")
        return

    exist_time_list = existing.column("time").to_pylist()
    new_times = new_table.column("time").to_pylist()
    new_day_keys = set(
        int(x)
        for x in utc_midnight_ms_from_time_ms(
            pd.Series(new_times, dtype="int64")
        ).tolist()
    )
    exist_day_keys = utc_midnight_ms_from_time_ms(
        pd.Series(exist_time_list, dtype="int64")
    ).tolist()

    max_exist = (
        max(int(t) for t in exist_time_list if t is not None)
        if exist_time_list
        else None
    )
    min_new = min(int(t) for t in new_times if t is not None) if new_times else None
    exist_all_utc = all(
        int(t) % _MS_PER_DAY == 0 for t in exist_time_list if t is not None
    )

    # Append-fast only when history is already UTC-midnight and new is strictly after.
    if (
        exist_all_utc
        and max_exist is not None
        and min_new is not None
        and int(min_new) > int(max_exist)
    ):
        merged = pa.concat_tables([existing, new_table])
    else:
        keep_mask = [int(k) not in new_day_keys for k in exist_day_keys]
        kept = existing.filter(pa.array(keep_mask))
        merged = pa.concat_tables([kept, new_table])

    merged = canonicalize_arrow_daily_table(merged.sort_by("time"))
    pq.write_table(merged, file_path, compression="snappy")


def merge_write_many_parallel(
    items: Sequence[Tuple[Path, pd.DataFrame]],
    *,
    max_workers: int | None = None,
    progress_label: str | None = None,
    progress_interval_sec: float = 10.0,
) -> Tuple[int, List[str]]:
    """Parallel merge-write. Returns (ok_count, error messages).

    When ``progress_label`` is set, emit heartbeat lines about every
    ``progress_interval_sec`` (lesson 43: Agent must not treat write/mirror
    silence as hang).
    """
    workers = max_workers or _DEFAULT_WORKERS
    ok = 0
    errors: List[str] = []
    if not items:
        return 0, errors

    total = len(items)
    label = (progress_label or "").strip()
    interval = max(0.0, float(progress_interval_sec))
    last_beat = mono_now()
    done = 0

    def _one(pair: Tuple[Path, pd.DataFrame]) -> Optional[str]:
        path, df = pair
        try:
            merge_write_one_daily(path, df)
            return None
        except Exception as exc:  # noqa: BLE001
            return f"{path}: {type(exc).__name__}: {exc}"

    if label:
        logger.info(f"{label}: start {total} files (workers={workers})")

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(_one, it): it[0] for it in items}
        for fut in as_completed(futs):
            err = fut.result()
            if err is None:
                ok += 1
            else:
                errors.append(err)
            done += 1
            if label:
                now = mono_now()
                # interval<=0 → every completion (tests / verbose)
                due = done == total or interval <= 0 or (now - last_beat) >= interval
                if due:
                    pct = 100.0 * done / total
                    logger.info(
                        f"{label}: progress {done}/{total} "
                        f"({pct:.1f}%) ok={ok} err={len(errors)}"
                    )
                    last_beat = now
    return ok, errors


def write_processed_data(
    base_dir: Path | str,
    adjust_type: str,
    processed: Dict[str, pd.DataFrame],
    *,
    mode: WriteMode | None = None,
    max_workers: int | None = None,
) -> Tuple[int, List[str]]:
    """Write downloader ``processed_data`` map to hive partitions."""
    base = Path(base_dir)
    m = resolve_write_mode(mode)
    items: List[Tuple[Path, pd.DataFrame]] = []
    for code, df in processed.items():
        items.append((_file_path(base, adjust_type, code), df))

    if m == "legacy":
        ok = 0
        errors: List[str] = []
        for path, df in items:
            try:
                _legacy_merge_write(path, df)
                ok += 1
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{path}: {exc}")
        return ok, errors

    # parallel and batch: in-memory frames → same PyArrow parallel write
    return merge_write_many_parallel(
        items,
        max_workers=max_workers,
        progress_label=f"parquet write ({adjust_type})",
    )


def _legacy_merge_write(file_path: Path, df_new: pd.DataFrame) -> None:
    """Legacy pandas merge — same Shanghai-day / UTC-midnight contract as merge_write_one_daily."""
    df_new = normalize_daily_times_to_utc_midnight(_normalize_new_frame(df_new))
    if file_path.exists() and file_path.stat().st_size > 0:
        df_existing = pd.read_parquet(file_path, engine="pyarrow")
        for col in STANDARD_COLUMNS:
            if col not in df_existing.columns and col in df_new.columns:
                df_existing[col] = pd.NA
        df_existing = df_existing[STANDARD_COLUMNS].copy()
        df_existing["_day"] = utc_midnight_ms_from_time_ms(
            cast(pd.Series, df_existing["time"])
        )
        new_days = set(
            utc_midnight_ms_from_time_ms(cast(pd.Series, df_new["time"])).tolist()
        )
        df_existing = df_existing.loc[
            ~as_series(df_existing["_day"]).isin(list(new_days))
        ].drop(columns=["_day"])
        df_merged = cast(
            pd.DataFrame, pd.concat([df_existing, df_new], ignore_index=True)
        )
        df_merged = df_merged.sort_values("time", kind="mergesort")
        df_merged = df_merged.drop_duplicates(subset=["time"], keep="last")
        df_merged.to_parquet(
            file_path, engine="pyarrow", compression="snappy", index=False
        )
    else:
        df_new.to_parquet(
            file_path, engine="pyarrow", compression="snappy", index=False
        )


def path_b_append_front_today(
    codes: Sequence[str],
    target_date: pd.Timestamp,
    base_dir: Path | str,
    *,
    mode: str | None = None,
    max_workers: int | None = None,
) -> int:
    """Path B: front today OHLC = none today OHLC for non-ex-date codes."""
    m = resolve_write_mode(mode)
    base = Path(base_dir)
    target_norm = normalize_timestamp(pd.Timestamp(target_date))
    target_ms = int(target_norm.value // 10**6)

    if m == "batch":
        return _path_b_batch(codes, target_ms, base, max_workers=max_workers)
    if m == "legacy":
        return _path_b_legacy(codes, target_norm, base)
    return _path_b_parallel(
        codes, target_norm, target_ms, base, max_workers=max_workers
    )


def _load_none_today_row(
    base: Path, code: str, target_ms: int
) -> Optional[pd.DataFrame]:
    path = _file_path(base, "none", code)
    if not path.is_file() or path.stat().st_size == 0:
        return None
    try:
        table = _read_single_parquet(path, columns=STANDARD_COLUMNS)
    except Exception:
        return None
    times = table.column("time").to_pylist()
    # Match Shanghai calendar day under either encoding:
    # - UTC midnight of D (path B / some QMT paths)
    # - CST-as-UTC: Shanghai midnight stored as (D-1) 16:00 UTC (dominant history)
    # Do NOT rewrite full history; only select today's row for path-b-repair.
    target_day = normalize_timestamp(pd.Timestamp(target_ms, unit="ms"))
    idxs: List[int] = []
    for i, t in enumerate(times):
        if t is None:
            continue
        sh_day = normalize_timestamp(
            pd.Timestamp(int(t), unit="ms") + pd.Timedelta(hours=8)
        )
        if sh_day == target_day:
            idxs.append(i)
    if not idxs:
        return None
    i = idxs[0]
    row = table.slice(i, 1).to_pandas()
    if row["close"].isna().any():
        return None
    # Path B today-only: write UTC midnight ms (pre-existing; not full-history unify)
    row = row.copy()
    row.loc[:, "time"] = target_ms
    return row[STANDARD_COLUMNS]


def _path_b_parallel(
    codes: Sequence[str],
    target_norm: pd.Timestamp,
    target_ms: int,
    base: Path,
    *,
    max_workers: int | None,
) -> int:
    items: List[Tuple[Path, pd.DataFrame]] = []
    for code in codes:
        row = _load_none_today_row(base, code, target_ms)
        if row is None:
            continue
        items.append((_file_path(base, "front", code), row))
    ok, _errors = merge_write_many_parallel(items, max_workers=max_workers)
    return ok


def _path_b_legacy(codes: Sequence[str], target_norm: pd.Timestamp, base: Path) -> int:
    """Serial path matching historical ``_path_b_append_front_today`` semantics."""
    ok = 0
    target_ms = int(target_norm.value // 10**6)
    for code in codes:
        row = _load_none_today_row(base, code, target_ms)
        if row is None:
            continue
        try:
            merge_write_one_daily(_file_path(base, "front", code), row)
            ok += 1
        except Exception:
            continue
    return ok


def _path_b_batch(
    codes: Sequence[str],
    target_ms: int,
    base: Path,
    *,
    max_workers: int | None,
) -> int:
    """DuckDB batch-**read** today's none, then PyArrow parallel merge-write front."""
    import duckdb

    if not codes:
        return 0

    parts = sorted({to_partition_key(to_canonical_symbol(c)) for c in codes})
    from common.infra.data_root import resolve_period_root

    none_glob = str(
        resolve_period_root("1d", base=base)
        / "dividend_type=none" / "symbol=*" / "data.parquet"
    ).replace("\\", "/")
    day_end = target_ms + 86_400_000

    conn = duckdb.connect()
    try:
        conn.execute("CREATE TEMP TABLE path_b_parts (symbol_dir VARCHAR)")
        conn.executemany("INSERT INTO path_b_parts VALUES (?)", [(p,) for p in parts])
        # filename .../symbol=000001_SZ/data.parquet
        today = conn.execute(
            f"""
            SELECT
                regexp_extract(filename, 'symbol=([^\\\\/]+)', 1) AS symbol_dir,
                {target_ms}::BIGINT AS time,
                open, high, low, close, volume, amount
            FROM read_parquet('{none_glob}', filename=true)
            WHERE time IS NOT NULL
              AND close IS NOT NULL
              AND time >= {target_ms}
              AND time < {day_end}
              AND regexp_extract(filename, 'symbol=([^\\\\/]+)', 1) IN (SELECT symbol_dir FROM path_b_parts)
            """
        ).df()
    finally:
        conn.close()

    if today.empty:
        return 0

    items: List[Tuple[Path, pd.DataFrame]] = []
    for symbol_dir, grp in today.groupby("symbol_dir", sort=False):
        row = grp.iloc[[0]][STANDARD_COLUMNS].copy()
        code = to_canonical_symbol(str(symbol_dir))
        items.append((_file_path(base, "front", code), row))
    ok, _errors = merge_write_many_parallel(items, max_workers=max_workers)
    return ok


def iter_write_modes() -> Iterable[WriteMode]:
    yield from ("legacy", "parallel", "batch")
