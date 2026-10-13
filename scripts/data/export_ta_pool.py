#!/usr/bin/env python3
"""Source B: resist_tr_bb_1000 → contract day CSVs (plan #31 A–C).

B-R2: filename = buy day T; only date<=T bars / section. Not Qlib pred_minus_one.
B-R3: only resist_tr_bb_1000 / window=1000.
B-R4: default universe = lake period=1d names with a bar on T.
      Inject with --universe-file. Never default to stock_pool/ or pred.
      Host fast path: --universe-mode lake_tr (lake partition names ∩ TR section).
B-R6: no TopK. To match width, post-truncate with m5_hand_topn --k 10.

Never writes stock_pool/. CI injects cross-section + universe. Live Store is
host-only and is not a merge gate.
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable, Optional, Sequence

import pandas as pd
import pyarrow.compute as pc
import pyarrow.parquet as pq

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backtest.research.csv_pool import (  # noqa: E402
    is_repo_stock_pool,
    validate_pool_dir,
)
from backtest.research.csv_sim_profile import (  # noqa: E402
    SimPhaseClock,
    format_profile_lines,
    profile_sim_enabled,
)
from backtest.research.market_layer import utc_ms_range  # noqa: E402
from backtest.research.source_b_tr_pool import (  # noqa: E402
    WINDOW,
    normalize_stock_code,
    scan_tr_days,
    unique_preserve,
    write_tr_pool,
)
from common.infra.data_root import resolve_period_root  # noqa: E402
from oskh_data.symbol_format import to_canonical_symbol, to_partition_key  # noqa: E402

HELP_LOCK = """
B-R2: 文件名=买入日 T。只用 date<=T 的 K / 截面。不是 Qlib pred_minus_one，无 --asof。
B-R3: v0 唯一规则 resist_tr_bb_1000（window=1000）。不改阈值。
B-R4: 默认宇宙=湖 period=1d 当日有 K 的代码（--universe-mode lake_bar）。
      宿主快路径 --universe-mode lake_tr：湖分区名 ∩ 当日 TR 截面（免逐票开 parquet）。
      --universe-file 注入。禁止默认 stock_pool/ 或 pred。
B-R6: 不做 TopK；过线几只写几只。对齐宽度后置 m5_hand_topn --k 10。
性能: 默认写 profile_export.json（OSKH_PROFILE_SIM=0 关闭）。Store 会话内整表只读一次。
"""


def default_out_dir(start: str, end: str) -> Path:
    return REPO_ROOT / "exports" / f"src_b_tr_bb1000_{start}_{end}"


def _dates_between(start: str, end: str) -> list[str]:
    return [ts.strftime("%Y%m%d") for ts in pd.bdate_range(start, end)]


def _loader_from_frame(frame: pd.DataFrame) -> Callable[[str], pd.DataFrame]:
    if frame.empty or "trade_date" not in frame.columns:
        return lambda _ymd: pd.DataFrame()
    work = frame.copy()
    work["trade_date"] = (
        work["trade_date"].astype(str).str.replace("-", "", regex=False)
    )

    def load(ymd: str) -> pd.DataFrame:
        return work.loc[work["trade_date"] == str(ymd)].copy()

    return load


def _loader_from_store(
    parquet_path: Optional[Path],
) -> tuple[Callable[[str], pd.DataFrame], Any]:
    from oskh_data.turnover_resistance_store import TurnoverResistanceStore

    store = TurnoverResistanceStore(parquet_path)

    def load(ymd: str) -> pd.DataFrame:
        return store.load_cross_section(ymd, window=WINDOW, require_bands=True)

    return load, store


def parse_universe_file(path: Path) -> list[str]:
    text = Path(path).read_text(encoding="utf-8")
    return unique_preserve(line.strip() for line in text.splitlines() if line.strip())


def list_lake_symbols(root: Path) -> list[str]:
    out: list[str] = []
    for part in sorted(Path(root).glob("symbol=*")):
        if not (part / "data.parquet").is_file():
            continue
        code = to_canonical_symbol(part.name[len("symbol=") :])
        if code:
            out.append(code)
    return out


def has_bar_on_day(code: str, root: Path, ymd: str) -> bool:
    """True when the lake has a non-zero-volume bar on T (date<=T by construction)."""
    path = Path(root) / f"symbol={to_partition_key(code)}" / "data.parquet"
    if not path.is_file():
        return False
    t0, t1 = utc_ms_range(ymd, ymd)
    try:
        names = pq.read_schema(path).names
        cols = ["time"] + (["volume"] if "volume" in names else [])
        table = pq.read_table(path, columns=cols)
        table = table.filter((pc.field("time") >= t0) & (pc.field("time") <= t1))
        if "volume" in table.column_names:
            table = table.filter(pc.field("volume") != 0)
    except Exception:
        return False
    return table.num_rows > 0


def lake_universe_on_day(
    root: Path,
    ymd: str,
    *,
    workers: int = 16,
    symbols: Optional[Sequence[str]] = None,
) -> list[str]:
    """B-R4: lake names that have a bar on T, partition-name order."""
    codes = list(symbols) if symbols is not None else list_lake_symbols(root)
    if not codes:
        return []
    kept: list[str] = []
    n = max(1, int(workers))
    with ThreadPoolExecutor(max_workers=n) as pool:
        futs = {pool.submit(has_bar_on_day, code, root, ymd): code for code in codes}
        present: set[str] = set()
        for fut in as_completed(futs):
            code = futs[fut]
            try:
                ok = bool(fut.result())
            except Exception:
                ok = False
            if ok:
                present.add(code)
    for code in codes:
        if code in present:
            kept.append(code)
    return kept


def lake_tr_universe_for_day(
    *,
    lake_order: Sequence[str],
    load_cross_section: Callable[[str], pd.DataFrame],
    ymd: str,
) -> list[str]:
    """Host fast path: lake partition names ∩ that day's TR section (cache-friendly)."""
    section = load_cross_section(ymd)
    if section is None or section.empty or "stock_code" not in section.columns:
        return []
    in_section = {
        normalize_stock_code(code)
        for code in section["stock_code"].tolist()
        if normalize_stock_code(code)
    }
    return [code for code in lake_order if code in in_section]


