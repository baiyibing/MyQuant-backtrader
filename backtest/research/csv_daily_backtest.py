#!/usr/bin/env python3
"""CSV 模式日线近似回测（策略 6 / 策略 8 共用向量化引擎）。

完整滚动投资流程（分钟 Cerebro 链）的日线近似版：同口径的 CSV 每日买入名单、
每日 100 万常规额度、补充资金、T+1、涨跌停拦截、全局 2100 万资金池。默认策略 6
卖点；`--strategy version8` 只换金榕元卖点（见 HELP_LOCK）。数据用不复权日线
（与分钟链 adjust_type='none' 对齐）；佣金 0.1% 双边（与 broker.setcommission
(0.001) 对齐），无最低佣金。

用法：
    python backtest/research/csv_daily_backtest.py --start 20251023 --end 20260909
    python backtest/research/csv_daily_backtest.py --strategy version8 --start 20251023 --end 20260909
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import pyarrow.compute as pc
import pyarrow.parquet as pq

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, REPO)

from backtest.research.ma_chip_edge_backtest import limit_pct  # noqa: E402
from common.infra.data_root import resolve_period_root  # noqa: E402
from common.infra.qmt_utils_adv import batch_format_stock_codes  # noqa: E402
from oskh_data.symbol_format import to_partition_key  # noqa: E402

DEFAULT_TOTAL_CASH = 21_000_000.0
DEFAULT_DAILY_QUOTA = 1_000_000.0
COMMISSION = 0.001  # 双边，与分钟链 cerebro.broker.setcommission(commission=0.001) 对齐
STOP_PCT = 0.06
PROFIT_BASE = 0.01
TIERS = {1: 0.30, 2: 0.40, 3: 0.50, 4: 0.60}
TIER_DEFAULT = 0.70
POS_TRAIL = 0.50  # 已停用：策略6不再做未过锚的正利润回撤
PEAK_GAP_MIN = 15  # 止盈与最高价间隔不能 < 15 分钟（分钟引擎执行；=15 允许）
CHASE_HM = 9 * 60 + 45  # 尾盘涨停后次日 09:45 追买/弃买
LIMIT_EPS = 0.001  # 涨跌停等值判定；须远小于 1 分，避免把普通价误判为涨停
WARMUP_DAYS = 10
# 2026-09-11 实测：F 盘 period=1m 最后一根交易日（抽样 50 只含 000001，无 20260910）。
MINUTE_LAKE_END = "20260909"
_PERIOD_ENV_KEYS = (
    "OSKH_PERIOD_1D_ROOT",
    "OSKH_PERIOD_1M_ROOT",
    "OSKH_INDEX_DAILY_ROOT",
    "OSKH_ETF_DAILY_ROOT",
    "OSKH_SOURCE_PARQUET_ROOT",
)

HELP_LOCK = """
日线近似口径（相对分钟保真版的唯一失真来源）：
  买入：池 CSV 当日候选、收盘价成交（分钟版 14:55≈收盘）；买价达到或超过
        涨停价 → 当日不买，记下该票额度，次日按追买规则处理。已持有则跳过。
        常规额度按当日池 CSV 全部名单均分（含随后被跳过的票）。
  止损：D+1 起，触发价 = 买入价×(1-stop)。开盘 ≤ 触发价 → 开盘价成交（跳空）；
        否则日内 low 触价 → 触发价成交。卖出日开盘跌停 → 顺延下一交易日。
  止盈：基础锚 +1%。仅当峰值超过买入价×1.01 后评估
        （开盘 < 锚则先观察，涨过锚再按档；开盘 ≥ 锚则当日起按档）。
        公式 (市价/买价-1.01)/(峰值/买价-1.01) ≤
        T+1=0.3 / T+2=0.4 / T+3=0.5 / T+4=0.6 / T+5+=0.7。
        触发价 < 买入价不止盈。未过 +1% 锚不止盈。收盘评估、次日开盘离场
        （隔夜间隔已 ≥ 15 分钟）。
  峰值：从 T+1 起用当日 high 更新；T+0 固定为买入价。T+0 不评估止盈。
  买侧：尾盘涨停不买。T+1 用收盘>开盘近似分钟 09:45 市价>开盘 → 收盘追买；
        否则弃买。只给一次机会，不再延期。成交价用收盘（相对 09:45 的失真）。
  资金：2100 万全局池；每日 100 万常规额度；不足 100 股用补充资金补足
        （force_min，自主池、不占额度）；佣金 0.1% 双边无最低。
  T+1：买入日不可卖；期末持仓按最后收盘估值（eod_mark）。
  窗口：--end 是估值/离场末日。买入只发生在 stock_pool/ 有 CSV 的交易日
        （缺日不买）。分钟湖若短于 --end，用日线版接到今天。
  落盘：backtest_output/csv_daily_v6_{start}_{end}/ 三件套 summary.txt、
        daily_equity.csv、trades.csv（与分钟版同结构）。
  环境：勿残留 OSKH_PERIOD_* ；有 F:\\stock_data\\.authority 时跟权威盘。
  比例：--stop-pct / --profit-base / --trail-t1..t5 可改，不必改代码。
  策略：--strategy version6（默认）或 version8。同一引擎，只换卖点。
