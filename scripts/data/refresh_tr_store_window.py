#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Research-only host helper: refresh TR store for a date window, then TR BB.

4090 / host tooling so Strategy10 (Source-B) pool export can load
``require_bands=True`` cross-sections. Does **not** write ``stock_pool/``.
Does **not** change production fill / scan / fee / defaults / hot-path code.

Primary path reuses the Rust bridge (``compute_turnover_resist``) +
``TurnoverResistanceStore.upsert_daily`` / ``compute_and_update_bands``, same
building blocks as ``scripts/tr/backfill_turnover_resistance_bands.py`` and
``scripts/tr/compute_turnover_resistance_bands.py``.

Float / free-float parquet normally live beside the lake (on 4090:
``E:/stock_data/float_shares.parquet`` and
``E:/stock_data/free_float_shares.parquet``). The Python research script
``full_market_canonical_resist.py`` hard-codes cwd-relative
``stock_data/float_shares.parquet`` — if you ever need that layout, copy or
symlink from ``E:/stock_data/``, or pass ``--float-shares`` /
``--free-float-shares`` so this helper materializes cwd ``stock_data/`` links
for the session.

4090 recipe::

    python scripts/data/refresh_tr_store_window.py \
        --start 20260825 --end 20260909 \
        --store-parquet E:/stock_data/turnover_resistance_daily.parquet

    python scripts/data/export_strategy10_pool.py \
        --start 20260825 --end 20260909 \
        --out-dir D:/exports/s10_tr_bb1000_20260825_20260909 \
        --store-parquet E:/stock_data/turnover_resistance_daily.parquet