def resolve_lake_root(explicit: Optional[Path]) -> Path:
    if explicit is not None:
        return Path(explicit)
    return resolve_period_root("1d") / "dividend_type=none"


def write_widths(rows: Sequence[tuple[str, int]], dest: Path) -> Path:
    dest = Path(dest)
    dest.write_text(
        "".join(f"{ymd} {width}\n" for ymd, width in rows),
        encoding="utf-8",
        newline="\n",
    )
    return dest


def write_profile_export(out_dir: Path, report: dict[str, Any]) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "profile_export.json"
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return path


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="Source B TA pool exporter (resist_tr_bb_1000); never stock_pool/",
        epilog=HELP_LOCK,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--start", required=True, help="first buy-day filename YYYYMMDD")
    ap.add_argument("--end", required=True, help="last buy-day filename YYYYMMDD")
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument(
        "--universe-file",
        type=Path,
        default=None,
        help="injected candidate codes (B-R4 CI path). Not stock_pool/",
    )
    ap.add_argument(
        "--universe-mode",
        choices=("lake_bar", "lake_tr"),
        default="lake_bar",
        help=(
            "when --universe-file is omitted: lake_bar=has bar on T (strict B-R4); "
            "lake_tr=lake partition ∩ TR section (host fast path)"
        ),
    )
    ap.add_argument(
        "--inject-cross-section",
        type=Path,
        default=None,
        help="CSV/Parquet fixture with trade_date + stock_code (CI)",
    )
    ap.add_argument(
        "--store-parquet",
        type=Path,
        default=None,
        help="optional TurnoverResistanceStore path; host only",
    )
    ap.add_argument(
        "--lake-root",
        type=Path,
        default=None,
        help="override period=1d dividend_type=none root (tests / host)",
    )
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument(
        "--profile",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="write profile_export.json (default on; OSKH_PROFILE_SIM=0 disables)",
    )
    args = ap.parse_args(argv if argv is not None else None)

    out_dir = (
        Path(args.out_dir)
        if args.out_dir is not None
        else default_out_dir(args.start, args.end)
    )
    if is_repo_stock_pool(out_dir):
        raise SystemExit(f"refusing to write into stock_pool/: {out_dir}")
    if args.universe_file is not None and is_repo_stock_pool(args.universe_file):
        raise SystemExit(f"refusing stock_pool/ as universe: {args.universe_file}")

    clock = SimPhaseClock() if profile_sim_enabled(args.profile) else None
    store: Any = None

    with (clock.phase("load_source") if clock else _null_phase()):
        if args.inject_cross_section is not None:
            path = Path(args.inject_cross_section)
            if path.suffix.lower() in {".csv", ".txt"}:
                frame = pd.read_csv(path)
            else:
                frame = pd.read_parquet(path)
            loader = _loader_from_frame(frame)
            source_kind = "inject"
        else:
            loader, store = _loader_from_store(args.store_parquet)
            source_kind = "store"
            # Warm the session cache once up front (whole-table read).
            loader(args.start)

    if args.universe_file is not None:
        with (clock.phase("universe_setup") if clock else _null_phase()):
            injected = parse_universe_file(args.universe_file)

        def universe_for(_ymd: str) -> Sequence[str]:
            return injected

        universe_mode = "file"
    elif args.inject_cross_section is not None:
        raise SystemExit(
            "B-R4: --inject-cross-section requires --universe-file "
            "(do not default universe to the section)"
        )
    else:
        lake = resolve_lake_root(args.lake_root)
        print(f"src_b lake universe from {lake} mode={args.universe_mode}", flush=True)
        with (clock.phase("list_lake_symbols") if clock else _null_phase()):
            lake_order = list_lake_symbols(lake)
        if args.universe_mode == "lake_tr":

            def universe_for(ymd: str) -> Sequence[str]:
                return lake_tr_universe_for_day(
                    lake_order=lake_order,
                    load_cross_section=loader,
                    ymd=ymd,
                )

            universe_mode = "lake_tr"
        else:

            def universe_for(ymd: str) -> Sequence[str]:
                return lake_universe_on_day(
                    lake, ymd, workers=args.workers, symbols=lake_order
                )

            universe_mode = "lake_bar"

    dates = _dates_between(args.start, args.end)
    days = scan_tr_days(
        dates,
        load_cross_section=loader,
        universe_for=universe_for,
        fail_closed=True,
        clock=clock,
    )
    with (clock.phase("write_pool") if clock else _null_phase()):
        written = write_tr_pool(days, out_dir, repo=REPO_ROOT)
        widths = [(ymd, len(days.get(ymd, []))) for ymd in sorted(days)]
        # Also record calendar days that produced zero width for audit.
        width_all = [(ymd, len(days.get(ymd, []))) for ymd in dates]
        write_widths(width_all, out_dir / "widths.txt")
    with (clock.phase("validate") if clock else _null_phase()):
        failures = validate_pool_dir(out_dir)
    if failures:
        raise SystemExit("validate_pool_dir failed: " + "; ".join(failures[:8]))

    name_total = sum(w for _d, w in widths)
    print(
        f"src_b wrote {len(written)} files, "
        f"{name_total} names -> {out_dir}",
        flush=True,
    )
    if not written:
        raise SystemExit(f"no TR pool days in [{args.start}, {args.end}]")

    if clock is not None:
        extra: dict[str, Any] = {
            "job": "export_ta_pool",
            "strategy": "version10",
            "start": str(args.start),
            "end": str(args.end),
            "universe_mode": universe_mode,
            "source_kind": source_kind,
            "calendar_days": len(dates),
            "pool_days": len(written),
            "pool_names": name_total,
            "out_dir": str(out_dir),
        }
        if store is not None:
            extra["store"] = store.cache_stats()
            extra["store_path"] = str(store.path)
        report = clock.report(**extra)
        write_profile_export(out_dir, report)
        for line in format_profile_lines(report):
            print(line, flush=True)
        store_bits = ""
        if store is not None:
            stats = store.cache_stats()
            store_bits = (
                f" | store_disk={stats['read_disk_loads']}"
                f" cache_hit={stats['read_cache_hits']}"
            )
        print(
            f"profile_export: wall={report['wall_s']:.1f}s "
            f"pool_days={len(written)} names={name_total}{store_bits} -> "
            f"{out_dir / 'profile_export.json'}",
            flush=True,
        )
    return 0


class _NullPhaseCtx:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _null_phase() -> _NullPhaseCtx:
    return _NullPhaseCtx()


if __name__ == "__main__":
    raise SystemExit(main())