"""

HELP_LOCK_V8 = """
策略 8 卖点（--strategy version8，买侧/资金/T+1 同上）：
  止损 15 个点。止盈：峰值涨幅须 > 20% 后按绝对涨幅分档回撤到
        20/30/50/70/90/110；涨幅 > 50% 且现价 <= 最高价×80% 也止盈。
  落盘：backtest_output/csv_{daily|minute}_v8_{start}_{end}/
"""


@dataclass
class Position:
    code: str
    shares: int
    cost: float  # 买入价（收盘成交价）
    entry_idx: int  # 全局日历下标
    peak: float  # 持仓期最高价（起始=买入价；T+1 起用每日 high 更新）
    peak_hm: int = -1  # 峰值所在分钟 hm；跨日为负间隔，分钟止盈用


@dataclass
class SimState:
    cash: float = DEFAULT_TOTAL_CASH
    positions: dict = field(default_factory=dict)
    daily_quota_used: float = 0.0
    supplementary_used: float = 0.0
    trades: list = field(default_factory=list)
    equity_curve: list = field(default_factory=list)
    stats: dict = field(
        default_factory=lambda: {
            "buys": 0,
            "skip_limit_up": 0,
            "chase_buy": 0,
            "chase_abandon": 0,
            "chase_skip_limit": 0,
            "chase_no_bar": 0,
            "skip_held": 0,
            "skip_no_bar": 0,
            "sell_stop": 0,
            "sell_trail": 0,
            "sell_pos_trail": 0,
            "defer_sell_limit_down": 0,
            "invested_notional": 0.0,
            "supplementary_used": 0.0,
            "bars_loaded": 0,
            "pool_days": 0,
        }
    )


def normalize_csv_strategy(strategy: str) -> str:
    raw = (strategy or "version6").strip().lower()
    aliases = {
        "6": "version6",
        "v6": "version6",
        "version6": "version6",
        "8": "version8",
        "v8": "version8",
        "version8": "version8",
    }
    if raw not in aliases:
        raise ValueError(
            f"unsupported csv strategy {strategy!r}; use version6 or version8"
        )
    return aliases[raw]


def apply_csv_strategy(
    strategy: str = "version6",
    *,
    stop_pct: Optional[float] = None,
    take_profit=None,
    record_params=None,
) -> dict:
    """同一引擎上的卖点挂钩。version8 默认止损 15%、金榕元分档。"""
    name = normalize_csv_strategy(strategy)
    if name == "version8":
        from backtest.research.strategy8_rules import (
            STOP_PCT as V8_STOP,
            record_strategy8_params,
            take_profit_reason,
        )

        resolved = V8_STOP if stop_pct is None else float(stop_pct)
        return {
            "stop_pct": resolved,
            "take_profit": take_profit_reason if take_profit is None else take_profit,
            "record_params": (
                record_params
                if record_params is not None
                else (lambda st: record_strategy8_params(st, stop_pct=resolved))
            ),
        }
    return {
        "stop_pct": STOP_PCT if stop_pct is None else float(stop_pct),
        "take_profit": take_profit,
        "record_params": record_params,
    }


def add_csv_strategy_arg(ap: argparse.ArgumentParser) -> None:
    ap.add_argument(
        "--strategy",
        choices=("version6", "version8"),
        default="version6",
        help="sell book on the shared CSV engine (default version6)",
    )


def engine_book(strategy: str) -> str:
    return "v8" if normalize_csv_strategy(strategy) == "version8" else "v6"


def help_lock_for(strategy: str) -> str:
    if normalize_csv_strategy(strategy) == "version8":
        return HELP_LOCK + HELP_LOCK_V8
    return HELP_LOCK


def add_strategy6_ratio_args(ap: argparse.ArgumentParser) -> None:
    """止损 / 锚 / 分档回撤：改比例走命令行，不必改常量。"""
    ap.add_argument(
        "--stop-pct",
        type=float,
        default=None,
        help="stop-loss fraction (version6 default 0.06, version8 default 0.15)",
    )
    ap.add_argument(
        "--profit-base",
        type=float,
        default=PROFIT_BASE,
        help=f"take-profit anchor fraction (default {PROFIT_BASE:g})",
    )
    ap.add_argument(
        "--trail-t1",
        type=float,
        default=TIERS[1],
        help=f"T+1 retain ratio of peak excess (default {TIERS[1]:g})",
    )
    ap.add_argument(
        "--trail-t2",
        type=float,
        default=TIERS[2],
        help=f"T+2 retain ratio (default {TIERS[2]:g})",
    )
    ap.add_argument(
        "--trail-t3",
        type=float,
        default=TIERS[3],
        help=f"T+3 retain ratio (default {TIERS[3]:g})",
    )
    ap.add_argument(
        "--trail-t4",
        type=float,
        default=TIERS[4],
        help=f"T+4 retain ratio (default {TIERS[4]:g})",
    )
    ap.add_argument(
        "--trail-t5",
        type=float,
        default=TIER_DEFAULT,
        help=f"T+5+ retain ratio (default {TIER_DEFAULT:g})",
    )


def strategy6_kwargs_from_args(args) -> dict:
    stop_pct = STOP_PCT if args.stop_pct is None else float(args.stop_pct)
    profit_base = float(args.profit_base)
    t1 = float(args.trail_t1)
    t2 = float(args.trail_t2)
    t3 = float(args.trail_t3)
    t4 = float(args.trail_t4)
    t5 = float(args.trail_t5)
    for name, val in (
        ("--stop-pct", stop_pct),
        ("--profit-base", profit_base),
        ("--trail-t1", t1),
        ("--trail-t2", t2),
        ("--trail-t3", t3),
        ("--trail-t4", t4),
        ("--trail-t5", t5),
    ):
        if not 0 < val < 1:
            raise SystemExit(f"{name} must be in (0, 1), got {val}")
    return {
        "stop_pct": stop_pct,
        "profit_base": profit_base,
        "tiers": {1: t1, 2: t2, 3: t3, 4: t4},
        "tier_default": t5,
    }


def csv_run_kwargs_from_args(args) -> dict:
    name = normalize_csv_strategy(getattr(args, "strategy", "version6"))
    if name == "version8":
        stop = args.stop_pct
        if stop is not None and not 0 < float(stop) < 1:
            raise SystemExit(f"--stop-pct must be in (0, 1), got {stop}")
        return {"strategy": "version8", "stop_pct": stop}
    return {"strategy": "version6", **strategy6_kwargs_from_args(args)}


def record_strategy6_params(
    st: SimState,
    *,
    stop_pct: float,
    profit_base: float,
    tiers: dict,
    tier_default: float,
) -> None:
    st.stats["stop_pct"] = float(stop_pct)
    st.stats["profit_base"] = float(profit_base)
    st.stats["trail_t1"] = float(tiers.get(1, TIERS[1]))
    st.stats["trail_t2"] = float(tiers.get(2, TIERS[2]))
    st.stats["trail_t3"] = float(tiers.get(3, TIERS[3]))
    st.stats["trail_t4"] = float(tiers.get(4, TIERS[4]))
    st.stats["trail_t5"] = float(tier_default)


def chase_decision(open_px: float, px: float, limit_up: float) -> str:
    """T+1 09:45：市价>开盘且非涨停 → buy；否则 abandon / limit。"""
    if hit_limit_up(px, limit_up):
        return "limit"
    if px > open_px:
        return "buy"
    return "abandon"


def _ymd(ts) -> str:
    return pd.Timestamp(ts).strftime("%Y%m%d")


def utc_ms_range(start: str, end: str) -> tuple[int, int]:
    """YYYYMMDD 闭区间 → UTC 午夜毫秒（日线/分钟湖把交易日钟点标成 UTC）。"""
    t0 = int(pd.Timestamp(start, tz="UTC").timestamp() * 1000)
    t1 = (
        int((pd.Timestamp(end, tz="UTC") + pd.Timedelta(days=1)).timestamp() * 1000) - 1
    )
    return t0, t1


def warmup_start(start: str, days: int = WARMUP_DAYS) -> str:
    return (pd.Timestamp(start) - pd.Timedelta(days=int(days))).strftime("%Y%m%d")


def warn_stale_period_env() -> None:
    hit = [k for k in _PERIOD_ENV_KEYS if os.environ.get(k)]
    if hit:
        print(
            f"[warn] {', '.join(hit)} is set; lake may ignore F:\\stock_data\\.authority",
            flush=True,
        )


def _progress(done: int, total: int, label: str, every: int = 200) -> None:
    if total <= 0:
        return
    if done == 1 or done == total or done % every == 0:
        print(f"{label} {done}/{total}", flush=True)


def build_calendar(bars: dict[str, pd.DataFrame], start: str, end: str) -> list:
    t0 = pd.Timestamp(start)
    t1 = pd.Timestamp(end)
    seen = set()
    for df in bars.values():
        idx = df.index
        for d in idx[(idx >= t0) & (idx <= t1)]:
            seen.add(d)
    calendar = sorted(seen)
    if not calendar:
        raise SystemExit("no daily bars in window")
    return calendar


def _at_limit(price: float, limit: float) -> bool:
    """价格≈等于涨/跌停价。买入拦截请用 hit_limit_up（含越过涨停价）。"""
    return abs(price - limit) <= LIMIT_EPS


def hit_limit_up(price: float, limit_up: float) -> bool:
    """买价达到或超过涨停价则不可买（含舍入导致买价高于算出的涨停价）。"""
    return float(price) + LIMIT_EPS >= float(limit_up)


def hit_limit_down(price: float, limit_down: float) -> bool:
    """卖价达到或低于跌停价则不可卖。"""
    return float(price) - LIMIT_EPS <= float(limit_down)


def peak_gap_blocks(gap, peak_gap_min: int = PEAK_GAP_MIN) -> bool:
    """同会话分钟差 < 15 则挡住止盈；隔夜/午休 gap<0 视为满足。"""
    return 0 <= int(gap) < int(peak_gap_min)


def trail_hits(
    px: float,
    cost: float,
    peak: float,
    profit_base: float,
    ratio: float,
) -> bool:
    """锚定回撤是否触发。触发价 < 买入价不执行止盈。"""
    if float(px) < float(cost):
        return False
    peak_excess = float(peak) / float(cost) - 1.0 - float(profit_base)
    if peak_excess <= 0:
        return False
    return (
        float(px) / float(cost) - 1.0 - float(profit_base) <= float(ratio) * peak_excess
    )


def round_fen(price: float) -> float:
    """A 股涨跌停：分位四舍五入（不用 Python round 的银行家舍入）。"""
    return float(Decimal(str(price)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _limit_prices(code: str, prev_close: float) -> tuple[float, float]:
    pct = limit_pct(code)
    prev = Decimal(str(prev_close))
    step = Decimal("0.01")
    up = (prev * (Decimal("1") + Decimal(str(pct)))).quantize(
        step, rounding=ROUND_HALF_UP
    )
    down = (prev * (Decimal("1") - Decimal(str(pct)))).quantize(
        step, rounding=ROUND_HALF_UP
    )
    return float(up), float(down)


def load_pool_days(
    start: str, end: str, pool_dir: Optional[Path] = None
) -> dict[str, list[str]]:
    """{YYYYMMDD: [canonical codes]}，直接读 stock_pool/ 头列（避免 read_stock_codes 刷 INFO）。"""
    root = Path(pool_dir) if pool_dir is not None else Path(REPO) / "stock_pool"
    days: dict[str, list[str]] = {}
    for p in sorted(root.glob("*.csv")):
        if not (start <= p.stem <= end):
            continue
        try:
            df = pd.read_csv(p, header=None, dtype={0: str}, encoding="utf-8-sig")
        except Exception as exc:
            print(f"skip pool {p.name}: {exc}", flush=True)
            continue
        if df.empty:
            continue
        raw = df.iloc[:, 0].dropna().astype(str).tolist()
        if not raw:
            continue
        days[p.stem] = list(batch_format_stock_codes(raw))
    return days


def _read_one_daily(
    code: str, root: Path, start: str, end: str
) -> Optional[pd.DataFrame]:
    path = root / f"symbol={to_partition_key(code)}" / "data.parquet"
    if not path.is_file():
        return None
    t0, t1 = utc_ms_range(start, end)
    try:
        table = pq.read_table(path, columns=["time", "open", "high", "low", "close"])
        table = table.filter((pc.field("time") >= t0) & (pc.field("time") <= t1))
    except Exception:
        return None
    if table.num_rows == 0:
        return None
    ms = table["time"].to_numpy()
    idx = pd.to_datetime(ms, unit="ms", utc=True).tz_localize(None).normalize()
    out = pd.DataFrame(
        {
            "open": table["open"].to_numpy(),
            "high": table["high"].to_numpy(),
            "low": table["low"].to_numpy(),
            "close": table["close"].to_numpy(),
        },
        index=idx,
    ).astype(np.float64)
    out = out[~out.index.duplicated(keep="last")].sort_index()
    return out if not out.empty else None


def load_daily_bars(
    codes: set[str], start: str, end: str, *, workers: int = 16
) -> dict[str, pd.DataFrame]:
    """不复权日线（与分钟链 adjust_type='none' 对齐），index=交易日 00:00。"""
    root = resolve_period_root("1d") / "dividend_type=none"
    out: dict[str, pd.DataFrame] = {}
    codes_list = sorted(codes)
    n = max(1, int(workers))
    with ThreadPoolExecutor(max_workers=n) as pool:
        futs = {
            pool.submit(_read_one_daily, c, root, start, end): c for c in codes_list
        }
        done = 0
        total = len(futs)
        for fut in as_completed(futs):
            done += 1
            _progress(done, total, "daily lake")
            code = futs[fut]
            try:
                df = fut.result()
            except Exception:
                continue
            if df is not None and not df.empty:
                out[code] = df
    return out


def simulate(
    bars: dict[str, pd.DataFrame],
    pool_days: dict[str, list[str]],
    start: str,
    end: str,
    *,
    total_cash: float = DEFAULT_TOTAL_CASH,
    daily_quota: float = DEFAULT_DAILY_QUOTA,
    stop_pct: Optional[float] = None,
    profit_base: float = PROFIT_BASE,
    tiers: Optional[dict] = None,
    tier_default: float = TIER_DEFAULT,
    pos_trail: float = POS_TRAIL,
    strategy: str = "version6",
    take_profit=None,
    record_params=None,
) -> SimState:
    """核心日循环。bars/pool_days 可由测试注入；run() 负责从湖与 CSV 加载。

    strategy=version8 换金榕元卖点；take_profit(...) 仍可显式覆盖。
    """
    del pos_trail
    hooks = apply_csv_strategy(
        strategy, stop_pct=stop_pct, take_profit=take_profit, record_params=record_params
    )
    stop_pct = hooks["stop_pct"]
    take_profit = hooks["take_profit"]
    record_params = hooks["record_params"]
    tier_map = dict(tiers or TIERS)
    calendar = build_calendar(bars, start, end)

    st = SimState(cash=float(total_cash))
    if record_params is not None:
        record_params(st)
    else:
        record_strategy6_params(
            st,
            stop_pct=stop_pct,
            profit_base=profit_base,
            tiers=tier_map,
            tier_default=tier_default,
        )
    st.stats["bars_loaded"] = len(bars)
    st.stats["pool_days"] = len(pool_days)
    pending_exit: dict[str, str] = {}  # code -> 原因（次日开盘离场）
    pending_chase: dict[str, tuple[float, int]] = {}  # code -> (per, signal_idx)

    for i, day in enumerate(calendar):
        ds = _ymd(day)
        st.daily_quota_used = 0.0  # 每个交易日开盘重置常规额度

        for code in list(st.positions):
            pos = st.positions[code]
            if code not in bars or day not in bars[code].index:
                continue
            row = bars[code].loc[day]
            prev_rows = bars[code].loc[bars[code].index < day]
            if prev_rows.empty:
                continue
            prev_close = float(prev_rows.iloc[-1]["close"])
            _, limit_down = _limit_prices(code, prev_close)
            n_days = i - pos.entry_idx  # 持仓交易日数（买入日=0）

            if code in pending_exit and n_days >= 1:
                if hit_limit_down(float(row["open"]), limit_down):
                    st.stats["defer_sell_limit_down"] += 1
                else:
                    _sell(
                        st, code, pos, float(row["open"]), day, pending_exit.pop(code)
                    )
                continue

            if n_days >= 1:
                trigger = pos.cost * (1.0 - stop_pct)
                if float(row["open"]) <= trigger:
                    if hit_limit_down(float(row["open"]), limit_down):
                        st.stats["defer_sell_limit_down"] += 1
                    else:
                        _sell(
                            st, code, pos, float(row["open"]), day, "stop_loss:gap_open"
                        )
                    continue
                if float(row["low"]) <= trigger:
                    _sell(st, code, pos, trigger, day, "stop_loss:touch")
                    continue

                pos.peak = max(pos.peak, float(row["high"]))
                close = float(row["close"])
                if take_profit is not None:
                    reason = take_profit(close, pos.cost, pos.peak, n_days)
                    if reason:
                        pending_exit[code] = reason
                else:
                    ratio = float(tier_map.get(n_days, tier_default))
                    if trail_hits(close, pos.cost, pos.peak, profit_base, ratio):
                        pending_exit[code] = f"trail:T+{n_days}"

        due = [c for c, (_per, sig) in pending_chase.items() if i == sig + 1]
        for code in due:
            per_ch, _sig = pending_chase.pop(code)
            if code in st.positions:
                st.stats["skip_held"] += 1
                continue
            if code not in bars or day not in bars[code].index:
                st.stats["chase_no_bar"] += 1
                continue
            df_c = bars[code]
            prev_rows = df_c.loc[df_c.index < day]
            if prev_rows.empty:
                st.stats["chase_no_bar"] += 1
                continue
            row = df_c.loc[day]
            open_px = float(row["open"])
            close_px = float(row["close"])
            prev_close = float(prev_rows.iloc[-1]["close"])
            limit_up, _ = _limit_prices(code, prev_close)
            decision = chase_decision(open_px, close_px, limit_up)
            if decision == "limit":
                st.stats["chase_skip_limit"] += 1
                continue
            if decision != "buy":
                st.stats["chase_abandon"] += 1
                continue
            execute_buy(st, code, close_px, per_ch, i, day, reason="chase:T+1")

        planned = list(pool_days.get(ds, []))
        if planned:
            n_plan = len(planned)
            per = min(daily_quota, st.cash) / n_plan
            for code in planned:
                if code in st.positions:
                    st.stats["skip_held"] += 1
                    continue
                if code not in bars or day not in bars[code].index:
                    st.stats["skip_no_bar"] += 1
                    continue
                df_c = bars[code]
                prev_rows = df_c.loc[df_c.index < day]
                if prev_rows.empty:
                    st.stats["skip_no_bar"] += 1
                    continue
                prev_close = float(prev_rows.iloc[-1]["close"])
                limit_up, _ = _limit_prices(code, prev_close)
                close = float(df_c.loc[day]["close"])
                if hit_limit_up(close, limit_up):
                    st.stats["skip_limit_up"] += 1
                    pending_chase[code] = (per, i)
                    continue
                execute_buy(st, code, close, per, i, day, reason="pool")

        eq = st.cash
        for code, pos in st.positions.items():
            df_c = bars.get(code)
            if df_c is not None and day in df_c.index:
                eq += pos.shares * float(df_c.loc[day]["close"])
            else:
                eq += pos.shares * pos.cost
        st.equity_curve.append((ds, eq))

        if day == calendar[-1] and st.positions:
            for code, pos in st.positions.items():
                df_c = bars.get(code)
                last = (
                    float(df_c.loc[day]["close"])
                    if df_c is not None and day in df_c.index
                    else pos.cost
                )
                st.trades.append(
                    {
                        "date": ds,
                        "code": code,
                        "side": "EOD_MARK",
                        "price": last,
                        "shares": pos.shares,
                        "notional": pos.shares * last,
                        "commission": 0.0,
                    }
                )

    return st


def run(
    start: str,
    end: str,
    *,
    total_cash: float = DEFAULT_TOTAL_CASH,
    daily_quota: float = DEFAULT_DAILY_QUOTA,
    stop_pct: Optional[float] = None,
    profit_base: float = PROFIT_BASE,
    tiers: Optional[dict] = None,
    tier_default: float = TIER_DEFAULT,
    pos_trail: float = POS_TRAIL,
    workers: int = 16,
    strategy: str = "version6",
    take_profit=None,
    record_params=None,
) -> SimState:
    warn_stale_period_env()
    t_pool = time.perf_counter()
    pool_days = load_pool_days(start, end)
    t_pool = time.perf_counter() - t_pool
    if not pool_days:
        raise SystemExit(f"no pool CSVs in [{start}, {end}] under stock_pool/")
    all_codes = {c for codes in pool_days.values() for c in codes}
    load_start = warmup_start(start)
    print(
        f"loading daily bars: {len(all_codes)} codes, {load_start}..{end}; "
        f"pool {min(pool_days)}..{max(pool_days)} ({len(pool_days)} days)",
        flush=True,
    )
    t_daily = time.perf_counter()
    bars = load_daily_bars(all_codes, load_start, end, workers=workers)
    t_daily = time.perf_counter() - t_daily
    print(
        f"loaded {len(bars)}/{len(all_codes)} daily series, {len(pool_days)} pool days",
        flush=True,
    )
    t_sim = time.perf_counter()
    st = simulate(
        bars,
        pool_days,
        start,
        end,
        total_cash=total_cash,
        daily_quota=daily_quota,
        stop_pct=stop_pct,
        profit_base=profit_base,
        tiers=tiers,
        tier_default=tier_default,
        pos_trail=pos_trail,
        strategy=strategy,
        take_profit=take_profit,
        record_params=record_params,
    )
    st.stats["t_pool_s"] = t_pool
    st.stats["t_daily_s"] = t_daily
    st.stats["t_sim_s"] = time.perf_counter() - t_sim
    st.stats["codes_missing"] = max(0, len(all_codes) - len(bars))
    return st


def _buy_size(per_quota: float, price: float) -> tuple[int, float]:
    """常规额度内最大整百股；不足 100 股用补充资金补足（返回 (shares, supp_used))。"""
    if price <= 0 or per_quota <= 0:
        return 0, 0.0
    shares = int(per_quota / price / 100.0) * 100
    supp = 0.0
    if shares == 0:
        notional = 100 * price
        supp = max(0.0, notional - per_quota)
        shares = 100
    return shares, supp


def execute_buy(
    st: SimState,
    code: str,
    px: float,
    per: float,
    entry_idx: int,
    day,
    *,
    reason: str = "pool",
) -> bool:
    """常规/追买共用：整百股 + force_min + 0.1% 佣金。成功返回 True。"""
    if px <= 0:
        return False
    shares, supp = _buy_size(per, px)
    if shares <= 0:
        return False
    notional = shares * px
    comm = notional * COMMISSION
    if notional + comm > st.cash:
        return False
    st.cash -= notional + comm
    st.daily_quota_used += min(per, notional)
    st.stats["supplementary_used"] += supp
    st.stats["invested_notional"] += notional
    st.positions[code] = Position(code, shares, px, entry_idx, px)
    st.trades.append(
        {
            "date": _ymd(day),
            "code": code,
            "side": "BUY",
            "price": px,
            "shares": shares,
            "notional": notional,
            "commission": comm,
            "reason": reason,
        }
    )
    st.stats["buys"] += 1
    if reason.startswith("chase"):
        st.stats["chase_buy"] += 1
    return True


def _sell(st: SimState, code: str, pos: Position, px: float, day, reason: str) -> None:
    notional = pos.shares * px
    comm = notional * COMMISSION
    st.cash += notional - comm
    st.trades.append(
        {
            "date": _ymd(day),
            "code": code,
            "side": "SELL",
            "price": px,
            "shares": pos.shares,
            "notional": notional,
            "commission": comm,
            "reason": reason,
        }
    )
    if reason.startswith("stop_loss"):
        st.stats["sell_stop"] += 1
    elif reason.startswith("trail"):
        st.stats["sell_trail"] += 1
    else:
        st.stats["sell_pos_trail"] += 1
    del st.positions[code]


def summarize(
    st: SimState,
    total_cash: float,
    start: str,
    end: str,
    *,
    engine: str = "csv_daily_v6",
) -> str:
    eq = pd.DataFrame(st.equity_curve, columns=["date", "equity"])
    final = float(eq["equity"].iloc[-1]) if len(eq) else total_cash
    peak = eq["equity"].cummax()
    max_dd = float((eq["equity"] / peak - 1.0).min()) if len(eq) else 0.0
    invested = st.stats["invested_notional"]
    deployed = (final - total_cash) / invested if invested > 0 else float("nan")
    lines = [
        f"{engine} {start}..{end}",
        f"  期末净值: {final:,.2f} / {total_cash:,.0f}",
        f"  总收益率(全资金): {final / total_cash - 1:+.2%}",
        f"  动用资金收益率: {deployed:+.2%}"
        if invested > 0
        else "  动用资金收益率: n/a",
        f"  最大回撤: {max_dd:.2%}",
    ]
    if st.stats.get("sell_book") == "v8":
        lines.append(
            f"  参数: 止损 {st.stats['stop_pct']:.0%} | 基础止盈 "
            f"{st.stats['profit_base']:.0%} | 涨幅>{st.stats['peak_dd_arm']:.0%} 时 "
            f"最高价回撤 {st.stats['peak_dd_pct']:.0%}"
        )
    elif "stop_pct" in st.stats:
        lines.append(
            f"  参数: 止损 {st.stats['stop_pct']:.0%} | 锚 {st.stats['profit_base']:.0%} | "
            f"回撤 T+1 {st.stats['trail_t1']:.0%} / T+2 {st.stats['trail_t2']:.0%} / "
            f"T+3 {st.stats.get('trail_t3', 0):.0%} / T+4 {st.stats.get('trail_t4', 0):.0%} / "
            f"T+5+ {st.stats.get('trail_t5', st.stats.get('trail_t3', 0)):.0%}"
        )
    lines.extend(
        [
            f"  买入 {st.stats['buys']} | 涨停跳过 {st.stats['skip_limit_up']} | "
            f"追买 {st.stats.get('chase_buy', 0)} | 弃买 {st.stats.get('chase_abandon', 0)} | "
            f"已持跳过 {st.stats['skip_held']}",
            f"  卖出: 止损 {st.stats['sell_stop']} | 锚定回撤 {st.stats['sell_trail']} | 正利润回撤 {st.stats['sell_pos_trail']}",
            f"  跌停顺延卖出 {st.stats['defer_sell_limit_down']} | 补充资金 {st.stats['supplementary_used']:,.0f}",
            f"  日线加载 {st.stats['bars_loaded']} | 池天数 {st.stats['pool_days']}",
        ]
    )
    timing_parts = []
    for key, lab in (
        ("t_pool_s", "池"),
        ("t_daily_s", "日线"),
        ("t_minute_s", "分钟"),
        ("t_sim_s", "模拟"),
    ):
        if key in st.stats:
            timing_parts.append(f"{lab} {float(st.stats[key]):.1f}s")
    cache = st.stats.get("cache")
    if cache:
        timing_parts.append(f"缓存 {cache}")
    if timing_parts:
        lines.append("  耗时: " + " | ".join(timing_parts))
    missing = st.stats.get("codes_missing")
    if missing:
        lines.append(f"  缺行情 {int(missing)}")
    return "\n".join(lines)


def write_run_artifacts(out_dir: Path, st: SimState, text: str, help_lock: str) -> Path:
    """三件套：summary.txt / daily_equity.csv / trades.csv。"""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(st.trades).to_csv(
        out_dir / "trades.csv", index=False, encoding="utf-8"
    )
    pd.DataFrame(st.equity_curve, columns=["date", "equity"]).to_csv(
        out_dir / "daily_equity.csv", index=False, encoding="utf-8"
    )
    (out_dir / "summary.txt").write_text(
        text + "\n" + help_lock, encoding="utf-8", newline="\n"
    )
    print(f"wrote {out_dir}", flush=True)
    return out_dir


def find_daily_equity_csv(
    start: str,
    end: str,
    output_root: Optional[Path] = None,
    *,
    book: str = "v6",
) -> Optional[Path]:
    root = (
        Path(output_root) if output_root is not None else Path(REPO) / "backtest_output"
    )
    exact = root / f"csv_daily_{book}_{start}_{end}" / "daily_equity.csv"
    if exact.is_file():
        return exact
    found: list[tuple[str, Path]] = []
    for path in root.glob(f"csv_daily_{book}_{start}_*/daily_equity.csv"):
        found.append((path.parent.name.rsplit("_", 1)[-1], path))
    if not found:
        return None
    covering = [item for item in found if item[0] >= end]
    pool = covering or found
    pool.sort(key=lambda item: item[0])
    return pool[-1][1]


def format_equity_compare(
    this_curve: list,
    peer_csv: Path,
    *,
    this_label: str,
    peer_label: str = "csv_daily_v6",
    highlight: str = "20251104",
) -> str:
    this = pd.DataFrame(this_curve, columns=["date", "equity"])
    peer = pd.read_csv(peer_csv, encoding="utf-8")
    if (
        this.empty
        or peer.empty
        or "date" not in peer.columns
        or "equity" not in peer.columns
    ):
        return f"对照 {peer_label}: 对端净值表为空（{peer_csv}）"
    this["date"] = this["date"].astype(str)
    peer["date"] = peer["date"].astype(str)
    merged = this.merge(peer, on="date", suffixes=("_this", "_peer"))
    if merged.empty:
        return f"对照 {peer_label}: 无重叠交易日（{peer_csv}）"
    merged["gap"] = merged["equity_this"] - merged["equity_peer"]
    merged["gap_pct"] = merged["gap"] / merged["equity_peer"]
    first = merged.iloc[0]
    last = merged.iloc[-1]
    worst = merged.loc[merged["gap"].abs().idxmax()]
    lines = [
        f"对照 {peer_label}（{peer_csv.parent.name}）重叠 {len(merged)} 日 "
        f"{first['date']}..{last['date']}（双方均为 none 成交价，差来自卖点时钟）:",
        f"  首日 {this_label} {first['equity_this']:,.2f} vs {peer_label} "
        f"{first['equity_peer']:,.2f} 差 {first['gap']:+,.2f}",
        f"  末日 {this_label} {last['equity_this']:,.2f} vs {peer_label} "
        f"{last['equity_peer']:,.2f} 差 {last['gap']:+,.2f} ({last['gap_pct']:+.2%})",
        f"  最大绝对偏差 {worst['date']} {worst['gap']:+,.2f} ({worst['gap_pct']:+.2%})",
    ]
    hit = merged.loc[merged["date"] == highlight]
    if not hit.empty:
        row = hit.iloc[0]
        lines.append(
            f"  {highlight} {this_label} {row['equity_this']:,.2f} vs "
            f"{peer_label} {row['equity_peer']:,.2f} 差 {row['gap']:+,.2f}"
        )
    return "\n".join(lines)


def maybe_compare_daily(
    this_curve: list,
    start: str,
    end: str,
    *,
    this_label: str,
    output_root: Optional[Path] = None,
    book: Optional[str] = None,
) -> str:
    if book is None:
        book = "v8" if "v8" in this_label else "v6"
    peer = find_daily_equity_csv(start, end, output_root, book=book)
    if peer is None:
        return ""
    peer_label = f"csv_daily_{book}"
    return format_equity_compare(
        this_curve, peer, this_label=this_label, peer_label=peer_label
    )


def main(argv: Optional[list] = None) -> int:
    ap = argparse.ArgumentParser(
        description="CSV-mode daily-bar backtest (version6 / version8)",
        epilog=HELP_LOCK + HELP_LOCK_V8,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--start", default="20251023")
    ap.add_argument("--end", default="20260909")
    ap.add_argument("--cash-total", type=float, default=DEFAULT_TOTAL_CASH)
    ap.add_argument("--daily-quota", type=float, default=DEFAULT_DAILY_QUOTA)
    ap.add_argument("--workers", type=int, default=16)
    add_csv_strategy_arg(ap)
    add_strategy6_ratio_args(ap)
    args = ap.parse_args(argv if argv is not None else None)

    st = run(
        args.start,
        args.end,
        total_cash=args.cash_total,
        daily_quota=args.daily_quota,
        workers=args.workers,
        **csv_run_kwargs_from_args(args),
    )
    book = engine_book(args.strategy)
    engine = f"csv_daily_{book}"
    text = summarize(st, args.cash_total, args.start, args.end, engine=engine)
    print(text)
    tag = f"{engine}_{args.start}_{args.end}"
    write_run_artifacts(
        Path(REPO) / "backtest_output" / tag, st, text, help_lock_for(args.strategy)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
