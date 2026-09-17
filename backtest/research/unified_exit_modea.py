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
    return dict(zip(pd.DatetimeIndex(df.index).strftime("%Y%m%d"), map(float, df["close"])))


class _PreparedBars(dict[str, pd.DataFrame]):
    """Run-local price maps; source frames must stay unchanged during a run.

    No DataFrame attributes or global cache: a later run sees edited input bars.
    Lazy columns also preserve support for close-only frames in exit evaluation.
    """

    def __init__(self, bars: Mapping[str, pd.DataFrame]):
        super().__init__(bars)
        self.close_maps: dict[str, dict[str, float]] = {}
        self.prev_maps: dict[str, dict[str, float]] = {}
        self.open_maps: dict[str, dict[str, float]] = {}

    def closes(self, symbol: str) -> dict[str, float]:
        if symbol not in self.close_maps:
            self.close_maps[symbol] = _bar_close_map(self[symbol])
        return self.close_maps[symbol]

    def previous(self, symbol: str) -> dict[str, float]:
        if symbol not in self.prev_maps:
            closes = self.closes(symbol)
            ordered = sorted(closes)
            self.prev_maps[symbol] = {
                y: closes[prev] for prev, y in zip(ordered, ordered[1:])
            }
        return self.prev_maps[symbol]

    def opens(self, symbol: str) -> dict[str, float]:
        if symbol not in self.open_maps:
            df = self[symbol]
            self.open_maps[symbol] = dict(
                zip(pd.DatetimeIndex(df.index).strftime("%Y%m%d"), map(float, df["open"]))
            )
        return self.open_maps[symbol]


def _prepare_bars(bars: Mapping[str, pd.DataFrame]) -> _PreparedBars:
    return bars if isinstance(bars, _PreparedBars) else _PreparedBars(bars)


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
    bars = _prepare_bars(bars)
    out: list[Instance] = []
    for symbol, name, ymd in iterate_pool_entries(pool_dir, sessions):
        df = bars.get(symbol)
        if df is None or df.empty:
            out.append(Instance(symbol, name, ymd, 0.0, False, "no_bar"))
            continue
        closes = bars.closes(symbol)
        if ymd not in closes:
            out.append(Instance(symbol, name, ymd, 0.0, False, "no_bar"))
            continue
        buy_price = closes[ymd]
        lp = limit_pct(symbol, name)
        if lp is None:
            out.append(Instance(symbol, name, ymd, buy_price, False, "unknown_board"))
            continue
        prev = bars.previous(symbol).get(ymd)
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

    rule: int  # 1 | 2 | 3 | 0 (anchor) | 4 (Mode B Livermore path, unused by A)
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
        if self.rule == 4:
            if self.x is None:
                return f"livermore_l2_stale{self.n}_y{_fmt(self.y)}"
            return f"livermore_l1_x{_fmt(self.x)}_stale{self.n}_y{_fmt(self.y)}"
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

    bars = _prepare_bars(bars)
    close_by = bars.closes(inst.symbol)
    prev_by = bars.previous(inst.symbol)

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
    bars = _prepare_bars(bars)
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


# ---------------------------------------------------------------------------
# Slice C — aggregation, anchors, robustness, reports
# ---------------------------------------------------------------------------

@dataclass
class StrategyMetrics:
    label: str
    n_instances: int
    total_return: float
    annualized: float
    max_drawdown: float
    win_rate: float
    profit_factor: Optional[float]
    avg_hold_sessions: float
    mean_return_pct: float
    median_return_pct: float
    total_pnl: float
    peak_concurrent_capital: float
    peak_concurrent_lots: int


def _annualize(total_return: float) -> float:
    return (1.0 + total_return) ** (365.0 / float(WINDOW_CALENDAR_DAYS)) - 1.0


def _profit_factor(pnls: Sequence[float]) -> Optional[float]:
    gains = sum(p for p in pnls if p > 0)
    losses = sum(p for p in pnls if p < 0)
    if losses == 0:
        return None if gains == 0 else float("inf")
    return gains / abs(losses)


def _last_close_on_or_before(
    close_by: Mapping[str, float], ymd: str, sessions: Sequence[str]
) -> Optional[float]:
    if ymd in close_by:
        return close_by[ymd]
    for y in reversed(list(sessions)):
        if y <= ymd and y in close_by:
            return close_by[y]
    return None


