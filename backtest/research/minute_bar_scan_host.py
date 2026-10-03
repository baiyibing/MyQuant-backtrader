"""Opt-in, read-only minute scan using the existing wired strategy books."""

from __future__ import annotations

import argparse
import math
import sys
from bisect import bisect_left, bisect_right
from collections.abc import Iterator, Mapping, Sequence
from contextlib import redirect_stdout
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from backtest.research.ashare_bars import MinuteBarReadError, load_minute_from_lake
from backtest.research.bar_scan_exit import BarScanExit, HeldPosition, OhlcBar, scan_bar_exit
from backtest.research.csv_minute_backtest import BUY_HM, _buy_px
from backtest.research.csv_pool import load_pool_day_map
from backtest.research.minute_true_core_wire import (
    invoke_minute_strategy, wired_names, _DRAWDOWN,
    MinuteStrategyNotOnBarScan, minute_strategy_entries,
)
from backtest.research.qlib_bin_1min import (
    load_qlib_1min_calendar,
    qlib_inst_dir,
    read_qlib_bin,
)
from backtest.research.topk_dropout_rules import decide_topk_dropout
from backtest.research.topk_dropout_scores import load_scores_from_args, require_day_scores
from backtest.research.topk_score_exit_rules import decide_topk_score_exit
from oskh_data.symbol_format import is_canonical_symbol, to_canonical_symbol

SOURCES = ("qlib_1min", "lake")
OHLC = ("open", "high", "low", "close")
UNIVERSE_BOOKS = ("topk_dropout", "topk_score_exit")


@dataclass(frozen=True, slots=True)
class ScanSummary:
    bars: int
    fills: int
    skips: int


@dataclass(frozen=True, slots=True)
class RoundTripSummary:
    bars: int
    buys: int
    sells: int
    skips: int
    equity: float
    return_pct: float


def scan_version1_round_trip(frame, *, symbol: str, pool_days: Mapping,
                             cash: float = 100000.0, shares: int = 100) -> RoundTripSummary:
    """Flat-start, same-bar host accounting; no fees or old-engine parity claim.

    Buy reason is pool. Only bars after the selected buy close can exit.
    A sold name may re-enter on a later pool day, never again on the same day.
    Skips count bars with neither a buy nor a sell.
    """
    if not math.isfinite(cash) or cash <= 0:
        raise ValueError("cash must be finite and > 0")
    if isinstance(shares, bool) or not isinstance(shares, int) or shares <= 0 or shares % 100:
        raise ValueError("shares must be a positive whole-lot share count (multiple of 100)")
    if frame.empty:
        raise ValueError("bars must not be empty")
    code = _symbol(symbol)
    bars = _frame_bars(frame, code, Path("host-frame"))
    initial_cash = cash
    held_shares = buys = sells = 0
    cost = peak = 0.0
    book = _version1_book()
    offset = 0
    for day, day_frame in frame.groupby("date", sort=False):
        buy_index = None
        if not held_shares and code in pool_days.get(_as_date(day), []):
            px = _buy_px(day_frame)
            if px is not None:
                if not math.isfinite(px) or px <= 0:
                    raise ValueError("buy price must be finite and > 0")
                exact = day_frame["hm"] == BUY_HM
                eligible = (day_frame["hm"] >= 14 * 60 + 30) & (day_frame["hm"] <= BUY_HM)
                positions = [i for i, flag in enumerate(exact if exact.any() else eligible) if flag]
                buy_index = positions[0] if exact.any() else positions[-1]
        for index in range(len(day_frame)):
            bar = bars[offset + index]
            if index == buy_index and cash >= shares * px:
                cash -= shares * px
                held_shares = shares
                cost = peak = px
                buys += 1
                continue
            if held_shares:
                result = scan_bar_exit(
                    bar, HeldPosition(cost, peak, book.stop_pct, book.drawdown_of(1)),
                    timing="same_bar",
                )
                peak = result.peak
                if result.decision == "fill":
                    cash += held_shares * result.fill_price
                    held_shares = 0
                    sells += 1
        offset += len(day_frame)
    equity = cash + held_shares * bars[-1].close
    return RoundTripSummary(len(bars), buys, sells, len(bars) - buys - sells,
                            equity, (equity / initial_cash - 1) * 100)


