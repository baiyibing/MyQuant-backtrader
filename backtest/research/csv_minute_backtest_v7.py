# -*- coding: utf-8 -*-
"""Strategy 7 minute matcher and its small standalone CLI.

The matcher deliberately accepts injected records.  Lake discovery belongs to the
CLI edge; lot ``buy_date`` values are the sole source of T+1 eligibility.
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backtest.research.ashare_bars import bars_from_pool
from backtest.research.ashare_fees import DEFAULT_SCHEDULE, FeeSchedule
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
    defer_sell_at_limit,
    k_for,
    load_limit_context,
    session_limit_prices,
    session_prev_close,
    skip_buy_at_limit,
    t1_sellable,
)
from backtest.research.csv_pool import load_pool_day_map
from common.infra.data_root import resolve_index_daily_root
from oskh_data.lake_kind import classify_daily_lake_kind
from oskh_data.symbol_format import to_canonical_symbol, to_partition_key

NAME_BUDGET = 1_000_000.0


@dataclass
class Lot:
    shares: int
    buy_date: date
    price: float
    kind: str


@dataclass
class Position:
    symbol: str
    entry_A: float
    stage: str = TRIAL
    add1_A1: float | None = None
    lots: list[Lot] = field(default_factory=list)
    avg_cost: float = 0.0
    last_add_date: date | None = None
    peak: float = 0.0

    @property
    def shares(self) -> int:
        return sum(lot.shares for lot in self.lots)


@dataclass
class SimResult:
    cash: float
    positions: dict[str, Position] = field(default_factory=dict)
    trades: list[dict[str, Any]] = field(default_factory=list)
    equity_curve: list[dict[str, Any]] = field(default_factory=list)


def _record_stamp(record: Mapping[str, Any]) -> Any:
    for key in ("datetime", "timestamp", "date", "time"):
        if key in record and record[key] is not None:
            return record[key]
    return None


def _record_dict(record: Any) -> dict[str, Any]:
    if isinstance(record, Mapping):
        return dict(record)
    if hasattr(record, "_asdict"):
        return dict(record._asdict())
    return dict(vars(record))


def _minute_records(minute_bars: Any) -> dict[date, dict[str, list[dict[str, Any]]]]:
    """Accept symbol->records, day->symbol->records, or a flat record iterable."""
    out: dict[date, dict[str, list[dict[str, Any]]]] = {}
    if minute_bars is None:
        return out
    flat: list[dict[str, Any]] = []
    if isinstance(minute_bars, Mapping):
        for key, value in minute_bars.items():
            if isinstance(value, Mapping) and not any(k in value for k in ("close", "open", "datetime", "date")):
                day = _as_date(key)
                for symbol, records in value.items():
                    for record in _iter_records(records):
                        record.setdefault("date", day)
                        record.setdefault("symbol", symbol)
                        flat.append(record)
            else:
                for record in _iter_records(value):
                    record.setdefault("symbol", key)
                    flat.append(record)
    else:
        flat = list(_iter_records(minute_bars))
    for record in flat:
        stamp = _record_stamp(record)
        if stamp is None:
            raise ValueError("minute record requires datetime/timestamp/date/time")
        parsed = _as_datetime(stamp)
        day = parsed.date()
        if "hm" not in record:
            record["hm"] = int(parsed.hour) * 60 + int(parsed.minute)
        symbol = to_canonical_symbol(str(record["symbol"]))
        record["symbol"] = symbol
        record["date"] = day
        out.setdefault(day, {}).setdefault(symbol, []).append(record)
    for symbols in out.values():
        for records in symbols.values():
            records.sort(key=lambda row: int(row["hm"]))
    return out


def _iter_records(value: Any) -> Iterable[dict[str, Any]]:
    if hasattr(value, "to_dict"):
        try:
            value = value.to_dict("records")
        except TypeError:
            pass
    if isinstance(value, Mapping):
        value = [value]
    for record in value or []:
        yield _record_dict(record)


def _daily_closes(daily_bars: Any) -> dict[str, dict[date, float]]:
    out: dict[str, dict[date, float]] = {}
    if not daily_bars:
        return out
    if isinstance(daily_bars, Mapping):
        for symbol, records in daily_bars.items():
            canonical = to_canonical_symbol(str(symbol))
            if isinstance(records, Mapping) and "close" not in records:
                for day, close in records.items():
                    out.setdefault(canonical, {})[_as_date(day)] = float(close)
            else:
                for row in _iter_records(records):
                    stamp = _record_stamp(row)
                    if stamp is None:
                        raise ValueError("daily record requires date/datetime/time")
                    out.setdefault(canonical, {})[_as_date(stamp)] = float(row["close"])
    return out


def _pool(pool_days: Mapping[Any, Sequence[str]] | None) -> dict[date, list[str]]:
    return {
        _as_date(day): [to_canonical_symbol(str(symbol)) for symbol in symbols]
        for day, symbols in (pool_days or {}).items()
    }


def _rescale_position(position: Position, k: float) -> None:
    factor = float(k)
    if factor <= 0:
        return
    position.entry_A *= factor
    position.avg_cost *= factor
    position.peak *= factor
    if position.add1_A1 is not None:
        position.add1_A1 *= factor
    position.lots = [Lot(lot.shares, lot.buy_date, lot.price * factor, lot.kind) for lot in position.lots]


def _event(state: SimResult, day: date, symbol: str, hm: int | None, side: str, shares: int,
           price: float | None, reason: str) -> None:
    state.trades.append({"date": day.isoformat(), "symbol": symbol, "hm": hm, "side": side,
                         "shares": shares, "price": price, "reason": reason})


def _buy(state: SimResult, position: Position | None, symbol: str, day: date, hm: int,
         price: float, fraction: float, reason: str, kind: str,
         fee: FeeSchedule = DEFAULT_SCHEDULE) -> Position | None:
    target = NAME_BUDGET * fraction
    shares = int(target / price / 100) * 100
    cost = fee.debit_buy(shares * price)
    if shares <= 0 or cost > state.cash:
        _event(state, day, symbol, hm, "skip", 0, price, "skip_cash")
        return None
    state.cash -= cost
    if position is None:
        position = Position(symbol=symbol, entry_A=price, last_add_date=day)
        state.positions[symbol] = position
    old_shares = position.shares
    position.avg_cost = ((position.avg_cost * old_shares) + price * shares) / (old_shares + shares)
    position.lots.append(Lot(shares, day, price, kind))
    position.last_add_date = day
    _event(state, day, symbol, hm, "buy", shares, price, reason)
    return position


def _sell_lots(state: SimResult, position: Position, day: date, hm: int, price: float,
               reason: str, *, kind: str | None = None,
               fee: FeeSchedule = DEFAULT_SCHEDULE) -> int:
    wanted = sum(
        lot.shares for lot in position.lots
        if t1_sellable(lot.buy_date, day) and (kind is None or lot.kind == kind)
    )
    if wanted <= 0:
        return 0
    remaining = wanted
    kept: list[Lot] = []
    for lot in position.lots:
        eligible = t1_sellable(lot.buy_date, day) and (kind is None or lot.kind == kind)
        take = min(lot.shares, remaining) if eligible else 0
        if lot.shares > take:
            kept.append(Lot(lot.shares - take, lot.buy_date, lot.price, lot.kind))
        remaining -= take
    sold = wanted - remaining
    position.lots = kept
    state.cash += fee.credit_sell(sold * price)
    _event(state, day, position.symbol, hm, "sell", sold, price, reason)
    if position.shares:
        position.avg_cost = sum(l.price * l.shares for l in position.lots) / position.shares
    else:
        state.positions.pop(position.symbol, None)
    return sold


def _is_frame_map(minute_bars: Any) -> bool:
    if not isinstance(minute_bars, Mapping) or not minute_bars:
        return False
    sample = next(iter(minute_bars.values()))
    return hasattr(sample, "loc") and hasattr(sample, "columns")


def _day_frame_records(frame: Any, day: date) -> list[dict[str, Any]]:
    if frame is None or getattr(frame, "empty", True):
        return []
    # Slice A frame contract (b): accept book ymd/DatetimeIndex here;
    # qlib_1min keeps its compact date column. Materialize only the needed day.
    if "ymd" in frame.columns:
        sl = frame.loc[frame["ymd"] == day.strftime("%Y%m%d")]
    elif "date" in frame.columns:
        sl = frame.loc[frame["date"] == day]
    else:
        sl = frame.loc[frame.index.date == day]
    if sl.empty:
        return []
    return sl.to_dict("records")


def simulate_v7(minute_bars: Any, daily_bars: Any, pool_days: Mapping[Any, Sequence[str]] | None,
                index_days: Any = None, *, cash_total: float = 21_000_000.0,
                start: Any = None, end: Any = None,
                exdiv: Mapping[str, Mapping[str, float]] | None = None,
                names: Mapping[str, str] | None = None,
                fee: FeeSchedule = DEFAULT_SCHEDULE) -> SimResult:
    """Run the matcher; an index date->close mapping enables the new-open gate."""
    frames = minute_bars if _is_frame_map(minute_bars) else None
    minutes = {} if frames is not None else _minute_records(minute_bars)
    closes = _daily_closes(daily_bars)
    pools = _pool(pool_days)
    state = SimResult(float(cash_total))
    gate: dict[date, bool] = {}
    if isinstance(index_days, Mapping):
        index_closes = {_as_date(day): float(close) for day, close in index_days.items()}
        gate = build_index_gate(index_closes)
        calendar = sorted(gate)
    elif index_days:
        calendar = sorted(_as_date(day) for day in index_days)
    else:
        calendar = sorted(set(minutes) | set(pools))
    if start is not None:
        calendar = [day for day in calendar if day >= _as_date(start)]
    if end is not None:
        calendar = [day for day in calendar if day <= _as_date(end)]
    if isinstance(index_days, Mapping) and any(day not in gate for day in calendar):
        raise ValueError("index closes lack the required 11-session gate warmup")

    last_prices: dict[str, float] = {}
    for day in calendar:
        cleared_today: set[str] = set()
        needed = list(dict.fromkeys(pools.get(day, []) + list(state.positions)))
        if frames is not None:
            symbols_today = {symbol: rows for symbol in needed
                             if (rows := _day_frame_records(frames.get(symbol), day))}
            ordered = needed
        else:
            symbols_today = minutes.get(day, {})
            ordered = list(dict.fromkeys(needed + list(symbols_today)))
        for symbol in ordered:
            records = symbols_today.get(symbol, [])
            if not records:
                if symbol in pools.get(day, []):
                    _event(state, day, symbol, None, "skip", 0, None, "skip_no_1455")
                continue
            ymd = day.strftime("%Y%m%d")
            factor = k_for(exdiv, symbol, ymd)
            position = state.positions.get(symbol)
            if factor is not None and position is not None:
                _rescale_position(position, factor)
            name = (names or {}).get(symbol, "")
            previous = session_prev_close(closes.get(symbol, {}), day, symbol, exdiv)
            limits = session_limit_prices(symbol, previous, name)
            first = True
            open_checked = False
            for row_index, row in enumerate(records):
                hm = int(row["hm"])
                open_px = float(row.get("open", row["close"]))
                close_px = float(row["close"])
                high_px = float(row.get("high", max(open_px, close_px)))
                last_prices[symbol] = close_px
                position = state.positions.get(symbol)
                if position is not None:
                    position.peak = max(position.peak, high_px)
                    decision = stop_decision(position.stage, entry_a=position.entry_A,
                                             average_cost=position.avg_cost)
                    check_px = open_px if first and decision.line is not None and open_px <= decision.line else close_px
                    if decision.line is not None and check_px <= decision.line:
                        if defer_sell_at_limit(check_px, limits):
                            _event(state, day, symbol, hm, "defer", 0, check_px, "defer_limit_down")
                        else:
                            reasons_stop = {
                                "dump_trial": "stop:trial_a090",
                                "clear_four": "stop:four_avg095",
                                "clear_six": "stop:six_avg0965",
                                "clear_eight": "stop:eight_avg0975",
                                "clear_full": "stop:full_avg098",
                            }
                            _sell_lots(state, position, day, hm, check_px,
                                       reasons_stop.get(decision.action, f"stop:{decision.action}"),
                                       fee=fee)
                    if symbol not in state.positions:
                        cleared_today.add(symbol)
                    position = state.positions.get(symbol)
                    if position is not None and in_add_window(hm):
                        ladder = ladder_decision(position.stage, close_px, entry_a=position.entry_A)
                        reasons = {
                            "add_a104": "buy:add_a104",
                            "add_a108": "buy:add_a108",
                            "add_a112": "buy:add_a112",
                            "add_a116": "buy:add_a116",
                        }
                        if ladder.action != "none":
                            if skip_buy_at_limit(close_px, limits):
                                _event(state, day, symbol, hm, "skip", 0, close_px, "skip_limit_up")
                            elif defer_sell_at_limit(close_px, limits):
                                pass
                            elif _buy(state, position, symbol, day, hm, close_px, ladder.fraction,
                                      reasons[ladder.action], ladder.action, fee=fee):
                                if ladder.action == "add_a104":
                                    position.stage = FOUR
                                elif ladder.action == "add_a108":
                                    position.stage = SIX
                                elif ladder.action == "add_a112":
                                    position.stage = EIGHT
                                elif ladder.action == "add_a116":
                                    position.stage = FULL
                if (hm == 895 and symbol in pools.get(day, []) and symbol not in state.positions
                        and symbol not in cleared_today):
                    open_checked = True
                    if gate.get(day, False):
                        _event(state, day, symbol, hm, "skip", 0, close_px, "skip_index_gate")
                    elif previous is None:
                        _event(state, day, symbol, hm, "skip", 0, close_px, "skip_no_prev_close")
                    else:
                        priced = session_limit_prices(symbol, previous, name)
                        if priced is None:
                            _event(state, day, symbol, hm, "skip", 0, close_px, "skip_unknown_board")
                        else:
                            if skip_buy_at_limit(close_px, priced):
                                _event(state, day, symbol, hm, "skip", 0, close_px, "skip_limit_up")
                            elif not defer_sell_at_limit(close_px, priced):
                                _buy(state, None, symbol, day, hm, close_px, TRIAL_FRACTION, "buy:trial", "trial",
                                     fee=fee)
                if row_index == len(records) - 1:
                    position = state.positions.get(symbol)
                    if (position is not None and position.last_add_date is not None
                            and timer_due(calendar, position.last_add_date, day, position.stage)):
                        if defer_sell_at_limit(close_px, limits):
                            _event(state, day, symbol, hm, "defer", 0, close_px, "defer_limit_down")
                        elif _sell_lots(state, position, day, hm, close_px, "exit:timer10", fee=fee):
                            if symbol not in state.positions:
                                cleared_today.add(symbol)
                first = False

            if symbol in pools.get(day, []) and symbol not in state.positions and not open_checked:
                if not any(int(row["hm"]) == 895 for row in records):
                    _event(state, day, symbol, None, "skip", 0, None, "skip_no_1455")

        holdings = sum(pos.shares * last_prices.get(symbol, pos.avg_cost) for symbol, pos in state.positions.items())
        state.equity_curve.append({"date": day.isoformat(), "cash": state.cash,
                                   "holdings": holdings, "equity": state.cash + holdings})
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
    buys = sum(row["side"] == "buy" for row in state.trades)
    sells = sum(row["side"] == "sell" for row in state.trades)
    equity = state.equity_curve[-1]["equity"] if state.equity_curve else state.cash
    return f"Strategy 7\ntrades={buys + sells}\nbuys={buys}\nsells={sells}\nfinal_equity={equity:.2f}\n"


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
) -> tuple[dict, dict]:
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
    parser = argparse.ArgumentParser(description="Strategy 7 turtle CSV minute backtest")
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--pool-dir")
    parser.add_argument("--cash-total", type=float, default=21_000_000.0)
    parser.add_argument("--output-dir")
    parser.add_argument("--minute-source", choices=("lake", "qlib_1min"), default="lake")
    parser.add_argument("--daily-source", choices=("lake", "qlib_day"), default="lake")
    parser.add_argument(
        "--qlib-1min-root",
        help="qlib my_data_1min root; implies --minute-source qlib_1min",
    )
    parser.add_argument("--qlib-day-root", help="qlib daily bin root for --daily-source qlib_day")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
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
    )
    source = f"minute={minute_source} daily={args.daily_source}"
    load_s = time.perf_counter() - load_t0
    symbols = {symbol for values in pools.values() for symbol in values}
    exdiv, names = load_limit_context(pool_dir, symbols, start, end)
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
    state = simulate_v7(minute, daily, pools, index_closes, cash_total=args.cash_total,
                        start=start, end=end, exdiv=exdiv, names=names)
    sim_s = time.perf_counter() - sim_t0
    output = Path(args.output_dir or f"backtest_output/csv_minute_v7_{args.start}_{args.end}")
    write_run_artifacts(state, output)
    print(summarize_v7(state), end="")
    print(f"timing load={load_s:.2f}s simulate={sim_s:.2f}s total={load_s + sim_s:.2f}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