def build_daily_equity(
    instances: Sequence[Instance],
    exits: Mapping[str, ExitResult],
    bars: Mapping[str, pd.DataFrame],
    sessions: Sequence[str],
    *,
    cash_pool: float = CASH_POOL,
) -> tuple[list[dict], int, float]:
    """Replay sells-then-buys; return (equity_rows, peak_lots, peak_capital).

    Mark-to-market uses each symbol's last available close on/before the day.

    Q33 ``mark_end_zero`` lots stay unsold (``is_trade=False``) but contribute
    **0** to MTM so total_return / max_drawdown move vs hold-to-end.
    """
    opened = opened_instances(instances)
    by_key = {instance_key(i): i for i in opened}
    buys_on: dict[str, list[Instance]] = {}
    for inst in opened:
        buys_on.setdefault(inst.list_date, []).append(inst)
    sells_on: dict[str, list[tuple[Instance, ExitResult]]] = {}
    for key, er in exits.items():
        if not er.is_trade:
            continue
        inst = by_key[key]
        sells_on.setdefault(er.sell_date, []).append((inst, er))

    bars = _prepare_bars(bars)
    close_maps = {sym: bars.closes(sym) for sym in bars}
    cash = float(cash_pool)
    # key -> shares
    held: dict[str, int] = {}
    equity_rows: list[dict] = []
    peak_lots = 0
    peak_cap = 0.0

    for ymd in sessions:
        for inst, er in sells_on.get(ymd, []):
            key = instance_key(inst)
            if key not in held:
                continue
            cash += er.shares * er.sell_price * (1.0 - COMMISSION)
            del held[key]
        for inst in buys_on.get(ymd, []):
            key = instance_key(inst)
            er = exits[key]
            cash -= er.shares * inst.buy_price * (1.0 + COMMISSION)
            held[key] = er.shares
        mtm = 0.0
        for key, shares in held.items():
            er = exits.get(key)
            # Q33 sensitivity: frozen lot valued at 0 (no sell fill / commission).
            if er is not None and er.reason == "mark_end_zero":
                continue
            inst = by_key[key]
            px = _last_close_on_or_before(
                close_maps.get(inst.symbol, {}), ymd, sessions
            )
            if px is None:
                px = inst.buy_price
            mtm += shares * px
        equity = cash + mtm
        lots = len(held)
        cap = lots * LOT_NOTIONAL
        if lots > peak_lots:
            peak_lots = lots
        if cap > peak_cap:
            peak_cap = cap
        equity_rows.append(
            {"date": ymd, "equity": equity, "cash": cash, "lots": lots, "mtm": mtm}
        )
    return equity_rows, peak_lots, peak_cap


def _max_drawdown(equity_rows: Sequence[Mapping]) -> float:
    peak = None
    max_dd = 0.0
    for row in equity_rows:
        eq = float(row["equity"])
        peak = eq if peak is None else max(peak, eq)
        if peak > 0:
            dd = (peak - eq) / peak
            if dd > max_dd:
                max_dd = dd
    return max_dd


