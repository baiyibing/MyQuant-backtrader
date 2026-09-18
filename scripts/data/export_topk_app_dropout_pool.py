#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Export topk_app_dropout day lists: app pool ∩ qlib TopK.

Optional dump for the new strategy runner
``csv_minute_backtest_topk_app_dropout.py``. Does not change strategy 7.
Never writes ``stock_pool/``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backtest.research.csv_pool import is_repo_stock_pool, validate_pool_dir  # noqa: E402
from backtest.research.topk_app_dropout import (  # noqa: E402
    BOOK_TAG,
    DEFAULT_TOPK,
    intersect_app_qlib,
    load_pred_frame,
    overlap_stats,
    qlib_topn_by_buy_day,
    write_overlap_report,
    write_topk_app_dropout_pool,
)


def default_out_dir(start: str, end: str) -> Path:
    return REPO_ROOT / "exports" / f"{BOOK_TAG}_{start}_{end}"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "Write app∩qlib-TopK pool CSVs for strategy 7. "
            "Not a csv_strategy_books name."
        )
    )
    p.add_argument("--app-pool-dir", required=True, type=Path)
    p.add_argument("--pred", required=True, type=Path, help="MyQuant pred CSV")
    p.add_argument("--start", required=True, help="YYYYMMDD inclusive")
    p.add_argument("--end", required=True, help="YYYYMMDD inclusive")
    p.add_argument("--topk", type=int, default=DEFAULT_TOPK)
    p.add_argument(
        "--asof",
        choices=("pred_minus_one", "identity"),
        default="pred_minus_one",
    )
    p.add_argument("--out-dir", type=Path)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    app_dir = args.app_pool_dir.expanduser().resolve()
    pred_path = args.pred.expanduser().resolve()
    out_dir = (args.out_dir or default_out_dir(args.start, args.end)).resolve()
    if not app_dir.is_dir():
        raise SystemExit(f"app pool dir missing: {app_dir}")
    if not pred_path.is_file():
        raise SystemExit(f"pred missing: {pred_path}")
    if is_repo_stock_pool(out_dir, repo=REPO_ROOT):
        raise SystemExit(f"refusing to write into stock_pool/: {out_dir}")
    if args.start > args.end or len(args.start) != 8 or len(args.end) != 8:
        raise SystemExit("start/end must be YYYYMMDD and start<=end")

    pred = load_pred_frame(pred_path)
    topn = qlib_topn_by_buy_day(pred, topk=int(args.topk), asof=args.asof)
    days = intersect_app_qlib(app_dir, topn, start=args.start, end=args.end)
    written = write_topk_app_dropout_pool(days, out_dir, repo=REPO_ROOT)
    stats = overlap_stats(days)
    report = {
        "book": BOOK_TAG,
        "app_pool_dir": str(app_dir),
        "pred": str(pred_path),
        "start": args.start,
        "end": args.end,
        "topk": int(args.topk),
        "asof": args.asof,
        "out_dir": str(out_dir),
        "files_written": len(written),
        **stats,
        "execute": (
            "csv_minute_backtest_topk_app_dropout.py "
            "--app-pool-dir … --pred …   (not strategy 7)"
        ),
    }
    write_overlap_report(out_dir / "overlap.json", report)
    errors = validate_pool_dir(out_dir)
    # empty files are valid contract days; validate may flag none
    print(f"[topk_app_dropout] days={stats['days']} hit={stats['hit_days']} "
          f"empty={stats['empty_days']} inter_med={stats['intersect_median']} "
          f"out={out_dir}", flush=True)
    if errors:
        print(f"[topk_app_dropout] validate warnings {len(errors)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
