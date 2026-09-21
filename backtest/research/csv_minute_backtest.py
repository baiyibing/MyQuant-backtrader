#!/usr/bin/env python3
"""CSV 模式分钟向量化回测（共用买侧/资金引擎，卖点由策略书提供）。

与日线近似版同一套 CSV 额度 / T+1 / 涨停跳过 / force_min / 0.1% 双边佣金。
卖点按分钟路径扫描：峰值用 bar high，现价用 close；开盘已跌破止损则按开盘价
成交。必须从已注册策略中显式指定 `--strategy`，无缺省。买入用 14:55 分钟收盘
（湖内时间为「中国交易时钟标成 UTC」——09:30 UTC = 09:30 CST）。

用法：
    python backtest/research/csv_minute_backtest.py --strategy version6 --start 20251023 --end 20251104
    python backtest/research/csv_minute_backtest.py --strategy version8 --start 20251023 --end 20260909
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, REPO)

from backtest.research.csv_ledger import (  # noqa: E402
    CHASE_HM,
    DEFAULT_TOTAL_CASH,
    PEAK_GAP_MIN,
    SimState,
    chase_decision as chase_decision,
    execute_buy as execute_buy,
    finish_pending_chase,
    queue_limit_up_chase as queue_limit_up_chase,
    hit_limit_down,
    hit_limit_up,
    last_close_mark as last_close_mark,
    peak_gap_blocks,
    _sell,
    _ymd,
    rescale_position,
    apply_exdiv_economics,
)

from backtest.research.ashare_exdiv_economics import EconomicLookup, ExDivEconomics  # noqa: E402

from backtest.research.exdiv_map import k_for, load_exdiv_ratios, mapped_prev_close  # noqa: E402
from backtest.research.ashare_session import defer_sell_at_limit, t1_sellable  # noqa: E402
from backtest.research.csv_common import (  # noqa: E402
    DEFAULT_DAILY_QUOTA,
    STRATEGY4_CALENDAR_SLACK_DAYS,
    WARMUP_DAYS,
    book_limit_prices,
    build_calendar,
    _named_limits as _named_limits,
    _pool_names_asof as _pool_names_asof,
    _progress as _progress,
)
from backtest.research.csv_pool import (  # noqa: E402
    load_pool_day_map,
    load_pool_names_by_day,
)
from backtest.research.csv_strategy_books import (  # noqa: E402
    add_csv_backtest_common_args,
    apply_csv_strategy,
    csv_run_kwargs_from_args,
    engine_book,
    resolve_research_pool_dir,
    help_lock_all,
    help_lock_for,
    normalize_csv_strategy,
)
from backtest.research.strategy6_rules import (  # noqa: E402
    POS_TRAIL,
    trail_hits,
)
from backtest.research.csv_artifacts import (  # noqa: E402
    maybe_compare_daily,
    summarize,
    write_run_artifacts,
)
from backtest.research.ashare_bars import (  # noqa: E402
    AM_CLOSE as AM_CLOSE,
    AM_OPEN,
    CACHE_ROOT as CACHE_ROOT,
    MINUTE_LAKE_END,
    PM_CLOSE as PM_CLOSE,
    PM_OPEN as PM_OPEN,
    annotate_session as _annotate,
    book_frames_from_compact,
    load_daily_ohlc,
    load_minute_bars,
    load_minute_from_lake as _load_minute_from_lake,
    minute_cache_path as minute_cache_path,
    read_lake_minute_ohlc as _read_one_minute,
    read_minute_cache as read_minute_cache,
    write_minute_cache as write_minute_cache,
    _load_minute_compact,
)
from backtest.research.csv_daily_loader import (  # noqa: E402
    warn_stale_period_env,
    warmup_start,
)
from oskh_data.symbol_format import to_partition_key as to_partition_key  # noqa: E402
from backtest.research.strategy3_rules import reserve_step_minute  # noqa: E402
from backtest.research.csv_simulate_loop import (  # noqa: E402
    append_equity_and_eod_marks,
    init_sim_state,
    prepare_strategy_hooks,
    run_chase_due_day,
    run_eod_exits,
    run_pool_buys_day,
    run_step_adds_day,
)

from backtest.research.ashare_volume_cap import VolumeCap, VolumeLookup  # noqa: E402

# Preserve historical loader aliases used by callers and tests.
_ = (_annotate, _load_minute_from_lake, _read_one_minute)

BUY_HM = 14 * 60 + 55

# Preserve the existing engine/test import surface (N-R9).
_ = (
    AM_CLOSE,
    CACHE_ROOT,
    PM_CLOSE,
    PM_OPEN,
    _annotate,
    _named_limits,
    _pool_names_asof,
    _progress,
    _read_one_minute,
    chase_decision,
    execute_buy,
    last_close_mark,
    minute_cache_path,
    queue_limit_up_chase,
    read_minute_cache,
    to_partition_key,
    write_minute_cache,
)

HELP_LOCK = """
分钟向量化口径（相对 Cerebro 保真版：无事件总线，同公式逐分钟扫描）：
  时钟：分钟湖 time 把 A 股会话钟点标成 UTC（09:30 UTC=开盘）。交易日=该 UTC 日期。
  买入：池 CSV 当日候选、14:55 收盘价；买价达到或超过涨停价 → 当日不买，
        记下额度。T+1 09:45 市价>当日开盘 → 09:45 收盘追买；否则弃买。
        追买日无 K 保留 pending 到下一有 K 日（仍只评一次）。
        per_name 是否加仓见策略书（v8 允许同码加仓、独立 lot）；daily_quota 沿用历史路径。
        未知板块且无 ST 名 → skip_unknown_board，不交易。
  止损：D+1 起，开盘 ≤ 买入价×(1-stop) → 开盘成交；否则该分钟 close 触价 → close 成交。
  跌停禁卖：任何卖因成交前若开盘或成交价跌停 → 不成交、当日跳过、次日再评
        （含 trail / profit_take / force / ma_signal / open_board，不只 stop_loss）。
  停牌：冻仓；净值用最近有 K 的 close。
  止盈 / 峰值：见下方对应策略书。峰值用 bar high，现价用 close。
        策略 6 触价 bar 与创新高 bar 间隔不能 < 15 分钟（=15 允许；隔夜/午休 gap<0 视为满足）。
        盘中触线按该分钟 close 走。v8：T+1 只评止损不评止盈。
  T+0：不可卖；峰值固定为买入价，14:55 之后的 high 不计入。峰值从 T+1 起算。
  资金 / T+1 / force_min / 佣金：与 csv_daily_backtest 相同。
        资金模式见策略书（v8=每股预算）；per_name 现金不足（含佣金）整笔 skip_cash。
  配给：--ration file_order 保持 CSV 行序；seeded_shuffle 用 --ration-seed 与日期
        经 SHA-256 派生逐日稳定乱序；追买沿该次名单遍历产生的排队顺序。
  复权：E-R6 除权日参考价修正 — 持仓期除权日一次性缩放 open lot 的 cost/peak，
        并将当日 prev_close→档位换算点映射到 D 域；成交价/净值/股数仍 none。
        非除权日与 ≤0.5% 噪声带见 E-R5 收窄声明（engine-ashare-correctness.md）。
  窗口：分钟湖目前到 2026-05-25；要「→今天」用日线版。
  加载 / 缓存：走 ashare_bars.load_minute_ohlc（湖 parquet 或命中 bar_cache）。
        --no-cache 跳过；--rebuild-cache 重做。
  落盘：与日线同三件套；若已有同策略 csv_daily_{book}_{start}_* 净值，summary 末尾附对照。
  策略：必须显式指定已注册 --strategy（无缺省）。共用引擎，策略书换卖点与加仓。
        strategy12 人裁（#151 option 2）约定：
        1) 分钟成交域默认 none（--dividend-type none）；front 仅可选且缺 1m/front 时 fail-closed。
        2) 日线信号域固定 front（MA/形态来自 1d/front）。
        3) 分钟成交仍用分钟原始价（none 域）；
        4) 除权只走显式 economics/文档路径，禁止与 front 日线信号形成静默双重调整。
