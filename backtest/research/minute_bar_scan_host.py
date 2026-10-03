"""Opt-in, read-only minute scan using the existing wired strategy books."""

from __future__ import annotations

import argparse
import math
import sys
from collections.abc import Mapping, Sequence
from contextlib import redirect_stdout
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from backtest.research.ashare_bars import MinuteBarReadError, load_minute_from_lake
from backtest.research.bar_scan_exit import OhlcBar
from backtest.research.minute_true_core_wire import invoke_minute_strategy, wired_names
from backtest.research.qlib_bin_1min import (
    calendar_slice,
    load_qlib_1min_calendar,
    load_qlib_bin_1min_bars,
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
        try:
            frames = load_qlib_bin_1min_bars(
                [code], first, last, qlib_root=root, preload_days=0, workers=1
            )
        except (FileNotFoundError, SystemExit) as exc:
            raise FileNotFoundError(f"minute bars missing for {code} under {root}: {exc}") from exc
        frame = frames.get(code)
        if frame is None or frame.empty:
            raise FileNotFoundError(f"minute bars missing for {code} under {root}")

        calendar = load_qlib_1min_calendar(root)
        i0, i1 = calendar_slice(
            calendar, f"{first.isoformat()} 00:00:00", f"{last.isoformat()} 23:59:59"
        )
        folder = root / "features" / qlib_inst_dir(code)
        close = read_qlib_bin(folder / "close.1min.bin", i0, i1)
        # The public reader drops non-finite closes, then resets row indices.
        # Recover those kept calendar positions before aligning the separate low.
        kept = close.loc[close.map(math.isfinite)].index
        if len(kept) != len(frame):
            raise ValueError(f"qlib close alignment changed for {code} under {root}")
        low = read_qlib_bin(folder / "low.1min.bin", i0, i1)
        if low.empty:
            raise FileNotFoundError(f"low.1min.bin missing or empty for {code} under {root}")
        # Refuse the public reader's fallback for absent open/high feature bins.
        for name in ("open", "high"):
            values = read_qlib_bin(folder / f"{name}.1min.bin", i0, i1)
            if values.empty:
                raise FileNotFoundError(f"{name}.1min.bin missing or empty for {code} under {root}")
        frame = frame.assign(low=low.reindex(kept).to_numpy())
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
    return bars


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
    parser.add_argument("--cost", type=float, required=True)
    parser.add_argument("--peak", type=float, required=True)
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
        # Existing reader progress belongs on stderr; stdout is one summary line.
        with redirect_stdout(sys.stderr):
            scores = None
            if args.strategy in UNIVERSE_BOOKS:
                scores = load_scores_from_args(pred_csv=args.pred_csv, scores_dir=args.scores_dir)
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
    print(
        f"symbol={code} source={args.source} {args.strategy} "
        f"bars={summary.bars} fills={summary.fills} skips={summary.skips}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
