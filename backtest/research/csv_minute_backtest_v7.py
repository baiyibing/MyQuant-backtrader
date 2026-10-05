# -*- coding: utf-8 -*-
"""Strategy 7 minute matcher and its small standalone CLI.

The matcher deliberately accepts injected records.  Lake discovery belongs to the
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


@dataclass
class _DayCursor:
    symbol: str
    records: list[dict[str, Any]]
    previous: float | None
    limits: tuple[float, float] | None
    open_checked: bool = False


def _run_chronological_day(
    state: SimResult, day: date, calendar: Sequence[date],
    symbols_today: Mapping[str, list[dict[str, Any]]], ordered: Sequence[str],
    pool: Sequence[str], closes: Mapping[str, Mapping[date, float]],
    last_prices: dict[str, float], cleared_today: set[str], *,
    exdiv: Mapping[str, Mapping[str, float]] | None,
    names: Mapping[str, str] | None,
    names_by_day: Mapping[str, Mapping[str, str]] | None,
    blocked_new: bool, fee: FeeSchedule, audit_sink: Any,
    tail_window_buy: bool = False,
    tail_volume_unit: str | None = "shares",
) -> None:
    """Merge v7 bars; timer decisions observe the completed buy phase.

    Quote and decision clocks coincide: v7 has no target-minute fallback or
    chase. Stable ties retain the legacy pool/held/input-symbol order. All daily
    reference/economic work snapshots only positions held before any new buy.
    Missing-bar entitlement behavior deliberately remains the legacy X-13 rule.
    """
    if tail_window_buy:
        tail_volume_unit = resolve_tail_volume_unit(tail_volume_unit)
    ymd = day.strftime("%Y%m%d")
    cursors: list[_DayCursor] = []
    tail_parents: dict[str, TailParent] = {}
    tail_attempted: set[tuple[str, int]] = set()
    by_hm: dict[int, list[tuple[_DayCursor, int, dict[str, Any]]]] = {}
    for symbol in ordered:
        source = symbols_today.get(symbol, [])
        keep = _in_session([int(row["hm"]) for row in source])
        records = [row for row, valid in zip(source, keep) if valid]
        if not records:
            if symbol in pool:
                _event(state, day, symbol, None, "skip", 0, None,
                       "skip_no_tail_start" if tail_window_buy else "skip_no_1455")
            continue
        position = state.positions.get(symbol)
        if position is not None:
            _apply_exdiv_economics(state, position, ymd)
            factor = k_for(exdiv, symbol, ymd)
            if factor is not None:
                _rescale_position(position, factor)
        name = (asof_pool_name(names_by_day, ymd, symbol) if names_by_day is not None
                else (names or {}).get(symbol, ""))
        previous = session_prev_close(closes.get(symbol, {}), day, symbol, exdiv)
        cursor = _DayCursor(symbol, records, previous, session_limit_prices(symbol, previous, name, as_of=day))
        cursors.append(cursor)
        for index, row in enumerate(records):
            by_hm.setdefault(int(row["hm"]), []).append((cursor, index, row))

    if tail_window_buy:
        for tail_hm in TAIL_MINUTES:
            by_hm.setdefault(tail_hm, [])
    for hm, rows in sorted(by_hm.items()):
        duplicate_tail_symbols: set[str] = set()
        if tail_window_buy and hm in TAIL_MINUTES:
            seen: set[str] = set()
            for cursor, _, row in rows:
                if cursor.symbol in seen or row.get("_tail_duplicate", False):
                    duplicate_tail_symbols.add(cursor.symbol)
                seen.add(cursor.symbol)
        # As in the original scanner, this bar's high is observed before its
        # gap-open stop. It never advances a different, later minute.
        for cursor, _, row in rows:
            close_px = float(row["close"])
            open_px = float(row.get("open", close_px))
            last_prices[cursor.symbol] = close_px
            position = state.positions.get(cursor.symbol)
            if position is not None and cursor.symbol not in tail_parents:
                # ON trial lots retain their initial fill's peak on T+0.
                # Preexisting positions and OFF retain the original scan.
                position.peak = max(position.peak, float(row.get("high", max(open_px, close_px))))

        # Independent stop sells precede close buys. Opening fills settle first;
        # the original first-row-only gap rule and completed-volume clock stay.
        stopped_rows: set[tuple[str, int]] = set()
        for phase in ("open", "close"):
            for cursor, index, row in rows:
                symbol = cursor.symbol
                if (symbol, index) in stopped_rows:
                    continue
                position = state.positions.get(symbol)
                if position is None:
                    continue
                decision = stop_decision(position.stage, entry_a=position.entry_A,
                                         average_cost=position.avg_cost)
                open_px, close_px = float(row.get("open", row["close"])), float(row["close"])
                gap_open = index == 0 and decision.line is not None and open_px <= decision.line
                if phase != ("open" if gap_open else "close"):
                    continue
                check_px = open_px if gap_open else close_px
                if decision.line is None or check_px > decision.line:
                    continue
                stopped_rows.add((symbol, index))
                with audit_scope(audit_sink, decision_hm=hm, phase=phase):
                    if cursor.limits is None:
                        _event(state, day, symbol, hm, "skip", 0, check_px,
                               "skip_no_prev_close" if cursor.previous is None else "skip_unknown_board")
                    elif defer_sell_at_limit(check_px, cursor.limits):
                        _event(state, day, symbol, hm, "defer", 0, check_px, "defer_limit_down")
                    else:
                        reasons_stop = {
                            "dump_trial": "stop:trial_a090", "clear_four": "stop:four_avg095",
                            "clear_six": "stop:six_avg0965", "clear_eight": "stop:eight_avg0975",
                            "clear_full": "stop:full_avg098",
                        }
                        _sell_lots(state, position, day, hm, check_px,
                                   reasons_stop.get(decision.action, f"stop:{decision.action}"),
                                   fee=fee, at=hm - 1 if gap_open else hm)
                if symbol not in state.positions:
                    cleared_today.add(symbol)

            # The opening quote fixes quantity before the completed 14:30 bar
            # exists; cash only constrains each later close-phase child fill.
            if tail_window_buy and hm == TAIL_START and phase == "open":
                for cursor, _, row in rows:
                    symbol = cursor.symbol
                    if (symbol not in pool or symbol in state.positions
                            or symbol in cleared_today or cursor.open_checked):
                        continue
                    cursor.open_checked = True
                    with audit_scope(audit_sink, decision_hm=hm, phase="open"):
                        if symbol in duplicate_tail_symbols:
                            _event(state, day, symbol, hm, "skip", 0, None, "skip_duplicate_tail_start")
                        elif blocked_new:
                            _event(state, day, symbol, hm, "skip", 0, None, "skip_index_gate")
                        elif cursor.previous is None:
                            _event(state, day, symbol, hm, "skip", 0, None, "skip_no_prev_close")
                        elif cursor.limits is None:
                            _event(state, day, symbol, hm, "skip", 0, None, "skip_unknown_board")
                        else:
                            try:
                                opening = float(row["open"])
                            except (KeyError, TypeError, ValueError):
                                opening = 0.0
                            if isfinite(opening) and opening > 0:
                                tail_parents[symbol] = TailParent.from_budget(NAME_BUDGET * TRIAL_FRACTION, opening)
                            else:
                                _event(state, day, symbol, hm, "skip", 0, None, "skip_no_tail_start")

        if tail_window_buy and hm in TAIL_MINUTES:
            present = {cursor.symbol for cursor, _, _ in rows}
            for symbol in tail_parents:
                if symbol not in present:
                    with audit_scope(audit_sink, decision_hm=hm, phase="close"):
                        _event(state, day, symbol, hm, "skip", 0, None, "skip_tail_quote")
        for cursor, _, row in rows:
            symbol, close_px = cursor.symbol, float(row["close"])
            with audit_scope(audit_sink, decision_hm=hm, phase="close"):
                if (tail_window_buy and hm in TAIL_MINUTES and symbol in tail_parents
                        and (symbol, hm) not in tail_attempted):
                    tail_attempted.add((symbol, hm))
                    quote = (None if symbol in duplicate_tail_symbols
                             else tail_quote(row, hm, tail_volume_unit))
                    if symbol in duplicate_tail_symbols:
                        _event(state, day, symbol, hm, "skip", 0, None, "skip_duplicate_tail_bar")
                    elif quote is not None and skip_buy_at_limit(quote.price, cursor.limits):
                        _event(state, day, symbol, hm, "skip", 0, quote.price, "skip_limit_up")
                    elif quote is not None and defer_sell_at_limit(quote.price, cursor.limits):
                        _event(state, day, symbol, hm, "skip", 0, quote.price, "skip_limit_down")
                    else:
                        _buy_tail_slice(state, tail_parents[symbol], symbol, day, hm, row, tail_volume_unit, fee)
                position = state.positions.get(symbol)
                if position is not None and in_add_window(hm):
                    ladder = ladder_decision(position.stage, close_px, entry_a=position.entry_A)
                    if ladder.action != "none":
                        if cursor.limits is None:
                            _event(state, day, symbol, hm, "skip", 0, close_px,
                                   "skip_no_prev_close" if cursor.previous is None else "skip_unknown_board")
                        elif skip_buy_at_limit(close_px, cursor.limits):
                            _event(state, day, symbol, hm, "skip", 0, close_px, "skip_limit_up")
                        elif (not defer_sell_at_limit(close_px, cursor.limits)
                              and _buy(state, position, symbol, day, hm, close_px, ladder.fraction,
                                       f"buy:{ladder.action}", ladder.action, fee=fee)):
                            position.stage = {"add_a104": FOUR, "add_a108": SIX,
                                              "add_a112": EIGHT, "add_a116": FULL}[ladder.action]
                if (not tail_window_buy and hm == 895 and symbol in pool and symbol not in state.positions
                        and symbol not in cleared_today):
                    cursor.open_checked = True
                    if blocked_new:
                        _event(state, day, symbol, hm, "skip", 0, close_px, "skip_index_gate")
                    elif cursor.previous is None:
                        _event(state, day, symbol, hm, "skip", 0, close_px, "skip_no_prev_close")
                    elif cursor.limits is None:
                        _event(state, day, symbol, hm, "skip", 0, close_px, "skip_unknown_board")
                    elif skip_buy_at_limit(close_px, cursor.limits):
                        _event(state, day, symbol, hm, "skip", 0, close_px, "skip_limit_up")
                    elif not defer_sell_at_limit(close_px, cursor.limits):
                        _buy(state, None, symbol, day, hm, close_px, TRIAL_FRACTION,
                             "buy:trial", "trial", fee=fee)

        # The last-bar timer depends on last_add_date and stage AFTER all buys.
        # Its proceeds never retry a failed buy in this hm.
        for cursor, index, row in rows:
            if index != len(cursor.records) - 1:
                continue
            symbol, close_px = cursor.symbol, float(row["close"])
            position = state.positions.get(symbol)
            if (position is None or position.last_add_date is None
                    or not timer_due(calendar, position.last_add_date, day, position.stage)):
                continue
            with audit_scope(audit_sink, decision_hm=hm, phase="timer"):
                if cursor.limits is None:
                    _event(state, day, symbol, hm, "skip", 0, close_px,
                           "skip_no_prev_close" if cursor.previous is None else "skip_unknown_board")
                elif defer_sell_at_limit(close_px, cursor.limits):
                    _event(state, day, symbol, hm, "defer", 0, close_px, "defer_limit_down")
                elif (_sell_lots(state, position, day, hm, close_px, "exit:timer10", fee=fee)
                      and symbol not in state.positions):
                    cleared_today.add(symbol)

    for cursor in cursors:
        symbol = cursor.symbol
        if tail_window_buy:
            if symbol in pool and symbol not in state.positions and not cursor.open_checked:
                _event(state, day, symbol, None, "skip", 0, None, "skip_no_tail_start")
            continue
        if (symbol in pool and symbol not in state.positions and not cursor.open_checked
                and not any(int(row["hm"]) == 895 for row in cursor.records)):
            _event(state, day, symbol, None, "skip", 0, None, "skip_no_1455")


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
    """Delegate OFF to main; retain the native X02 loop until PR4.

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
    if not fix_minute_cash_order:
        from backtest.research.csv_minute_backtest import simulate
        from backtest.research.minute_engine_policies import MinutePolicyContext
        return simulate(
            minute_bars, daily_bars, pool_days, start, end, strategy="version7",
            total_cash=cash_total, exdiv=exdiv, exdiv_economics=exdiv_economics,
            pool_names=names, pool_names_by_day=names_by_day,
            participation_rate=participation_rate, volume_for_bucket=volume_for_bucket,
            audit_sink=audit_sink,
            policy_context=MinutePolicyContext(index_days=index_days, fee_schedule=fee),
        )
    frames = minute_bars if _is_frame_map(minute_bars) else None
    minutes = {} if frames is not None else _minute_records(minute_bars)
    closes = _daily_closes(daily_bars)
    pools = _pool(pool_days)
    state = SimResult(float(cash_total))
    if exdiv_economics is not None:
        state.exdiv_economics = ExDivEconomics(exdiv_economics)
    if participation_rate is not None:
        state.volume_cap = VolumeCap(participation_rate, volume_for_bucket)
    calendar, gate = prepare_calendar(index_days, frames, minutes, pools, start, end)

    last_prices: dict[str, float] = {}
    for day in calendar:
        AccountingPolicy.settle_day(state, day)
        cleared_today: set[str] = set()
        needed = list(dict.fromkeys(pools.get(day, []) + list(state.positions)))
        if frames is not None:
            symbols_today = {symbol: rows for symbol in needed
                             if (rows := _day_frame_records(frames.get(symbol), day))}
            ordered = needed
        else:
            symbols_today = minutes.get(day, {})
            ordered = list(dict.fromkeys(needed + list(symbols_today)))
        _run_chronological_day(
            state, day, calendar, symbols_today, ordered, pools.get(day, []),
            closes, last_prices, cleared_today, exdiv=exdiv, names=names,
            names_by_day=names_by_day, blocked_new=gate.get(day, False), fee=fee,
            audit_sink=audit_sink,
            tail_window_buy=tail_window_buy,
            tail_volume_unit=tail_volume_unit,
        )

        AccountingPolicy.append_equity(state, day, last_prices)
    return state


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