"""

_LIMIT_EPS = 0.001  # mirror csv_ledger.LIMIT_EPS for numba core

try:
    from numba import njit as _njit  # type: ignore

    @_njit(cache=True)
    def _scan_held_day_numba_trail(
        o,
        h,
        c,
        hm,
        cost,
        peak,
        n_days,
        can_sell,
        stop_pct,
        stop_enabled,
        profit_base,
        trail_ratio,
        limit_down,
        peak_hm,
        peak_gap_min,
        force_sell_hm,
        has_force,
    ):
        """Pure trail path (no sell_gate / take_profit / reserve). Reasons as int codes."""
        trigger = cost * (1.0 - stop_pct) if stop_enabled else 0.0
        new_peak = peak
        new_peak_hm = peak_hm
        n = len(c)
        for i in range(n):
            if (not can_sell) or n_days < 1:
                continue
            hi = h[i]
            cur_hm = hm[i]
            if hi > new_peak:
                new_peak = hi
                new_peak_hm = cur_hm
            px_open = o[i]
            px_close = c[i]
            if limit_down > 0.0 and (px_open - _LIMIT_EPS) <= limit_down:
                continue
            if stop_enabled and px_open <= trigger:
                return i, px_open, 1, new_peak, new_peak_hm
            ret = px_close / cost - 1.0
            if stop_enabled and ret <= -stop_pct:
                return i, px_close, 2, new_peak, new_peak_hm
            gap = cur_hm - new_peak_hm
            peak_blocked = new_peak_hm >= 0 and (0 <= gap < peak_gap_min)
            if not peak_blocked:
                # inline trail_hits
                if px_close >= cost:
                    peak_excess = new_peak / cost - 1.0 - profit_base
                    if peak_excess > 0.0:
                        if (
                            px_close / cost - 1.0 - profit_base
                            <= trail_ratio * peak_excess
                        ):
                            return i, px_close, 3, new_peak, new_peak_hm
            if has_force and cur_hm >= force_sell_hm:
                if limit_down > 0.0 and (px_close - _LIMIT_EPS) <= limit_down:
                    continue
                return i, px_close, 4, new_peak, new_peak_hm
        return -1, np.nan, 0, new_peak, new_peak_hm

    _NUMBA_SCAN_AVAILABLE = True
except Exception:  # pragma: no cover - optional dep
    _NUMBA_SCAN_AVAILABLE = False
    _scan_held_day_numba_trail = None  # type: ignore


_NUMBA_REASON = {
    1: "stop_loss:gap_open",
    2: "stop_loss:touch",
    3: None,  # filled with trail:T+N
    4: "force_sell:time",
}


def _want_numba_scan(use_numba: Optional[bool]) -> bool:
    if use_numba is True:
        return True
    if use_numba is False:
        return False
    backend = (os.environ.get("CSV_SCAN_HELD_DAY_BACKEND") or "python").strip().lower()
    return backend in {"numba", "jit"}


def scan_held_day_python(
    o: np.ndarray,
    h: np.ndarray,
    c: np.ndarray,
    *,
    cost: float,
    peak: float,
    n_days: int,
    can_sell: bool,
    stop_pct: Optional[float],
    profit_base: float,
    trail_ratio: float,
    pos_trail: float = 0.0,
    limit_down: float = 0.0,
    hm: Optional[np.ndarray] = None,
    peak_hm: int = -1,
    peak_gap_min: int = PEAK_GAP_MIN,
    take_profit=None,
    sell_gate=None,
    gate_code=None,
    gate_day=None,
    daily_closes_ending_yesterday=None,
    force_sell_hm: Optional[int] = None,
    reserve_limit_up: bool = False,
    defer_limit_up: bool = False,
    limit_up: float = 0.0,
    reserved: bool = False,
    reserve_state: Optional[dict] = None,
    exit_plan=None,
    exit_state: Optional[dict] = None,
) -> tuple[int, float, str, float, int]:
    """Python reference implementation of the minute sell scan."""
    del pos_trail  # reserved for future; kept for API parity with callers
    stop_enabled = isinstance(stop_pct, float) and 0 < stop_pct < 1
    trigger = cost * (1.0 - stop_pct) if stop_enabled else None
    new_peak = float(peak)
    new_peak_hm = int(peak_hm)
    current_reserved = bool(reserved)
    lu_today = False
    defer_lu = bool(defer_limit_up)
    n = int(len(c))
    for i in range(n):
        # T+0 不卖、不更新峰值（历史最高价从 T+1 起算）
        if (not can_sell) or n_days < 1:
            continue
        hi = float(h[i])
        cur_hm = int(hm[i]) if hm is not None else i
        if hi > new_peak:
            new_peak = hi
            new_peak_hm = cur_hm
        px_open = float(o[i])
        px_close = float(c[i])
        if limit_down > 0 and hit_limit_down(px_open, limit_down):
            continue
        if stop_enabled and trigger is not None and px_open <= trigger:
            return i, px_open, "stop_loss:gap_open", new_peak, new_peak_hm
        ret = px_close / cost - 1.0
        if stop_enabled and ret <= -stop_pct:
            return i, px_close, "stop_loss:touch", new_peak, new_peak_hm
        if defer_lu and limit_up > 0 and hit_limit_up(px_close, limit_up):
            lu_today = True
        if defer_lu and lu_today:
            continue
        if reserve_limit_up:
            is_limit_up = limit_up > 0 and hit_limit_up(px_close, limit_up)
            current_reserved, reserve_reason = reserve_step_minute(
                reserved=current_reserved, hm=cur_hm, is_limit_up=is_limit_up
            )
            if reserve_state is not None:
                reserve_state["reserved"] = current_reserved
            if reserve_reason:
                return i, px_close, reserve_reason, new_peak, new_peak_hm
            if current_reserved and is_limit_up:
                continue
        peak_blocked = new_peak_hm >= 0 and peak_gap_blocks(
            cur_hm - new_peak_hm, peak_gap_min
        )
        if not peak_blocked:
            if callable(exit_plan):
                plan = exit_plan(gate_code, px_close, gate_day,
                                 daily_closes_ending_yesterday or [])
                if plan is not None:
                    reason, shares = plan
                    if exit_state is None:
                        raise ValueError("partial exit_plan requires exit_state out-param")
                    exit_state["shares"] = shares
                    return i, px_close, reason, new_peak, new_peak_hm
            elif callable(sell_gate):
                reason = sell_gate(
                    gate_code,
                    px_close,
                    gate_day,
                    daily_closes_ending_yesterday or [],
                )
                if reason:
                    return i, px_close, reason, new_peak, new_peak_hm
            elif take_profit is not None:
                reason = take_profit(px_close, cost, new_peak, n_days)
                if reason:
                    return i, px_close, reason, new_peak, new_peak_hm
            elif trail_hits(px_close, cost, new_peak, profit_base, trail_ratio):
                return i, px_close, f"trail:T+{max(1, n_days)}", new_peak, new_peak_hm
        if force_sell_hm is not None and cur_hm >= int(force_sell_hm):
            if limit_down > 0 and hit_limit_down(px_close, limit_down):
                continue
            return i, px_close, "force_sell:time", new_peak, new_peak_hm
    return -1, float("nan"), "", new_peak, new_peak_hm


def scan_held_day(
    o: np.ndarray,
    h: np.ndarray,
    c: np.ndarray,
    *,
    cost: float,
    peak: float,
    n_days: int,
    can_sell: bool,
    stop_pct: Optional[float],
    profit_base: float,
    trail_ratio: float,
    pos_trail: float = 0.0,
    limit_down: float = 0.0,
    hm: Optional[np.ndarray] = None,
    peak_hm: int = -1,
    peak_gap_min: int = PEAK_GAP_MIN,
    take_profit=None,
    sell_gate=None,
    gate_code=None,
    gate_day=None,
    daily_closes_ending_yesterday=None,
    force_sell_hm: Optional[int] = None,
    reserve_limit_up: bool = False,
    defer_limit_up: bool = False,
    limit_up: float = 0.0,
    reserved: bool = False,
    reserve_state: Optional[dict] = None,
    use_numba: Optional[bool] = None,
    exit_plan=None,
    exit_state: Optional[dict] = None,
) -> tuple[int, float, str, float, int]:
    """逐分钟扫描。返回 (idx, px, reason, new_peak, new_peak_hm)。

    Default backend is the Python reference. Optional numba trail-only path
    is gated by ``use_numba=True`` or env ``CSV_SCAN_HELD_DAY_BACKEND=numba``.
    Callables (sell_gate / take_profit) and reserve_limit_up always use Python.
    """
    can_offload = (
        _want_numba_scan(use_numba)
        and _NUMBA_SCAN_AVAILABLE
        and sell_gate is None
        and take_profit is None
        and not reserve_limit_up
        and not defer_limit_up
        and reserve_state is None
        and exit_plan is None
    )
    if can_offload:
        o64 = np.asarray(o, dtype=np.float64)
        h64 = np.asarray(h, dtype=np.float64)
        c64 = np.asarray(c, dtype=np.float64)
        if hm is None:
            hm64 = np.arange(len(c64), dtype=np.int64)
        else:
            hm64 = np.asarray(hm, dtype=np.int64)
        stop_enabled = isinstance(stop_pct, float) and 0 < float(stop_pct) < 1
        stop_v = float(stop_pct) if stop_enabled else 0.0
        has_force = force_sell_hm is not None
        force_v = int(force_sell_hm) if has_force else 0
        idx, px, code, new_peak, new_peak_hm = _scan_held_day_numba_trail(
            o64,
            h64,
            c64,
            hm64,
            float(cost),
            float(peak),
            int(n_days),
            bool(can_sell),
            stop_v,
            bool(stop_enabled),
            float(profit_base),
            float(trail_ratio),
            float(limit_down),
            int(peak_hm),
            int(peak_gap_min),
            force_v,
            bool(has_force),
        )
        if code == 0:
            return -1, float("nan"), "", float(new_peak), int(new_peak_hm)
        if code == 3:
            reason = f"trail:T+{max(1, int(n_days))}"
        else:
            reason = _NUMBA_REASON[int(code)]
        return int(idx), float(px), reason, float(new_peak), int(new_peak_hm)

    return scan_held_day_python(
        o,
        h,
        c,
        cost=cost,
        peak=peak,
        n_days=n_days,
        can_sell=can_sell,
        stop_pct=stop_pct,
        profit_base=profit_base,
        trail_ratio=trail_ratio,
        pos_trail=pos_trail,
        limit_down=limit_down,
        hm=hm,
        peak_hm=peak_hm,
        peak_gap_min=peak_gap_min,
        take_profit=take_profit,
        sell_gate=sell_gate,
        gate_code=gate_code,
        gate_day=gate_day,
        daily_closes_ending_yesterday=daily_closes_ending_yesterday,
        force_sell_hm=force_sell_hm,
        reserve_limit_up=reserve_limit_up,
        defer_limit_up=defer_limit_up,
        limit_up=limit_up,
        reserved=reserved,
        reserve_state=reserve_state,
        exit_plan=exit_plan,
        exit_state=exit_state,
    )


def _day_arrays(df: pd.DataFrame, ymd: str) -> Optional[pd.DataFrame]:
    sl = df.loc[df["ymd"] == ymd]
    return sl if not sl.empty else None


def build_day_spans(df: pd.DataFrame) -> dict[str, tuple[int, int]]:
    """按 ymd 切 iloc 区间。要求时间升序；乱序则返回空，调用方回退 _day_arrays。"""
    if df is None or df.empty or "ymd" not in df.columns:
        return {}
    ymd = df["ymd"].to_numpy()
    if len(ymd) >= 2 and np.any(ymd[1:] < ymd[:-1]):
        return {}
    change = np.flatnonzero(ymd[1:] != ymd[:-1]) + 1
    starts = np.concatenate(([0], change))
    ends = np.concatenate((change, [len(ymd)]))
    return {str(ymd[s]): (int(s), int(e)) for s, e in zip(starts, ends)}


def _slice_day(
    df: pd.DataFrame, spans: dict[str, tuple[int, int]], ymd: str
) -> Optional[pd.DataFrame]:
    span = spans.get(ymd)
    if span is not None:
        sl = df.iloc[span[0] : span[1]]
        return sl if not sl.empty else None
    if spans:
        return None
    return _day_arrays(df, ymd)


def _previous_rows(df: pd.DataFrame, day) -> pd.DataFrame:
    """Rows strictly before ``day``; kept named so orchestration can be profiled."""
    return df.loc[df.index < day]


def _buy_px(day_df: pd.DataFrame) -> Optional[float]:
    hit = day_df.loc[day_df["hm"] == BUY_HM]
    if not hit.empty:
        return float(hit["close"].iloc[0])
    late = day_df.loc[(day_df["hm"] >= 14 * 60 + 30) & (day_df["hm"] <= BUY_HM)]
    if late.empty:
        return None
    return float(late["close"].iloc[-1])


def _chase_quotes(day_df: pd.DataFrame) -> Optional[tuple[float, float]]:
    """(当日开盘, 09:45 市价)。缺 09:45 则用 ≤09:45 最后一根 close。"""
    if day_df is None or day_df.empty:
        return None
    open_px = float(day_df.iloc[0]["open"])
    hit = day_df.loc[day_df["hm"] == CHASE_HM]
    if not hit.empty:
        return open_px, float(hit["close"].iloc[0])
    early = day_df.loc[(day_df["hm"] >= AM_OPEN) & (day_df["hm"] <= CHASE_HM)]
    if early.empty:
        return None
    return open_px, float(early["close"].iloc[-1])


def _open_quote_for(day_df: pd.DataFrame):
    """Exact 09:30 first open; a missing opening bar never borrows a later row."""
    hit = day_df.loc[day_df["hm"] == AM_OPEN]
    return None if hit.empty else hit.iloc[0]


def simulate(
    minute_bars: dict[str, pd.DataFrame],
    daily_bars: dict[str, pd.DataFrame],
    pool_days: dict[str, list[str]],
    start: str,
    end: str,
    *,
    total_cash: float = DEFAULT_TOTAL_CASH,
    daily_quota: float = DEFAULT_DAILY_QUOTA,
    name_budget: Optional[float] = None,
    ration: str = "file_order",
    ration_seed: int = 0,
    stop_pct: Optional[float] = None,
    profit_base: Optional[float] = None,
    tiers: Optional[dict] = None,
    tier_default: Optional[float] = None,
    pos_trail: float = POS_TRAIL,
    strategy: str,
    take_profit=None,
    record_params=None,
    pool_names: Optional[dict[str, str]] = None,
    pool_names_by_day: Optional[dict[str, dict[str, str]]] = None,
    exdiv: Optional[dict] = None,
    exdiv_economics: EconomicLookup | None = None,
    scores_by_day=None,
    topk=None,
    n_drop=None,
    eligible_buy=None,
    index_block_new=None,
    participation_rate: float | None = None,
    volume_for_bucket: VolumeLookup | None = None,
) -> SimState:
    """Opt-in cap uses caller-attested completed minutes; daily volume is unused.

    exdiv_economics is an explicit (symbol, YYYYMMDD) -> ExDivEvent lookup for
    raw bars. None retains the baseline; E-R6 ratios never imply entitlements.
    """
    hooks = prepare_strategy_hooks(
        strategy,
        stop_pct=stop_pct,
        take_profit=take_profit,
        record_params=record_params,
        name_budget=name_budget,
        ration=ration,
        ration_seed=ration_seed,
        profit_base=profit_base,
        tiers=tiers,
        tier_default=tier_default,
        apply_fn=apply_csv_strategy,
        scores_by_day=scores_by_day,
        topk=topk,
        n_drop=n_drop,
        eligible_buy=eligible_buy,
        index_block_new=index_block_new,
    )
    stop_pct = hooks["stop_pct"]
    take_profit = hooks["take_profit"]
    buy_gate = hooks.get("buy_gate")
    sell_gate = hooks.get("sell_gate")
    peak_gap_min = int(hooks["peak_gap_min"])
    force_sell_hm = hooks.get("force_sell_hm")
    reserve_limit_up = bool(hooks.get("reserve_limit_up"))
    defer_limit_up = bool(hooks.get("defer_limit_up"))
    calendar = build_calendar(daily_bars, start, end)

    st, pending_chase, names_asof = init_sim_state(
        hooks,
        total_cash=total_cash,
        bars_loaded=len(minute_bars),
        pool_days=pool_days,
        pool_names=pool_names,
        pool_names_by_day=pool_names_by_day,
    )
    if participation_rate is not None:
        st.volume_cap = VolumeCap(participation_rate, volume_for_bucket)
    if exdiv_economics is not None:
        st.exdiv_economics = ExDivEconomics(exdiv_economics, st.stats)
    allow_add = bool(hooks["allow_add"])
    qlib_limit_pct = hooks.get("qlib_limit_pct")
    limit_up_chase = bool(hooks.get("limit_up_chase", True))
    forbid_all_trade_at_limit = bool(hooks.get("forbid_all_trade_at_limit", False))
    minute_open = bool(hooks.get("minute_open"))
    if minute_open:
        for code, frame in minute_bars.items():
            if "volume" not in frame:
                raise ValueError(f"{hooks['name']} requires minute volume for {code}; use the lake volume path")
    hold_modes = {}
    day_spans = {code: build_day_spans(df) for code, df in minute_bars.items()}

    for i, day in enumerate(calendar):
        ds = _ymd(day)
        day_trade_start = len(st.trades)
        if st.exdiv_economics is not None:
            st.cash += st.exdiv_economics.settle(ds)
        names = names_asof(ds)
        st.daily_quota_used = 0.0

        if callable(hooks.get("run_minute_day")):
            hooks["run_minute_day"](
                st, pending_chase, hooks=hooks, minute_bars=minute_bars,
                daily_bars=daily_bars, pool_days=pool_days, day_i=i, day=day,
                ds=ds, names=names, daily_quota=daily_quota, exdiv=exdiv,
                slice_day=lambda code, date: _slice_day(
                    minute_bars[code], day_spans.get(code, {}), date),
                scan=scan_held_day,
            )
        else:
            bind_opening = hooks.get("bind_opening_held")
            if callable(bind_opening):
                bind_opening(ds, list(st.positions.keys()))

            for code in list(st.positions):
                mdf = minute_bars.get(code)
                ddf = daily_bars.get(code)
                if mdf is None or ddf is None or day not in ddf.index:
                    continue
                day_m = _slice_day(mdf, day_spans.get(code, {}), ds)
                if day_m is None:
                    continue
                prev_rows = _previous_rows(ddf, day)
                if prev_rows.empty:
                    continue
                apply_exdiv_economics(st, code, ds)
                # E-R6: rescale before scan_held_day; never between scan and peak writeback.
                kk = k_for(exdiv, code, ds)
                if kk is not None:
                    for pos in list(st.positions.get(code, [])):
                        rescale_position(pos, kk)
                        st.stats["exdiv_adjusted_lots"] = (
                            int(st.stats.get("exdiv_adjusted_lots", 0)) + 1
                        )
                prev_close, did_map = mapped_prev_close(
                    exdiv, code, ds, float(prev_rows.iloc[-1]["close"])
                )
                if did_map:
                    st.stats["exdiv_prev_close_mapped"] = (
                        int(st.stats.get("exdiv_prev_close_mapped", 0)) + 1
                    )
                limits = book_limit_prices(
                    code, prev_close, names, qlib_limit_pct=qlib_limit_pct
                )
                if limits is None:
                    st.stats["skip_unknown_board"] += 1
                    continue
                limit_up, limit_down = limits
                o = day_m["open"].to_numpy(np.float64)
                h = day_m["high"].to_numpy(np.float64)
                c = day_m["close"].to_numpy(np.float64)
                hm = day_m["hm"].to_numpy(np.int64)
                for pos in list(st.positions.get(code, [])):
                    if getattr(pos, "ride_with", None) is not None:
                        continue
                    n_days = i - pos.entry_idx
                    if minute_open:
                        # Only yesterday's pending EOD decision can sell, once at open.
                        if not pos.pending_exit or not t1_sellable(calendar[pos.entry_idx].date(), day.date()):
                            continue
                        opening = _open_quote_for(day_m)
                        if opening is None:
                            continue
                        px = float(opening["open"])
                        volume = float(opening["volume"])
                        if not np.isfinite(px) or px <= 0:
                            continue
                        if not np.isfinite(volume) or volume <= 0:
                            st.stats["defer_sell_volume"] += 1
                            continue
                        if defer_sell_at_limit(px, limits):
                            st.stats["defer_sell_limit_down"] += 1
                            continue
                        before = len(st.trades)
                        _sell(st, code, pos, px, day, pos.pending_exit,
                              bucket_id=AM_OPEN, at=AM_OPEN - 1, day_i=i,
                              hm=AM_OPEN, price_rule="minute_pending_next_open")
                        if any(t["side"] == "SKIP" and t["reason"].startswith("skip_volume")
                               for t in st.trades[before:]):
                            st.stats["defer_sell_volume"] += 1
                        continue
                    # Resolve dates here; only the eligibility bool reaches the scanner.
                    reserve_state = {"reserved": bool(pos.reserved)}
                    idx, px, reason, new_peak, new_peak_hm = scan_held_day(
                        o,
                        h,
                        c,
                        cost=pos.cost,
                        peak=pos.peak,
                        n_days=n_days,
                        can_sell=t1_sellable(calendar[pos.entry_idx].date(), day.date()),
                        stop_pct=stop_pct,
                        profit_base=profit_base if profit_base is not None else 0.0,
                        trail_ratio=0.0,
                        pos_trail=pos_trail,
                        limit_down=limit_down,
                        hm=hm,
                        peak_hm=int(pos.peak_hm),
                        peak_gap_min=peak_gap_min,
                        take_profit=take_profit,
                        sell_gate=sell_gate,
                        gate_code=code,
                        gate_day=day,
                        daily_closes_ending_yesterday=prev_rows["close"]
                        .astype(float)
                        .tolist(),
                        force_sell_hm=force_sell_hm,
                        reserve_limit_up=reserve_limit_up,
                        defer_limit_up=defer_limit_up,
                        limit_up=limit_up,
                        reserved=bool(pos.reserved),
                        reserve_state=reserve_state,
                    )
                    pos.peak = new_peak
                    pos.peak_hm = new_peak_hm
                    pos.reserved = bool(reserve_state["reserved"])
                    if idx >= 0:
                        fill_open = float(o[idx])
                        if limit_down > 0 and (
                            defer_sell_at_limit(fill_open, limits)
                            or defer_sell_at_limit(float(px), limits)
                        ):
                            st.stats["defer_sell_limit_down"] += 1
                            continue
                        volume_kwargs = {}
                        if st.volume_cap is not None:
                            bucket = int(hm[idx])
                            volume_kwargs = {"bucket_id": bucket, "day_i": i,
                                             "at": bucket - 1 if reason == "stop_loss:gap_open" else bucket}
                        # P2=B names only these two stop paths; other fills stay unlabeled.
                        price_rule = {
                            "stop_loss:gap_open": "minute_gap_open",
                            "stop_loss:touch": "minute_trigger_bar_close",
                        }.get(reason, "")
                        _sell(st, code, pos, px, day, reason, **volume_kwargs,
                              hm=int(hm[idx]) if price_rule else None, price_rule=price_rule)

            def _volume_bucket_for(code: str, target: int, earliest: int):
                # Mirror the quote helpers' exact/fallback row, never a later bucket.
                frame = _slice_day(minute_bars[code], day_spans.get(code, {}), ds)
                if frame is None:
                    return None
                hit = frame.loc[frame["hm"] == target]
                if not hit.empty:
                    return int(hit["hm"].iloc[0])
                eligible = frame.loc[(frame["hm"] >= earliest) & (frame["hm"] <= target)]
                return None if eligible.empty else int(eligible["hm"].iloc[-1])

            def chase_volume(code):
                return _volume_bucket_for(code, CHASE_HM, AM_OPEN)

            def pool_volume(code):
                return AM_OPEN if minute_open else _volume_bucket_for(code, BUY_HM, 14 * 60 + 30)

            def _chase_quotes_for(code: str):
                mdf = minute_bars.get(code)
                ddf = daily_bars.get(code)
                if mdf is None or ddf is None or day not in ddf.index:
                    return None
                day_m = _slice_day(mdf, day_spans.get(code, {}), ds)
                quotes = _chase_quotes(day_m) if day_m is not None else None
                if quotes is None:
                    return None
                open_px, px = quotes
                prev_rows = _previous_rows(ddf, day)
                if prev_rows.empty:
                    return None
                closes = prev_rows["close"].astype(float).tolist()
                return open_px, px, closes

            run_chase_due_day(
                st,
                pending_chase,
                day_i=i,
                day=day,
                names=names,
                allow_add=allow_add,
                buy_gate=buy_gate,
                quotes_for=_chase_quotes_for,
                volume_bucket_for=chase_volume if st.volume_cap is not None else None,
                exdiv=exdiv,
                ds=ds,
                qlib_limit_pct=qlib_limit_pct,
                allow_new_name=hooks.get("allow_new_name"),
                add_gate=hooks.get("add_gate"),
                index_blocks_add=hooks.get("index_blocks_add", True),
            )

            def _pool_quote_for(code: str):
                mdf = minute_bars.get(code)
                ddf = daily_bars.get(code)
                if mdf is None or ddf is None or day not in ddf.index:
                    return None
                day_m = _slice_day(mdf, day_spans.get(code, {}), ds)
                if day_m is None:
                    return None
                prev_rows = _previous_rows(ddf, day)
                if prev_rows.empty:
                    return None
                if minute_open:
                    opening = _open_quote_for(day_m)
                    if opening is None:
                        return None
                    volume = float(opening["volume"])
                    if not np.isfinite(volume) or volume <= 0:
                        st.stats["skip_buy_volume"] += 1
                        return None
                    px = float(opening["open"])
                else:
                    px = _buy_px(day_m)
                if px is None or px <= 0 or (minute_open and not np.isfinite(px)):
                    return None
                closes = prev_rows["close"].astype(float).tolist()
                return px, closes

            volume_skips = int(st.stats.get("skip_volume_unavailable", 0)) + int(st.stats.get("skip_volume_cap", 0))
            run_pool_buys_day(
                st,
                pending_chase,
                day_i=i,
                day=day,
                ds=ds,
                pool_days=pool_days,
                daily_quota=daily_quota,
                names=names,
                allow_add=allow_add,
                buy_gate=buy_gate,
                buy_quote_for=_pool_quote_for,
                volume_bucket_for=pool_volume if st.volume_cap is not None else None,
                volume_at=AM_OPEN - 1 if minute_open else None,
                sold_today={t["code"] for t in st.trades[day_trade_start:] if t["side"] == "SELL"}
                if hooks.get("skip_sold_today") else None,
                sizing=hooks.get("sizing", "daily_quota"),
                name_budget=hooks.get("name_budget", 1_000_000.0),
                ration=hooks.get("ration", "file_order"),
                ration_seed=hooks.get("ration_seed", 0),
                exdiv=exdiv,
                planned_for_day=hooks.get("planned_for_day"),
                cash_deploy_frac=hooks.get("cash_deploy_frac"),
                qlib_limit_pct=qlib_limit_pct,
                limit_up_chase=limit_up_chase,
                forbid_all_trade_at_limit=forbid_all_trade_at_limit,
                allow_new_name=hooks.get("allow_new_name"),
                add_gate=hooks.get("add_gate"),
                name_lot_budget=hooks.get("name_lot_budget"),
                index_blocks_add=hooks.get("index_blocks_add", True),
            )
            if minute_open:
                st.stats["skip_buy_volume"] += (
                    int(st.stats.get("skip_volume_unavailable", 0))
                    + int(st.stats.get("skip_volume_cap", 0)) - volume_skips
                )
            run_step_adds_day(
                st,
                day_i=i,
                day=day,
                ds=ds,
                names=names,
                buy_quote_for=_pool_quote_for,
                volume_bucket_for=pool_volume if st.volume_cap is not None else None,
                sizing=hooks.get("sizing", "daily_quota"),
                name_budget=hooks.get("name_budget", 1_000_000.0),
                exdiv=exdiv,
                qlib_limit_pct=qlib_limit_pct,
                forbid_all_trade_at_limit=forbid_all_trade_at_limit,
                buy_gate=buy_gate,
                name_lot_budget=hooks.get("name_lot_budget"),
                step_add=hooks.get("step_add"),
            )

        run_eod_exits(st, day=day, ds=ds, bars=daily_bars, eod_exit=hooks.get("eod_exit"),
                      hold_modes=hold_modes, exdiv=exdiv)
        append_equity_and_eod_marks(
            st,
            ds=ds,
            day=day,
            calendar_last=calendar[-1],
            mark_bars=daily_bars,
        )

    finish_pending_chase(st, pending_chase)
    return st


def run(
    start: str,
    end: str,
    *,
    total_cash: float = DEFAULT_TOTAL_CASH,
    daily_quota: float = DEFAULT_DAILY_QUOTA,
    name_budget: Optional[float] = None,
    ration: str = "file_order",
    ration_seed: int = 0,
    stop_pct: Optional[float] = None,
    profit_base: Optional[float] = None,
    tiers: Optional[dict] = None,
    tier_default: Optional[float] = None,
    pos_trail: float = POS_TRAIL,
    workers: int = 16,
    use_cache: bool = True,
    rebuild_cache: bool = False,
    pool_dir: Optional[Path] = None,
    strategy: str,
    take_profit=None,
    record_params=None,
    scores_by_day=None,
    topk=None,
    n_drop=None,
    eligible_buy=None,
    return_threshold_filter: bool = False,
    minute_source: str = "lake",
    daily_source: str = "lake",
    qlib_1min_root: Optional[Path] = None,
    qlib_day_root: Optional[Path] = None,
    dividend_type: str = "none",
) -> SimState:
    book = normalize_csv_strategy(strategy)
    if book == "version12":
        if dividend_type not in ("none", "front") or minute_source != "lake" or daily_source != "lake":
            raise ValueError(
                "version12 minute requires lake daily/minute and --dividend-type none|front"
            )
    elif dividend_type != "none":
        raise ValueError("minute --dividend-type front is supported only by version12")
    warn_stale_period_env()
    volume_required = normalize_csv_strategy(strategy) == "version11"
    if volume_required and minute_source != "lake":
        raise ValueError("version11 requires lake minute volume; qlib_1min frames do not carry it")
    if minute_source == "lake" and end > MINUTE_LAKE_END:
        print(
            f"[warn] --end {end} past minute lake {MINUTE_LAKE_END}; "
            "bars after that date are missing, use daily engine to reach today",
            flush=True,
        )
    t_pool = time.perf_counter()
    actual_pool_dir = resolve_research_pool_dir(strategy, pool_dir, repo=REPO)
    pool_days = load_pool_day_map(
        actual_pool_dir, start, end, key="ymd", empty_in_map=False
    )
    pool_names_by_day = load_pool_names_by_day(actual_pool_dir, start, end)
    t_pool = time.perf_counter() - t_pool
    if not pool_days:
        raise SystemExit(f"no pool CSVs in [{start}, {end}] under {actual_pool_dir}")
    all_codes = {c for codes in pool_days.values() for c in codes}
    from backtest.research.topk_dropout_scores import codes_from_scores

    all_codes |= codes_from_scores(scores_by_day)
    load_start = warmup_start(
        start,
        STRATEGY4_CALENDAR_SLACK_DAYS
        if book in ("version4", "version12")
        else (20 if return_threshold_filter else WARMUP_DAYS),
    )
    print(
        f"loading daily+minute: {len(all_codes)} codes, {load_start}..{end}; "
        f"pool {min(pool_days)}..{max(pool_days)} ({len(pool_days)} days)",
        flush=True,
    )
    t_daily = time.perf_counter()
    daily_domain_front = (book == "version12") or (dividend_type == "front")
    if daily_domain_front:
        from common.infra.data_root import resolve_period_root

        front_daily_root = resolve_period_root("1d") / "dividend_type=front"
        if not front_daily_root.is_dir():
            raise FileNotFoundError(f"missing front daily partition: {front_daily_root}")
    daily = load_daily_ohlc(
        all_codes,
        load_start,
        end,
        source=daily_source,
        qlib_root=qlib_day_root,
        workers=workers,
        **({"dividend_type": "front"} if daily_domain_front else {}),
    )
    if book == "version12" and (missing := all_codes - daily.keys()):
        raise ValueError(f"missing front daily bars for strategy12: {sorted(missing)}")
    t_daily = time.perf_counter() - t_daily
    cache_status: dict = {}
    t_minute = time.perf_counter()
    if dividend_type == "front":
        root = resolve_period_root("1m") / "dividend_type=front"
        if not root.is_dir():
            raise FileNotFoundError(f"missing front minute partition: {root}")
        # The existing window cache is none-domain; read the configured front tree.
        minute = _load_minute_from_lake(all_codes, load_start, end, workers=workers,
                                        lake_root=root)
        if missing := all_codes - minute.keys():
            raise ValueError(f"missing front minute bars for strategy12: {sorted(missing)} under {root}")
        cache_status["cache"] = "front_uncached"
    elif minute_source == "qlib_1min":
        compact = _load_minute_compact(
            all_codes,
            load_start,
            end,
            source="qlib_1min",
            qlib_root=qlib_1min_root,
            workers=workers,
        )
        minute = book_frames_from_compact(compact)
        cache_status["cache"] = "qlib_1min"
    else:
        minute = load_minute_bars(
            all_codes,
            load_start,
            end,
            workers=workers,
            use_cache=use_cache,
            rebuild_cache=rebuild_cache,
            status=cache_status,
            **({"include_volume": True} if volume_required else {}),
        )
    t_minute = time.perf_counter() - t_minute
    print(
        f"loaded daily {len(daily)} / minute {len(minute)} / pool days {len(pool_days)}",
        flush=True,
    )
    if return_threshold_filter:
        from backtest.research.topk_dropout_eligibility import with_return_threshold

        eligible_buy = with_return_threshold(eligible_buy, daily)
    skipped: dict[str, int] = {}
    # Human cut #151 option 2: mixed-domain strategy12 (daily front + minute none)
    # must avoid silent ex-div double adjustment. Keep ex-div explicit-only there.
    exdiv = (
        None
        if (book == "version12" or dividend_type == "front")
        else load_exdiv_ratios(all_codes, start, end, skipped_out=skipped)
    )
    index_block_new = None
    gate_book = normalize_csv_strategy(strategy)
    if gate_book in ("version8", "version8_3"):
        from backtest.research.strategy8_rules import (
            INDEX_GATE_ON,
            load_sse_ma10_block_new,
        )

        # 8.3 冻结包闸门无条件开（历史年代无开关，默认即开）。
        if INDEX_GATE_ON or gate_book == "version8_3":
            index_block_new = load_sse_ma10_block_new(start, end)
    t_sim = time.perf_counter()
    st = simulate(
        minute,
        daily,
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
        name_budget=name_budget,
        ration=ration,
        ration_seed=ration_seed,
        pool_names_by_day=pool_names_by_day,
        exdiv=exdiv,
        scores_by_day=scores_by_day,
        topk=topk,
        n_drop=n_drop,
        eligible_buy=eligible_buy,
        index_block_new=index_block_new,
    )
    if skipped.get("exdiv_skipped_no_factor"):
        st.stats["exdiv_skipped_no_factor"] = int(skipped["exdiv_skipped_no_factor"])
    st.stats["t_pool_s"] = t_pool
    st.stats["t_daily_s"] = t_daily
    st.stats["t_minute_s"] = t_minute
    st.stats["t_sim_s"] = time.perf_counter() - t_sim
    st.stats["cache"] = cache_status.get("cache", "")
    st.stats["codes_missing"] = max(0, len(all_codes) - min(len(daily), len(minute)))
    if book == "version12":
        st.stats["daily_signal_domain"] = "front"
        st.stats["minute_fill_domain"] = dividend_type
        st.stats["price_domain"] = dividend_type
    return st


def main(argv: Optional[list] = None) -> int:
    ap = argparse.ArgumentParser(
        description="CSV-mode vectorized minute backtest (required --strategy)",
        epilog=help_lock_all(HELP_LOCK),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    add_csv_backtest_common_args(
        ap,
        repo=REPO,
        end_default=MINUTE_LAKE_END,
        end_help=(
            f"minute lake last day is {MINUTE_LAKE_END}; short parity window: 20251104"
        ),
        cash_total_default=DEFAULT_TOTAL_CASH,
        daily_quota_default=DEFAULT_DAILY_QUOTA,
    )
    ap.add_argument("--no-cache", action="store_true", help="skip minute window cache")
    ap.add_argument(
        "--rebuild-cache", action="store_true", help="reload lake and rewrite cache"
    )
    ap.add_argument("--minute-source", choices=("lake", "qlib_1min"), default="lake")
    ap.add_argument("--daily-source", choices=("lake", "qlib_day"), default="lake")
    ap.add_argument("--dividend-type", choices=("none", "front"), default="none",
                    help="version12 minute fills allow none/front; daily signals fixed to 1d/front")
    ap.add_argument(
        "--qlib-1min-root",
        help="qlib my_data_1min root; implies --minute-source qlib_1min",
    )
    ap.add_argument("--qlib-day-root", help="qlib daily bin root for --daily-source qlib_day")
    ap.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="artifact directory; default backtest_output/csv_minute_{book}_{start}_{end}",
    )
    args = ap.parse_args(argv if argv is not None else None)
    pool_dir = resolve_research_pool_dir(args.strategy, args.pool_dir, repo=REPO)
    minute_source = "qlib_1min" if args.qlib_1min_root else args.minute_source
    daily_source = "qlib_day" if args.qlib_day_root else args.daily_source

    st = run(
        args.start,
        args.end,
        total_cash=args.cash_total,
        daily_quota=args.daily_quota,
        workers=args.workers,
        pool_dir=pool_dir,
        use_cache=not args.no_cache,
        rebuild_cache=args.rebuild_cache,
        minute_source=minute_source,
        daily_source=daily_source,
        dividend_type=args.dividend_type,
        qlib_1min_root=Path(args.qlib_1min_root) if args.qlib_1min_root else None,
        qlib_day_root=Path(args.qlib_day_root) if args.qlib_day_root else None,
        **csv_run_kwargs_from_args(args),
    )
    book = engine_book(args.strategy)
    engine = f"csv_minute_{book}"
    text = summarize(st, args.cash_total, args.start, args.end, engine=engine)
    cmp = maybe_compare_daily(
        st.equity_curve, args.start, args.end, this_label=engine, book=book
    )
    if cmp:
        text = text + "\n" + cmp
    print(text)
    tag = f"{engine}_{args.start}_{args.end}"
    out_dir = Path(args.out_dir) if args.out_dir else Path(REPO) / "backtest_output" / tag
    if out_dir.exists() and any(out_dir.iterdir()):
        raise SystemExit(f"refuse overwrite existing {out_dir}; pick a new stamp directory")
    write_run_artifacts(
        out_dir,
        st,
        text,
        help_lock_for(args.strategy, shared=HELP_LOCK),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
