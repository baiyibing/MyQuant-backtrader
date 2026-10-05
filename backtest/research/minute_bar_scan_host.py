"""Read-only minute host: load bars and call csv_minute_backtest.simulate,
v7 or topk_app runners. The bar-scan / true-core-wire probe path is retired.
"""

from __future__ import annotations

import argparse
import math
import os
import sys
from bisect import bisect_left, bisect_right
from collections.abc import Sequence
from contextlib import redirect_stdout
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

from backtest.research.ashare_bars import _in_session, load_daily_ohlc
from backtest.research import csv_minute_backtest
from backtest.research.csv_strategy_books import csv_strategy_names
from backtest.research.csv_pool import load_pool_day_map
from backtest.research.csv_common import DEFAULT_DAILY_QUOTA, STRATEGY4_CALENDAR_SLACK_DAYS
from backtest.research.csv_daily_loader import warmup_start
from backtest.research.qlib_bin_1min import (
    load_qlib_1min_calendar,
    qlib_inst_dir,
    read_qlib_bin,
)
from backtest.research.topk_dropout_scores import load_scores_from_args
from oskh_data.symbol_format import is_canonical_symbol, to_canonical_symbol, to_partition_key

SOURCES = ("qlib_1min", "lake")
OHLC = ("open", "high", "low", "close")
UNIVERSE_BOOKS = ("topk_dropout", "topk_score_exit")


@dataclass(frozen=True, slots=True)
class OhlcBar:
    open: float
    high: float
    low: float
    close: float


@dataclass(frozen=True, slots=True)
class RoundTripSummary:
    bars: int
    buys: int
    sells: int
    skips: int
    equity: float
    return_pct: float


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


def _load_lake_window(code: str, root: Path, start: str, end: str):
    """Read one closed UTC-ms window; preserve the default book-reader rules."""
    import pyarrow.parquet as pq

    from backtest.research.market_layer import utc_ms_range

    path = root / f"symbol={to_partition_key(code)}" / "data.parquet"
    if not path.is_file():
        raise FileNotFoundError(f"minute parquet missing for {code} under {root}")
    t0, t1 = utc_ms_range(start, end)
    try:
        has_volume = "volume" in pq.read_schema(path).names
        table = pq.read_table(
            path, columns=["time", *OHLC] + (["volume"] if has_volume else []),
            filters=[("time", ">=", t0), ("time", "<=", t1)],
        )
    except Exception as exc:
        raise FileNotFoundError(
            f"minute OHLC unavailable for {code} under {root}: {exc}"
        ) from exc
    utc = pd.to_datetime(table["time"].to_numpy(), unit="ms", utc=True)
    hm = utc.hour * 60 + utc.minute
    keep = _in_session(hm.to_numpy())
    utc = utc[keep]
    frame = pd.DataFrame(
        {**{name: table[name].to_numpy()[keep] for name in OHLC},
         "ymd": utc.strftime("%Y%m%d"), "hm": hm.to_numpy()[keep],
         **({"_volume": table["volume"].to_numpy()[keep]} if has_volume else {})},
        index=utc.tz_localize(None),
    ).astype({**{name: "float64" for name in OHLC}, "hm": "int64"})
    frame = frame[~frame.index.duplicated(keep="last")].sort_index()
    if has_volume:
        day_volume = frame.groupby("ymd")["_volume"].transform("sum")
        frame = frame.loc[day_volume != 0].rename(columns={"_volume": "volume"})
    return frame


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
        frame = _load_lake_window(
            code, root, first.strftime("%Y%m%d"), last.strftime("%Y%m%d"),
        )
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


def summarize_simulate(st, *, bars: int, total_cash: float) -> RoundTripSummary:
    """Report only engine trades and engine end-of-day equity."""
    if st.equity_curve:
        last = st.equity_curve[-1]
        equity = last["equity"] if isinstance(last, dict) else last[1]
    else:
        equity = st.cash
    return RoundTripSummary(
        bars=bars,
        buys=sum(t["side"] == "BUY" for t in st.trades),
        sells=sum(t["side"] == "SELL" for t in st.trades),
        skips=sum(t["side"] == "SKIP" for t in st.trades),
        equity=equity, return_pct=(equity / total_cash - 1) * 100,
    )


