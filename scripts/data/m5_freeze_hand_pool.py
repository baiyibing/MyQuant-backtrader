#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Freeze handmade stock_pool CSVs in a date window (M5 r2 column ②).

Copies matching ``YYYYMMDD.csv`` bytes as-is. Never writes into ``stock_pool/``.
Default destination: ``exports/m5r2_hand_snap_{start}_{end}/`` (gitignored).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.data.m5_hand_topn import refuses_stock_pool  # noqa: E402

DEFAULT_START = "20260303"
DEFAULT_END = "20260908"


def default_out_dir(start: str, end: str) -> Path:
    return REPO_ROOT / "exports" / f"m5r2_hand_snap_{start}_{end}"


def iter_window_csvs(pool_dir: Path, start: str, end: str) -> list[Path]:
    found: list[Path] = []
    for path in sorted(Path(pool_dir).glob("*.csv")):
        stem = path.stem
        if len(stem) != 8 or not stem.isdigit() or not start <= stem <= end:
            continue
        found.append(path)
    return found


def freeze_hand_pool(
    pool_dir: Path,
    out_dir: Path,
    *,
    start: str,
    end: str,
) -> list[Path]:
    out_root = Path(out_dir)
    if refuses_stock_pool(out_root):
        raise SystemExit(f"refusing to write into stock_pool/: {out_root}")
    out_root.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for src in iter_window_csvs(pool_dir, start, end):
        dest = out_root / src.name
        dest.write_bytes(src.read_bytes())
        written.append(dest)
    return written


def stems_missing(written: Sequence[Path], expected_stems: Sequence[str]) -> list[str]:
    have = {path.stem for path in written}
    return [stem for stem in expected_stems if stem not in have]


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--pool-dir",
        type=Path,
        default=REPO_ROOT / "stock_pool",
        help="handmade pool directory (default: repo stock_pool/)",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="output directory (default: exports/m5r2_hand_snap_{start}_{end}/)",
    )
    parser.add_argument("--start", default=DEFAULT_START)
    parser.add_argument("--end", default=DEFAULT_END)
    parser.add_argument(
        "--expected-dir",
        type=Path,
        default=None,
        help="optional pool dir whose YYYYMMDD stems are the expected set (e.g. pred)",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    out_dir = (
        args.out_dir
        if args.out_dir is not None
        else default_out_dir(args.start, args.end)
    )
    written = freeze_hand_pool(
        args.pool_dir,
        out_dir,
        start=args.start,
        end=args.end,
    )
    print(f"wrote {len(written)} pool CSV file(s) to {out_dir}")
    if args.expected_dir is not None:
        expected = [
            p.stem for p in iter_window_csvs(args.expected_dir, args.start, args.end)
        ]
        missing = stems_missing(written, expected)
        print(f"missing vs expected-dir: {len(missing)} {missing}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