If ``tr_bb_*`` are NaN on dates that already have TR rows, re-run with
``--bands-only`` (widen ``--start``/``--end`` if needed). For BB quality
across a coverage gap, also refresh the missing trading days before the
export window (period=20 needs ~20 prior TR rows per name).
"""

from __future__ import annotations

import argparse
import shutil
import sys
import time
from pathlib import Path
from typing import Callable, Optional, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts._script_bootstrap import ensure_repo_on_syspath  # noqa: E402

ensure_repo_on_syspath(__file__)

from common.infra.data_root import resolve_turnover_resist_parquet_root  # noqa: E402
from common.infra.quant_logger import get_logger  # noqa: E402
from oskh_core.turnover_resist_bridge import compute_turnover_resist  # noqa: E402
from oskh_data.turnover_resistance_store import (  # noqa: E402
    DEFAULT_FREE_FLOAT_POLICY,
    DEFAULT_WINDOW,
    TurnoverResistanceStore,
)
from scripts.tr.backfill_turnover_resistance_bands import (  # noqa: E402
    list_trading_dates,
)

_log = get_logger(__name__)

CANONICAL_WINDOW = 1000
ComputeFn = Callable[..., list]


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Research-only: refresh TurnoverResistanceStore for [start, end] "
            "and compute tr_bb_* so require_bands=True returns rows."
        )
    )
    p.add_argument("--start", required=True, help="Inclusive YYYYMMDD")
    p.add_argument("--end", required=True, help="Inclusive YYYYMMDD")
    p.add_argument(
        "--store-parquet",
        required=True,
        help="Path to turnover_resistance_daily.parquet",
    )
    p.add_argument(
        "--lake-root",
        default="",
        help=(
            "Parquet lake / TR data_dir (period=1d hive + float shares). "
            "Default: resolve_turnover_resist_parquet_root() / "
            "TURNOVER_RESIST_DATA_DIR."
        ),
    )
    p.add_argument(
        "--workers",
        type=int,
        default=1,
        help=(
            "Reserved for host parallelism hints (Rust/FFI path is per-day "
            "sequential; value is logged only)."
        ),
    )
    p.add_argument(
        "--skip-existing-tr",
        action="store_true",
        help="Skip Rust TR compute/upsert when trade_date already in store",
    )
    p.add_argument(
        "--bands-only",
        action="store_true",
        help="Skip TR compute; only compute_and_update_bands for dates in window",
    )
    p.add_argument("--window", type=int, default=CANONICAL_WINDOW)
    p.add_argument(
        "--free-float-policy",
        default=DEFAULT_FREE_FLOAT_POLICY,
        choices=("warn-zero", "skip", "fail"),
    )
    p.add_argument(
        "--bands-history",
        type=int,
        default=60,
        help="Trading-day history window for TR BB rolling (default 60)",
    )
    p.add_argument("--bb-period", type=int, default=20)
    p.add_argument(
        "--float-shares",
        default="",
        help=(
            "Optional path to float_shares.parquet. If set, symlink/copy into "
            "./stock_data/float_shares.parquet for Python canonical-resist "
            "layouts that hard-code that relative path."
        ),
    )
    p.add_argument(
        "--free-float-shares",
        default="",
        help=(
            "Optional path to free_float_shares.parquet. Same materialize "
            "behavior as --float-shares."
        ),
    )
    return p.parse_args(list(argv) if argv is not None else None)


def _ymd_ok(value: str, label: str) -> str:
    s = str(value).strip()
    if len(s) != 8 or not s.isdigit():
        raise SystemExit(f"invalid {label}={value!r}; expected YYYYMMDD")
    return s


def _materialize_share_file(src: str, dest_name: str) -> Optional[Path]:
    """Link or copy *src* into cwd stock_data/<dest_name> when override given."""
    if not src:
        return None
    src_path = Path(src)
    if not src_path.is_file():
        raise SystemExit(f"{dest_name} override not found: {src_path}")
    dest_dir = Path("stock_data")
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / dest_name
    if dest.exists() or dest.is_symlink():
        if dest.resolve() == src_path.resolve():
            print(f"[shares] {dest_name} already at {dest}", flush=True)
            return dest
        dest.unlink()
    try:
        dest.symlink_to(src_path.resolve())
        print(f"[shares] linked {dest} -> {src_path}", flush=True)
    except OSError:
        shutil.copy2(src_path, dest)
        print(f"[shares] copied {src_path} -> {dest}", flush=True)
    return dest


def _resolve_lake_root(explicit: str) -> Path:
    if explicit:
        return Path(explicit)
    return resolve_turnover_resist_parquet_root()


def _count_banded_days(
    store: TurnoverResistanceStore,
    dates: Sequence[str],
    *,
    window: int,
) -> tuple[int, int, list[str]]:
    """Return (days_with_any_tr, days_with_bands, empty_or_missing_band_dates)."""
    with_tr = 0
    with_bands = 0
    empty_bands: list[str] = []
    for ymd in dates:
        raw = store.load_cross_section(ymd, window=window, require_bands=False)
        if raw.empty:
            empty_bands.append(ymd)
            continue
        with_tr += 1
        banded = store.load_cross_section(ymd, window=window, require_bands=True)
        if banded.empty:
            empty_bands.append(ymd)
        else:
            with_bands += 1
    return with_tr, with_bands, empty_bands


def refresh_window(
    *,
    start: str,
    end: str,
    store_parquet: str | Path,
    lake_root: str | Path,
    skip_existing_tr: bool = False,
    bands_only: bool = False,
    window: int = CANONICAL_WINDOW,
    free_float_policy: str = DEFAULT_FREE_FLOAT_POLICY,
    bands_history: int = 60,
    bb_period: int = 20,
    workers: int = 1,
    dates: Optional[Sequence[str]] = None,
    compute_fn: Optional[ComputeFn] = None,
) -> int:
    """Refresh TR (+ bands) for trading days in [start, end].

    *compute_fn* / *dates* are injectable for unit tests (data-free).
    Returns process exit code (0 ok, non-zero if window still empty for bands).
    """
    start = _ymd_ok(start, "start")
    end = _ymd_ok(end, "end")
    if start > end:
        print(f"[error] start={start} > end={end}", flush=True)
        return 1

    data_dir = Path(lake_root)
    store = TurnoverResistanceStore(store_parquet)
    compute = compute_fn or compute_turnover_resist

    if dates is None:
        try:
            dates = list_trading_dates(
                data_dir, start_date=start, end_date=end
            )
        except Exception as exc:
            print(
                f"[error] list_trading_dates failed under lake-root={data_dir}: {exc}",
                flush=True,
            )
            return 1

    dates = [str(d) for d in dates]
    if not dates:
        print(
            f"[error] no trading dates in [{start}, {end}] under {data_dir}",
            flush=True,
        )
        return 1

    if int(window) != CANONICAL_WINDOW:
        _log.warning(
            "non-canonical window",
            context={"window": window, "canonical": CANONICAL_WINDOW},
        )

    print(
        f"[plan] range={dates[0]}..{dates[-1]} days={len(dates)} "
        f"store={store.path} lake={data_dir} "
        f"bands_only={bands_only} skip_existing_tr={skip_existing_tr} "
        f"workers={workers} (rust path is sequential)",
        flush=True,
    )

    ok = fail = skip = 0
    t0 = time.perf_counter()

    if not bands_only:
        for i, trade_date in enumerate(dates, 1):
            if skip_existing_tr and store.has_trade_date(
                trade_date, window=window
            ):
                skip += 1
                print(
                    f"[{i}/{len(dates)}] skip-existing-tr {trade_date}",
                    flush=True,
                )
                continue
            try:
                rows = compute(
                    trade_date,
                    data_dir=str(data_dir),
                    window=window,
                    free_float_policy=free_float_policy,
                )
                if not rows:
                    fail += 1
                    print(f"[{i}/{len(dates)}] empty-tr {trade_date}", flush=True)
                    continue
                stats = store.upsert_daily(
                    trade_date,
                    rows,
                    window=window,
                    source="canonical_rust",
                    free_float_policy=free_float_policy,
                )
                ok += 1
                print(
                    f"[{i}/{len(dates)}] upsert {trade_date} rows={len(rows)} "
                    f"inserted={stats.get('inserted')} "
                    f"replaced={stats.get('replaced')} "
                    f"total={stats.get('total_after')}",
                    flush=True,
                )
            except Exception as exc:
                fail += 1
                _log.warning(
                    "compute_turnover_resist failed",
                    context={"trade_date": trade_date, "error": str(exc)},
                )
                print(f"[{i}/{len(dates)}] fail {trade_date}: {exc}", flush=True)

    t_bands = time.perf_counter()
    band_stats = store.compute_and_update_bands(
        trade_dates=list(dates),
        n_history=bands_history,
        period=bb_period,
        window=window,
    )
    print(
        f"[bands] updated_rows={band_stats.get('updated_rows')} "
        f"trade_dates={band_stats.get('trade_dates')} "
        f"elapsed={time.perf_counter() - t_bands:.1f}s",
        flush=True,
    )

    with_tr, with_bands, empty_bands = _count_banded_days(
        store, dates, window=window
    )
    elapsed = time.perf_counter() - t0
    print(
        f"[summary] tr_ok={ok} tr_fail={fail} tr_skip={skip} "
        f"days={len(dates)} with_tr={with_tr} with_bands={with_bands} "
        f"empty_or_no_bands={len(empty_bands)} elapsed={elapsed:.1f}s",
        flush=True,
    )
    if empty_bands:
        preview = ",".join(empty_bands[:8])
        more = "" if len(empty_bands) <= 8 else f"...(+{len(empty_bands) - 8})"
        print(
            f"[summary] still empty require_bands dates: {preview}{more}",
            flush=True,
        )

    # Fail-closed for Strategy10 export: window must yield banded cross-sections.
    if with_bands == 0:
        print(
            f"[error] window [{start},{end}] still has 0 days with "
            f"require_bands=True rows after refresh (store={store.path})",
            flush=True,
        )
        return 1
    if fail and not bands_only:
        return 1
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    _materialize_share_file(args.float_shares, "float_shares.parquet")
    _materialize_share_file(args.free_float_shares, "free_float_shares.parquet")
    try:
        lake = _resolve_lake_root(args.lake_root)
    except Exception as exc:
        print(f"[error] lake-root resolve failed: {exc}", flush=True)
        return 1
    return refresh_window(
        start=args.start,
        end=args.end,
        store_parquet=args.store_parquet,
        lake_root=lake,
        skip_existing_tr=args.skip_existing_tr,
        bands_only=args.bands_only,
        window=args.window,
        free_float_policy=args.free_float_policy,
        bands_history=args.bands_history,
        bb_period=args.bb_period,
        workers=args.workers,
    )


if __name__ == "__main__":
    raise SystemExit(main())