def run_simulate(symbol, start, end, *, pool_dir: Path, cash=100000.0,
                 daily_quota=DEFAULT_DAILY_QUOTA, strategy="version1",
                 scores_by_day=None, topk=None, n_drop=None, **source_args):
    """Adapt host readers to the complete shared minute engine, starting flat."""
    if strategy not in csv_strategy_names():
        raise ValueError(f"unregistered CSV book: {strategy}")
    first = _as_date(start).strftime("%Y%m%d")
    last = _as_date(end).strftime("%Y%m%d")
    code = _symbol(symbol)
    raw_pool = load_pool_day_map(pool_dir, first, last, key="date")
    pool_days = {_as_date(day).strftime("%Y%m%d"): list(codes)
                 for day, codes in raw_pool.items()}
    codes = {code}
    if strategy in UNIVERSE_BOOKS:
        codes.update(c for members in pool_days.values() for c in members)
        codes.update(c for scores in (scores_by_day or {}).values() for c in scores)
    minute_bars = {}
    for member in sorted(codes):
        frames = []
        load_scan_bars(member, start, end, source_frames=frames, **source_args)
        frame = frames[0].copy()
        frame["ymd"] = pd.to_datetime(frame["date"]).dt.strftime("%Y%m%d")
        minute_bars[member] = frame
    history_start = (warmup_start(first, STRATEGY4_CALENDAR_SLACK_DAYS)
                     if strategy in ("version4", "version12") else warmup_start(first))
    daily_bars = load_daily_ohlc(
        sorted(codes), history_start, last,
        **({"source": "qlib_day", "qlib_root": source_args.get("qlib_root")}
           if source_args["source"] == "qlib_1min" else {"source": "lake"}),
        **({"dividend_type": "front"} if strategy == "version12" else {}),
    )
    for member in codes:
        if member not in daily_bars or daily_bars[member].empty:
            raise FileNotFoundError(f"daily OHLC missing for {member}")
    st = csv_minute_backtest.simulate(
        minute_bars, daily_bars, pool_days, first, last, strategy=strategy,
        total_cash=cash, daily_quota=daily_quota,
        scores_by_day=scores_by_day, topk=topk, n_drop=n_drop,
    )
    return summarize_simulate(st, bars=sum(len(f) for f in minute_bars.values()),
                              total_cash=cash)


def run_version7(start, end, *, pool_dir: Path | None = None,
                 cash: float = 21_000_000.0, asof_pool_names: bool = False):
    """Load the complete v7 pool through its existing CLI and invoke its runner."""
    from backtest.research import ashare_session, csv_minute_backtest_v7 as v7

    pool_value = pool_dir or os.environ.get("OSKH_TURTLE_POOL_DIR")
    if not pool_value:
        raise ValueError("--pool-dir or OSKH_TURTLE_POOL_DIR is required")
    start, end = _as_date(start), _as_date(end)
    if end < start:
        raise ValueError("--end must be on or after --start")
    pool_dir = Path(pool_value)
    pool_days = v7.load_pool_days(pool_dir, start, end)
    minute_bars, daily_bars = v7._load_cli_bars(pool_days, start, end)
    symbols = {code for codes in pool_days.values() for code in codes}
    exdiv, names = ashare_session.load_limit_context(pool_dir, symbols, start, end)
    names_by_day = (v7.load_pool_names_by_day(pool_dir, start, end)
                    if asof_pool_names else None)
    index_days = (v7.load_index_daily(start, end) if pool_days else
                  [start + timedelta(days=n) for n in range((end - start).days + 1)])
    state = v7.simulate_v7(
        minute_bars, daily_bars, pool_days, index_days, cash_total=cash,
        start=start, end=end, exdiv=exdiv,
        names=None if asof_pool_names else names, names_by_day=names_by_day,
    )
    return summarize_simulate(state, bars=sum(len(f) for f in minute_bars.values()),
                              total_cash=cash)


