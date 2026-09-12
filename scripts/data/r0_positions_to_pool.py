#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Convert MyQuant ``position_analysis.txt`` into dated pool CSV files.

This is one-shot R0 glue, not another Qlib export source of truth.  The source
``持仓标的列表:`` is Qlib end-of-day holdings, not that day's new buys; when a
holding appears again, the vectorized engine uses ``skip_held`` for the
already-held symbol.

The source has no security-name column.  Consequently, an unnamed ST security
on any board uses its code-prefix board limit (10%, 20%, or 30%), not the 5%
ST limit.  Output is a single column of bare six-digit codes.  Empty holdings
days produce no file.  Do not use this output as a strategy-7 pool.
"""

from __future__ import annotations

import argparse
import ast
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Sequence


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE = REPO_ROOT.parent / "MyQuant" / "my_scripts" / "position_analysis.txt"
DEFAULT_OUT_DIR = Path("exports/r0_20260302_20260323")

_DATE_LABEL_RE = re.compile(r"^\s*日期\s*:\s*(\d{4}-\d{2}-\d{2})(?:\s.*)?$")
_HOLDINGS_LABEL_RE = re.compile(r"^\s*持仓标的列表\s*:\s*(.*)$")
_QLIB_CODE_RE = re.compile(r"^(?:SH|SZ|BJ)(\d{6})$")


def _parse_date_line(line: str, line_number: int) -> str | None:
    """Return YYYYMMDD for a date label, or None for an unrelated line."""
    if not line.lstrip().startswith("日期"):
        return None
    match = _DATE_LABEL_RE.fullmatch(line)
    if match is None:
        raise ValueError(f"line {line_number}: malformed 日期: line")
    try:
        return datetime.strptime(match.group(1), "%Y-%m-%d").strftime("%Y%m%d")
    except ValueError as exc:
        raise ValueError(f"line {line_number}: invalid date {match.group(1)!r}") from exc


def _parse_holdings(raw: str, line_number: int) -> list[str]:
    try:
        value = ast.literal_eval(raw)
    except (SyntaxError, ValueError) as exc:
        raise ValueError(
            f"line {line_number}: 持仓标的列表 must be a Python list"
        ) from exc
    if not isinstance(value, list):
        raise ValueError(f"line {line_number}: 持仓标的列表 must be a Python list")

    codes: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError(
                f"line {line_number}: holding must be a Qlib symbol string: {item!r}"
            )
        match = _QLIB_CODE_RE.fullmatch(item.strip())
        if match is None:
            raise ValueError(
                f"line {line_number}: invalid Qlib holding symbol: {item!r}"
            )
        codes.append(match.group(1))
    return codes


def parse_positions_text(text: str) -> dict[str, list[str]]:
    """Parse dated holdings, using only each labelled Python list as holdings."""
    positions_by_day: dict[str, list[str]] = {}
    nearest_date: str | None = None

    for line_number, line in enumerate(text.splitlines(), start=1):
        parsed_date = _parse_date_line(line, line_number)
        if parsed_date is not None:
            nearest_date = parsed_date
            continue

        match = _HOLDINGS_LABEL_RE.fullmatch(line)
        if match is None:
            continue
        if nearest_date is None:
            raise ValueError(
                f"line {line_number}: 持仓标的列表 has no preceding 日期: line"
            )
        if nearest_date in positions_by_day:
            raise ValueError(f"line {line_number}: duplicate holdings date {nearest_date}")
        positions_by_day[nearest_date] = _parse_holdings(match.group(1), line_number)

    return positions_by_day


def write_pool_csvs(
    positions_by_day: dict[str, list[str]], out_dir: Path
) -> list[Path]:
    """Write non-empty holdings as headerless, one-column pool CSVs."""
    output_root = Path(out_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for ymd, codes in positions_by_day.items():
        if not codes:
            continue
        path = output_root / f"{ymd}.csv"
        path.write_text("".join(f"{code}\n" for code in codes), encoding="utf-8", newline="\n")
        written.append(path)
    return written


def convert_positions_file(src: Path, out_dir: Path) -> list[Path]:
    """Read one MyQuant report and write its non-empty dated pools."""
    text = Path(src).read_text(encoding="utf-8-sig")
    return write_pool_csvs(parse_positions_text(text), Path(out_dir))


def resolve_source(cli_source: Path | None) -> Path:
    """Resolve the explicit, environment, or sibling-repository source path."""
    if cli_source is not None:
        candidates = [Path(cli_source).expanduser()]
    else:
        env_source = os.environ.get("OSKH_R0_POSITIONS", "").strip()
        candidates = [Path(env_source).expanduser()] if env_source else [DEFAULT_SOURCE]

    for candidate in candidates:
        if candidate.is_file():
            return candidate
    tried = "\n".join(f"  - {candidate}" for candidate in candidates)
    raise SystemExit(f"position_analysis.txt not found; tried paths:\n{tried}")


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--src",
        type=Path,
        help=(
            "MyQuant position_analysis.txt (default: OSKH_R0_POSITIONS, then "
            "repo-root/../MyQuant/my_scripts/position_analysis.txt)"
        ),
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUT_DIR,
        help="dated pool output directory (default: exports/r0_20260302_20260323/)",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    src = resolve_source(args.src)
    written = convert_positions_file(src, args.out_dir)
    print(f"wrote {len(written)} pool CSV file(s) to {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
