# -*- coding: utf-8 -*-
"""Strategy 7 compatibility entry, native writer and small standalone CLI.

Main executes both native schedules from injected records. Lake discovery belongs to the
CLI edge; lot ``buy_date`` values are the sole source of T+1 eligibility.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import date, timedelta
from math import isfinite
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backtest.research.ashare_bars import _in_session, bars_from_pool
from backtest.research.ashare_fees import DEFAULT_SCHEDULE, FeeSchedule
from backtest.research.ashare_volume_cap import VolumeCap, VolumeLookup
from backtest.research.csv_minute_volume import completed_minute_volumes
from backtest.research.participation_rate_precheck import (
    precheck_cli_participation_rate,
    precheck_completed_bucket_samples,
)
from backtest.research.market_layer import (
    as_date as _as_date,
    as_datetime as _as_datetime,
)
from backtest.research.strategy7_rules import (
    EIGHT,
    FOUR,
    FULL,
    SIX,
    TRIAL,
    TRIAL_FRACTION,
    build_index_gate,
    in_add_window,
    ladder_decision,
    stop_decision,
    timer_due,
    validate_index_symbol,
)
from backtest.research.ashare_session import (
    asof_pool_name,
    defer_sell_at_limit,
    k_for,
    load_limit_context,
    session_limit_prices,
    session_prev_close,
    skip_buy_at_limit,
    t1_sellable,
)
from backtest.research.csv_pool import load_pool_day_map, load_pool_names_by_day
from backtest.research.ashare_exdiv_economics import EconomicLookup, ExDivEconomics
from backtest.research.minute_audit import audit_scope, record_fill, write_audit
from backtest.research.tail_window_buy import (
    TAIL_MINUTES,
    TAIL_START,
    TailParent,
    resolve_tail_volume_unit,
    tail_policy,
    tail_quote,
    validate_tail_options,
)
from common.infra.data_root import resolve_index_daily_root
from oskh_data.lake_kind import classify_daily_lake_kind
from oskh_data.symbol_format import to_canonical_symbol, to_partition_key

from backtest.research.strategy7_engine import (
    NAME_BUDGET,
    Lot,
    Position,
    SimResult,
    _record_stamp,
    _record_dict,
    _minute_records,
    _iter_records,
    _daily_closes,
    _pool,
    _rescale_position,
    _apply_exdiv_economics,
    _event,
    _buy,
    _sell_lots,
    _buy_tail_slice,
    _is_frame_map,
    _day_frame_records,
    MinuteSession, AccountingPolicy, prepare_calendar,
)



def simulate_v7(minute_bars: Any, daily_bars: Any, pool_days: Mapping[Any, Sequence[str]] | None,
                index_days: Any = None, *, cash_total: float = 21_000_000.0,
                start: Any = None, end: Any = None,
                exdiv: Mapping[str, Mapping[str, float]] | None = None,
                exdiv_economics: EconomicLookup | None = None,
                names: Mapping[str, str] | None = None,
                names_by_day: Mapping[str, Mapping[str, str]] | None = None,
                fee: FeeSchedule = DEFAULT_SCHEDULE,
                participation_rate: float | None = None,
                volume_for_bucket: VolumeLookup | None = None,
                fix_minute_cash_order: bool = False,
                tail_window_buy: bool = False,
                tail_volume_unit: str | None = "shares",
                audit_sink: Any = None,
                **unsupported_options) -> SimResult:
    """Delegate both native schedules to the main minute engine.

    Same-bar close capacity is a completed-bar approximation. Gap opens cannot
    use that bucket. An index date->close mapping enables the new-open gate.
    exdiv_economics accepts explicit ExDivEvents for raw bars; None retains the
    baseline. Bonus lots acquire list_date and use the existing T+1 predicate.
    Without an explicit index calendar, frame indexes supply observed dates,
    unioned with pool dates, matching the records-path calendar contract.
    Dates absent from all frames and pools are not backfilled, as with records.
    """
    from backtest.research.csv_ledger import reject_short_cash_override
    reject_short_cash_override(unsupported_options, "v7 simulate")
    if unsupported_options:
        raise TypeError(f"Unexpected v7 options: {sorted(unsupported_options)}")
    validate_tail_options(tail_window_buy, fix_minute_cash_order, tail_volume_unit)
    if tail_window_buy:
        tail_volume_unit = resolve_tail_volume_unit(tail_volume_unit)
    from backtest.research.strategy7_engine import simulate_native
    return simulate_native(
        minute_bars, daily_bars, pool_days, index_days, cash_total=cash_total,
        start=start, end=end, exdiv=exdiv, exdiv_economics=exdiv_economics,
        names=names, names_by_day=names_by_day, fee=fee,
        participation_rate=participation_rate, volume_for_bucket=volume_for_bucket,
        audit_sink=audit_sink, fix_minute_cash_order=fix_minute_cash_order,
        tail_window_buy=tail_window_buy, tail_volume_unit=tail_volume_unit,
    )


def load_index_daily(start: date, end: date, *, symbol: str = "000001.SH",
                     root: Path | None = None) -> dict[date, float]:
    """Read the locked SSE index partition directly and validate the run range."""
    validate_index_symbol(symbol)
    if classify_daily_lake_kind(symbol) != "index":
        raise ValueError(f"not an index daily-lake symbol: {symbol}")
    directory = (root or resolve_index_daily_root()) / "dividend_type=none" / f"symbol={to_partition_key(symbol)}"
    files = sorted(directory.glob("*.parquet"))
    if not files:
        raise FileNotFoundError(f"missing index daily partition: {directory}")
    import pandas as pd

    frame = pd.concat((pd.read_parquet(path) for path in files), ignore_index=True)
    day_column = next((name for name in ("date", "datetime", "timestamp", "time") if name in frame), None)
    if day_column is None or "close" not in frame:
        raise ValueError("index daily parquet requires a date/time column and close")
    closes: dict[date, float] = {}
    for raw_day, raw_close in zip(frame[day_column], frame["close"]):
        day = _as_date(raw_day)
        if day <= end:
            closes[day] = float(raw_close)
    sessions = sorted(closes)
    window = [day for day in sessions if start <= day <= end]
    preload = [day for day in sessions if day < start][-11:]
    required = preload + window
    if len(preload) < 11 or not window:
        raise ValueError("index daily data lacks 11 preload sessions or the requested window")
    if any(closes[day] <= 0 for day in required):
        raise ValueError("index closes must be positive in preload and requested window")
    selected = {day: closes[day] for day in required}
    built = build_index_gate(selected, symbol=symbol)
    if any(day not in built for day in window):
        raise ValueError("index daily data is insufficient for every requested session")
    return selected


def summarize_v7(state: SimResult) -> str:
    from collections import Counter

    buys = sum(row["side"] == "buy" for row in state.trades)
    sells = sum(row["side"] == "sell" for row in state.trades)
    equity = state.equity_curve[-1]["equity"] if state.equity_curve else state.cash
    start_eq = state.equity_curve[0]["equity"] if state.equity_curve else state.cash
    peak = start_eq
    max_dd = 0.0
    for row in state.equity_curve:
        value = float(row["equity"])
        peak = max(peak, value)
        if peak > 0:
            max_dd = min(max_dd, value / peak - 1.0)
    ret = equity / start_eq - 1.0 if start_eq else 0.0
    reasons = Counter(str(row["reason"]) for row in state.trades)
    reason_line = " ".join(f"{name}={count}" for name, count in sorted(reasons.items()))
    return (
        f"Strategy 7\n"
        f"trades={buys + sells}\n"
        f"buys={buys}\n"
        f"sells={sells}\n"
        f"final_equity={equity:.2f}\n"
        f"return={ret:.2%}\n"
        f"max_dd={max_dd:.2%}\n"
        f"reasons: {reason_line}\n"
    )


def write_run_artifacts(state: SimResult, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "summary.txt").write_text(summarize_v7(state), encoding="utf-8")
    for filename, rows, fields in (
        ("daily_equity.csv", state.equity_curve, ("date", "cash", "holdings", "equity")),
        ("trades.csv", state.trades, ("date", "symbol", "hm", "side", "shares", "price", "reason")),
    ):
        with (output_dir / filename).open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)


def load_pool_days(pool_dir: Path, start: date, end: date) -> dict[date, list[str]]:
    if not pool_dir.is_dir():
        raise FileNotFoundError(f"pool directory does not exist: {pool_dir}")
    return load_pool_day_map(pool_dir, start, end, key="date", empty_in_map=True)


def _load_cli_bars(
    pool_days: Mapping[date, Sequence[str]],
    start: date,
    end: date,
    *,
    minute_source: str = "lake",
    qlib_1min_root: Path | None = None,
    daily_source: str = "lake",
    qlib_day_root: Path | None = None,
    tail_window_buy: bool = False,
    include_volume: bool = False,
) -> tuple[dict, dict]:
    # Volume / amount lake path: shell loader only (cap / tail). Not simulate.
    if tail_window_buy or include_volume:
        if minute_source != "lake" or daily_source != "lake":
            raise ValueError(
                "participation_rate / --tail-window-buy require --minute-source lake "
                "and --daily-source lake with raw bars"
            )
        from backtest.research.ashare_bars import load_daily_closes, load_minute_from_lake

        symbols = {symbol for pool in pool_days.values() for symbol in pool}
        if not symbols:
            return {}, {}
        minute = load_minute_from_lake(
            symbols, start.strftime("%Y%m%d"), end.strftime("%Y%m%d"),
            include_volume=True,
            **({"include_amount": True} if tail_window_buy else {}),
        )
        daily = load_daily_closes(symbols, start, end, source=daily_source, qlib_root=qlib_day_root)
        return minute, daily
    # Shared with topk: bars_from_pool/load_session_bars dispatches lake to
    # one book-frame window (cache off), qlib_1min to the private compact path.
    bars = bars_from_pool(
        pool_days,
        start,
        end,
        minute_source=minute_source,
        daily_source=daily_source,
        qlib_1min_root=qlib_1min_root,
        qlib_day_root=qlib_day_root,
    )
    return bars.minute, bars.daily_close


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Strategy 7 turtle CSV minute backtest",
                                     epilog="v7 不接 --minute-stop-trigger (hl or close); argparse rejects this flag.")
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--pool-dir")
    parser.add_argument(
        "--asof-pool-names", action="store_true",
        help="use names as of each session (default off: uses the window-flat name)",
    )
    parser.add_argument("--fix-minute-cash-order", action="store_true",
                        help="settle cash and positions chronologically (default off)")
    parser.add_argument("--tail-window-buy", action="store_true",
                        help="TWAP first buy 14:30-14:56 plus 15:00 auction; requires --fix-minute-cash-order (default off); "
                             "target Q<2800 shares gives zero-share slices and no fills")
    parser.add_argument("--tail-volume-unit", choices=("shares", "lots"), default="shares",
                        help="lake minute volume unit (default shares); lots multiplies volume by 100")
    parser.add_argument("--execution-audit-file", help="optional execution JSON sidecar; leaves CSVs unchanged")
    parser.add_argument("--cash-total", type=float, default=21_000_000.0)
    parser.add_argument("--output-dir")
    parser.add_argument("--minute-source", choices=("lake", "qlib_1min"), default="lake")
    parser.add_argument("--daily-source", choices=("lake", "qlib_day"), default="lake")
    parser.add_argument(
        "--qlib-1min-root",
        help="qlib my_data_1min root; implies --minute-source qlib_1min",
    )
    parser.add_argument("--qlib-day-root", help="qlib daily bin root for --daily-source qlib_day")
    parser.add_argument(
        "--participation-rate", type=float, default=None,
        help="research opt-in finite [0,1]; omitted = cap off (byte-identical old arm). "
             "Requires raw lake SHARE volume; completed bucket_end approximation. "
             "Shell precheck (P2-B) fail-closed on unit/domain; ≠δ5 certified ≠R4 "
             "(not capacity certified)",
    )
    return parser


def write_run_config(output: Path, config: dict) -> None:
    """Independent provenance writer; legacy CSV writer stays unchanged."""
    output.mkdir(parents=True, exist_ok=True)
    (output / "run-config.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        validate_tail_options(args.tail_window_buy, args.fix_minute_cash_order, args.tail_volume_unit)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    # P2-B: CLI-parse shell precheck (unit/domain). None → no-op. ≠δ5≠R4.
    # Keep ValueError (not SystemExit) so invalid-rate contract matches API/tests.
    minute_source_early = "qlib_1min" if args.qlib_1min_root else args.minute_source
    precheck_cli_participation_rate(
        args.participation_rate,
        minute_source=minute_source_early,
        qlib_1min_root=args.qlib_1min_root,
        dividend_type="none",
        tail_window_buy=args.tail_window_buy,
        tail_volume_unit=args.tail_volume_unit,
    )
    if args.tail_window_buy and (args.qlib_1min_root or args.minute_source != "lake" or args.daily_source != "lake"):
        raise SystemExit("--tail-window-buy requires --minute-source lake and --daily-source lake with raw bars")
    pool_value = args.pool_dir or os.environ.get("OSKH_TURTLE_POOL_DIR")
    if not pool_value:
        raise SystemExit("--pool-dir or OSKH_TURTLE_POOL_DIR is required")
    start, end = _as_date(args.start), _as_date(args.end)
    if end < start:
        raise SystemExit("--end must be on or after --start")
    pool_dir = Path(pool_value)
    pools = load_pool_days(pool_dir, start, end)
    minute_source = "qlib_1min" if args.qlib_1min_root else args.minute_source
    load_t0 = time.perf_counter()
    minute, daily = _load_cli_bars(
        pools,
        start,
        end,
        minute_source=minute_source,
        qlib_1min_root=Path(args.qlib_1min_root) if args.qlib_1min_root else None,
        daily_source=args.daily_source,
        qlib_day_root=Path(args.qlib_day_root) if args.qlib_day_root else None,
        **({"tail_window_buy": True} if args.tail_window_buy else {}),
        **({"include_volume": True} if args.participation_rate is not None else {}),
    )
    source = f"minute={minute_source} daily={args.daily_source}"
    load_s = time.perf_counter() - load_t0
    symbols = {symbol for values in pools.values() for symbol in values}
    exdiv, names = load_limit_context(pool_dir, symbols, start, end)
    names_by_day = (
        load_pool_names_by_day(pool_dir, start, end) if args.asof_pool_names else None
    )
    print(
        f"loaded {source}: minute_names={len(minute)} daily_names={len(daily)} "
        f"exdiv_names={len(exdiv)} st_names={sum(1 for n in names.values() if n)} "
        f"in {load_s:.2f}s",
        flush=True,
    )
    if pools:
        index_closes = load_index_daily(start, end)
    else:
        index_closes = [start + timedelta(days=n) for n in range((end - start).days + 1)]
    sim_t0 = time.perf_counter()
    audit = [] if args.execution_audit_file else None
    volume_options: dict = {}
    if args.participation_rate is not None:
        if missing := symbols - minute.keys():
            raise ValueError(f"missing minute volume frames: {sorted(missing)}")
        samples = completed_minute_volumes(minute)
        # P2-B loader-exit completed-bucket precheck (shell; does not redefine buckets).
        precheck_completed_bucket_samples(samples)
        volume_options = {
            "participation_rate": args.participation_rate,
            "volume_for_bucket": samples,
        }
    state = simulate_v7(minute, daily, pools, index_closes, cash_total=args.cash_total,
                        start=start, end=end, exdiv=exdiv,
                        names=None if args.asof_pool_names else names,
                        names_by_day=names_by_day,
                        fix_minute_cash_order=args.fix_minute_cash_order,
                        tail_window_buy=args.tail_window_buy,
                        tail_volume_unit=args.tail_volume_unit, audit_sink=audit,
                        **volume_options)
    sim_s = time.perf_counter() - sim_t0
    output = Path(args.output_dir or f"backtest_output/csv_minute_v7_{args.start}_{args.end}")
    write_run_artifacts(state, output)
    config = {
        **vars(args),
        "cash_order_policy": "chronological" if args.fix_minute_cash_order else "legacy_symbol_day",
        "same_hm_policy": ("open_stop_then_close_stop_then_buy_then_timer"
                           if args.fix_minute_cash_order else "legacy_symbol_scan"),
        "fallback_order_clock": "exact_quote_only_no_chase",
        "stable_order": "pool_then_opening_held_then_input_symbols",
    }
    if not args.tail_window_buy:
        config.pop("tail_window_buy", None)
        config.pop("tail_volume_unit", None)
    else:
        config.update(tail_policy(args.tail_volume_unit))
    if args.participation_rate is None:
        config.pop("participation_rate", None)
    write_run_config(output, config)
    if args.execution_audit_file:
        write_audit(args.execution_audit_file, audit, engine="csv_minute_v7",
                    enabled=args.fix_minute_cash_order)
    print(summarize_v7(state), end="")
    print(f"timing load={load_s:.2f}s simulate={sim_s:.2f}s total={load_s + sim_s:.2f}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
