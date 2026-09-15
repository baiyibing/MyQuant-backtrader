# -*- coding: utf-8 -*-
"""Read-only pool-dir list-quality reporter (H9 / Theme C soft slice).

Scans ``YYYYMMDD.csv`` trees: day count, empty days, code-count histogram,
``validate_pool_dir`` failures, and optional day-aligned overlap vs a second
directory. Uses ``backtest.research.csv_pool`` helpers only — no lake writes,
no qlib, no run-manifest.

CLI: ``scripts/research/report_pool_list_quality.py``.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Sequence

from backtest.research.csv_pool import (
    parse_pool_csv,
    validate_pool_dir,
)


def _ymd_csv_paths(pool_dir: Path) -> list[Path]:
    """Stable sorted ``*.csv`` under ``pool_dir`` (same order as csv_pool loaders)."""
    return sorted(Path(pool_dir).glob("*.csv"))


def _stem_is_ymd(stem: str) -> bool:
    return len(stem) == 8 and stem.isdigit()


def load_pool_codes_by_day(pool_dir: Path) -> dict[str, list[str]]:
    """Parse each ``YYYYMMDD.csv`` via ``parse_pool_csv`` (loose engine dialect).

    Non-``YYYYMMDD`` filenames are skipped for the day map (they still surface
    via ``validate_pool_dir``). Unreadable files yield an empty code list and
    are still counted as a day key when the stem is eight digits.
    """
    days: dict[str, list[str]] = {}
    for path in _ymd_csv_paths(pool_dir):
        stem = path.stem
        if not _stem_is_ymd(stem):
            continue
        try:
            codes = parse_pool_csv(path)
        except Exception:
            codes = []
        days[stem] = codes
    return days


@dataclass(frozen=True)
class DayOverlap:
    ymd: str
    n_a: int
    n_b: int
    n_intersection: int
    jaccard: float


@dataclass
class PoolOverlapSummary:
    days_only_a: list[str] = field(default_factory=list)
    days_only_b: list[str] = field(default_factory=list)
    shared_days: list[str] = field(default_factory=list)
    per_day: list[DayOverlap] = field(default_factory=list)
    mean_jaccard: float | None = None
    mean_intersection: float | None = None


@dataclass
class PoolListQualityReport:
    pool_dir: Path
    day_count: int
    empty_days: list[str]
    code_count_histogram: dict[int, int]
    validation_errors: list[str]
    codes_by_day: dict[str, list[str]]
    other_dir: Path | None = None
    overlap: PoolOverlapSummary | None = None


def code_count_histogram(codes_by_day: Mapping[str, Sequence[str]]) -> dict[int, int]:
    """Map code-count → number of days (sorted keys for stable display)."""
    counts = Counter(len(codes) for codes in codes_by_day.values())
    return dict(sorted(counts.items()))


def empty_day_stems(codes_by_day: Mapping[str, Sequence[str]]) -> list[str]:
    return sorted(ymd for ymd, codes in codes_by_day.items() if not codes)


def overlap_pools(
    a: Mapping[str, Sequence[str]],
    b: Mapping[str, Sequence[str]],
) -> PoolOverlapSummary:
    keys_a = set(a)
    keys_b = set(b)
    shared = sorted(keys_a & keys_b)
    per_day: list[DayOverlap] = []
    for ymd in shared:
        set_a = set(a[ymd])
        set_b = set(b[ymd])
        inter = set_a & set_b
        union = set_a | set_b
        jaccard = (len(inter) / len(union)) if union else 1.0
        per_day.append(
            DayOverlap(
                ymd=ymd,
                n_a=len(set_a),
                n_b=len(set_b),
                n_intersection=len(inter),
                jaccard=jaccard,
            )
        )
    mean_j = (
        sum(d.jaccard for d in per_day) / len(per_day) if per_day else None
    )
    mean_i = (
        sum(d.n_intersection for d in per_day) / len(per_day) if per_day else None
    )
    return PoolOverlapSummary(
        days_only_a=sorted(keys_a - keys_b),
        days_only_b=sorted(keys_b - keys_a),
        shared_days=shared,
        per_day=per_day,
        mean_jaccard=mean_j,
        mean_intersection=mean_i,
    )


def report_pool_list_quality(
    pool_dir: Path,
    *,
    other_dir: Path | None = None,
) -> PoolListQualityReport:
    """Build a read-only quality report for ``pool_dir`` (optional overlap)."""
    root = Path(pool_dir)
    codes_by_day = load_pool_codes_by_day(root)
    validation_errors = validate_pool_dir(root)
    overlap: PoolOverlapSummary | None = None
    other: Path | None = None
    if other_dir is not None:
        other = Path(other_dir)
        other_codes = load_pool_codes_by_day(other)
        overlap = overlap_pools(codes_by_day, other_codes)
    return PoolListQualityReport(
        pool_dir=root,
        day_count=len(codes_by_day),
        empty_days=empty_day_stems(codes_by_day),
        code_count_histogram=code_count_histogram(codes_by_day),
        validation_errors=validation_errors,
        codes_by_day=codes_by_day,
        other_dir=other,
        overlap=overlap,
    )


def format_report(report: PoolListQualityReport) -> str:
    lines: list[str] = []
    lines.append(f"pool_dir: {report.pool_dir}")
    lines.append(f"day_count: {report.day_count}")
    lines.append(
        f"empty_days ({len(report.empty_days)}): "
        + (", ".join(report.empty_days) if report.empty_days else "(none)")
    )
    hist = report.code_count_histogram
    if hist:
        hist_txt = ", ".join(f"{n_codes}→{n_days}d" for n_codes, n_days in hist.items())
    else:
        hist_txt = "(none)"
    lines.append(f"code_count_histogram (codes→days): {hist_txt}")
    verr = report.validation_errors
    lines.append(f"validate_pool_dir errors ({len(verr)}):")
    if verr:
        for err in verr:
            lines.append(f"  - {err}")
    else:
        lines.append("  (none)")
    if report.overlap is not None and report.other_dir is not None:
        ov = report.overlap
        lines.append(f"other_dir: {report.other_dir}")
        lines.append(
            f"overlap shared_days={len(ov.shared_days)} "
            f"only_a={len(ov.days_only_a)} only_b={len(ov.days_only_b)}"
        )
        if ov.mean_jaccard is not None:
            lines.append(
                f"mean_jaccard={ov.mean_jaccard:.4f} "
                f"mean_intersection={ov.mean_intersection:.2f}"
            )
        else:
            lines.append("mean_jaccard=(n/a) mean_intersection=(n/a)")
        if ov.days_only_a:
            preview = ", ".join(ov.days_only_a[:8])
            more = "" if len(ov.days_only_a) <= 8 else f" …(+{len(ov.days_only_a) - 8})"
            lines.append(f"  days_only_a: {preview}{more}")
        if ov.days_only_b:
            preview = ", ".join(ov.days_only_b[:8])
            more = "" if len(ov.days_only_b) <= 8 else f" …(+{len(ov.days_only_b) - 8})"
            lines.append(f"  days_only_b: {preview}{more}")
        for d in ov.per_day[:12]:
            lines.append(
                f"  {d.ymd}: |A|={d.n_a} |B|={d.n_b} "
                f"|∩|={d.n_intersection} jaccard={d.jaccard:.4f}"
            )
        if len(ov.per_day) > 12:
            lines.append(f"  …(+{len(ov.per_day) - 12} shared days)")
    return "\n".join(lines) + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "Report pool-dir list quality (day count, empty days, "
            "code-count histogram, validate_pool_dir, optional overlap)."
        )
    )
    p.add_argument(
        "--pool-dir",
        type=Path,
        required=True,
        help="Directory of YYYYMMDD.csv pool files",
    )
    p.add_argument(
        "--other-dir",
        type=Path,
        default=None,
        help="Optional second pool-dir for day-aligned overlap",
    )
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    pool_dir = Path(args.pool_dir)
    if not pool_dir.is_dir():
        print(f"error: --pool-dir is not a directory: {pool_dir}", file=sys.stderr)
        return 2
    other = Path(args.other_dir) if args.other_dir is not None else None
    if other is not None and not other.is_dir():
        print(f"error: --other-dir is not a directory: {other}", file=sys.stderr)
        return 2
    report = report_pool_list_quality(pool_dir, other_dir=other)
    sys.stdout.write(format_report(report))
    return 1 if report.validation_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
