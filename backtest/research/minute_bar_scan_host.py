"""Opt-in, read-only version1 minute scan for one symbol and date window."""

from __future__ import annotations

import argparse
import math
import sys
from collections.abc import Sequence
from contextlib import redirect_stdout
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from backtest.research.ashare_bars import MinuteBarReadError, load_minute_from_lake
from backtest.research.bar_scan_exit import OhlcBar
from backtest.research.minute_true_core_wire import invoke_minute_strategy
from backtest.research.qlib_bin_1min import (
    calendar_slice,
    load_qlib_1min_calendar,
    load_qlib_bin_1min_bars,
    qlib_inst_dir,
    read_qlib_bin,
)
from oskh_data.symbol_format import is_canonical_symbol, to_canonical_symbol

SOURCES = ("qlib_1min", "lake")
OHLC = ("open", "high", "low", "close")


@dataclass(frozen=True, slots=True)
class ScanSummary:
    bars: int
    fills: int
    skips: int


def scan_held_bars(
    bars: Sequence[OhlcBar], *, cost: float, peak: float, n_days: int = 1
) -> ScanSummary:
    """Count each current-bar decision, carrying peak and keeping cost fixed."""
    if not bars:
        raise ValueError("bars must not be empty")
    if n_days != 1:
        raise ValueError("n_days must stay 1 for the version1 scan")
    running_peak = peak
    fills = skips = 0
    for bar in bars:
        result = invoke_minute_strategy(
            "version1", bar, cost=cost, peak=running_peak, n_days=1, timing="same_bar"
        )
        running_peak = result.peak
        if result.decision == "fill":
            fills += 1
        else:
            skips += 1
    return ScanSummary(bars=len(bars), fills=fills, skips=skips)


def _as_date(value: date | str) -> date:
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
) -> list[OhlcBar]:
    """Read only the explicit source, preserving its time order and real low."""
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
    return _frame_bars(frame, code, root)


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
) -> ScanSummary:
    bars = load_scan_bars(
        symbol, start, end, source=source, qlib_root=qlib_root, lake_root=lake_root
    )
    return scan_held_bars(bars, cost=cost, peak=peak)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only version1 minute bar scan")
    parser.add_argument("--source", choices=SOURCES, required=True)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--start", type=_as_date, metavar="YYYYMMDD", required=True)
    parser.add_argument("--end", type=_as_date, metavar="YYYYMMDD", required=True)
    parser.add_argument("--qlib-root", type=Path)
    parser.add_argument("--lake-root", type=Path)
    parser.add_argument("--cost", type=float, required=True)
    parser.add_argument("--peak", type=float, required=True)
    args = parser.parse_args(argv)
    try:
        code = _symbol(args.symbol)
        # Existing reader progress belongs on stderr; stdout is one summary line.
        with redirect_stdout(sys.stderr):
            summary = run_scan(
                code, args.start, args.end, source=args.source,
                qlib_root=args.qlib_root, lake_root=args.lake_root,
                cost=args.cost, peak=args.peak,
            )
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(
        f"symbol={code} source={args.source} version1 "
        f"bars={summary.bars} fills={summary.fills} skips={summary.skips}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