def scan_held_bars(
    bars: Sequence[OhlcBar], *, cost: float, peak: float, n_days: int = 1,
    strategy: str = "version1",
    level: float | None = None,
    stage: str | None = None,
    entry_a: float | None = None,
    symbol: str | None = None,
    held: Sequence[str] | None = None,
    scores_by_day: Mapping[str, Mapping[str, float]] | None = None,
    topk: int | None = None,
    n_drop: int | None = None,
    bar_dates: Sequence[date | str] | None = None,
) -> ScanSummary:
    """Count each current-bar decision, carrying peak and keeping cost fixed."""
    if not bars:
        raise ValueError("bars must not be empty")
    if n_days != 1:
        raise ValueError("n_days must stay 1 for every strategy scan")
    if strategy == "version1":
        if bar_dates is not None and len(bar_dates) != len(bars):
            raise ValueError("bar_dates must have one source date per bar")
        fills = sum(result.decision == "fill"
                    for result in _scan_held_decisions(bars, cost=cost, peak=peak))
        return ScanSummary(len(bars), fills, len(bars) - fills)
    if strategy not in wired_names():
        raise ValueError(f"unknown minute strategy {strategy!r}")
    days = None
    if bar_dates is not None:
        if len(bar_dates) != len(bars):
            raise ValueError("bar_dates must have one source date per bar")
        days = [_as_date(day).strftime("%Y%m%d") for day in bar_dates]
    day_flags = {}
    score_days = days
    if strategy in UNIVERSE_BOOKS:
        if not scores_by_day:
            raise ValueError(
                "a single-symbol run cannot supply the day's cross-section; "
                "a full score universe is required"
            )
        if score_days is None:
            # Undated bars may use one explicitly supplied score day. This does
            # not give them session dates or change the wire's session_open default.
            if len(scores_by_day) != 1:
                raise ValueError("bar_dates are required for multiple score days")
            score_days = [next(iter(scores_by_day))] * len(bars)
        day_scores = {}
        for day in dict.fromkeys(score_days):
            scores = require_day_scores(scores_by_day, day)
            if len(scores) < 2:
                raise ValueError(
                    f"{day}: a single-symbol run cannot supply the day's cross-section; "
                    "a full score universe is required"
                )
            day_scores[day] = scores
        if not held or any(not is_canonical_symbol(code) for code in held):
            raise ValueError("held requires the opening universe of canonical codes")
        if len(set(held)) != len(held):
            raise ValueError("held must not contain duplicate codes")
        if symbol is None or _symbol(symbol) not in held:
            raise ValueError("the scan symbol must be in held")
        code = _symbol(symbol)
        for field, value in (("topk", topk), ("n_drop", n_drop)):
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"{field} requires an integer >= 0")
        for day, scores in day_scores.items():
            if strategy == "topk_dropout":
                _buy, sell = decide_topk_dropout(held, scores, topk=topk, n_drop=n_drop)
                day_flags[day] = (code in sell, None)
            else:
                plan = decide_topk_score_exit(held, scores, topk=topk, n_drop=n_drop)
                day_flags[day] = (code in plan.sell_bottom, code in plan.sell_sx0)
    running_peak = peak
    fills = skips = 0
    for index, bar in enumerate(bars):
        fields = {"level": level, "stage": stage, "entry_a": entry_a}
        if days is not None:
            fields["session_open"] = index == 0 or days[index] != days[index - 1]
        if strategy in UNIVERSE_BOOKS:
            fields["dropout_sell"], fields["sx0_sell"] = day_flags[score_days[index]]
        result = invoke_minute_strategy(
            strategy, bar, cost=cost, peak=running_peak, n_days=1,
            timing="same_bar", **fields,
        )
        running_peak = result.peak
        if result.decision == "fill":
            fills += 1
        else:
            skips += 1
    return ScanSummary(bars=len(bars), fills=fills, skips=skips)


def _version1_book():
    entries = {entry.name: entry for entry in minute_strategy_entries()}
    entry = entries.get("version1")
    if entry is None:
        raise ValueError("unknown minute strategy 'version1'")
    if entry.status != "wired":
        raise MinuteStrategyNotOnBarScan("version1", str(entry.missing_field))
    book = _DRAWDOWN["version1"]
    return book


def _scan_held_decisions(
    bars: Sequence[OhlcBar], *, cost: float, peak: float
) -> Iterator[BarScanExit]:
    """Resolve the catalog once; use the same core and book as the wire."""
    book = _version1_book()
    cost_f, running_peak = float(cost), float(peak)
    if cost_f <= 0 or running_peak <= 0:
        raise ValueError("cost and peak must be finite numbers > 0")
    drawdown = book.drawdown_of(1)
    for bar in bars:
        result = scan_bar_exit(
            bar, HeldPosition(cost_f, running_peak, book.stop_pct, drawdown),
            timing="same_bar",
        )
        running_peak = result.peak
        yield result


