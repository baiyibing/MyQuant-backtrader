# -*- coding: utf-8 -*-
"""Read-only ex-div hold-hit counting (NP2).

Design locks (survey-exdiv-adj-data-prep-2026-09-16.md §3):
1. Primary source = ex_date_index.parquet (QMT detect product).
   cumulative_adj_factor jumps (ε=5e-3) are PARITY SECONDARY only — never the
   primary enumerator (cash div ≤0.5% is drowned in 0.01-yuan rounding noise).
2. Default window 20251023–20260909. Hit = hold interval ∩ ex_date for lots
   held from D+1 (entry day itself is NOT evaluated — T+1 align):
   entry_date < ex_date <= exit_date (open lots use --end as exit bound).
3. Outputs: (1) hold-period ex-div hit counts; (2) among those, sell-reason
   buckets stop_loss:gap_open / defer_sell_limit_down / trail:band:*;
   (3) trades.csv row samples.

Adjudication (E-R5 vs 复权 plan) is a HUMAN cut after host numbers — never auto.
NP2 is separate from NP1 (capital ration) and fees. Does not implement 复权.
No engine imports, market-data writes, or golden regeneration.
Non-BUY/SELL sides (e.g. EOD_MARK valuation rows) are skipped with a count —
never hard-fail the probe.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict, deque
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

from oskh_core.a_share_symbol_normalize import normalize_a_share_code

DEFAULT_START = "20251023"
DEFAULT_END = "20260909"
# Parity secondary only (survey §1② / §3 L1) — not a primary enumerator.
PARITY_EPS = 5e-3

DESIGN_LOCKS = (
    "primary=ex_date_index; adj_factor jumps ε=5e-3 parity-only; "
    "hit=entry<ex<=exit (T+1 excludes entry day); "
    "outputs=hit counts + gap_open/defer/band-trail buckets + trade samples; "
    "adjudication=HUMAN after numbers (E-R5 vs 复权 plan), not auto"
)

ATTRIBUTION_NOTE = (
    "defer_sell_limit_down is primarily an engine summary counter and may be "
    "absent from trades.csv reason; gap_open and trail:band:* are reason strings. "
    "Primary enumerator is ex_date_index; factor jumps are parity secondary only."
)

ADJUDICATION_NOTE = (
    "HUMAN cut after host numbers: E-R5 (known none-chain boundary) vs new "
    "复权 implementation plan — never auto from this probe."
)

REASON_GAP_OPEN = "stop_loss:gap_open"
REASON_DEFER = "defer_sell_limit_down"
REASON_BAND_PREFIX = "trail:band:"


@dataclass(frozen=True)
class HoldLot:
    code: str
    lot: int
    entry_date: str
    exit_date: str | None
    buy_row: dict[str, str]
    sell_row: dict[str, str] | None
    sell_reason: str


@dataclass(frozen=True)
class HitSample:
    code: str
    lot: int
    entry_date: str
    exit_date: str | None
    ex_dates: list[str]
    sell_reason: str
    reason_family: str
    buy: dict[str, str]
    sell: dict[str, str] | None


@dataclass
class ParityReport:
    eps: float = PARITY_EPS
    n_jumps_in_window: int = 0
    n_primary_hit_events_with_jump: int = 0
    n_jumps_on_traded_hold_missed_by_ex: int = 0
    skip_parity_no_factor: int = 0  # G2
    g4_ex_minus_adj: int = 0
    g4_adj_minus_ex: int = 0
    note: str = (
        "parity secondary only; do not treat jumps as primary ex enumerator"
    )


@dataclass
class ExdivHoldHitsReport:
    start: str
    end: str
    trades: str
    ex_date_index: str
    adj_factor: str | None
    design_locks: str = DESIGN_LOCKS
    attribution_note: str = ATTRIBUTION_NOTE
    adjudication_note: str = ADJUDICATION_NOTE
    n_lots_matched: int = 0
    n_lots_open: int = 0
    n_lots_in_window: int = 0
    n_skipped_non_trade_sides: int = 0
    n_ex_events_in_window: int = 0
    n_codes_in_ex_index_window: int = 0
    hold_exdiv_hit_events: int = 0
    hold_exdiv_hit_lots: int = 0
    among_hits_sell_gap_open: int = 0
    among_hits_sell_defer_limit_down: int = 0
    among_hits_sell_band_trail: int = 0
    among_hits_sell_other: int = 0
    among_hits_sell_open_lot: int = 0
    samples: list[dict[str, Any]] = field(default_factory=list)
    parity: dict[str, Any] | None = None


def normalize_date(value: object) -> str:
    """Accept YYYYMMDD, ISO dates, and datetime/Timestamp-like strings."""
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "nat"}:
        raise ValueError(f"invalid date {value!r}")
    if len(text) >= 10 and text[4] == "-" and text[7] == "-":
        text = text[:10]
        day = datetime.strptime(text, "%Y-%m-%d")
    elif len(text) == 8 and text.isdigit():
        day = datetime.strptime(text, "%Y%m%d")
    else:
        day = datetime.fromisoformat(text)
    return day.strftime("%Y%m%d")


def classify_sell_reason(reason: str) -> str:
    if reason == REASON_GAP_OPEN:
        return "gap_open"
    if reason == REASON_DEFER:
        return "defer_limit_down"
    if reason.startswith(REASON_BAND_PREFIX):
        return "band_trail"
    if not reason:
        return "open_lot"
    return "other"


def _load_table(path: Path) -> list[dict[str, Any]]:
    """Load parquet or csv into list-of-dicts (stringifies values lightly)."""
    suffix = path.suffix.lower()
    if suffix in {".parquet", ".pq"}:
        import pandas as pd

        frame = pd.read_parquet(path)
        return frame.to_dict(orient="records")
    if suffix in {".csv", ".txt"}:
        with path.open(encoding="utf-8-sig", newline="") as stream:
            return list(csv.DictReader(stream))
    raise ValueError(f"unsupported table format (use .parquet/.csv): {path}")


def load_ex_date_index(path: Path, *, start: str, end: str) -> dict[str, list[str]]:
    """Return code -> sorted unique ex_date YYYYMMDD in [start, end]."""
    rows = _load_table(path)
    if not rows:
        return {}
    keys = {str(k).strip().lower() for k in rows[0]}
    code_key = next((k for k in rows[0] if str(k).strip().lower() in {"stock_code", "code"}), None)
    date_key = next((k for k in rows[0] if str(k).strip().lower() in {"ex_date", "date"}), None)
    if code_key is None or date_key is None:
        raise ValueError(
            f"ex-date-index missing stock_code/ex_date columns; got {sorted(keys)}"
        )
    by_code: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        try:
            ds = normalize_date(row[date_key])
        except ValueError:
            continue
        if not start <= ds <= end:
            continue
        code = normalize_a_share_code(str(row[code_key]).strip())
        by_code[code].add(ds)
    return {code: sorted(dates) for code, dates in by_code.items()}


def parse_hold_lots(trades: Path) -> tuple[list[HoldLot], int]:
    """Chronological FIFO BUY→SELL match on (code, lot); lot ids may restart.

    Non-BUY/SELL sides (e.g. ``EOD_MARK`` valuation marks in real trades.csv)
    are skipped silently and counted — they must not hard-fail the probe.
    """
    required = {"date", "code", "side", "reason", "lot"}
    open_buys: dict[tuple[str, int], deque[tuple[str, dict[str, str]]]] = defaultdict(deque)
    lots: list[HoldLot] = []
    skipped_non_trade = 0
    with Path(trades).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"trades CSV missing columns: {', '.join(sorted(missing))}")
        for row in reader:
            raw = {k: ("" if v is None else str(v)) for k, v in row.items()}
            side = raw["side"].strip().upper()
            if side not in {"BUY", "SELL"}:
                # Valuation / bookkeeping rows (EOD_MARK, …) — skip with count.
                skipped_non_trade += 1
                continue
            try:
                ds = normalize_date(raw["date"])
            except ValueError as exc:
                raise ValueError(
                    f"trades row {reader.line_num}: invalid date {raw['date']!r}"
                ) from exc
            code = normalize_a_share_code(raw["code"].strip())
            try:
                lot_id = int(float(str(raw["lot"]).strip()))
            except ValueError as exc:
                raise ValueError(
                    f"trades row {reader.line_num}: invalid lot {raw['lot']!r}"
                ) from exc
            key = (code, lot_id)
            if side == "BUY":
                open_buys[key].append((ds, raw))
            else:  # SELL
                if not open_buys[key]:
                    raise ValueError(
                        f"trades row {reader.line_num}: SELL without open BUY "
                        f"for {code} lot={lot_id}"
                    )
                entry_ds, buy_row = open_buys[key].popleft()
                lots.append(
                    HoldLot(
                        code=code,
                        lot=lot_id,
                        entry_date=entry_ds,
                        exit_date=ds,
                        buy_row=buy_row,
                        sell_row=raw,
                        sell_reason=raw.get("reason", "") or "",
                    )
                )
    for (code, lot_id), pending in open_buys.items():
        for entry_ds, buy_row in pending:
            lots.append(
                HoldLot(
                    code=code,
                    lot=lot_id,
                    entry_date=entry_ds,
                    exit_date=None,
                    buy_row=buy_row,
                    sell_row=None,
                    sell_reason="",
                )
            )
    lots.sort(key=lambda x: (x.entry_date, x.code, x.lot))
    return lots, skipped_non_trade


def _lot_in_window(lot: HoldLot, start: str, end: str) -> bool:
    if lot.entry_date > end:
        return False
    if lot.exit_date is not None and lot.exit_date < start:
        return False
    return True


def _hit_ex_dates(lot: HoldLot, ex_dates: Sequence[str], end: str) -> list[str]:
    """T+1: exclude entry day; include exit day if still held that session."""
    upper = lot.exit_date if lot.exit_date is not None else end
    return [ds for ds in ex_dates if lot.entry_date < ds <= upper]


def _detect_factor_jumps(
    path: Path, *, start: str, end: str, eps: float = PARITY_EPS
) -> tuple[set[tuple[str, str]], set[str], set[str]]:
    """Return (jumps as (code,date), codes_with_any_factor, codes_all_nan_in_window)."""
    import math

    rows = _load_table(path)
    if not rows:
        return set(), set(), set()
    code_key = next(
        (k for k in rows[0] if str(k).strip().lower() in {"stock_code", "code"}), None
    )
    date_key = next((k for k in rows[0] if str(k).strip().lower() == "date"), None)
    factor_key = next(
        (
            k
            for k in rows[0]
            if str(k).strip().lower() in {"cumulative_adj_factor", "adj_factor"}
        ),
        None,
    )
    if code_key is None or date_key is None or factor_key is None:
        raise ValueError(
            "adj-factor missing stock_code/date/cumulative_adj_factor columns"
        )
    series: dict[str, list[tuple[str, float | None]]] = defaultdict(list)
    codes_all: set[str] = set()
    for row in rows:
        try:
            ds = normalize_date(row[date_key])
        except ValueError:
            continue
        code = normalize_a_share_code(str(row[code_key]).strip())
        codes_all.add(code)
        if not start <= ds <= end:
            continue
        raw_f = row[factor_key]
        try:
            if raw_f is None or (isinstance(raw_f, float) and math.isnan(raw_f)):
                val: float | None = None
            else:
                text = str(raw_f).strip()
                if not text or text.lower() in {"nan", "none", "null"}:
                    val = None
                else:
                    val = float(text)
                    if math.isnan(val):
                        val = None
        except (TypeError, ValueError):
            val = None
        series[code].append((ds, val))

    jumps: set[tuple[str, str]] = set()
    codes_with_factor: set[str] = set()
    no_factor: set[str] = set()
    for code, points in series.items():
        points.sort(key=lambda x: x[0])
        prev: float | None = None
        saw_finite = False
        for ds, val in points:
            if val is None:
                continue
            saw_finite = True
            codes_with_factor.add(code)
            if prev is not None and prev != 0:
                chg = abs(val / prev - 1.0)
                if chg > eps:
                    jumps.add((code, ds))
            prev = val
        if points and not saw_finite:
            no_factor.add(code)
    # G2-ish: codes that appear in window rows but never had a finite factor
    for code in series:
        if code not in codes_with_factor:
            no_factor.add(code)
    return jumps, codes_all, no_factor


def report_exdiv_hold_hits(
    trades: Path,
    ex_date_index: Path,
    *,
    start: str | None = None,
    end: str | None = None,
    adj_factor: Path | None = None,
    sample_limit: int = 20,
) -> ExdivHoldHitsReport:
    lower = normalize_date(start) if start is not None else DEFAULT_START
    upper = normalize_date(end) if end is not None else DEFAULT_END
    if lower > upper:
        raise ValueError("start must not be after end")
    if sample_limit < 0:
        raise ValueError("sample_limit must be non-negative")

    lots, n_skipped_non_trade = parse_hold_lots(Path(trades))
    ex_by_code = load_ex_date_index(Path(ex_date_index), start=lower, end=upper)
    n_ex_events = sum(len(v) for v in ex_by_code.values())

    window_lots = [lot for lot in lots if _lot_in_window(lot, lower, upper)]
    hit_events = 0
    hit_lot_count = 0
    bucket = {
        "gap_open": 0,
        "defer_limit_down": 0,
        "band_trail": 0,
        "other": 0,
        "open_lot": 0,
    }
    samples: list[dict[str, Any]] = []
    primary_hit_keys: set[tuple[str, str]] = set()
    traded_codes = {lot.code for lot in window_lots}

    for lot in window_lots:
        hits = _hit_ex_dates(lot, ex_by_code.get(lot.code, []), upper)
        if not hits:
            continue
        hit_lot_count += 1
        hit_events += len(hits)
        for ds in hits:
            primary_hit_keys.add((lot.code, ds))
        family = classify_sell_reason(lot.sell_reason)
        bucket[family] = bucket.get(family, 0) + 1
        if len(samples) < sample_limit:
            sample = HitSample(
                code=lot.code,
                lot=lot.lot,
                entry_date=lot.entry_date,
                exit_date=lot.exit_date,
                ex_dates=hits,
                sell_reason=lot.sell_reason,
                reason_family=family,
                buy={k: lot.buy_row.get(k, "") for k in ("date", "code", "side", "price", "shares", "reason", "lot")},
                sell=(
                    None
                    if lot.sell_row is None
                    else {
                        k: lot.sell_row.get(k, "")
                        for k in ("date", "code", "side", "price", "shares", "reason", "lot")
                    }
                ),
            )
            samples.append(asdict(sample))

    parity_payload: dict[str, Any] | None = None
    if adj_factor is not None:
        jumps, adj_codes, no_factor = _detect_factor_jumps(
            Path(adj_factor), start=lower, end=upper, eps=PARITY_EPS
        )
        ex_codes = set(ex_by_code)
        # G2: traded or ex codes lacking finite factor in window
        skip_no_factor = len((traded_codes | ex_codes) & no_factor)
        primary_with_jump = len(primary_hit_keys & jumps)
        # Jumps on codes we actually held, falling inside some hold interval,
        # but missing from primary hit set (ex index miss / lag) — secondary only.
        missed = 0
        hold_by_code: dict[str, list[HoldLot]] = defaultdict(list)
        for lot in window_lots:
            hold_by_code[lot.code].append(lot)
        for code, ds in jumps:
            if (code, ds) in primary_hit_keys:
                continue
            for lot in hold_by_code.get(code, []):
                if _hit_ex_dates(lot, [ds], upper):
                    missed += 1
                    break
        parity_payload = asdict(
            ParityReport(
                eps=PARITY_EPS,
                n_jumps_in_window=len(jumps),
                n_primary_hit_events_with_jump=primary_with_jump,
                n_jumps_on_traded_hold_missed_by_ex=missed,
                skip_parity_no_factor=skip_no_factor,
                g4_ex_minus_adj=len(ex_codes - adj_codes),
                g4_adj_minus_ex=len(adj_codes - ex_codes),
            )
        )

    return ExdivHoldHitsReport(
        start=lower,
        end=upper,
        trades=str(trades),
        ex_date_index=str(ex_date_index),
        adj_factor=str(adj_factor) if adj_factor is not None else None,
        n_lots_matched=sum(1 for lot in lots if lot.exit_date is not None),
        n_lots_open=sum(1 for lot in lots if lot.exit_date is None),
        n_lots_in_window=len(window_lots),
        n_skipped_non_trade_sides=n_skipped_non_trade,
        n_ex_events_in_window=n_ex_events,
        n_codes_in_ex_index_window=len(ex_by_code),
        hold_exdiv_hit_events=hit_events,
        hold_exdiv_hit_lots=hit_lot_count,
        among_hits_sell_gap_open=bucket["gap_open"],
        among_hits_sell_defer_limit_down=bucket["defer_limit_down"],
        among_hits_sell_band_trail=bucket["band_trail"],
        among_hits_sell_other=bucket["other"],
        among_hits_sell_open_lot=bucket["open_lot"],
        samples=samples,
        parity=parity_payload,
    )


def _summary_items(report: ExdivHoldHitsReport) -> list[tuple[str, Any]]:
    data = asdict(report)
    skip = {"samples", "parity"}
    return [(k, v) for k, v in data.items() if k not in skip]


def format_report_json(report: ExdivHoldHitsReport) -> str:
    return json.dumps(asdict(report), ensure_ascii=False, indent=2) + "\n"


def format_report(report: ExdivHoldHitsReport) -> str:
    lines = [f"{k}: {v}" for k, v in _summary_items(report)]
    if report.parity is not None:
        lines.append(f"parity: {json.dumps(report.parity, ensure_ascii=False)}")
    lines.append(f"samples ({len(report.samples)}):")
    for sample in report.samples:
        lines.append(
            f"  {sample['code']} lot={sample['lot']} "
            f"{sample['entry_date']}->{sample['exit_date']} "
            f"ex={sample['ex_dates']} family={sample['reason_family']} "
            f"reason={sample['sell_reason']!r}"
        )
    return "\n".join(lines) + "\n"


def format_report_markdown(report: ExdivHoldHitsReport) -> str:
    lines = ["# Ex-div hold hits (NP2)", ""]
    for k, v in _summary_items(report):
        lines.append(f"- **{k}**: {v}")
    if report.parity is not None:
        lines.extend(["", "## Parity (secondary only)", ""])
        for k, v in report.parity.items():
            lines.append(f"- **{k}**: {v}")
    lines.extend(
        [
            "",
            "## Samples",
            "",
            "| code | lot | entry | exit | ex_dates | family | sell_reason |",
            "|---|---:|---|---|---|---|---|",
        ]
    )
    for sample in report.samples:
        lines.append(
            f"| {sample['code']} | {sample['lot']} | {sample['entry_date']} | "
            f"{sample['exit_date']} | {','.join(sample['ex_dates'])} | "
            f"{sample['reason_family']} | `{sample['sell_reason']}` |"
        )
    return "\n".join(lines) + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only NP2 ex-div hold-hit probe. "
            "Primary source=ex_date_index; adj_factor jumps are parity only. "
            + ADJUDICATION_NOTE
        )
    )
    parser.add_argument("--trades", type=Path, required=True, help="trades.csv path")
    parser.add_argument(
        "--ex-date-index",
        type=Path,
        required=True,
        help="Primary ex_date_index.parquet (or .csv)",
    )
    parser.add_argument(
        "--adj-factor",
        type=Path,
        default=None,
        help="Optional adj_factor for parity secondary only (ε=5e-3)",
    )
    parser.add_argument("--start", metavar="YYYYMMDD", default=DEFAULT_START)
    parser.add_argument("--end", metavar="YYYYMMDD", default=DEFAULT_END)
    parser.add_argument("--format", choices=("text", "json", "markdown"), default="text")
    parser.add_argument("--sample-limit", type=int, default=20)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    try:
        report = report_exdiv_hold_hits(
            args.trades,
            args.ex_date_index,
            start=args.start,
            end=args.end,
            adj_factor=args.adj_factor,
            sample_limit=args.sample_limit,
        )
    except (OSError, ValueError, csv.Error, ImportError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    formatter = {
        "text": format_report,
        "json": format_report_json,
        "markdown": format_report_markdown,
    }[args.format]
    sys.stdout.write(formatter(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
