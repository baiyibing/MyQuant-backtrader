#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Truncate handmade stock_pool CSVs to first K codes (M5 column ③).

Uses ``parse_pool_csv`` so order and de-dup match the engine. Output is bare
six-digit codes, UTF-8, no BOM, no header, LF. Never writes into ``stock_pool/``.
Default destination: ``exports/m5_hand_top10_{start}_{end}/`` (gitignored).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backtest.research.csv_pool import parse_pool_csv  # noqa: E402

DEFAULT_K = 10
DEFAULT_START = "20260303"
DEFAULT_END = "20260323"


def default_out_dir(start: str, end: str, k: int = DEFAULT_K) -> Path:
    return REPO_ROOT / "exports" / f"m5_hand_top{int(k)}_{start}_{end}"


def _bare_code(canonical: str) -> str:
    return canonical.split(".", 1)[0]


def stock_pool_root() -> Path:
    return (REPO_ROOT / "stock_pool").resolve()


def refuses_stock_pool(out_dir: Path) -> bool:
    """True when ``out_dir`` is the repo ``stock_pool/`` or a path inside it."""
    try:
        Path(out_dir).resolve().relative_to(stock_pool_root())
    except ValueError:
        return False
    return True


def truncate_pool_file(src: Path, k: int) -> list[str]:
    """First K engine-order codes, as bare six-digit strings."""
    return [_bare_code(code) for code in parse_pool_csv(src)[: int(k)]]


def write_truncated_pools(
    pool_dir: Path,
    out_dir: Path,
    *,
    start: str,
    end: str,
    k: int = DEFAULT_K,
) -> list[Path]:
    out_root = Path(out_dir)
    if refuses_stock_pool(out_root):
        raise SystemExit(f"refusing to write into stock_pool/: {out_root}")
    out_root.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for path in sorted(Path(pool_dir).glob("*.csv")):
        stem = path.stem
        if len(stem) != 8 or not stem.isdigit() or not start <= stem <= end:
            continue
        codes = truncate_pool_file(path, k)
        if not codes:
            continue
        dest = out_root / f"{stem}.csv"
        dest.write_text(
            "".join(f"{code}\n" for code in codes),
            encoding="utf-8",
            newline="\n",
        )
        written.append(dest)
    return written


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
        help="output directory (default: exports/m5_hand_topK_{start}_{end}/)",
    )
    parser.add_argument("--start", default=DEFAULT_START)
    parser.add_argument("--end", default=DEFAULT_END)
    parser.add_argument(
        "--k",
        type=int,
        default=DEFAULT_K,
        help="keep first K codes per file (default: 10)",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    out_dir = (
        args.out_dir
        if args.out_dir is not None
        else default_out_dir(args.start, args.end, args.k)
    )
    written = write_truncated_pools(
        args.pool_dir,
        out_dir,
        start=args.start,
        end=args.end,
        k=args.k,
    )
    print(f"wrote {len(written)} pool CSV file(s) to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
