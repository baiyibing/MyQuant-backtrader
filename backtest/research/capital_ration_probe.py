# -*- coding: utf-8 -*-
"""Read-only capital-ration attribution (NP1(a), plan R-8 / P3).

Not allocated (广义「挤出」) means a planned code has no same-day BUY with
reason=pool. It may include skip_cash, held, no_bar, gate, or limit-up chase
queues; it is NOT an exact skip_cash count. Ranks are zero-based file order.
Chase BUY rows are counted separately, including dates without a pool file,
and never enter the planned-slot denominator or pool allocation count.

Pool files use the loose parse_pool_csv dialect (file order; duplicates fail).
Non-YYYYMMDD filenames are ignored; unreadable files and invalid dates fail.
Days with pool counts selected files, including empty pools. Date bounds are
inclusive. ISO timestamps retain their written calendar date (no UTC shift).
No engine imports, market data access, or writes.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Sequence

from backtest.research.csv_pool import parse_pool_csv
from oskh_core.a_share_symbol_normalize import normalize_a_share_code

ATTRIBUTION_NOTE = (
    "not_allocated is broad (cash/held/no_bar/gate/limit-up chase), "
    "not an exact skip_cash count; ranks are 0-based; chase buys are separate."
)


@dataclass(frozen=True)
class CapitalRationDay:
    date: str
    width: int
    allocated: int
    not_allocated_count: int
    not_allocated_ranks: list[int]
    not_allocated_codes: list[str]
    chase_buys: int
    wide_day: bool | None


@dataclass
class CapitalRationReport:
    trades: str
    pool_dir: str
    total_planned_slots: int
    total_allocated_pool: int
    total_not_allocated: int
    days_with_pool: int
    cash_cap_names: int | None
    wide_days: int | None
    total_chase_buys: int
    chase_buys_by_day: dict[str, int]
    not_allocated_rank_histogram: dict[int, int]
    per_day: list[CapitalRationDay]
    attribution_note: str = ATTRIBUTION_NOTE


def normalize_date(value: object) -> str:
    """Accept YYYYMMDD, ISO dates, and datetime/Timestamp-like strings."""
    text = str(value).strip()
    if len(text) == 8 and text.isdigit():
        day = datetime.strptime(text, "%Y%m%d")
    else:
        day = datetime.fromisoformat(text)
    return day.strftime("%Y%m%d")


def report_capital_ration(
    trades: Path,
    pool_dir: Path,
    *,
    cash_cap_names: int | None = None,
    start: str | None = None,
    end: str | None = None,
) -> CapitalRationReport:
    """Compare distinct same-day pool BUY codes with each ordered pool."""
    if cash_cap_names is not None and cash_cap_names < 0:
        raise ValueError("cash_cap_names must be non-negative")
    lower = normalize_date(start) if start is not None else "00000000"
    upper = normalize_date(end) if end is not None else "99999999"
    if lower > upper:
        raise ValueError("start must not be after end")
    root = Path(pool_dir)
    if not root.is_dir():
        raise ValueError(f"pool-dir is not a directory: {root}")
    planned_by_day: dict[str, list[str]] = {}
    # Same sorted filename scan as pool_list_quality.load_pool_codes_by_day,
    # but propagate read failures rather than reporting a false empty pool.
    for path in sorted(root.glob("*.csv")):
        ds = path.stem
        if len(ds) != 8 or not ds.isdigit():
            continue
        if lower <= ds <= upper:
            normalize_date(ds)
            planned_by_day[ds] = parse_pool_csv(path)

    pool_buys: dict[str, set[str]] = defaultdict(set)
    chase_buys: Counter[str] = Counter()
    with Path(trades).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"date", "code", "side", "price", "shares", "notional",
                    "commission", "reason", "lot"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"trades CSV missing columns: {', '.join(sorted(missing))}")
        for row in reader:
            if row["side"] != "BUY":
                continue
            try:
                ds = normalize_date(row["date"])
            except ValueError as exc:
                raise ValueError(f"trades row {reader.line_num}: invalid date {row['date']!r}") from exc
            if not lower <= ds <= upper:
                continue
            reason = row["reason"] or ""
            if reason == "pool":
                pool_buys[ds].add(normalize_a_share_code(row["code"]))
            elif reason.startswith("chase"):
                chase_buys[ds] += 1

    per_day: list[CapitalRationDay] = []
    histogram: Counter[int] = Counter()
    for ds, planned in planned_by_day.items():
        ranks = [rank for rank, code in enumerate(planned) if code not in pool_buys[ds]]
        histogram.update(ranks)
        per_day.append(CapitalRationDay(
            date=ds, width=len(planned), allocated=len(planned) - len(ranks),
            not_allocated_count=len(ranks), not_allocated_ranks=ranks,
            not_allocated_codes=[planned[rank] for rank in ranks],
            chase_buys=chase_buys[ds],
            wide_day=len(planned) > cash_cap_names if cash_cap_names is not None else None,
        ))
    return CapitalRationReport(
        trades=str(trades), pool_dir=str(root),
        total_planned_slots=sum(d.width for d in per_day),
        total_allocated_pool=sum(d.allocated for d in per_day),
        total_not_allocated=sum(d.not_allocated_count for d in per_day),
        days_with_pool=len(per_day), cash_cap_names=cash_cap_names,
        wide_days=sum(bool(d.wide_day) for d in per_day) if cash_cap_names is not None else None,
        total_chase_buys=sum(chase_buys.values()),
        chase_buys_by_day=dict(sorted(chase_buys.items())),
        not_allocated_rank_histogram=dict(sorted(histogram.items())), per_day=per_day,
    )


def format_report_json(report: CapitalRationReport) -> str:
    return json.dumps(asdict(report), ensure_ascii=False, indent=2) + "\n"


def _summary_lines(report: CapitalRationReport) -> list[str]:
    return [f"{key}: {value}" for key, value in asdict(report).items() if key != "per_day"]


def format_report(report: CapitalRationReport) -> str:
    lines = _summary_lines(report)
    for d in report.per_day:
        lines.append(
            f"{d.date}: width={d.width} allocated={d.allocated} "
            f"not_allocated_count={d.not_allocated_count} "
            f"not_allocated_ranks={d.not_allocated_ranks} "
            f"chase_buys={d.chase_buys} wide_day={d.wide_day}"
        )
    return "\n".join(lines) + "\n"


def format_report_markdown(report: CapitalRationReport) -> str:
    lines = ["# Capital ration probe", ""]
    lines.extend(f"- {line}" for line in _summary_lines(report))
    lines.extend(["", "| date | width | allocated | not_allocated_count | not_allocated_ranks (0-based) | chase_buys | wide_day |",
                  "|---|---:|---:|---:|---|---:|---|"])
    for d in report.per_day:
        lines.append(f"| {d.date} | {d.width} | {d.allocated} | {d.not_allocated_count} | "
                     f"{d.not_allocated_ranks} | {d.chase_buys} | {d.wide_day} |")
    return "\n".join(lines) + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=f"Read-only capital-ration probe. {ATTRIBUTION_NOTE}")
    parser.add_argument("--trades", type=Path, required=True)
    parser.add_argument("--pool-dir", type=Path, required=True)
    parser.add_argument("--format", choices=("text", "json", "markdown"), default="text")
    parser.add_argument("--cash-cap-names", type=int, help="Wide day iff width > N; observational only")
    parser.add_argument("--start", metavar="YYYYMMDD", help="Inclusive first day")
    parser.add_argument("--end", metavar="YYYYMMDD", help="Inclusive last day")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    try:
        report = report_capital_ration(
            args.trades, args.pool_dir, cash_cap_names=args.cash_cap_names,
            start=args.start, end=args.end,
        )
    except (OSError, ValueError, csv.Error) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    formatter = {"text": format_report, "json": format_report_json,
                 "markdown": format_report_markdown}[args.format]
    sys.stdout.write(formatter(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
