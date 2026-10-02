# -*- coding: utf-8 -*-
"""Read-only pool-dir list-quality reporter (H9 / H16 Theme C soft+).

Scans ``YYYYMMDD.csv`` trees: day count, empty days, code-count histogram,
``validate_pool_dir`` failures, optional day-aligned overlap vs a second
directory, plus H16 deepeners: invalid calendar stems, top-N frequent codes,
day-over-day churn, and text/json/markdown output. Uses
``backtest.research.csv_pool`` helpers only — no lake writes, no qlib,
no run-manifest.

CLI: ``scripts/research/report_pool_list_quality.py``.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from backtest.research.csv_pool import (
    PoolDuplicateCodeError,
    parse_pool_csv,
    validate_pool_dir,
)


def _ymd_csv_paths(pool_dir: Path) -> list[Path]:
    """Stable sorted ``*.csv`` under ``pool_dir`` (same order as csv_pool loaders)."""
    return sorted(Path(pool_dir).glob("*.csv"))


def _stem_is_ymd(stem: str) -> bool:
    return len(stem) == 8 and stem.isdigit()


def _stem_is_valid_calendar(stem: str) -> bool:
    """True iff ``stem`` is eight digits and a real Gregorian date."""
    if not _stem_is_ymd(stem):
        return False
    try:
        datetime.strptime(stem, "%Y%m%d")
    except ValueError:
        return False
    return True


def load_pool_codes_by_day(pool_dir: Path) -> dict[str, list[str]]:
    """Parse each ``YYYYMMDD.csv`` via ``parse_pool_csv`` (loose engine dialect).

    Non-``YYYYMMDD`` filenames are skipped for the day map (they still surface
    via ``validate_pool_dir``). Unreadable files yield an empty code list and
    are still counted as a day key when the stem is eight digits.
    Same-day duplicate codes always raise ``PoolDuplicateCodeError``.

    Eight-digit stems that fail calendar validation (e.g. ``20260230``) still
    enter the map; callers can filter via ``invalid_calendar_stems``.
    """
    days: dict[str, list[str]] = {}
    for path in _ymd_csv_paths(pool_dir):
        stem = path.stem
        if not _stem_is_ymd(stem):
            continue
        try:
            codes = parse_pool_csv(path)
        except PoolDuplicateCodeError:
            raise
        except Exception:
            codes = []
        days[stem] = codes
    return days


def invalid_calendar_stems(codes_by_day: Mapping[str, Sequence[str]]) -> list[str]:
    """Eight-digit day keys that are not valid Gregorian dates."""
    return sorted(ymd for ymd in codes_by_day if not _stem_is_valid_calendar(ymd))


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


@dataclass(frozen=True)
class DayChurn:
    """Codes added/removed between two consecutive calendar-sorted days."""

    from_ymd: str
    to_ymd: str
    n_added: int
    n_removed: int


@dataclass
class PoolChurnSummary:
    per_day: list[DayChurn] = field(default_factory=list)
    total_added: int = 0
    total_removed: int = 0
    mean_added: float | None = None
    mean_removed: float | None = None


@dataclass
class PoolListQualityReport:
    pool_dir: Path
    day_count: int
    empty_days: list[str]
    code_count_histogram: dict[int, int]
    validation_errors: list[str]
    codes_by_day: dict[str, list[str]]
    invalid_calendar_stems: list[str] = field(default_factory=list)
    valid_calendar_day_count: int = 0
    top_codes: list[tuple[str, int]] = field(default_factory=list)
    churn: PoolChurnSummary | None = None
    other_dir: Path | None = None
    overlap: PoolOverlapSummary | None = None
    other_validation_errors: list[str] = field(default_factory=list)


def code_count_histogram(codes_by_day: Mapping[str, Sequence[str]]) -> dict[int, int]:
    """Map code-count → number of days (sorted keys for stable display)."""
    counts = Counter(len(codes) for codes in codes_by_day.values())
    return dict(sorted(counts.items()))


def empty_day_stems(codes_by_day: Mapping[str, Sequence[str]]) -> list[str]:
    return sorted(ymd for ymd, codes in codes_by_day.items() if not codes)


def top_frequent_codes(
    codes_by_day: Mapping[str, Sequence[str]],
    *,
    top_n: int = 20,
) -> list[tuple[str, int]]:
    """Codes ranked by number of days they appear in (desc, then code asc).

    Within a day, duplicate codes are counted once. ``top_n <= 0`` returns [].
    """
    if top_n <= 0:
        return []
    freq: Counter[str] = Counter()
    for codes in codes_by_day.values():
        freq.update(set(codes))
    ranked = sorted(freq.items(), key=lambda kv: (-kv[1], kv[0]))
    return ranked[:top_n]


def day_over_day_churn(
    codes_by_day: Mapping[str, Sequence[str]],
) -> PoolChurnSummary:
    """Adjacent-day set diffs on sorted YMD keys (includes invalid calendar stems)."""
    ymds = sorted(codes_by_day)
    per_day: list[DayChurn] = []
    for i in range(1, len(ymds)):
        prev, cur = ymds[i - 1], ymds[i]
        set_prev = set(codes_by_day[prev])
        set_cur = set(codes_by_day[cur])
        n_added = len(set_cur - set_prev)
        n_removed = len(set_prev - set_cur)
        per_day.append(
            DayChurn(
                from_ymd=prev,
                to_ymd=cur,
                n_added=n_added,
                n_removed=n_removed,
            )
        )
    total_added = sum(d.n_added for d in per_day)
    total_removed = sum(d.n_removed for d in per_day)
    n = len(per_day)
    return PoolChurnSummary(
        per_day=per_day,
        total_added=total_added,
        total_removed=total_removed,
        mean_added=(total_added / n) if n else None,
        mean_removed=(total_removed / n) if n else None,
    )


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


def _validated_pool_days(
    root: Path, *, side: str,
) -> tuple[dict[str, list[str]], list[str]]:
    try:
        errors = validate_pool_dir(root)
        return load_pool_codes_by_day(root), errors
    except OSError as exc:
        raise OSError(f"{side} ({root}): {exc}") from exc


def report_pool_list_quality(
    pool_dir: Path,
    *,
    other_dir: Path | None = None,
    top_n: int = 20,
) -> PoolListQualityReport:
    """Validate both directories and build a read-only report with optional overlap."""
    root = Path(pool_dir)
    codes_by_day, validation_errors = _validated_pool_days(root, side="primary")
    bad_cal = invalid_calendar_stems(codes_by_day)
    overlap: PoolOverlapSummary | None = None
    other: Path | None = None
    other_validation_errors: list[str] = []
    if other_dir is not None:
        other = Path(other_dir)
        other_codes, other_validation_errors = _validated_pool_days(other, side="other")
        overlap = overlap_pools(codes_by_day, other_codes)
    return PoolListQualityReport(
        pool_dir=root,
        day_count=len(codes_by_day),
        empty_days=empty_day_stems(codes_by_day),
        code_count_histogram=code_count_histogram(codes_by_day),
        validation_errors=validation_errors,
        codes_by_day=codes_by_day,
        invalid_calendar_stems=bad_cal,
        valid_calendar_day_count=len(codes_by_day) - len(bad_cal),
        top_codes=top_frequent_codes(codes_by_day, top_n=top_n),
        churn=day_over_day_churn(codes_by_day),
        other_dir=other,
        overlap=overlap,
        other_validation_errors=other_validation_errors,
    )


def _report_to_dict(report: PoolListQualityReport) -> dict[str, Any]:
    """JSON-serializable dict (paths as str; omit bulky codes_by_day)."""
    out: dict[str, Any] = {
        "pool_dir": str(report.pool_dir),
        "day_count": report.day_count,
        "valid_calendar_day_count": report.valid_calendar_day_count,
        "invalid_calendar_stems": list(report.invalid_calendar_stems),
        "empty_days": list(report.empty_days),
        "code_count_histogram": {
            str(k): v for k, v in report.code_count_histogram.items()
        },
        "validation_errors": list(report.validation_errors),
        "top_codes": [{"code": c, "days": n} for c, n in report.top_codes],
    }
    if report.churn is not None:
        ch = report.churn
        out["churn"] = {
            "total_added": ch.total_added,
            "total_removed": ch.total_removed,
            "mean_added": ch.mean_added,
            "mean_removed": ch.mean_removed,
            "per_day": [asdict(d) for d in ch.per_day],
        }
    if report.other_dir is not None:
        out["other_dir"] = str(report.other_dir)
        out["validation_errors_by_side"] = {
            "primary": list(report.validation_errors),
            "other": list(report.other_validation_errors),
        }
    if report.overlap is not None:
        ov = report.overlap
        out["overlap"] = {
            "days_only_a": list(ov.days_only_a),
            "days_only_b": list(ov.days_only_b),
            "shared_days": list(ov.shared_days),
            "mean_jaccard": ov.mean_jaccard,
            "mean_intersection": ov.mean_intersection,
            "per_day": [asdict(d) for d in ov.per_day],
        }
    return out


def format_report(report: PoolListQualityReport) -> str:
    lines: list[str] = []
    lines.append(f"pool_dir: {report.pool_dir}")
    lines.append(f"day_count: {report.day_count}")
    lines.append(f"valid_calendar_day_count: {report.valid_calendar_day_count}")
    bad = report.invalid_calendar_stems
    lines.append(
        f"invalid_calendar_stems ({len(bad)}): "
        + (", ".join(bad) if bad else "(none)")
    )
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
    if report.top_codes:
        top_txt = ", ".join(f"{c}×{n}d" for c, n in report.top_codes)
        lines.append(f"top_codes ({len(report.top_codes)}): {top_txt}")
    else:
        lines.append("top_codes (0): (none)")
    if report.churn is not None:
        ch = report.churn
        if ch.mean_added is not None:
            lines.append(
                f"churn: transitions={len(ch.per_day)} "
                f"total_added={ch.total_added} total_removed={ch.total_removed} "
                f"mean_added={ch.mean_added:.2f} mean_removed={ch.mean_removed:.2f}"
            )
        else:
            lines.append("churn: transitions=0 (need ≥2 days)")
        for d in ch.per_day[:12]:
            lines.append(
                f"  {d.from_ymd}→{d.to_ymd}: +{d.n_added} -{d.n_removed}"
            )
        if len(ch.per_day) > 12:
            lines.append(f"  …(+{len(ch.per_day) - 12} transitions)")
    verr = report.validation_errors
    primary_label = "primary " if report.other_dir is not None else ""
    lines.append(f"{primary_label}validate_pool_dir errors ({len(verr)}):")
    if verr:
        for err in verr:
            lines.append(f"  - {err}")
    else:
        lines.append("  (none)")
    if report.other_dir is not None:
        errors = report.other_validation_errors
        lines.append(f"other validate_pool_dir errors ({len(errors)}):")
        lines.extend(f"  - {err}" for err in errors)
        if not errors:
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


def format_report_json(report: PoolListQualityReport) -> str:
    return json.dumps(_report_to_dict(report), ensure_ascii=False, indent=2) + "\n"


def format_report_markdown(report: PoolListQualityReport) -> str:
    lines: list[str] = []
    lines.append("# Pool list-quality summary")
    lines.append("")
    lines.append(f"- **pool_dir**: `{report.pool_dir}`")
    lines.append(f"- **day_count**: {report.day_count}")
    lines.append(
        f"- **valid_calendar_day_count**: {report.valid_calendar_day_count}"
    )
    bad = report.invalid_calendar_stems
    lines.append(
        f"- **invalid_calendar_stems** ({len(bad)}): "
        + (", ".join(f"`{s}`" for s in bad) if bad else "(none)")
    )
    lines.append(
        f"- **empty_days** ({len(report.empty_days)}): "
        + (", ".join(f"`{s}`" for s in report.empty_days) if report.empty_days else "(none)")
    )
    hist = report.code_count_histogram
    if hist:
        hist_txt = ", ".join(f"{n_codes}→{n_days}d" for n_codes, n_days in hist.items())
    else:
        hist_txt = "(none)"
    lines.append(f"- **code_count_histogram**: {hist_txt}")
    lines.append("")
    lines.append("## Top codes")
    lines.append("")
    if report.top_codes:
        lines.append("| code | days |")
        lines.append("|------|------|")
        for c, n in report.top_codes:
            lines.append(f"| `{c}` | {n} |")
    else:
        lines.append("(none)")
    lines.append("")
    lines.append("## Day-over-day churn")
    lines.append("")
    if report.churn is not None and report.churn.per_day:
        ch = report.churn
        lines.append(
            f"- transitions={len(ch.per_day)}; "
            f"total_added={ch.total_added}; total_removed={ch.total_removed}; "
            f"mean_added={ch.mean_added:.2f}; mean_removed={ch.mean_removed:.2f}"
        )
        lines.append("")
        lines.append("| from | to | added | removed |")
        lines.append("|------|----|-------|---------|")
        for d in ch.per_day[:20]:
            lines.append(
                f"| `{d.from_ymd}` | `{d.to_ymd}` | {d.n_added} | {d.n_removed} |"
            )
        if len(ch.per_day) > 20:
            lines.append("")
            lines.append(f"_…(+{len(ch.per_day) - 20} transitions)_")
    else:
        lines.append("(need ≥2 days)")
    lines.append("")
    primary_label = "primary " if report.other_dir is not None else ""
    lines.append(f"## {primary_label}validate_pool_dir")
    lines.append("")
    verr = report.validation_errors
    if verr:
        for err in verr:
            lines.append(f"- {err}")
    else:
        lines.append("(none)")
    if report.other_dir is not None:
        lines.extend(["", "## other validate_pool_dir", ""])
        lines.extend(f"- {err}" for err in report.other_validation_errors)
        if not report.other_validation_errors:
            lines.append("(none)")
    if report.overlap is not None and report.other_dir is not None:
        ov = report.overlap
        lines.append("")
        lines.append("## Overlap")
        lines.append("")
        lines.append(f"- **other_dir**: `{report.other_dir}`")
        lines.append(
            f"- shared={len(ov.shared_days)}; only_a={len(ov.days_only_a)}; "
            f"only_b={len(ov.days_only_b)}"
        )
        if ov.mean_jaccard is not None:
            lines.append(
                f"- mean_jaccard={ov.mean_jaccard:.4f}; "
                f"mean_intersection={ov.mean_intersection:.2f}"
            )
    lines.append("")
    return "\n".join(lines)


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "Report pool-dir list quality (day count, empty days, "
            "code-count histogram, top-N codes, day-over-day churn, "
            "calendar stems, validate_pool_dir, optional overlap). "
            "Exit 1 for contract errors on either side; exit 2 for path/IO errors."
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
        help="Optional second pool-dir, strictly validated, for day-aligned overlap",
    )
    p.add_argument(
        "--format",
        choices=("text", "json", "markdown"),
        default="text",
        help="Output format (default: text)",
    )
    p.add_argument(
        "--top-n",
        type=int,
        default=20,
        help="Max frequent codes to report (default: 20; 0 disables)",
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
    try:
        report = report_pool_list_quality(
            pool_dir, other_dir=other, top_n=int(args.top_n)
        )
    except PoolDuplicateCodeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"error: pool directory IO: {exc}", file=sys.stderr)
        return 2
    fmt = args.format
    if fmt == "json":
        sys.stdout.write(format_report_json(report))
    elif fmt == "markdown":
        sys.stdout.write(format_report_markdown(report))
    else:
        sys.stdout.write(format_report(report))
    errors = report.validation_errors + report.other_validation_errors
    # validate_pool_dir reports read failures as strings alongside contract errors.
    if any(err.partition(": ")[2].startswith("cannot read pool CSV:") for err in errors):
        return 2
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