def aggregate_strategy(
    label: str,
    instances: Sequence[Instance],
    exits: Mapping[str, ExitResult],
    bars: Mapping[str, pd.DataFrame],
    sessions: Sequence[str],
    *,
    cash_pool: float = CASH_POOL,
) -> StrategyMetrics:
    opened = opened_instances(instances)
    rets = [exits[instance_key(i)].return_pct for i in opened]
    pnls = [exits[instance_key(i)].pnl for i in opened]
    holds = [exits[instance_key(i)].hold_sessions for i in opened]
    equity_rows, peak_lots, peak_cap = build_daily_equity(
        opened, exits, bars, sessions, cash_pool=cash_pool
    )
    final_eq = float(equity_rows[-1]["equity"]) if equity_rows else cash_pool
    total_return = (final_eq - cash_pool) / cash_pool
    wins = sum(1 for r in rets if r > 0)
    n = len(opened)
    return StrategyMetrics(
        label=label,
        n_instances=n,
        total_return=total_return,
        annualized=_annualize(total_return),
        max_drawdown=_max_drawdown(equity_rows),
        win_rate=(wins / n) if n else 0.0,
        profit_factor=_profit_factor(pnls),
        avg_hold_sessions=(sum(holds) / n) if n else 0.0,
        mean_return_pct=(sum(rets) / n) if n else 0.0,
        median_return_pct=float(sorted(rets)[n // 2]) if n else 0.0,
        total_pnl=sum(pnls),
        peak_concurrent_capital=peak_cap,
        peak_concurrent_lots=peak_lots,
    )


def rank_strategies(metrics: Sequence[StrategyMetrics]) -> list[StrategyMetrics]:
    return sorted(metrics, key=lambda m: m.total_return, reverse=True)


def oracle_exits(
    instances: Sequence[Instance],
    bars: Mapping[str, pd.DataFrame],
    sessions: Sequence[str],
    *,
    end: str = DEFAULT_END,
    tol: float = DEFAULT_TOL,
) -> dict[str, ExitResult]:
    """Per-instance best T+1..end close excluding limit-down days (non-tradable)."""
    bars = _prepare_bars(bars)
    out: dict[str, ExitResult] = {}
    for inst in opened_instances(instances):
        close_by = bars.closes(inst.symbol)
        prev_by = bars.previous(inst.symbol)
        buy_i = _session_index(sessions, inst.list_date)
        end_i = _session_index(sessions, end) if end in sessions else len(sessions) - 1
        best: Optional[ExitResult] = None
        for i in range(buy_i + 1, end_i + 1):
            ymd = sessions[i]
            if ymd not in close_by:
                continue
            close = close_by[ymd]
            prev = prev_by.get(ymd)
            if prev is not None and prev > 0 and _is_limit_down(
                close, prev, inst.symbol, inst.name, tol=tol
            ):
                continue
            shares, pnl, ret = _price_return(inst.buy_price, close, is_trade=True)
            cand = ExitResult(
                sell_date=ymd,
                sell_price=close,
                reason="oracle",
                return_pct=ret,
                pnl=pnl,
                shares=shares,
                hold_sessions=i - buy_i,
                is_trade=True,
            )
            if best is None or cand.return_pct > best.return_pct:
                best = cand
        if best is None:
            # Fall back to mark_end path via hold-to-end evaluator
            best = evaluate_exit(
                inst, StrategySpec(0, None), bars, sessions, end=end, tol=tol
            )
        out[instance_key(inst)] = best
    return out


def delisting_zero_exits(
    instances: Sequence[Instance],
    exits: Mapping[str, ExitResult],
    sessions: Sequence[str],
    *,
    end: str = DEFAULT_END,
) -> dict[str, ExitResult]:
    """Q33 sensitivity: early-stop mark_end lots valued at 0 (full buy-cost loss)."""
    out = dict(exits)
    for inst in opened_instances(instances):
        key = instance_key(inst)
        er = exits[key]
        if er.reason == "mark_end" and er.sell_date < end:
            shares = er.shares
            buy_cost = shares * inst.buy_price * (1.0 + COMMISSION)
            out[key] = ExitResult(
                sell_date=er.sell_date,
                sell_price=0.0,
                reason="mark_end_zero",
                return_pct=-1.0,
                pnl=-buy_cost,
                shares=shares,
                hold_sessions=er.hold_sessions,
                is_trade=False,
            )
    return out


def next_open_buy_instances(
    instances: Sequence[Instance],
    bars: Mapping[str, pd.DataFrame],
    sessions: Sequence[str],
) -> list[Instance]:
    """Q34④: replace buy_price with next session open; shift list_date to that day."""
    bars = _prepare_bars(bars)
    out: list[Instance] = []
    for inst in instances:
        if not inst.opened:
            out.append(inst)
            continue
        df = bars.get(inst.symbol)
        if df is None:
            out.append(Instance(inst.symbol, inst.name, inst.list_date, 0.0, False, "no_bar"))
            continue
        open_by = bars.opens(inst.symbol)
        buy_i = _session_index(sessions, inst.list_date)
        shifted = None
        for ymd in sessions[buy_i + 1 :]:
            if ymd in open_by and open_by[ymd] > 0:
                shifted = ymd
                break
        if shifted is None:
            out.append(
                Instance(inst.symbol, inst.name, inst.list_date, 0.0, False, "no_bar")
            )
            continue
        px = open_by[shifted]
        if _lot_shares(px) < 100:
            out.append(
                Instance(inst.symbol, inst.name, shifted, px, False, "shares_zero")
            )
            continue
        out.append(Instance(inst.symbol, inst.name, shifted, px, True, None))
    return out


def board_bucket(code: str) -> str:
    """Q34③ board strata: main / chinext / star / bse (prefix, not limit %)."""
    from backtest.research.market_layer import board_limit_pct

    num = code.split(".", 1)[0]
    if num.startswith(("300", "301", "302")):
        return "chinext"
    if num.startswith(("688", "689")):
        return "star"
    lp = board_limit_pct(code)
    if lp == 0.10:
        return "main"
    if lp == 0.30:
        return "bse"
    return "unknown"


def half_window_split(
    start: str = DEFAULT_START, end: str = DEFAULT_END
) -> tuple[str, str, str, str]:
    """Return (h1_start, h1_end, h2_start, h2_end) per Q34 locked dates."""
    return "20251023", "20260404", "20260407", "20260909"


def filter_instances_by_list_date(
    instances: Sequence[Instance], start: str, end: str
) -> list[Instance]:
    return [i for i in instances if start <= i.list_date <= end]


def neighborhood_plateau_flags(
    ranked: Sequence[StrategyMetrics], *, top_n: int = 20
) -> list[dict]:
    """Flag rule-2/3 top cells far above their ranked neighbor family."""
    rows = []
    for m in ranked[:top_n]:
        if not m.label.startswith(("r2_", "r3_")):
            continue
        # r2_x{X}_y{Y}_n{N} or r3_y{Y}_n{N}; r1 remains excluded.
        parts = m.label.split("_")
        try:
            if parts[0] == "r2":
                x_s, y_s, n_s = parts[1][1:], parts[2][1:], parts[3][1:]
            else:
                x_s, y_s, n_s = "inf", parts[1][1:], parts[2][1:]
            x = None if x_s == "inf" else float(x_s.replace("p", "."))
            y = None if y_s == "inf" else float(y_s.replace("p", "."))
            n = int(n_s)
        except (IndexError, ValueError):
            continue
        # Collect ranked labels sharing the same N or nearby x/y family.
        # Use endswith for N so "_n1" does not match "_n10" / "_n15".
        family = [
            o for o in ranked
            if o.label.startswith(parts[0] + "_") and o.label != m.label
            and (
                o.label.endswith(f"_n{n}")
                or (x is not None and f"_x{_fmt_grid(x)}_" in o.label)
                or (y is not None and f"_y{_fmt_grid(y)}_" in o.label)
            )
        ][:8]
        if not family:
            rows.append({"label": m.label, "island": False, "neighbor_gap": 0.0})
            continue
        best_nb = max(o.total_return for o in family)
        gap = m.total_return - best_nb
        rows.append(
            {
                "label": m.label,
                "island": gap > 0.01,  # >1pp vs best scanned neighbor family
                "neighbor_gap": gap,
            }
        )
    return rows


def _fmt_grid(v: float) -> str:
    if float(v).is_integer():
        return str(int(v))
    return str(v).replace(".", "p")


def stratify_mean_returns(
    instances: Sequence[Instance],
    exits: Mapping[str, ExitResult],
    *,
    by: str = "board",
) -> dict[str, float]:
    buckets: dict[str, list[float]] = {}
    for inst in opened_instances(instances):
        er = exits[instance_key(inst)]
        if by == "board":
            key = board_bucket(inst.symbol)
        elif by == "month":
            key = inst.list_date[:6]
        else:
            raise ValueError(by)
        buckets.setdefault(key, []).append(er.return_pct)
    return {k: (sum(v) / len(v) if v else 0.0) for k, v in sorted(buckets.items())}


def metrics_to_row(m: StrategyMetrics) -> dict:
    pf = m.profit_factor
    return {
        "label": m.label,
        "n_instances": m.n_instances,
        "total_return": m.total_return,
        "annualized": m.annualized,
        "max_drawdown": m.max_drawdown,
        "win_rate": m.win_rate,
        "profit_factor": (None if pf is None else (None if pf == float("inf") else pf)),
        "profit_factor_inf": pf == float("inf"),
        "avg_hold_sessions": m.avg_hold_sessions,
        "mean_return_pct": m.mean_return_pct,
        "median_return_pct": m.median_return_pct,
        "total_pnl": m.total_pnl,
        "peak_concurrent_capital": m.peak_concurrent_capital,
        "peak_concurrent_lots": m.peak_concurrent_lots,
    }


def write_reports(
    out_dir: Path,
    ranked: Sequence[StrategyMetrics],
    matrix: Mapping[str, Mapping[str, ExitResult]],
    instances: Sequence[Instance],
    anchors: Mapping[str, StrategyMetrics],
    robustness: Mapping[str, object],
    *,
    meta: Optional[dict] = None,
) -> None:
    import csv
    import json

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    rank_path = out_dir / "ranking.csv"
    with rank_path.open("w", encoding="utf-8", newline="") as fh:
        rows = [metrics_to_row(m) for m in ranked]
        if rows:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)

    # Instance detail for top label + anchors (compact)
    detail_path = out_dir / "instance_detail_top.csv"
    top_label = ranked[0].label if ranked else None
    with detail_path.open("w", encoding="utf-8", newline="") as fh:
        fields = [
            "strategy",
            "instance_key",
            "symbol",
            "list_date",
            "buy_price",
            "sell_date",
            "sell_price",
            "reason",
            "return_pct",
            "pnl",
            "shares",
            "hold_sessions",
            "is_trade",
        ]
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        labels_to_dump = []
        if top_label:
            labels_to_dump.append(top_label)
        for a in ("anchor_hold_end", "r1_n1", "oracle", "delist_zero"):
            if a in matrix:
                labels_to_dump.append(a)
        by_key = {instance_key(i): i for i in opened_instances(instances)}
        for lab in labels_to_dump:
            for key, er in matrix.get(lab, {}).items():
                inst = by_key[key]
                w.writerow(
                    {
                        "strategy": lab,
                        "instance_key": key,
                        "symbol": inst.symbol,
                        "list_date": inst.list_date,
                        "buy_price": inst.buy_price,
                        "sell_date": er.sell_date,
                        "sell_price": er.sell_price,
                        "reason": er.reason,
                        "return_pct": er.return_pct,
                        "pnl": er.pnl,
                        "shares": er.shares,
                        "hold_sessions": er.hold_sessions,
                        "is_trade": er.is_trade,
                    }
                )

    summary = {
        "meta": meta or {},
        "top20": [metrics_to_row(m) for m in ranked[:20]],
        "anchors": {k: metrics_to_row(v) for k, v in anchors.items()},
        "robustness": robustness,
        "n_strategies": len(ranked),
        "n_opened": len(opened_instances(instances)),
    }
    (out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=True, indent=1, default=str),
        encoding="utf-8",
    )


