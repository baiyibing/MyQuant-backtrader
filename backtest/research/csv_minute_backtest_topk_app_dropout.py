# -*- coding: utf-8 -*-
"""Strategy topk_app_dropout — new book, does not modify strategy 7.

Buy universe = app day-list ∩ qlib TopK (default 50, pred_minus_one).
Position machine = same functions strategy 7 uses (imported, not edited).
Entry is this file. Output is ``backtest_output/csv_minute_topk_app_dropout_*``.
Do not call ``csv_minute_backtest_v7.py`` for this book.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Sequence

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backtest.research.csv_minute_backtest_v7 import (
    _load_cli_bars,
    load_index_daily,
    load_pool_days,
    simulate_v7,
    summarize_v7,
    write_run_artifacts,
)
from backtest.research.csv_pool import is_repo_stock_pool
from backtest.research.market_layer import as_date as _as_date
from backtest.research.topk_app_dropout import (
    BOOK_TAG,
    DEFAULT_TOPK,
    intersect_app_qlib,
    load_pred_frame,
    overlap_stats,
    qlib_topn_by_buy_day,
    write_overlap_report,
    write_topk_app_dropout_pool,
)

# 50 名 × 单票 100 万 = 5000 万；默认 5 亿（与 v8 研究口径同级）。不改策略 7 的 2100 万。
DEFAULT_CASH_TOTAL = 500_000_000.0

REPO_ROOT = Path(__file__).resolve().parents[2]


def build_intersect_pool_days(
    app_dir: Path,
    pred_path: Path,
    start: str,
    end: str,
    *,
    topk: int = DEFAULT_TOPK,
    asof: str = "pred_minus_one",
    dump_dir: Path | None = None,
) -> dict:
    pred = load_pred_frame(pred_path)
    topn = qlib_topn_by_buy_day(pred, topk=int(topk), asof=asof)
    days = intersect_app_qlib(app_dir, topn, start=start, end=end)
    if dump_dir is not None:
        if is_repo_stock_pool(dump_dir, repo=REPO_ROOT):
            raise SystemExit(f"refusing to write into stock_pool/: {dump_dir}")
        write_topk_app_dropout_pool(days, dump_dir, repo=REPO_ROOT)
        write_overlap_report(
            dump_dir / "overlap.json",
            {
                "book": BOOK_TAG,
                "app_pool_dir": str(app_dir),
                "pred": str(pred_path),
                "start": start,
                "end": end,
                "topk": int(topk),
                "asof": asof,
                **overlap_stats(days),
            },
        )
    out = {}
    for ymd, rows in days.items():
        out[datetime.strptime(ymd, "%Y%m%d").date()] = [canon for canon, _name in rows]
    return out


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            f"Strategy {BOOK_TAG}: app ∩ qlib TopK buys; "
            "own entry, does not change strategy 7"
        )
    )
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--app-pool-dir", type=Path)
    parser.add_argument("--pred", type=Path, help="MyQuant pred CSV")
    parser.add_argument("--topk", type=int, default=DEFAULT_TOPK)
    parser.add_argument(
        "--asof",
        choices=("pred_minus_one", "identity"),
        default="pred_minus_one",
    )
    parser.add_argument(
        "--pool-dir",
        type=Path,
        help="Prebuilt intersect pool (skip --app-pool-dir/--pred)",
    )
    parser.add_argument("--dump-pool-dir", type=Path, help="Write intersect CSVs here")
    parser.add_argument("--cash-total", type=float, default=DEFAULT_CASH_TOTAL)
    parser.add_argument("--output-dir")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    start, end = _as_date(args.start), _as_date(args.end)
    if end < start:
        raise SystemExit("--end must be on or after --start")
    start_ymd, end_ymd = start.strftime("%Y%m%d"), end.strftime("%Y%m%d")

    if args.pool_dir is not None:
        pools = load_pool_days(Path(args.pool_dir), start, end)
    else:
        if args.app_pool_dir is None or args.pred is None:
            raise SystemExit("need --pool-dir, or both --app-pool-dir and --pred")
        app_dir = args.app_pool_dir.expanduser().resolve()
        pred_path = args.pred.expanduser().resolve()
        if not app_dir.is_dir():
            raise SystemExit(f"app pool dir missing: {app_dir}")
        if not pred_path.is_file():
            raise SystemExit(f"pred missing: {pred_path}")
        dump = args.dump_pool_dir
        if dump is None:
            dump = REPO_ROOT / "exports" / f"{BOOK_TAG}_{start_ymd}_{end_ymd}"
        pools = build_intersect_pool_days(
            app_dir,
            pred_path,
            start_ymd,
            end_ymd,
            topk=int(args.topk),
            asof=args.asof,
            dump_dir=dump,
        )

    minute, daily = _load_cli_bars(pools, start, end)
    if pools:
        index_closes = load_index_daily(start, end)
    else:
        index_closes = []
    state = simulate_v7(
        minute,
        daily,
        pools,
        index_closes,
        cash_total=args.cash_total,
        start=start,
        end=end,
    )
    output = Path(
        args.output_dir
        or f"backtest_output/csv_minute_{BOOK_TAG}_{args.start}_{args.end}"
    )
    write_run_artifacts(state, output)
    header = f"strategy={BOOK_TAG} (not strategy 7)\n"
    (output / "summary.txt").write_text(
        header + summarize_v7(state), encoding="utf-8"
    )
    print(header, end="")
    print(summarize_v7(state), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