def run_topk_app_dropout(start, end, *, pool_dir=None, app_pool_dir=None,
                         pred=None, topk=None, asof=None, cash=None):
    """Reuse the standalone topk_app loaders without writing pool exports."""
    from backtest.research import ashare_session, csv_minute_backtest_v7 as v7
    from backtest.research import csv_minute_backtest_topk_app_dropout as topk_app
    from backtest.research.topk_app_dropout import DEFAULT_TOPK
    from backtest.research.csv_minute_backtest_topk_app_dropout import DEFAULT_CASH_TOTAL

    start, end = _as_date(start), _as_date(end)
    if end < start:
        raise ValueError("--end must be on or after --start")
    topk = DEFAULT_TOPK if topk is None else topk
    cash = DEFAULT_CASH_TOTAL if cash is None else cash
    asof = "pred_minus_one" if asof is None else asof
    if asof not in ("pred_minus_one", "identity"):
        raise ValueError("--asof must be pred_minus_one or identity")
    if pool_dir is not None:
        name_dir = Path(pool_dir)
        pools = v7.load_pool_days(name_dir, start, end)
    else:
        if app_pool_dir is None or pred is None:
            raise ValueError("--pool-dir or both --app-pool-dir and --pred are required")
        app_dir = Path(app_pool_dir).expanduser().resolve()
        pred_path = Path(pred).expanduser().resolve()
        if not app_dir.is_dir():
            raise FileNotFoundError(f"app pool dir missing: {app_dir}")
        if not pred_path.is_file():
            raise FileNotFoundError(f"pred missing: {pred_path}")
        pools = topk_app.build_intersect_pool_days(
            app_dir, pred_path, start.strftime("%Y%m%d"), end.strftime("%Y%m%d"),
            topk=topk, asof=asof, dump_dir=None,
        )
        name_dir = Path(app_pool_dir)
    minute, daily = v7._load_cli_bars(pools, start, end)
    index = v7.load_index_daily(start, end) if pools else []
    symbols = {code for codes in pools.values() for code in codes}
    exdiv, names = ashare_session.load_limit_context(name_dir, symbols, start, end)
    state = v7.simulate_v7(
        minute, daily, pools, index, cash_total=cash,
        start=start, end=end, exdiv=exdiv, names=names,
    )
    return summarize_simulate(state, bars=sum(len(f) for f in minute.values()),
                              total_cash=cash)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only minute host (flat-start CSV simulation)")
    parser.add_argument("--source", choices=SOURCES, required=True)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--start", type=_as_date, metavar="YYYYMMDD", required=True)
    parser.add_argument("--end", type=_as_date, metavar="YYYYMMDD", required=True)
    parser.add_argument("--qlib-root", type=Path)
    parser.add_argument("--lake-root", type=Path)
    parser.add_argument("--cost", type=float, help="unsupported held seed (fails closed)")
    parser.add_argument("--peak", type=float, help="unsupported held seed (fails closed)")
    parser.add_argument("--pool-dir", type=Path,
                        help="flat-start daily membership CSVs; minute bars contain no pool signal")
    parser.add_argument("--cash", type=float, help="initial cash (v7: 21000000; registered books: 100000)")
    parser.add_argument("--asof-pool-names", action="store_true", help="v7: use pool names as of each day")
    parser.add_argument("--daily-quota", type=float, default=DEFAULT_DAILY_QUOTA,
                        help="CSV engine daily buy budget")
    parser.add_argument("--strategy", choices=(*csv_strategy_names(), "version7", "topk_app_dropout"), default="version1")
    parser.add_argument("--app-pool-dir", type=Path, help="topk_app_dropout app pool directory")
    parser.add_argument("--pred", type=Path, help="topk_app_dropout prediction file")
    parser.add_argument("--asof", choices=("pred_minus_one", "identity"),
                        help="topk_app_dropout prediction date mapping")
    parser.add_argument("--pred-csv", type=Path)
    parser.add_argument("--scores-dir", type=Path)
    parser.add_argument("--held", help="comma-separated canonical opening held codes")
    parser.add_argument("--topk", type=int)
    parser.add_argument("--n-drop", type=int)
    try:
        args = parser.parse_args(argv)
        code = _symbol(args.symbol)
        if args.cost is not None or args.peak is not None or args.held:
            raise ValueError(
                "minute host runs csv_minute_backtest.simulate from a flat pool start "
                "and does not accept a partial held seed (--cost/--peak/--held)"
            )
        # Existing reader progress belongs on stderr; stdout is one summary line.
        with redirect_stdout(sys.stderr):
            scores = None
            if args.strategy in UNIVERSE_BOOKS:
                scores = load_scores_from_args(pred_csv=args.pred_csv, scores_dir=args.scores_dir)
            if args.strategy == "topk_app_dropout":
                if args.source != "lake" or args.qlib_root or args.lake_root:
                    raise ValueError("topk_app_dropout host requires the existing default lake loaders")
                if args.asof_pool_names:
                    raise ValueError("--asof-pool-names requires version7")
                summary = run_topk_app_dropout(
                    args.start, args.end, pool_dir=args.pool_dir,
                    app_pool_dir=args.app_pool_dir, pred=args.pred,
                    topk=args.topk, asof=args.asof, cash=args.cash,
                )
            elif args.strategy == "version7":
                if args.source != "lake" or args.qlib_root or args.lake_root:
                    raise ValueError("version7 host requires the existing default lake loaders")
                summary = run_version7(
                    args.start, args.end, pool_dir=args.pool_dir,
                    cash=21_000_000.0 if args.cash is None else args.cash,
                    asof_pool_names=args.asof_pool_names,
                )
            else:
                if args.asof_pool_names:
                    raise ValueError("--asof-pool-names requires version7")
                summary = run_simulate(
                    code, args.start, args.end, source=args.source,
                    qlib_root=args.qlib_root, lake_root=args.lake_root,
                    pool_dir=args.pool_dir or Path(__file__).resolve().parents[2] / "stock_pool",
                    cash=100000.0 if args.cash is None else args.cash, daily_quota=args.daily_quota,
                    strategy=args.strategy, scores_by_day=scores,
                    topk=args.topk, n_drop=args.n_drop,
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
    print(f"symbol={code} source={args.source} {args.strategy} bars={summary.bars} "
          f"buys={summary.buys} sells={summary.sells} skips={summary.skips} "
          f"equity={summary.equity:.2f} return_pct={summary.return_pct:.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