def run_modea(
    pool_dir: Path,
    *,
    start: str = DEFAULT_START,
    end: str = DEFAULT_END,
    front_root: Optional[Path] = None,
    sessions: Optional[Sequence[str]] = None,
    bars: Optional[Mapping[str, pd.DataFrame]] = None,
    tol: float = DEFAULT_TOL,
    workers: int = 8,
    out_dir: Path = Path("backtest_output/unified_exit_modea"),
    cash_pool: float = CASH_POOL,
) -> dict:
    """Full Mode A pipeline: assemble → matrix → aggregate → reports."""
    sess = load_session_calendar(start, end, sessions=sessions)
    pool_rows = iterate_pool_entries(Path(pool_dir), sess)
    codes = sorted({c for c, _n, _y in pool_rows})
    bar_map = load_front_bars(
        codes, start, end, front_root=front_root, workers=workers, bars=bars
    )
    bar_map = _prepare_bars(bar_map)
    instances = assemble_instances(Path(pool_dir), sess, bar_map, tol=tol)
    specs = iter_grid(include_anchor_hold_end=True)
    matrix = evaluate_matrix(instances, specs, bar_map, sess, end=end, tol=tol)

    # Oracle + delist sensitivity overlays
    matrix["oracle"] = oracle_exits(instances, bar_map, sess, end=end, tol=tol)
    hold_label = "anchor_hold_end"
    matrix["delist_zero"] = delisting_zero_exits(
        instances, matrix[hold_label], sess, end=end
    )

    metrics = [
        aggregate_strategy(lab, instances, exits, bar_map, sess, cash_pool=cash_pool)
        for lab, exits in matrix.items()
        if lab not in ("oracle", "delist_zero", "anchor_hold_end")
    ]
    ranked = rank_strategies(metrics)
    anchors = {
        "anchor_hold_end": aggregate_strategy(
            hold_label, instances, matrix[hold_label], bar_map, sess, cash_pool=cash_pool
        ),
        "r1_n1": next(m for m in ranked if m.label == "r1_n1"),
        "oracle": aggregate_strategy(
            "oracle", instances, matrix["oracle"], bar_map, sess, cash_pool=cash_pool
        ),
        "delist_zero": aggregate_strategy(
            "delist_zero",
            instances,
            matrix["delist_zero"],
            bar_map,
            sess,
            cash_pool=cash_pool,
        ),
    }

    # Robustness ① half windows
    h1s, h1e, h2s, h2e = half_window_split(start, end)
    robustness: dict = {"half_windows": {}, "board": {}, "month": {}, "plateau": []}
    for tag, s0, s1 in (("h1", h1s, h1e), ("h2", h2s, h2e)):
        sub = filter_instances_by_list_date(instances, s0, s1)
        # Re-aggregate existing exits on the subset (same sell paths)
        sub_metrics = []
        # Full 280 labels (excl. anchors) so half-window top20 is not truncated
        # by full-window ranked[:50] (Q34①).
        half_labs = [
            lab
            for lab in matrix
            if lab not in ("oracle", "delist_zero", "anchor_hold_end")
        ]
        for lab in half_labs:
            sub_exits = {
                instance_key(i): matrix[lab][instance_key(i)]
                for i in opened_instances(sub)
                if instance_key(i) in matrix[lab]
            }
            if not sub_exits:
                continue
            # Equity curve on full sessions but only subset instances
            sub_metrics.append(
                aggregate_strategy(lab, sub, sub_exits, bar_map, sess, cash_pool=cash_pool)
            )
        robustness["half_windows"][tag] = [
            metrics_to_row(x) for x in rank_strategies(sub_metrics)[:20]
        ]

    # top20 name consistency
    h1_labs = [r["label"] for r in robustness["half_windows"].get("h1", [])]
    h2_labs = [r["label"] for r in robustness["half_windows"].get("h2", [])]
    robustness["half_windows"]["top20_overlap"] = len(set(h1_labs) & set(h2_labs))

    # ② plateau
    robustness["plateau"] = neighborhood_plateau_flags(ranked, top_n=20)

    # ③ board / month on best label
    if ranked:
        best = ranked[0].label
        robustness["board"] = stratify_mean_returns(instances, matrix[best], by="board")
        robustness["month"] = stratify_mean_returns(instances, matrix[best], by="month")

    # ④ next-open buy sensitivity (rebuild matrix for top specs + r1_n1 only — cost control)
    sens_inst = next_open_buy_instances(instances, bar_map, sess)
    sens_specs = [s for s in specs if s.label() in {m.label for m in ranked[:5]} or s.label() == "r1_n1"]
    if not sens_specs:
        sens_specs = [StrategySpec(1, 1)]
    sens_matrix = evaluate_matrix(sens_inst, sens_specs, bar_map, sess, end=end, tol=tol)
    robustness["next_open_buy"] = [
        metrics_to_row(
            aggregate_strategy(lab, sens_inst, ex, bar_map, sess, cash_pool=cash_pool)
        )
        for lab, ex in sens_matrix.items()
    ]

    write_reports(
        out_dir,
        ranked,
        matrix,
        instances,
        anchors,
        robustness,
        meta={"start": start, "end": end, "cash_pool": cash_pool, "tol": tol},
    )
    return {
        "ranked": ranked,
        "anchors": anchors,
        "robustness": robustness,
        "instances": instances,
        "matrix": matrix,
        "sessions": sess,
    }


