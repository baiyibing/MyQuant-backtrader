# -*- coding: utf-8 -*-
"""Unified-exit Mode A: instance assembly + exit matrix + aggregation.

Spec SSOT: docs/backtest/stock-backtest-unified-exit-proposal-2026-09-17.md
§1 / §12 (Q1–Q35 locked). Uncovered boundary → STOP, open Q36+ in proposal §10.

Mode A only (front daily close). No backtrader / Cerebro / Mode B / E-R6.
Entry set is strategy-independent (nominal cash pool 1.1e9 never caps).
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Iterable, Mapping, Optional, Sequence

import pandas as pd

from backtest.research.csv_daily_loader import _read_one_daily, warmup_start
from backtest.research.csv_pool import parse_pool_csv_entries
from backtest.research.market_layer import limit_pct
from common.infra.data_root import resolve_period_root

DEFAULT_START = "20251023"
DEFAULT_END = "20260909"
DEFAULT_TOL = 0.002
LOT_NOTIONAL = 1_000_000.0
CASH_POOL = 1_100_000_000.0
COMMISSION = 0.001
WINDOW_CALENDAR_DAYS = 322  # 20251023–20260909 inclusive calendar span for annualization


def ymd_to_date(ymd: str) -> date:
    return date(int(ymd[:4]), int(ymd[4:6]), int(ymd[6:8]))


def date_to_ymd(d: date | pd.Timestamp) -> str:
    if isinstance(d, pd.Timestamp):
        d = d.date()
    return d.strftime("%Y%m%d")


def load_session_calendar(
    start: str = DEFAULT_START,
    end: str = DEFAULT_END,
    *,
    sessions: Optional[Sequence[str]] = None,
) -> list[str]:
    """Market sessions YYYYMMDD in ``[start, end]``.

    Production path uses v7 ``load_index_daily`` (000001.SH). Tests inject
    ``sessions`` so CI stays data-free. Master has no ``load_index_daily_closes``.
    """
    if sessions is not None:
        d0, d1 = ymd_to_date(start), ymd_to_date(end)
        out = sorted(
            y for y in sessions if d0 <= ymd_to_date(y) <= d1
        )
        if not out:
            raise ValueError("injected sessions empty inside window")
        return out

    from backtest.research.csv_minute_backtest_v7 import load_index_daily

    closes = load_index_daily(ymd_to_date(start), ymd_to_date(end))
    d0, d1 = ymd_to_date(start), ymd_to_date(end)
    return [date_to_ymd(d) for d in sorted(closes) if d0 <= d <= d1]


def resolve_front_root(front_root: Optional[Path] = None) -> Path:
    """Front dividend daily root via lake resolvers (never cwd stock_data/)."""
    if front_root is not None:
        return Path(front_root)
    return resolve_period_root("1d") / "dividend_type=front"


def load_front_bars(
    codes: Iterable[str],
    start: str,
    end: str,
    *,
    front_root: Optional[Path] = None,
    workers: int = 8,
    bars: Optional[Mapping[str, pd.DataFrame]] = None,
) -> dict[str, pd.DataFrame]:
    """Load front daily OHLCV keyed by canonical code.

    ``bars`` injects an in-memory map for synthetic tests (skip lake I/O).
    """
    if bars is not None:
        return {c: bars[c] for c in codes if c in bars}

    root = resolve_front_root(front_root)
    warm = warmup_start(start, days=20)
    codes_list = sorted(set(codes))
    out: dict[str, pd.DataFrame] = {}

    def _one(code: str) -> tuple[str, Optional[pd.DataFrame]]:
        return code, _read_one_daily(code, root, warm, end)

    n = max(1, int(workers))
    with ThreadPoolExecutor(max_workers=n) as pool:
        for code, df in pool.map(_one, codes_list):
            if df is not None and not df.empty:
                out[code] = df
    return out


@dataclass(frozen=True)
class Instance:
    """One pool-row appearance = one independent lot."""

    symbol: str
    name: str
    list_date: str
    buy_price: float
    opened: bool
    skip_reason: Optional[str] = None  # no_bar | limit_up | unknown_board | shares_zero


def _bar_close_map(df: pd.DataFrame) -> dict[str, float]:
    return {date_to_ymd(idx): float(close) for idx, close in zip(df.index, df["close"])}


def _prev_close_on(df: pd.DataFrame, ymd: str) -> Optional[float]:
    """Previous bar close (cross-suspension): prior row in the series, not calendar-1."""
    closes = _bar_close_map(df)
    if ymd not in closes:
        return None
    ordered = sorted(closes)
    i = ordered.index(ymd)
    if i == 0:
        return None
    return closes[ordered[i - 1]]


def _lot_shares(buy_price: float) -> int:
    if buy_price <= 0:
        return 0
    return int(LOT_NOTIONAL // buy_price // 100) * 100


def _is_limit_up(
    close: float,
    prev_close: float,
    code: str,
    name: str,
    *,
    tol: float = DEFAULT_TOL,
) -> bool:
    lp = limit_pct(code, name)
    if lp is None:
        return False  # caller handles unknown_board separately
    pct = close / prev_close - 1.0
    return pct >= lp - tol


def _is_limit_down(
    close: float,
    prev_close: float,
    code: str,
    name: str,
    *,
    tol: float = DEFAULT_TOL,
) -> bool:
    lp = limit_pct(code, name)
    if lp is None:
        return False
    pct = close / prev_close - 1.0
    return pct <= -(lp - tol)


def iterate_pool_entries(
    pool_dir: Path,
    sessions: Sequence[str],
) -> list[tuple[str, str, str]]:
    """Yield (symbol, name, list_ymd) for each pool file that exists.

    Missing session files (e.g. 20260525 / 20260605) = no list that day: skip, no error.
    """
    root = Path(pool_dir)
    rows: list[tuple[str, str, str]] = []
    for ymd in sessions:
        path = root / f"{ymd}.csv"
        if not path.is_file():
            continue
        for symbol, name in parse_pool_csv_entries(path):
            rows.append((symbol, name, ymd))
    return rows


def assemble_instances(
    pool_dir: Path,
    sessions: Sequence[str],
    bars: Mapping[str, pd.DataFrame],
    *,
    tol: float = DEFAULT_TOL,
) -> list[Instance]:
    """Build the Mode A instance table (opened + skipped).

    Buy filter (Q5/Q6): no K on list day → skip; close limit-up (±tol) → skip no chase;
    unknown board → skip; shares round-down to 0 → skip.
    Buy price = list-day front close. prev_close = prior bar in series (cross halt).
    """
    out: list[Instance] = []
    for symbol, name, ymd in iterate_pool_entries(pool_dir, sessions):
        df = bars.get(symbol)
        if df is None or df.empty:
            out.append(Instance(symbol, name, ymd, 0.0, False, "no_bar"))
            continue
        closes = _bar_close_map(df)
        if ymd not in closes:
            out.append(Instance(symbol, name, ymd, 0.0, False, "no_bar"))
            continue
        buy_price = closes[ymd]
        lp = limit_pct(symbol, name)
        if lp is None:
            out.append(Instance(symbol, name, ymd, buy_price, False, "unknown_board"))
            continue
        prev = _prev_close_on(df, ymd)
        if prev is None or prev <= 0:
            # No prior bar to judge limit-up — still allow buy (first bar in series).
            prev = None
        if prev is not None and _is_limit_up(buy_price, prev, symbol, name, tol=tol):
            out.append(Instance(symbol, name, ymd, buy_price, False, "limit_up"))
            continue
        if _lot_shares(buy_price) < 100:
            out.append(Instance(symbol, name, ymd, buy_price, False, "shares_zero"))
            continue
        out.append(Instance(symbol, name, ymd, buy_price, True, None))
    return out


def opened_instances(instances: Sequence[Instance]) -> list[Instance]:
    return [inst for inst in instances if inst.opened]



def instance_key(inst: Instance) -> str:
    return f"{inst.symbol}|{inst.list_date}"


# ---------------------------------------------------------------------------
# Slice B — exit evaluator (instance × strategy matrix)
# ---------------------------------------------------------------------------

RULE1_NS = (1, 2, 3, 5, 8, 10, 15, 20)
RULE2_XS = (2.0, 3.0, 5.0, 7.0, 10.0, 15.0, None)  # None = no take-profit
RULE2_YS = (2.0, 3.0, 5.0, 7.0, 10.0, None)  # None = no stop-loss
RULE2_NS = (1, 3, 5, 8, 10, 15)
RULE3_YS = (3.0, 5.0, 8.0, 10.0, 15.0)
RULE3_NS = (5, 10, 15, 20)


@dataclass(frozen=True)
class StrategySpec:
    """One grid cell. ``x``/``y`` are percent points (2.0 = 2%); None = unset.

    ``n`` is max hold in market sessions after buy (Q32). ``n is None`` = hold
    to window end (anchor ①, no TP/SL).
    """

    rule: int  # 1 | 2 | 3 | 0 (anchor hold-to-end)
    n: Optional[int]
    x: Optional[float] = None
    y: Optional[float] = None

    def label(self) -> str:
        def _fmt(v: Optional[float]) -> str:
            if v is None:
                return "inf"
            if float(v).is_integer():
                return str(int(v))
            return str(v).replace(".", "p")

        if self.rule == 0:
            return "anchor_hold_end"
        if self.rule == 1:
            return f"r1_n{self.n}"
        if self.rule == 2:
            return f"r2_x{_fmt(self.x)}_y{_fmt(self.y)}_n{self.n}"
        if self.rule == 3:
            return f"r3_y{_fmt(self.y)}_n{self.n}"
        raise ValueError(f"unknown rule {self.rule}")


def iter_grid(*, include_anchor_hold_end: bool = False) -> list[StrategySpec]:
    """Full Mode A grid: 8 + 252 + 20 = 280 (+ optional hold-to-end anchor)."""
    specs: list[StrategySpec] = []
    if include_anchor_hold_end:
        specs.append(StrategySpec(rule=0, n=None, x=None, y=None))
    for n in RULE1_NS:
        specs.append(StrategySpec(rule=1, n=n))
    for x in RULE2_XS:
        for y in RULE2_YS:
            for n in RULE2_NS:
                specs.append(StrategySpec(rule=2, n=n, x=x, y=y))
    for y in RULE3_YS:
        for n in RULE3_NS:
            specs.append(StrategySpec(rule=3, n=n, y=y))
    return specs


@dataclass(frozen=True)
class ExitResult:
    sell_date: str  # trade date or mark date
    sell_price: float
    reason: str  # n_expire | take_profit | stop_loss | trailing | mark_end
    return_pct: float
    pnl: float
    shares: int
    hold_sessions: int  # market sessions buy→sell/mark (Q32)
    is_trade: bool


def _price_return(buy_price: float, sell_price: float, *, is_trade: bool) -> tuple[int, float, float]:
    shares = _lot_shares(buy_price)
    buy_cost = shares * buy_price * (1.0 + COMMISSION)
    if is_trade:
        proceeds = shares * sell_price * (1.0 - COMMISSION)
    else:
        proceeds = shares * sell_price  # mark-to-market, no sell fill
    pnl = proceeds - buy_cost
    ret = pnl / buy_cost if buy_cost else 0.0
    return shares, pnl, ret


def _session_index(sessions: Sequence[str], ymd: str) -> int:
    try:
        return list(sessions).index(ymd)
    except ValueError as exc:
        raise ValueError(f"list_date {ymd} not in session calendar") from exc


def evaluate_exit(
    inst: Instance,
    spec: StrategySpec,
    bars: Mapping[str, pd.DataFrame],
    sessions: Sequence[str],
    *,
    end: str = DEFAULT_END,
    tol: float = DEFAULT_TOL,
) -> ExitResult:
    """Evaluate one (instance × strategy) exit on front daily closes.

    Semantics (proposal §2/§4, Q32):
    - T+1: buy day not sellable.
    - N counts market sessions after buy; expiry on a no-K day postpones to the
      first later session that has a bar.
    - Limit-down close: do not sell; re-check next session.
    - Halt / no K: freeze (no trigger, peak frozen, N still advances).
    - Rule 3: peak = max(buy_price, closes incl. buy day); buy day peak-only;
      sellable day updates peak then tests close < peak×(1−Y%).
    - Window end / early bar stop: mark last available close, no trade (Q12/Q33).
    """
    if not inst.opened:
        raise ValueError("evaluate_exit requires an opened instance")
    df = bars.get(inst.symbol)
    if df is None or df.empty:
        raise ValueError(f"missing bars for {inst.symbol}")

    close_by = _bar_close_map(df)
    ordered_bars = sorted(close_by)
    prev_by: dict[str, float] = {}
    for i, y in enumerate(ordered_bars):
        if i > 0:
            prev_by[y] = close_by[ordered_bars[i - 1]]

    buy_i = _session_index(sessions, inst.list_date)
    end_i = _session_index(sessions, end) if end in sessions else len(sessions) - 1
    # Peak seeds at buy price; buy-day close (usually equal) may lift it.
    peak = float(inst.buy_price)
    if inst.list_date in close_by:
        peak = max(peak, close_by[inst.list_date])

    def _try_finish(ymd: str, close: float, reason: str) -> Optional[ExitResult]:
        prev = prev_by.get(ymd)
        if prev is not None and prev > 0 and _is_limit_down(
            close, prev, inst.symbol, inst.name, tol=tol
        ):
            return None  # postpone
        sell_i = _session_index(sessions, ymd)
        shares, pnl, ret = _price_return(inst.buy_price, close, is_trade=True)
        return ExitResult(
            sell_date=ymd,
            sell_price=close,
            reason=reason,
            return_pct=ret,
            pnl=pnl,
            shares=shares,
            hold_sessions=sell_i - buy_i,
            is_trade=True,
        )

    for i in range(buy_i + 1, end_i + 1):
        ymd = sessions[i]
        market_held = i - buy_i  # 1 on first session after buy (= N=1 day)
        if ymd not in close_by:
            continue  # halt: freeze peak, N already advanced via market_held
        close = close_by[ymd]

        triggered = False
        reason = ""

        if spec.rule == 0:
            # Hold to end — never trigger inside the loop.
            pass
        elif spec.rule == 1:
            assert spec.n is not None
            if market_held >= spec.n:
                triggered, reason = True, "n_expire"
        elif spec.rule == 2:
            assert spec.n is not None
            if spec.x is not None and close >= inst.buy_price * (1.0 + spec.x / 100.0):
                triggered, reason = True, "take_profit"
            elif spec.y is not None and close <= inst.buy_price * (1.0 - spec.y / 100.0):
                triggered, reason = True, "stop_loss"
            elif market_held >= spec.n:
                triggered, reason = True, "n_expire"
        elif spec.rule == 3:
            assert spec.n is not None and spec.y is not None
            peak = max(peak, close)  # update then test
            if close < peak * (1.0 - spec.y / 100.0):
                triggered, reason = True, "trailing"
            elif market_held >= spec.n:
                triggered, reason = True, "n_expire"
        else:
            raise ValueError(f"unknown rule {spec.rule}")

        if triggered:
            done = _try_finish(ymd, close, reason)
            if done is not None:
                return done
            # limit-down postpone: keep looping

    # Mark at last available close on or before window end (Q12 / Q33).
    mark_ymd = None
    for y in reversed(sessions[: end_i + 1]):
        if y in close_by and y >= inst.list_date:
            mark_ymd = y
            break
    if mark_ymd is None:
        # Should not happen for opened instances (buy day had a bar).
        mark_ymd = inst.list_date
        mark_px = float(inst.buy_price)
    else:
        mark_px = close_by[mark_ymd]
    mark_i = _session_index(sessions, mark_ymd)
    shares, pnl, ret = _price_return(inst.buy_price, mark_px, is_trade=False)
    return ExitResult(
        sell_date=mark_ymd,
        sell_price=mark_px,
        reason="mark_end",
        return_pct=ret,
        pnl=pnl,
        shares=shares,
        hold_sessions=mark_i - buy_i,
        is_trade=False,
    )


def evaluate_matrix(
    instances: Sequence[Instance],
    specs: Sequence[StrategySpec],
    bars: Mapping[str, pd.DataFrame],
    sessions: Sequence[str],
    *,
    end: str = DEFAULT_END,
    tol: float = DEFAULT_TOL,
) -> dict[str, dict[str, ExitResult]]:
    """Return ``{strategy_label: {instance_key: ExitResult}}`` for opened lots."""
    opened = opened_instances(instances)
    out: dict[str, dict[str, ExitResult]] = {}
    for spec in specs:
        label = spec.label()
        bucket: dict[str, ExitResult] = {}
        for inst in opened:
            bucket[instance_key(inst)] = evaluate_exit(
                inst, spec, bars, sessions, end=end, tol=tol
            )
        out[label] = bucket
    return out

def main(argv: Optional[list[str]] = None) -> int:
    """CLI: Slice A prints assembly counts; B/C extend this entry."""
    import argparse
    import json

    ap = argparse.ArgumentParser(description="unified-exit Mode A (front daily grid)")
    ap.add_argument("--start", default=DEFAULT_START)
    ap.add_argument("--end", default=DEFAULT_END)
    ap.add_argument("--pool-dir", type=Path, default=Path("stock_pool"))
    ap.add_argument("--front-root", type=Path, default=None)
    ap.add_argument("--tol", type=float, default=DEFAULT_TOL)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument(
        "--out-dir",
        type=Path,
        default=Path("backtest_output/unified_exit_modea"),
    )
    ap.add_argument(
        "--stage",
        choices=("assemble", "all"),
        default="assemble",
        help="assemble = instances only (Slice A); all = full grid (Slices B/C)",
    )
    args = ap.parse_args(argv)

    sessions = load_session_calendar(args.start, args.end)
    pool_rows = iterate_pool_entries(args.pool_dir, sessions)
    codes = sorted({c for c, _n, _y in pool_rows})
    bars = load_front_bars(
        codes, args.start, args.end, front_root=args.front_root, workers=args.workers
    )
    instances = assemble_instances(args.pool_dir, sessions, bars, tol=args.tol)
    opened = opened_instances(instances)
    summary = {
        "stage": "assemble",
        "start": args.start,
        "end": args.end,
        "sessions": len(sessions),
        "pool_rows": len(pool_rows),
        "instances": len(instances),
        "opened": len(opened),
        "skipped": {
            reason: sum(1 for i in instances if i.skip_reason == reason)
            for reason in sorted({i.skip_reason for i in instances if i.skip_reason})
        },
    }
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "assemble_summary.json").write_text(
        json.dumps(summary, ensure_ascii=True, indent=1), encoding="utf-8"
    )
    print(
        f"[assemble] sessions={summary['sessions']} rows={summary['pool_rows']} "
        f"opened={summary['opened']} skipped={summary['skipped']}"
    )
    if args.stage != "assemble":
        print("[warn] stage=all requires Slices B/C; falling back to assemble-only")
    return 0