def _as_date(value: date | str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if len(value) != 8 or not value.isdigit():
        raise ValueError(f"date must be YYYYMMDD, got {value!r}")
    return datetime.strptime(value, "%Y%m%d").date()


def _symbol(value: str) -> str:
    symbol = to_canonical_symbol(value.strip().upper())
    if not is_canonical_symbol(symbol):
        raise ValueError(f"symbol must include an exchange, got {value!r}")
    return symbol


def _frame_bars(frame, symbol: str, root: Path) -> list[OhlcBar]:
    missing = [name for name in OHLC if name not in frame.columns]
    if missing:
        raise FileNotFoundError(f"missing {missing} for {symbol} under {root}")
    bars = []
    for values in frame.loc[:, list(OHLC)].itertuples(index=False, name=None):
        prices = tuple(float(value) for value in values)
        for name, price in zip(OHLC, prices):
            if not math.isfinite(price):
                raise ValueError(f"non-finite {name} for {symbol} under {root}")
        bars.append(OhlcBar(*prices))
    return bars


def load_scan_bars(
    symbol: str,
    start: date | str,
    end: date | str,
    *,
    source: str,
    qlib_root: Path | str | None = None,
    lake_root: Path | None = None,
    bar_dates: list[date] | None = None,
    source_frames: list | None = None,
) -> list[OhlcBar]:
    """Read explicit bars; optionally collect their source dates in bar order."""
    if source not in SOURCES:
        raise ValueError(f"source must be one of {SOURCES}, got {source!r}")
    code = _symbol(symbol)
    first, last = _as_date(start), _as_date(end)
    if first > last:
        raise ValueError("start must be on or before end")
    if source == "qlib_1min":
        if qlib_root is None:
            raise ValueError("qlib_1min source requires qlib_root")
        root = Path(qlib_root)
        if not (root / "features").is_dir():
            raise FileNotFoundError(f"minute features missing for {code} under {root}")
        try:
            calendar = load_qlib_1min_calendar(root)
        except FileNotFoundError as exc:
            raise FileNotFoundError(f"minute calendar missing for {code} under {root}: {exc}") from exc
        i0 = bisect_left(calendar, f"{first.isoformat()} 00:00:00")
        i1 = bisect_right(calendar, f"{last.isoformat()} 23:59:59") - 1
        if i0 > i1:
            raise FileNotFoundError(f"minute window missing for {code} under {root}")
        folder = root / "features" / qlib_inst_dir(code)
        columns = {}
        for name in OHLC:
            values = read_qlib_bin(folder / f"{name}.1min.bin", i0, i1)
            if values.empty:
                raise FileNotFoundError(f"{name}.1min.bin missing or empty for {code} under {root}")
            columns[name] = values
        close = columns["close"]
        kept = close.loc[close.map(math.isfinite)].index
        # Reproduce the public reader's index union / finite-close filtering,
        # without full-calendar conversion, thread pool or duplicate bin reads.
        frame = pd.DataFrame({name: columns[name] for name in ("close", "open", "high")})
        frame = frame.loc[frame["close"].map(math.isfinite)]
        if not frame.index.equals(kept):
            raise ValueError(f"qlib close alignment changed for {code} under {root}")
        if frame.empty:
            raise FileNotFoundError(f"minute bars missing for {code} under {root}")
        frame = frame.assign(low=columns["low"].reindex(kept).to_numpy())
        stamps = pd.to_datetime([calendar[int(index)] for index in kept])
        frame = frame.assign(date=stamps.date, hm=stamps.hour * 60 + stamps.minute)
        frame = frame.reset_index(drop=True)
    else:
        if lake_root is None:
            raise ValueError("lake source requires lake_root")
        root = Path(lake_root)
        if not root.is_dir():
            raise FileNotFoundError(f"lake root missing for {code}: {root}")
        try:
            frames = load_minute_from_lake(
                [code], first.strftime("%Y%m%d"), last.strftime("%Y%m%d"),
                workers=1, lake_root=root,
            )
        except MinuteBarReadError as exc:
            raise FileNotFoundError(
                f"minute OHLC unavailable for {code} under {root}: {exc.__cause__ or exc}"
            ) from exc
        frame = frames.get(code)
        if frame is None or frame.empty:
            raise FileNotFoundError(f"minute bars missing for {code} under {root}")
    bars = _frame_bars(frame, code, root)
    if bar_dates is not None:
        dates = frame["date"] if source == "qlib_1min" else frame.index
        bar_dates.extend(_as_date(day) for day in dates)
    if source_frames is not None:
        dates = frame["date"] if source == "qlib_1min" else frame.index
        source_frames.append(frame.assign(date=[_as_date(day) for day in dates]).reset_index(drop=True))
    return bars


def run_round_trip(symbol, start, end, *, pool_dir: Path, cash=100000.0, shares=100,
                   **source_args) -> RoundTripSummary:
    frames = []
    load_scan_bars(symbol, start, end, source_frames=frames, **source_args)
    pool_days = load_pool_day_map(pool_dir, start, end, key="date")
    return scan_version1_round_trip(frames[0], symbol=symbol, pool_days=pool_days,
                                   cash=cash, shares=shares)


def run_scan(
    symbol: str,
    start: date | str,
    end: date | str,
    *,
    source: str,
    qlib_root: Path | str | None = None,
    lake_root: Path | None = None,
    cost: float,
    peak: float,
    strategy: str = "version1",
    level: float | None = None,
    stage: str | None = None,
    entry_a: float | None = None,
    held: Sequence[str] | None = None,
    scores_by_day: Mapping[str, Mapping[str, float]] | None = None,
    topk: int | None = None,
    n_drop: int | None = None,
) -> ScanSummary:
    bar_dates = []
    bars = load_scan_bars(
        symbol, start, end, source=source, qlib_root=qlib_root, lake_root=lake_root,
        bar_dates=bar_dates,
    )
    return scan_held_bars(
        bars, cost=cost, peak=peak, strategy=strategy,
        level=level, stage=stage, entry_a=entry_a, symbol=symbol,
        held=held, scores_by_day=scores_by_day, topk=topk, n_drop=n_drop,
        bar_dates=bar_dates,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only minute bar scan")
    parser.add_argument("--source", choices=SOURCES, required=True)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--start", type=_as_date, metavar="YYYYMMDD", required=True)
    parser.add_argument("--end", type=_as_date, metavar="YYYYMMDD", required=True)
    parser.add_argument("--qlib-root", type=Path)
    parser.add_argument("--lake-root", type=Path)
    parser.add_argument("--cost", type=float, help="held-only scan; requires --peak")
    parser.add_argument("--peak", type=float, help="held-only scan; requires --cost")
    parser.add_argument("--pool-dir", type=Path, default=Path(__file__).resolve().parents[2] / "stock_pool",
                        help="version1 flat-start daily membership CSVs; minute bars contain no pool signal")
    parser.add_argument("--cash", type=float, default=100000.0, help="host-simple initial cash")
    parser.add_argument("--shares", type=int, default=100, help="shares per pool buy, multiple of 100")
    parser.add_argument("--strategy", choices=wired_names(), default="version1")
    parser.add_argument("--level", type=float, help="caller-supplied sma5 or ma10")
    parser.add_argument("--stage", choices=("trial", "four", "six", "eight", "full"))
    parser.add_argument("--entry-a", type=float)
    parser.add_argument("--pred-csv", type=Path)
    parser.add_argument("--scores-dir", type=Path)
    parser.add_argument("--held", help="comma-separated canonical opening held codes")
    parser.add_argument("--topk", type=int)
    parser.add_argument("--n-drop", type=int)
    try:
        args = parser.parse_args(argv)
        code = _symbol(args.symbol)
        round_trip = args.strategy == "version1" and args.cost is None and args.peak is None
        if not round_trip and (args.cost is None or args.peak is None):
            raise ValueError("held-only scan requires both --cost and --peak")
        # Existing reader progress belongs on stderr; stdout is one summary line.
        with redirect_stdout(sys.stderr):
            scores = None
            if args.strategy in UNIVERSE_BOOKS:
                scores = load_scores_from_args(pred_csv=args.pred_csv, scores_dir=args.scores_dir)
            if round_trip:
                summary = run_round_trip(
                    code, args.start, args.end, source=args.source,
                    qlib_root=args.qlib_root, lake_root=args.lake_root,
                    pool_dir=args.pool_dir, cash=args.cash, shares=args.shares,
                )
            else:
                summary = run_scan(
                    code, args.start, args.end, source=args.source,
                    qlib_root=args.qlib_root, lake_root=args.lake_root,
                    cost=args.cost, peak=args.peak,
                    strategy=args.strategy, level=args.level, stage=args.stage,
                    entry_a=args.entry_a,
                    held=[code.strip() for code in args.held.split(",")] if args.held else None,
                    scores_by_day=scores, topk=args.topk, n_drop=args.n_drop,
                )
    except SystemExit as exc:
        if exc.code == 0:
            return 0
        if isinstance(exc.code, str):
            print(f"error: {exc.code}", file=sys.stderr)
        return 1
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if round_trip:
        print(f"symbol={code} source={args.source} version1 bars={summary.bars} "
              f"buys={summary.buys} sells={summary.sells} skips={summary.skips} "
              f"equity={summary.equity:.2f} return_pct={summary.return_pct:.6f}")
        return 0
    print(
        f"symbol={code} source={args.source} {args.strategy} "
        f"bars={summary.bars} fills={summary.fills} skips={summary.skips}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