def main(argv: Optional[list[str]] = None) -> int:
    """CLI: assemble-only or full Mode A grid (Slices A/B/C)."""
    import argparse
    import json

    ap = argparse.ArgumentParser(
        description="统一卖出规则网格 · 模式 A（前复权日线；名义现金池 11 亿）"
    )
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
        default="all",
        help="assemble = instances only; all = grid + reports",
    )
    args = ap.parse_args(argv)

    if args.stage == "assemble":
        sessions = load_session_calendar(args.start, args.end)
        pool_rows = iterate_pool_entries(args.pool_dir, sessions)
        codes = sorted({c for c, _n, _y in pool_rows})
        bars = load_front_bars(
            codes,
            args.start,
            args.end,
            front_root=args.front_root,
            workers=args.workers,
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
        return 0

    result = run_modea(
        args.pool_dir,
        start=args.start,
        end=args.end,
        front_root=args.front_root,
        tol=args.tol,
        workers=args.workers,
        out_dir=args.out_dir,
    )
    top = result["ranked"][:5]
    print(
        f"[modea] opened={len(opened_instances(result['instances']))} "
        f"strategies={len(result['ranked'])} out={args.out_dir}"
    )
    for i, m in enumerate(top, 1):
        print(
            f"  #{i} {m.label} total_return={m.total_return:.4%} "
            f"mean_ret={m.mean_return_pct:.4%} peak_lots={m.peak_concurrent_lots}"
        )
    return 0
