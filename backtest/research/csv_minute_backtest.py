#!/usr/bin/env python3
"""CSV 模式分钟向量化回测（共用买侧/资金引擎，卖点由策略书提供）。

与日线近似版同一套 CSV 额度 / T+1 / 涨停跳过 / force_min / 0.1% 双边佣金。
卖点按分钟路径扫描：峰值用 bar high，现价用 close；开盘已跌破止损则按开盘价
成交。必须从已注册策略中显式指定 `--strategy`，无缺省。买入用 14:55 分钟收盘
（湖内时间为「中国交易时钟标成 UTC」——09:30 UTC = 09:30 CST）。

version7 为 minute-only 注册书：main 拥有日循环与状态，minute_cash_order 拥有
symbol-major 默认与 X02 chronological 调度；v7 / APP 保留各自 CLI 与原生账本。

用法：
    python backtest/research/csv_minute_backtest.py --strategy version6 --start 20251023 --end 20251104
    python backtest/research/csv_minute_backtest.py --strategy version8 --start 20251023 --end 20260909
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, REPO)

from backtest.research.sell_pending_observability import (  # noqa: E402
    pending_callback, carry_session, finish_pending_sells, record_limit,
)

from backtest.research.strategy9_rules import (  # noqa: E402
    evaluate_stop_range, RANGE_LOOKBACK_CALENDAR_DAYS,
    evaluate_version9_exit, plan_stop_price, plan_close_reason,
)

from backtest.research.csv_ledger import (  # noqa: E402
    CHASE_HM,
    DEFAULT_TOTAL_CASH,
    PEAK_GAP_MIN,
    QLIB_CLOSE_COST,
    QLIB_MIN_COST,
    QLIB_OPEN_COST,
    IndependentExitPosition,
    SimState,
    chase_decision as chase_decision,
    configure_s8,
    reject_short_cash_override,
    execute_buy as execute_buy,
    exit_positions,
    held_fill_key,
    finish_pending_chase,
    queue_limit_up_chase as queue_limit_up_chase,
    hit_limit_down,
    hit_limit_up,
    last_close_mark as last_close_mark,
    peak_gap_blocks,
    _sell,
    _ymd,
    rescale_position,
    rescale_s8_groups,
    apply_exdiv_economics,
)

from backtest.research.ashare_exdiv_economics import EconomicLookup, ExDivEconomics  # noqa: E402

from backtest.research.exdiv_map import k_for, load_exdiv_ratios, mapped_prev_close  # noqa: E402
from backtest.research.ashare_session import defer_sell_open_or_fill, t1_sellable  # noqa: E402
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
from backtest.research.minute_engine_policies import (  # noqa: E402
    MinutePolicyContext, minute_policy_for,
)

from backtest.research.csv_pool import (  # noqa: E402
    load_pool_day_map,
    load_pool_names_by_day,
)
from backtest.research.csv_strategy_books import (  # noqa: E402
    add_csv_backtest_common_args,
    apply_csv_strategy,
    get_minute_book,
    csv_run_kwargs_from_args,
    engine_book,
    resolve_daily_quota,
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
    require_market_marks,
    run_chase_due_day,
    run_eod_exits,
    run_pool_buys_day,
    run_step_adds_day,
)

from backtest.research.ashare_volume_cap import VolumeCap, VolumeLookup  # noqa: E402
from backtest.research.csv_minute_volume import (  # noqa: E402
    completed_minute_volumes, validate_participation_rate,
)
from backtest.research.participation_rate_precheck import (  # noqa: E402
    precheck_cli_participation_rate,
    precheck_completed_bucket_samples,
)
from backtest.research.minute_audit import audit_scope, write_audit
from backtest.research.fill_config import FillConfig, default_fill_config, book_fill_defaults, is_open_fill
from backtest.research.minute_stop_trigger import (
    blocked_bar, target_fill, validate_low, validate_minute_stop_trigger,
)
from backtest.research.minute_cash_order import (
    HeldMinuteCursor,
    advance_independent_exit,
    peak_dd_clear_exits,
    fill_side_pending,
    run_chronological_day,
    scale_out_exits,
    step_stop_exits,
)
from backtest.research.tail_window_buy import (
    resolve_tail_volume_unit,
    tail_policy,
    validate_tail_options,
)
from backtest.research.topk_minute_exec import (
    TOPK_EXEC_HELP_LOCK, parse_topk_exec, validate_topk_exec, write_topk_exec_audit,
)

# Preserve historical loader aliases used by callers and tests.
_ = (_annotate, _load_minute_from_lake, _read_one_minute)

BUY_HM = 14 * 60 + 55
CLOSE_CLEAR_HM = 15 * 60

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

from backtest.research.minute_entry_validation import validate_minute_entry
from backtest.research.minute_held_scan_core import (
    HeldMinuteCursor, _LIMIT_EPS, sell_allowed, stop_touch, limit_down_blocks,
    stop_trigger, gap_stop, force_due,
)

try:
    from numba import njit as _njit  # type: ignore

    from numba.extending import register_jitable

    # register_jitable returns the callable numba will compile; rebind so the
    # njit kernel closes over the registered helpers, not the raw Python ones.
    sell_allowed = register_jitable(sell_allowed)
    stop_touch = register_jitable(stop_touch)
    limit_down_blocks = register_jitable(limit_down_blocks)
    stop_trigger = register_jitable(stop_trigger)
    gap_stop = register_jitable(gap_stop)
    force_due = register_jitable(force_due)
    peak_gap_blocks = register_jitable(peak_gap_blocks)
    trail_hits = register_jitable(trail_hits)

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
        trigger = stop_trigger(cost, stop_pct) if stop_enabled else 0.0
        new_peak = peak
        new_peak_hm = peak_hm
        n = len(c)
        for i in range(n):
            if not sell_allowed(can_sell, n_days):
                continue
            hi = h[i]
            cur_hm = hm[i]
            if hi > new_peak:
                new_peak = hi
                new_peak_hm = cur_hm
            px_open = o[i]
            px_close = c[i]
            if limit_down_blocks(px_open, limit_down):
                continue
            if stop_enabled and gap_stop(px_open, trigger):
                return i, px_open, 1, new_peak, new_peak_hm
            ret = px_close / cost - 1.0
            if stop_enabled and stop_touch(ret, stop_pct):
                return i, px_close, 2, new_peak, new_peak_hm
            gap = cur_hm - new_peak_hm
            peak_blocked = new_peak_hm >= 0 and peak_gap_blocks(gap, peak_gap_min)
            if not peak_blocked:
                if trail_hits(px_close, cost, new_peak, profit_base, trail_ratio):
                    return i, px_close, 3, new_peak, new_peak_hm
            if has_force and force_due(cur_hm, force_sell_hm):
                if limit_down_blocks(px_close, limit_down):
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
    l: Optional[np.ndarray] = None,
    minute_stop_trigger: str = "close",
    fill_config: FillConfig | None = None,
    take_profit_pct: Optional[float] = None,
    cost: float,
    peak: float,
    n_days: int,
    can_sell: bool,
    stop_pct: Optional[float],
    fill_state: dict | None = None,
    session_exit_reason=None, session_volume=None, session_stats=None,
    pending_log=None,
    version9_plan=None,
    version9_max_hold=False,
    stop_range_ratio: Optional[float] = None,
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
    close_clear=None,
) -> tuple[int, float, str, float, int]:
    """Python reference implementation of the minute sell scan."""
    validate_low(minute_stop_trigger, l, c)
    cursor = HeldMinuteCursor(
        o, h, c, cost, peak, n_days, can_sell, stop_pct, profit_base, trail_ratio,
        stop_range_ratio=stop_range_ratio,
        pos_trail=pos_trail, limit_down=limit_down, hm=hm, peak_hm=peak_hm,
        peak_gap_min=peak_gap_min, take_profit=take_profit, sell_gate=sell_gate,
        gate_code=gate_code, gate_day=gate_day,
        daily_closes_ending_yesterday=daily_closes_ending_yesterday,
        force_sell_hm=force_sell_hm, reserve_limit_up=reserve_limit_up,
        defer_limit_up=defer_limit_up, limit_up=limit_up, reserved=reserved,
        reserve_state=reserve_state, exit_plan=exit_plan, exit_state=exit_state,
        close_clear=close_clear, l=l, minute_stop_trigger=minute_stop_trigger,
        fill_config=fill_config, fill_state=fill_state, pending_log=pending_log,
        session_exit_reason=session_exit_reason, session_volume=session_volume, session_stats=session_stats,
        take_profit_pct=take_profit_pct, version9_plan=version9_plan,
        version9_max_hold=version9_max_hold,
    )
    for i in range(len(c)):
        for phase in ("open", "close"):
            event = cursor.advance(i, phase)
            if event is not None:
                return (*event, cursor.peak, cursor.peak_hm)
    if "pending" in cursor.fill_state and fill_state is None:
        raise ValueError("next_bar_open carry requires a fill_state out-param across sessions")
    return -1, float("nan"), "", cursor.peak, cursor.peak_hm


def scan_held_day(
    o: np.ndarray,
    h: np.ndarray,
    c: np.ndarray,
    *,
    l: Optional[np.ndarray] = None,
    minute_stop_trigger: str = "close",
    fill_config: FillConfig | None = None,
    take_profit_pct: Optional[float] = None,
    cost: float,
    peak: float,
    n_days: int,
    can_sell: bool,
    stop_pct: Optional[float],
    fill_state: dict | None = None,
    session_exit_reason=None, session_volume=None, session_stats=None,
    pending_log=None,
    version9_plan=None,
    version9_max_hold=False,
    stop_range_ratio: Optional[float] = None,
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
    close_clear=None,
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
        session_volume is None
        and minute_stop_trigger == "close"
        and version9_plan is None
        and stop_range_ratio is None
        and _want_numba_scan(use_numba)
        and _NUMBA_SCAN_AVAILABLE
        and sell_gate is None
        and take_profit is None
        and close_clear is None
        and not reserve_limit_up
        and not defer_limit_up
        and reserve_state is None
        and exit_plan is None
    )
    if can_offload and fill_config is not None and fill_config != default_fill_config(minute_stop_trigger):
        raise ValueError("non-default fill_config is unsupported by numba; select the Python backend")
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
        l=l, minute_stop_trigger=minute_stop_trigger, take_profit_pct=take_profit_pct,
        fill_config=fill_config, fill_state=fill_state, pending_log=pending_log,
        session_exit_reason=session_exit_reason, session_volume=session_volume, session_stats=session_stats,
        cost=cost,
        peak=peak,
        n_days=n_days,
        can_sell=can_sell,
        stop_pct=stop_pct,
        version9_plan=version9_plan, version9_max_hold=version9_max_hold,
        stop_range_ratio=stop_range_ratio,
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
        close_clear=close_clear,
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
    star_lot_declare_check: bool = False,
    scores_by_day=None,
    topk=None,
    n_drop=None,
    eligible_buy=None,
    index_block_new=None,
    participation_rate: float | None = None,
    volume_for_bucket: VolumeLookup | None = None,
    stop_fill: Optional[str] = None,
    keep_buy_vacancy: bool = False,
    buy_cost_rate: Optional[float] = None,
    sell_cost_rate: Optional[float] = None,
    min_cost: Optional[float] = None,
    fix_s12_price_domain: bool = False,
    s12_price_context=None,
    fix_s11_exit_domain: bool = False,
    version9_sell=None,
    max_hold: bool = False,
    fix_s81_band_precision: bool = False,
    signal_bars_front: dict[str, pd.DataFrame] | None = None,
    minute_stop_trigger: str = "close",
    fill_config: FillConfig | None = None,
    exdiv_ref_fen: bool = False,
    fix_minute_cash_order: bool = False,
    tail_window_buy: bool = False,
    tail_volume_unit: str | None = "shares",
    audit_sink=None,
    topk_exec: str = "close",
    limit_walkdown: bool = False,
    topk_limit_rule: str = "qlib",
    policy_context: MinutePolicyContext | None = None,
) -> SimState:
    """Opt-in cap uses caller-attested completed minutes; daily volume is unused.

    exdiv_economics is an explicit (symbol, YYYYMMDD) -> ExDivEvent lookup for
    raw bars. None retains the baseline; E-R6 ratios never imply entitlements.
    """
    book = get_minute_book(strategy)
    native_v7 = book.name == "version7"
    if native_v7:
        if fill_config is not None:
            raise ValueError("version7 does not accept FillConfig overrides")
        validate_tail_options(tail_window_buy, fix_minute_cash_order, tail_volume_unit)
        if tail_window_buy:
            tail_volume_unit = resolve_tail_volume_unit(tail_volume_unit)
        hooks = book.apply(fix_minute_cash_order=fix_minute_cash_order)
        policy = minute_policy_for(hooks)
        if policy.schedule not in {"symbol_major", "chronological"}:
            raise ValueError("version7 requires a native schedule policy")
        from backtest.research import strategy7_engine as v7
        from backtest.research.ashare_fees import DEFAULT_SCHEDULE
        from backtest.research.minute_cash_order import run_symbol_major_day, run_v7_chronological_day
        frames, minutes, closes, pools, calendar, gate = v7.prepare_main_inputs(
            minute_bars, daily_bars, pool_days, start, end, policy_context)
        st = v7.SimResult(float(total_cash))
        configure_s8(st, hooks)
        if exdiv_economics is not None:
            st.exdiv_economics = ExDivEconomics(exdiv_economics)
        if participation_rate is not None:
            st.volume_cap = VolumeCap(participation_rate, volume_for_bucket)
        fee = (policy_context.fee_schedule if policy_context and
               policy_context.fee_schedule is not None else DEFAULT_SCHEDULE)
        last_prices = {}
    if not native_v7:
        validate_minute_entry(strategy, stage="sell", version9_sell=version9_sell, max_hold=max_hold)
        validate_minute_stop_trigger(minute_stop_trigger, normalize_csv_strategy(strategy), fix_s11_exit_domain)
        validate_topk_exec(topk_exec, strategy, limit_walkdown, topk_limit_rule)
        validate_tail_options(tail_window_buy, fix_minute_cash_order, tail_volume_unit)
        if tail_window_buy:
            tail_volume_unit = resolve_tail_volume_unit(tail_volume_unit)
        validate_minute_entry(strategy, stage="tail", tail_window_buy=tail_window_buy)
        validate_minute_entry(strategy, stage="cash", fix_minute_cash_order=fix_minute_cash_order)
        if audit_sink is not None and normalize_csv_strategy(strategy) == "version12":
            raise ValueError("X-02 execution audit is not applicable to version12")
        if fix_s12_price_domain:
            from backtest.research.signal_price_domain import S12PriceContext

            if normalize_csv_strategy(strategy) != "version12":
                raise ValueError("--fix-s12-price-domain applies only to version12")
            if exdiv is not None:
                raise ValueError("--fix-s12-price-domain requires exdiv=None (no double adjustment)")
            if not isinstance(s12_price_context, S12PriceContext):
                raise ValueError("--fix-s12-price-domain requires an explicit validated s12_price_context")
            s12_price_context.validate_simulation(minute_bars, daily_bars, pool_days, start, end)
        elif s12_price_context is not None:
            raise ValueError("s12_price_context requires fix_s12_price_domain=True")
        if signal_bars_front is not None and not fix_s11_exit_domain:
            raise ValueError("signal_bars_front requires version11 + fix_s11_exit_domain=True")
        if fix_s11_exit_domain:
            validate_minute_entry(strategy, stage="s11", fix_s11_exit_domain=fix_s11_exit_domain)
            if signal_bars_front is None:
                raise ValueError("fix_s11_exit_domain requires independent signal_bars_front")
            from backtest.research.s11_exit_domain import validate_signal_bars

            validate_signal_bars(
                daily_bars, signal_bars_front, start=start, end=end,
                required_codes={c for codes in pool_days.values() for c in codes},
            )
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
            **({"version9_sell": version9_sell} if version9_sell is not None else {}),
            **({"max_hold": True} if max_hold else {}),
            **({"fix_s81_band_precision": True} if fix_s81_band_precision else {}),
            scores_by_day=scores_by_day,
            topk=topk,
            n_drop=n_drop,
            eligible_buy=eligible_buy,
            keep_buy_vacancy=keep_buy_vacancy,
            index_block_new=index_block_new,
            stop_fill=stop_fill,
        )
        if topk_exec != "close" or limit_walkdown:
            reject_short_cash_override(hooks, "topk_minute_exec")
        if topk_limit_rule == "real":
            hooks["qlib_limit_pct"] = None
        stop_pct = hooks["stop_pct"]
        stop_fill = str(hooks.get("stop_fill") or "touch").strip().lower()
        if stop_fill == "close":
            raise SystemExit(
                "--stop-fill close is daily EOD close only; "
                "minute entry refuses it (bar close is not 当日收盘)"
            )
        if stop_fill != "touch":
            raise SystemExit(f"--stop-fill must be touch or close, got {stop_fill}")
        take_profit = hooks["take_profit"]
        buy_gate = hooks.get("buy_gate")
        sell_gate = hooks.get("sell_gate")
        peak_gap_min = int(hooks["peak_gap_min"])
        force_sell_hm = hooks.get("force_sell_hm")
        close_clear = hooks.get("close_clear")
        reserve_limit_up = bool(hooks.get("reserve_limit_up"))
        defer_limit_up = bool(hooks.get("defer_limit_up"))
        policy = minute_policy_for(hooks)
        calendar = (build_calendar(daily_bars, start, end) if policy.calendar is None
                    else policy.calendar(minute_bars=minute_bars, daily_bars=daily_bars,
                                         pool_days=pool_days, start=start, end=end,
                                         context=policy_context))

        initialize = init_sim_state if policy.initialize is None else policy.initialize
        st, pending_chase, names_asof = initialize(
            hooks,
            total_cash=total_cash,
            bars_loaded=len(minute_bars),
            pool_days=pool_days,
            pool_names=pool_names,
            pool_names_by_day=pool_names_by_day,
            daily_quota=daily_quota,
            **({"context": policy_context} if policy.initialize is not None else {}),
        )
        defaults = book_fill_defaults(hooks, minute_stop_trigger)
        if hooks.get("run_minute_day") is not None:
            raise ValueError("run_minute_day is retired; use minute_session with HeldMinuteCursor")
        if fill_config is not None and fill_config != defaults["stop"]:
            if "bind_absolute_exit" in hooks and fill_config.trigger_basis != "bar_low":
                raise ValueError("absolute_exit requires trigger_basis=bar_low")
        if hooks.get("minute_open") and fill_config is None:
            fill_config = defaults["stop"]
        side_fill_config = None if fill_config == defaults["stop"] else fill_config
        held_fill_states = {}
        st.held_fill_states = held_fill_states
        absolute_exit = hooks["bind_absolute_exit"](st, daily_bars) if "bind_absolute_exit" in hooks else None
        configure_s8(st, hooks)
        if minute_stop_trigger == "hl" or absolute_exit:
            st.stats["minute_stop_trigger"] = "hl"
        if topk_exec != "close" or limit_walkdown or topk_limit_rule != "qlib":
            st.stats.update(topk_limit_rule=topk_limit_rule, topk_exec=topk_exec, limit_retry_fills=0, limit_retry_expired=0)
            st.topk_exec_audit = []
            if limit_walkdown:
                st.stats.update(limit_walkdown=True, walkdown_fills=0, walkdown_exhausted=0)
        if buy_cost_rate is not None:
            st.buy_cost_rate = float(buy_cost_rate)
        if sell_cost_rate is not None:
            st.sell_cost_rate = float(sell_cost_rate)
        if min_cost is not None:
            st.min_cost = float(min_cost)
        st.stats["buy_cost_rate"] = st.buy_cost_rate
        st.stats["sell_cost_rate"] = st.sell_cost_rate
        st.stats["min_cost"] = st.min_cost
        if participation_rate is not None:
            st.volume_cap = VolumeCap(participation_rate, volume_for_bucket)
        st.star_lot_declare_check = star_lot_declare_check
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
        if native_v7:
            policy.day_start(st, day=day, day_i=i, context=policy_context)
            cleared_today = set()
            needed = list(dict.fromkeys(pools.get(day, []) + list(st.positions)))
            if frames is not None:
                symbols_today = {symbol: rows for symbol in needed
                                 if (rows := v7._day_frame_records(frames.get(symbol), day))}
                ordered = needed
            else:
                symbols_today = minutes.get(day, {})
                ordered = list(dict.fromkeys(needed + list(symbols_today)))
            run_native_day = (run_v7_chronological_day if policy.schedule == "chronological"
                              else run_symbol_major_day)
            run_native_day(
                st, day, calendar, symbols_today, ordered, pools.get(day, []),
                closes, last_prices, cleared_today, exdiv=exdiv, names=pool_names,
                names_by_day=pool_names_by_day, blocked_new=gate.get(day, False),
                fee=fee, audit_sink=audit_sink, session=hooks["minute_session"],
                **({"tail_window_buy": tail_window_buy, "tail_volume_unit": tail_volume_unit}
                   if policy.schedule == "chronological" else {}))
            policy.append_marks(st, day=day, last_prices=last_prices,
                                context=policy_context)
            continue
        ds = _ymd(day)
        day_trade_start = len(st.trades)
        if st.exdiv_economics is not None:
            st.cash += st.exdiv_economics.settle(ds)
        names = names_asof(ds)
        st.daily_quota_used = 0.0

        if policy.day_start is not None:
            policy.day_start(st, day=day, ds=ds, day_i=i, context=policy_context)

        if policy.chronological(hooks, fix_cash_order=fix_minute_cash_order,
                                topk_exec=topk_exec, limit_walkdown=limit_walkdown):
            run_chronological_day(
                st, pending_chase, hooks=hooks, minute_bars=minute_bars,
                daily_bars=daily_bars, pool_days=pool_days, day_i=i, day=day,
                ds=ds, names=names, daily_quota=daily_quota, exdiv=exdiv,
                calendar=calendar,
                slice_day=lambda code, date: _slice_day(
                    minute_bars[code], day_spans.get(code, {}), date),
                profit_base=profit_base, pos_trail=pos_trail, audit_sink=audit_sink,
                tail_window_buy=tail_window_buy, tail_volume_unit=tail_volume_unit,
                exdiv_ref_fen=exdiv_ref_fen,
                minute_stop_trigger=minute_stop_trigger,
                fill_config=fill_config, held_fill_states=held_fill_states,
                topk_exec=topk_exec, limit_walkdown=limit_walkdown,
                price_context=s12_price_context if fix_s12_price_domain else None,
            )
        else:
            bind_opening = hooks.get("bind_opening_held")
            if callable(bind_opening):
                bind_opening(ds, list(st.positions.keys()))

            # Price-add books need the post-14:55 group scan to observe their
            # new weighted cost. Other OFF books retain full-day exits first.
            split_group_scan = hooks.get("name") in {
                "version6_1", "version6_2", "version6_3", "version6_4", "version6_5", "version6_6", "version6_7", "version6_8", "version6_9", "version6_10", "version6_11", "version6_12", "version6_13", "version6_14", "version6_15", "version6_16", "version6_17", "version6_18", "version6_19", "version6_20", "version6_21", "version6_22", "version6_23", "version6_24", "version6_25", "version6_26", "version6_27", "version6_28", "version6_29", "version6_30", "version6_31", "version6_32", "version6_33", "version6_34", "version6_35", "version6_36", "version6_37", "version6_38", "version6_39", "version6_40", "version6_41", "version6_42", "version6_43", "version6_44", "version8", "version8_3", "version8_4", "version8_5",
            } and hooks.get("sizing") == "per_name"
            post_group_scans = []
            confirm_peaks = {}
            s8_confirm = hooks.get("name") == "version8_3" and hooks.get("sizing") == "per_name"
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
                    rescale_s8_groups(st, code, kk)
                    for pos in list(st.positions.get(code, [])):
                        rescale_position(pos, kk)
                        st.stats["exdiv_adjusted_lots"] = (
                            int(st.stats.get("exdiv_adjusted_lots", 0)) + 1
                        )
                prev_close, did_map = mapped_prev_close(
                    exdiv, code, ds, float(prev_rows.iloc[-1]["close"]), **({"fen_round": True} if exdiv_ref_fen else {})
                )
                if did_map:
                    st.stats["exdiv_prev_close_mapped"] = (
                        int(st.stats.get("exdiv_prev_close_mapped", 0)) + 1
                    )
                limits = book_limit_prices(
                    code, prev_close, names, qlib_limit_pct=qlib_limit_pct, as_of=ds
                )
                if limits is None:
                    st.stats["skip_unknown_board"] += 1
                    continue
                limit_up, limit_down = limits
                o = day_m["open"].to_numpy(np.float64)
                h = day_m["high"].to_numpy(np.float64)
                c = day_m["close"].to_numpy(np.float64)
                hm = day_m["hm"].to_numpy(np.int64)
                if s8_confirm:
                    prefix_high = max((float(hi) for hi in h[hm <= BUY_HM] if hi > 0), default=0.0)
                    for pos in st.positions.get(code, []):
                        confirm_peaks[id(pos)] = max(
                            float(pos.peak), prefix_high if pos.entry_idx < i else 0.0,
                        )
                if absolute_exit:
                    line = absolute_exit(code, day)
                    if line is not None and float(day_m["low"].min()) <= line:
                        for lot in st.positions.get(code, []):
                            if lot.entry_idx >= i:
                                lot.pending_exit = "stop_loss:touch|t1_deferred"
                for pos in exit_positions(st, code, i, day=day):
                    if getattr(pos, "ride_with", None) is not None:
                        continue
                    n_days = i - pos.entry_idx
                    if isinstance(pos, IndependentExitPosition):
                        cursor = HeldMinuteCursor(
                            o, h, c, cost=pos.cost, peak=pos.peak,
                            l=day_m["low"].to_numpy(np.float64) if minute_stop_trigger == "hl" or absolute_exit or (fill_config and fill_config.trigger_basis == "bar_low") else None,
                            fill_config=fill_config, fill_state=held_fill_states.setdefault(held_fill_key(pos), {}),
                            pending_log=pending_callback(st, code, pos, day),
                            minute_stop_trigger="hl" if absolute_exit else minute_stop_trigger,
                            take_profit_pct=st.stats.get("profit_target"),
                            n_days=n_days,
                            can_sell=t1_sellable(calendar[pos.entry_idx].date(), day.date()),
                            stop_pct=stop_pct,
                            profit_base=profit_base if profit_base is not None else 0.0,
                            trail_ratio=0.0, pos_trail=pos_trail,
                            limit_down=limit_down, hm=hm, peak_hm=int(pos.peak_hm),
                            peak_gap_min=peak_gap_min, take_profit=take_profit,
                            sell_gate=sell_gate, gate_code=code, gate_day=day,
                            daily_closes_ending_yesterday=prev_rows["close"].astype(float).tolist(),
                            force_sell_hm=force_sell_hm,
                            reserve_limit_up=reserve_limit_up,
                            defer_limit_up=defer_limit_up, limit_up=limit_up,
                            reserved=bool(pos.reserved), close_clear=close_clear,
                        )
                        for bar_idx, at_hm in enumerate(hm):
                            if split_group_scan and int(at_hm) > BUY_HM:
                                continue
                            for phase in ("open", "close"):
                                advance_independent_exit(
                                    st, code, pos, cursor, bar_idx, phase, limits,
                                    day=day, day_i=i, audit_sink=audit_sink,
                                )
                                if phase == "open":
                                    fill_side_pending(st, code, pos, float(o[bar_idx]), day, i,
                                                      limits, hm=int(at_hm))
                                if phase == "close" and hooks.get("step_stop_pct"):
                                    step_stop_exits(
                                        st, code, pos, float(c[bar_idx]), day, i,
                                        limits, step_stop_pct=hooks["step_stop_pct"],
                                        fill_config=side_fill_config, open_px=float(o[bar_idx]),
                                        low=(float(day_m["low"].iloc[bar_idx])
                                             if side_fill_config and side_fill_config.trigger_basis == "bar_low" else None),
                                        hm=int(at_hm),
                                    )
                                if phase == "close" and hooks.get("scale_out_step"):
                                    scale_out_exits(
                                        st, code, pos, float(c[bar_idx]), day, i,
                                        limits, scale_step=hooks["scale_out_step"],
                                        scale_frac=hooks.get("scale_out_frac", 0.05),
                                        fill_config=side_fill_config, open_px=float(o[bar_idx]),
                                        hm=int(at_hm),
                                    )
                                if phase == "close" and hooks.get("peak_dd_exit"):
                                    peak_dd_clear_exits(
                                        st, code, pos, float(c[bar_idx]), day, i,
                                        limits,
                                        peak_dd_exit=hooks["peak_dd_exit"],
                                        fill_config=side_fill_config, open_px=float(o[bar_idx]),
                                        peak_dd_sessions=hooks.get("peak_dd_sessions", 15),
                                        hm=int(at_hm),
                                    )
                        if split_group_scan:
                            post_group_scans.append((code, pos, cursor, limits))
                        continue
                    # Resolve dates here; only the eligibility bool reaches the scanner.
                    reserve_state = {"reserved": bool(pos.reserved)}
                    v9_plan = (evaluate_version9_exit(hooks, ddf, day, st.stats)
                               if "version9_exit" in hooks and n_days >= 1 else None)
                    idx, px, reason, new_peak, new_peak_hm = scan_held_day(
                        o,
                        h,
                        c,
                        l=day_m["low"].to_numpy(np.float64) if minute_stop_trigger == "hl" or absolute_exit or (fill_config and fill_config.trigger_basis == "bar_low") else None,
                        session_exit_reason=pos.pending_exit,
                        session_volume=day_m["volume"].to_numpy(np.float64) if minute_open else None,
                        session_stats=st.stats,
                        minute_stop_trigger="hl" if absolute_exit else minute_stop_trigger,
                        fill_config=fill_config, fill_state=held_fill_states.setdefault(held_fill_key(pos), {}),
                        pending_log=pending_callback(st, code, pos, day),
                        take_profit_pct=v9_plan["take_profit_pct"] if v9_plan is not None else st.stats.get("profit_target"),
                        cost=pos.cost,
                        peak=pos.peak,
                        n_days=n_days,
                        can_sell=t1_sellable(calendar[pos.entry_idx].date(), day.date()),
                        stop_pct=stop_pct,
                        version9_plan=v9_plan, version9_max_hold=max_hold,
                        stop_range_ratio=((1 - absolute_exit(code, day) / pos.cost) if absolute_exit else evaluate_stop_range(hooks, ddf, day, st.stats)
                                          if (absolute_exit or "stop_range" in hooks) and n_days >= 1 else None),
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
                        close_clear=close_clear,
                    )
                    if absolute_exit and idx < 0 and float(day_m["low"].min()) <= absolute_exit(code, day):
                        pos.pending_exit = "stop_loss:touch"
                    pos.peak = new_peak
                    pos.peak_hm = new_peak_hm
                    pos.reserved = bool(reserve_state["reserved"])
                    if idx >= 0:
                        fill_open = float(o[idx])
                        if limit_down > 0 and (
                            defer_sell_open_or_fill(fill_open, float(px), limits)
                        ):
                            st.stats["defer_sell_limit_down"] += 1
                            record_limit(st, code, pos.shares, day, int(hm[idx]), fill_open, limits, key=held_fill_key(pos))
                            continue
                        volume_kwargs = {}
                        if st.volume_cap is not None:
                            bucket = int(hm[idx])
                            volume_kwargs = {"bucket_id": bucket, "day_i": i,
                                             "at": bucket - 1 if is_open_fill(reason) or (minute_open and fill_config.fill_timing == "next_bar_open") else bucket}
                        # P2=B names only these two stop paths; other fills stay unlabeled.
                        price_rule = {
                            "stop_loss:gap_open": "minute_gap_open",
                            "stop_loss:touch": "minute_stop_price" if minute_stop_trigger == "hl" else "minute_trigger_bar_close",
                        }.get(reason, "")
                        if minute_open:
                            price_rule = "minute_trigger_bar_close"
                        if reason.endswith(":next_open") or (minute_open and fill_config.fill_timing == "next_bar_open"):
                            price_rule = "minute_pending_next_open"
                        with audit_scope(
                            audit_sink, decision_hm=int(hm[idx]), quote_hm=int(hm[idx]),
                            phase="open" if is_open_fill(reason) or (minute_open and fill_config.fill_timing == "next_bar_open") else "close",
                        ):
                            before = len(st.trades)
                            _sell(st, code, pos, px, day, reason, **volume_kwargs,
                                  hm=int(hm[idx]) if price_rule else None, price_rule=price_rule)
                        if minute_open and any(t["side"] == "SKIP" and t["reason"].startswith("skip_volume") for t in st.trades[before:]):
                            st.stats["defer_sell_volume"] += 1

            def _volume_bucket_for(code: str, target: int, earliest: int):
                # Mirror the quote helpers' exact/fallback row, never a later bucket.
                if code not in minute_bars:
                    return None
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

            with audit_scope(audit_sink, decision_hm=CHASE_HM, phase="close", quote_for=chase_volume):
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
                    exdiv=exdiv, exdiv_ref_fen=exdiv_ref_fen,
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
            if callable(hooks.get("breakout_day")):
                hooks["breakout_day"](
                    st, day_i=i, day=day, ds=ds, names=names, pool_days=pool_days,
                    buy_quote_for=_pool_quote_for, exdiv=exdiv,
                    exdiv_ref_fen=exdiv_ref_fen, qlib_limit_pct=qlib_limit_pct,
                )
            with audit_scope(audit_sink, decision_hm=AM_OPEN if minute_open else BUY_HM,
                phase="open" if minute_open else "close", quote_for=pool_volume):
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
                    exdiv=exdiv, exdiv_ref_fen=exdiv_ref_fen,
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
            with audit_scope(audit_sink, decision_hm=AM_OPEN if minute_open else BUY_HM,
                phase="open" if minute_open else "close", quote_for=pool_volume):
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
                    exdiv=exdiv, exdiv_ref_fen=exdiv_ref_fen,
                    qlib_limit_pct=qlib_limit_pct,
                    forbid_all_trade_at_limit=forbid_all_trade_at_limit,
                    buy_gate=buy_gate,
                    name_lot_budget=hooks.get("name_lot_budget"),
                    step_add=hooks.get("step_add"),
                    # Clamp, rather than change the sell scanner's peak state.
                    # A T+0 chase lot has no snapshot and keeps its entry peak.
                    confirm_peak_for=(
                        lambda _code, pos: min(float(pos.peak), confirm_peaks.get(id(pos), float(pos.peak)))
                    ) if s8_confirm else None,
                )
            for code, pos, cursor, limits in post_group_scans:
                for bar_idx, at_hm in enumerate(cursor.hm):
                    if int(at_hm) <= BUY_HM:
                        continue
                    for phase in ("open", "close"):
                        advance_independent_exit(
                            st, code, pos, cursor, bar_idx, phase, limits,
                            day=day, day_i=i, audit_sink=audit_sink,
                        )
                        if phase == "open":
                            fill_side_pending(st, code, pos, float(cursor.o[bar_idx]), day, i,
                                              limits, hm=int(at_hm))

        run_eod_exits(st, day=day, ds=ds, bars=daily_bars, eod_exit=hooks.get("eod_exit"),
                      hold_modes=hold_modes, exdiv=exdiv,
                      **({"signal_bars_front": signal_bars_front, "strategy": strategy,
                          "fix_s11_exit_domain": True} if fix_s11_exit_domain else {}))
        if fix_s12_price_domain:
            require_market_marks(
                st, ds=ds, day=day, mark_bars=daily_bars,
                mark_source_for=s12_price_context.raw_path_for,
            )
        carry_session(
            st, ds, lambda code: _slice_day(minute_bars[code], day_spans.get(code, {}), ds)
            if code in minute_bars else None,
        )
        if policy.append_marks is None:
            append_equity_and_eod_marks(
                st,
                ds=ds,
                day=day,
                calendar_last=calendar[-1],
                mark_bars=daily_bars,
            )
        else:
            policy.append_marks(
                st, ds=ds, day=day, calendar_last=calendar[-1],
                mark_bars=daily_bars, context=policy_context,
            )

    if native_v7:
        return st

    finish_pending_sells(st)
    finish_pending_chase(st, pending_chase)
    if fix_s12_price_domain:
        st.stats.update(s12_price_context.metadata)
        st.stats.update(
            fix_s12_price_domain=True,
            economics_enabled=exdiv_economics is not None,
            total_return_complete=False,
        )
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
    require_signal_bundle: bool = False,
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
    stop_fill: Optional[str] = None,
    week_ma_gate: bool = False,
    ma5_gate: bool = False,
    keep_buy_vacancy: bool = False,
    buy_cost_rate: Optional[float] = None,
    sell_cost_rate: Optional[float] = None,
    min_cost: Optional[float] = None,
    strict_pool: bool = False,
    fix_s12_price_domain: bool = False,
    s12_price_transform_file: Path | None = None,
    fix_s11_exit_domain: bool = False,
    version9_sell=None,
    max_hold: bool = False,
    fix_s81_band_precision: bool = False,
    minute_stop_trigger: str = "close",
    fill_config: FillConfig | None = None,
    exdiv_ref_fen: bool = False,
    fix_minute_cash_order: bool = False,
    tail_window_buy: bool = False,
    tail_volume_unit: str | None = "shares",
    audit_sink=None,
    topk_exec: str = "close",
    limit_walkdown: bool = False,
    topk_limit_rule: str = "qlib",
    participation_rate: float | None = None,
) -> SimState:
    validate_minute_entry(strategy, stage="sell", version9_sell=version9_sell, max_hold=max_hold)
    # P2-B shell precheck (adapter surface on run facade; not simulate / VolumeCap).
    # participation_rate=None → no-op (byte-identical old arm). ≠δ5 certified ≠R4.
    precheck_cli_participation_rate(
        participation_rate,
        minute_source=minute_source,
        qlib_1min_root=qlib_1min_root,
        dividend_type=dividend_type,
        tail_window_buy=tail_window_buy,
        tail_volume_unit=tail_volume_unit,
    )
    if fix_s81_band_precision and normalize_csv_strategy(strategy) != "version8_1":
        raise ValueError("fix_s81_band_precision is supported only by version8_1")
    validate_minute_stop_trigger(minute_stop_trigger, normalize_csv_strategy(strategy), fix_s11_exit_domain)
    validate_topk_exec(topk_exec, strategy, limit_walkdown, topk_limit_rule)
    validate_tail_options(tail_window_buy, fix_minute_cash_order, tail_volume_unit)
    if tail_window_buy:
        tail_volume_unit = resolve_tail_volume_unit(tail_volume_unit)
        validate_minute_entry(strategy, stage="tail", tail_window_buy=tail_window_buy)
        if (minute_source != "lake" or daily_source != "lake" or dividend_type != "none"
                or qlib_1min_root is not None or qlib_day_root is not None):
            raise ValueError("--tail-window-buy requires raw lake minute and daily data")
    if fix_s11_exit_domain:
        validate_minute_entry(strategy, stage="s11", fix_s11_exit_domain=fix_s11_exit_domain)
        if (dividend_type != "none" or minute_source != "lake" or daily_source != "lake"
            or qlib_1min_root is not None or qlib_day_root is not None):
            raise ValueError("fix_s11_exit_domain requires raw lake execution + independent lake front")
    if str(stop_fill or "").strip().lower() == "close":
        raise SystemExit(
            "--stop-fill close is daily EOD close only; "
            "minute entry refuses it (bar close is not 当日收盘)"
        )
    book = normalize_csv_strategy(strategy)
    if fix_s12_price_domain and (
        book != "version12" or dividend_type != "none"
        or minute_source != "lake" or daily_source != "lake"
    ):
        raise ValueError("--fix-s12-price-domain requires version12 + lake/lake + --dividend-type none")
    if s12_price_transform_file is not None and not fix_s12_price_domain:
        raise ValueError("--s12-price-transform-file requires --fix-s12-price-domain")
    validate_minute_entry(strategy, stage="cash", fix_minute_cash_order=fix_minute_cash_order)
    if audit_sink is not None and book == "version12":
        raise ValueError("X-02 execution audit is not applicable to version12")
    if book == "version12":
        if dividend_type not in ("none", "front") or minute_source != "lake" or daily_source != "lake":
            raise ValueError(
                "version12 minute requires lake daily/minute and --dividend-type none|front"
            )
    elif dividend_type != "none":
        raise ValueError("minute --dividend-type front is supported only by version12")
    warn_stale_period_env()
    volume_required = normalize_csv_strategy(strategy) == "version11" or participation_rate is not None
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
    if strict_pool:
        from backtest.research.csv_pool import PoolDuplicateCodeError, validate_pool_dir

        try:
            failures = validate_pool_dir(actual_pool_dir)
        except PoolDuplicateCodeError as exc:
            raise SystemExit(f"strict pool validation failed: {exc}") from None
        if failures:
            raise SystemExit("strict pool validation failed: " + "; ".join(failures[:8]))
    signal_bundle = None
    if require_signal_bundle:
        from backtest.research.csv_pool import require_signal_bundle as _require_signal_bundle

        signal_bundle = _require_signal_bundle(actual_pool_dir)
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
    warm_days = (
        STRATEGY4_CALENDAR_SLACK_DAYS
        if book in ("version4", "version12")
        else (20 if return_threshold_filter else WARMUP_DAYS)
    )
    if normalize_csv_strategy(strategy) in {"version9", "version9_1"}:
        warm_days = max(warm_days, RANGE_LOOKBACK_CALENDAR_DAYS)
    if week_ma_gate:
        from backtest.research.topk_dropout_eligibility import WEEK_MA_WARMUP_DAYS

        warm_days = max(warm_days, WEEK_MA_WARMUP_DAYS)
    load_start = warmup_start(start, warm_days)
    # Week / stock MA5 only need daily history. Minute fills start on the first buy day.
    minute_load_start = start if (week_ma_gate or ma5_gate) else load_start
    print(
        f"loading daily+minute: {len(all_codes)} codes, {load_start}..{end}; "
        f"pool {min(pool_days)}..{max(pool_days)} ({len(pool_days)} days)",
        flush=True,
    )
    signal_bars_front = None
    signal_sources = None
    s12_price_context = None
    if fix_s12_price_domain:
        from backtest.research.signal_price_domain import load_s12_price_context

        t_load = time.perf_counter()
        s12_price_context, minute = load_s12_price_context(
            all_codes, start, end, load_start=load_start,
            transform_file=s12_price_transform_file,
        )
        daily = s12_price_context.raw_daily
        t_daily = time.perf_counter() - t_load
        t_minute = 0.0  # strict snapshot reader validates all domains together
        cache_status = {"cache": "s12_price_domain_uncached"}
    else:
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
        if fix_s11_exit_domain:
            from backtest.research.s11_exit_domain import load_signal_bars_front

            signal_bars_front, signal_sources = load_signal_bars_front(
                daily, all_codes, load_start, end,
            )
        t_daily = time.perf_counter() - t_daily
        cache_status: dict = {}
        t_minute = time.perf_counter()
        if dividend_type == "front":
            root = resolve_period_root("1m") / "dividend_type=front"
            if not root.is_dir():
                raise FileNotFoundError(f"missing front minute partition: {root}")
            # The existing window cache is none-domain; read the configured front tree.
            minute = _load_minute_from_lake(
                all_codes, minute_load_start, end, workers=workers, lake_root=root
            )
            if missing := all_codes - minute.keys():
                raise ValueError(f"missing front minute bars for strategy12: {sorted(missing)} under {root}")
            cache_status["cache"] = "front_uncached"
        elif minute_source == "qlib_1min":
            compact = _load_minute_compact(
                all_codes,
                minute_load_start,
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
                minute_load_start,
                end,
                workers=workers,
                use_cache=use_cache,
                rebuild_cache=rebuild_cache,
                status=cache_status,
                **({"include_volume": True} if volume_required or tail_window_buy else {}),
                **({"include_amount": True} if tail_window_buy else {}),
            )
        t_minute = time.perf_counter() - t_minute
    print(
        f"loaded daily {len(daily)} / minute {len(minute)} / pool days {len(pool_days)}",
        flush=True,
    )
    volume_options = {}
    if participation_rate is not None:
        if missing := all_codes - minute.keys():
            raise ValueError(f"missing minute volume frames: {sorted(missing)}")
        samples = completed_minute_volumes(minute)
        # P2-B loader-exit completed-bucket precheck (shell; does not redefine buckets).
        precheck_completed_bucket_samples(samples)
        volume_options = {
            "participation_rate": participation_rate,
            "volume_for_bucket": samples,
        }
    if week_ma_gate:
        from backtest.research.topk_dropout_eligibility import with_week_ma_gate

        eligible_buy = with_week_ma_gate(eligible_buy, daily)
    if ma5_gate:
        from backtest.research.topk_dropout_eligibility import with_ma5_gate

        eligible_buy = with_ma5_gate(eligible_buy, daily)
    if return_threshold_filter:
        from backtest.research.topk_dropout_eligibility import with_return_threshold

        eligible_buy = with_return_threshold(eligible_buy, daily)
    skipped: dict[str, int] = {}
    # Human cut #151 option 2: mixed-domain strategy12 (daily front + minute none)
    # must avoid silent ex-div double adjustment. Keep ex-div explicit-only there.
    exdiv = (
        None
        if (book == "version12" or dividend_type == "front")
        else load_exdiv_ratios(all_codes, start, end, skipped_out=skipped,
                               **({"noise_eps": 0} if exdiv_ref_fen else {}))
    )
    from backtest.research.strategy_book_helpers import load_book_index_gate

    index_block_new = load_book_index_gate(normalize_csv_strategy(strategy), start, end)
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
        **volume_options,
        **({"version9_sell": version9_sell} if version9_sell is not None else {}),
        **({"max_hold": True} if max_hold else {}),
        **({"fix_s81_band_precision": True} if fix_s81_band_precision else {}),
        take_profit=take_profit,
        record_params=record_params,
        name_budget=name_budget,
        ration=ration,
        ration_seed=ration_seed,
        pool_names_by_day=pool_names_by_day,
        **({"fix_s11_exit_domain": True, "signal_bars_front": signal_bars_front}
           if fix_s11_exit_domain else {}),
        exdiv=exdiv,
        exdiv_ref_fen=exdiv_ref_fen,
        scores_by_day=scores_by_day,
        topk=topk,
        n_drop=n_drop,
        eligible_buy=eligible_buy,
        keep_buy_vacancy=keep_buy_vacancy,
        index_block_new=index_block_new,
        stop_fill=stop_fill,
        buy_cost_rate=buy_cost_rate,
        sell_cost_rate=sell_cost_rate,
        min_cost=min_cost,
        **({"fix_s12_price_domain": True, "s12_price_context": s12_price_context}
           if fix_s12_price_domain else {}),
        fix_minute_cash_order=fix_minute_cash_order,
        tail_window_buy=tail_window_buy,
        tail_volume_unit=tail_volume_unit,
        audit_sink=audit_sink,
        minute_stop_trigger=minute_stop_trigger,
        fill_config=fill_config,
        topk_exec=topk_exec, limit_walkdown=limit_walkdown,
        topk_limit_rule=topk_limit_rule,
    )
    if skipped.get("exdiv_skipped_no_factor"):
        st.stats["exdiv_skipped_no_factor"] = int(skipped["exdiv_skipped_no_factor"])
    # Run-level provenance only: library simulate() OFF snapshots keep old keys.
    st.stats.update(
        fix_minute_cash_order=bool(fix_minute_cash_order),
        cash_order_policy="chronological" if fix_minute_cash_order else "legacy_full_day_scan",
        same_hm_policy=("open_before_close; independent_sells_before_buys"
                        if fix_minute_cash_order else "legacy_full_day_scan_before_buys"),
        fallback_order_clock="target_hm; capacity_uses_quote_bucket",
        stable_order="held_insertion_then_lot; original_ration_and_chase_queue",
    )
    if book == "version12":
        st.stats.update(cash_order_policy="strategy12_existing_minute_hook",
                        same_hm_policy="strategy12_existing_sells_then_buys",
                        fallback_order_clock="strategy12_existing_hook",
                        stable_order="strategy12_existing_hook")
    if topk_exec != "close" or limit_walkdown:
        st.stats.update(cash_order_policy="chronological",
                        same_hm_policy="open_before_close; independent_sells_before_buys",
                        fallback_order_clock="actual_session_open; no_open_fallback",
                        allocation_clock="09:30_buy_dispatch")
    if limit_walkdown and topk_exec == "close":
        st.stats.update(fallback_order_clock="14:55_decision; _buy_px_quote_bucket",
                        allocation_clock="14:55_buy_dispatch")
    if topk_exec != "close" or limit_walkdown or topk_limit_rule != "qlib":
        st.run_metadata = {**getattr(st, "run_metadata", {}), "topk_limit_rule": topk_limit_rule}
    if tail_window_buy:
        st.run_metadata = {**getattr(st, "run_metadata", {}), "tail_window_buy": tail_policy(tail_volume_unit)}
    if participation_rate is not None:
        st.run_metadata = {**getattr(st, "run_metadata", {}), "volume_capacity": {
            "participation_rate": participation_rate, "unit": "raw_shares_incremental",
            "available_at": "bucket_end", "auction_0930": "excluded",
            "assumption": "caller_declares_raw_incremental_shares; no_unit_conversion",
            "comparison_status": "no_ssot_compare_authorization",
        }}
    st.stats["t_pool_s"] = t_pool
    st.stats["t_daily_s"] = t_daily
    st.stats["t_minute_s"] = t_minute
    st.stats["t_sim_s"] = time.perf_counter() - t_sim
    st.stats["cache"] = cache_status.get("cache", "")
    st.stats["codes_missing"] = max(0, len(all_codes) - min(len(daily), len(minute)))
    if signal_bundle is not None:
        st.stats["signal_bundle_sha256"] = signal_bundle["bundle_sha256"]
    if book == "version12":
        st.stats["daily_signal_domain"] = "front"
        st.stats["minute_fill_domain"] = dividend_type
        st.stats["price_domain"] = dividend_type
    if book == "version11":
        from backtest.research.s11_exit_domain import build_run_metadata

        metadata = build_run_metadata(
            enabled=fix_s11_exit_domain, execution_domain=dividend_type,
            daily_source=daily_source, minute_source=minute_source,
            exdiv=exdiv, source_metadata=signal_sources, raw_bars=daily,
        )
        if daily_source == "qlib_day":
            metadata["mark_domain"] = "qlib_adjusted"
        st.run_metadata = {**getattr(st, "run_metadata", {}), "s11_exit_domain": metadata}
    return st


def main(argv: Optional[list] = None) -> int:
    ap = argparse.ArgumentParser(
        description="CSV-mode vectorized minute backtest (required --strategy)",
        epilog=help_lock_all(HELP_LOCK) + TOPK_EXEC_HELP_LOCK,
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
    ap.add_argument("--exdiv-ref-fen", action="store_true",
                    help="opt-in E-R6 mapped reference HALF_UP to fen and no event noise band; default off; version12/front unchanged")
    ap.add_argument("--minute-stop-trigger", choices=("hl", "close"), default="close",
                    help="close (default): legacy scan; hl: low stop/high fixed target, threshold fills; rejects version12 and --fix-s11-exit-domain; v7 does not accept this flag")
    ap.add_argument("--no-cache", action="store_true", help="skip minute window cache")
    ap.add_argument(
        "--participation-rate", type=float, default=None,
        help="research opt-in finite [0,1]; omitted = cap off (byte-identical old arm). "
             "Declares raw incremental SHARE volume in loaded lake minutes (no lots "
             "conversion); completed bucket_end approximation, excludes 09:30 auction, "
             "bypasses minute cache. Shell precheck (P2-B) fail-closed on unit/domain; "
             "≠δ5 certified ≠R4 (not capacity certified)",
    )
    ap.add_argument(
        "--rebuild-cache", action="store_true", help="reload lake and rewrite cache"
    )
    ap.add_argument("--minute-source", choices=("lake", "qlib_1min"), default="lake")
    ap.add_argument("--daily-source", choices=("lake", "qlib_day"), default="lake")
    ap.add_argument("--topk-limit-rule", choices=("qlib", "real"), default="qlib",
                    help="TopK limit band: qlib 0.095 (default) or real board/ST/date tiers")
    ap.add_argument("--limit-walkdown", action="store_true",
                    help="TopK first limit-up block hands whole seat quota to next eligible rank")
    ap.add_argument(
        "--topk-exec", type=parse_topk_exec, choices=("close", "open", "intraday", "vwap"),
        default="close", help="topk_dropout only: default close = 14:55 close; open/intraday/vwap opt-in",
    )
    ap.add_argument("--dividend-type", choices=("none", "front"), default="none",
                    help="version12 minute fills allow none/front; daily signals fixed to 1d/front")
    ap.add_argument(
        "--fix-s12-price-domain", action="store_true",
        help="X-01: strategy12 raw comparison/reference/mark; lake/lake + none only (default OFF)",
    )
    ap.add_argument(
        "--s12-price-transform-file", type=Path,
        help="read-only verified as-of affine price transforms; requires --fix-s12-price-domain",
    )
    ap.add_argument(
        "--qlib-1min-root",
        help="qlib my_data_1min root; implies --minute-source qlib_1min",
    )
    ap.add_argument(
        "--qlib-day-root", help="qlib daily bin root for --daily-source qlib_day"
    )
    ap.add_argument(
        "--qlib-cost",
        action="store_true",
        help="align fees with qlib: buy 5bp / sell 15bp / min 5 (default is 10bp both sides, no floor).",
    )
    ap.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="artifact directory; default backtest_output/csv_minute_{book}_{start}_{end}",
    )
    ap.add_argument(
        "--emit-run-manifest", action="store_true",
        help="write myquant.bt-run/1 provenance (default off)",
    )
    ap.add_argument(
        "--require-signal-bundle", action="store_true",
        help="require a valid signal-bundle.json with matching CSV hashes (default off)",
    )
    ap.add_argument(
        "--strict-pool", action="store_true",
        help="validate pool CSVs before loading bars (default off: permissive parser)",
    )
    ap.add_argument(
        "--fix-s11-exit-domain", action="store_true",
        help="version11 EOD exits use independent lake front; raw lake fills/marks (default OFF)",
    )
    ap.add_argument(
        "--fix-minute-cash-order", action="store_true",
        help="advance minute cash/holdings chronologically (default off; unavailable for version12)",
    )
    ap.add_argument(
        "--tail-window-buy", action="store_true",
        help="8.x first pool buy: 28 TWAP slices; requires --fix-minute-cash-order (default OFF); "
             "target Q<2800 shares gives zero-share slices and no fills, without OFF supplementary 100-share fallback",
    )
    ap.add_argument(
        "--tail-volume-unit", choices=("shares", "lots"), default="shares",
        help="lake minute volume unit (default shares); lots multiplies volume by 100",
    )
    ap.add_argument("--execution-audit-file", help="optional execution JSON sidecar; leaves CSVs unchanged")
    args = ap.parse_args(argv if argv is not None else None)
    # P2-B: CLI-parse shell precheck (unit/domain). None → no-op. ≠δ5≠R4.
    # Keep ValueError (not ap.error) so invalid-rate contract matches pre-P2 tests/API.
    minute_source_early = "qlib_1min" if args.qlib_1min_root else args.minute_source
    precheck_cli_participation_rate(
        args.participation_rate,
        minute_source=minute_source_early,
        qlib_1min_root=args.qlib_1min_root,
        dividend_type=args.dividend_type,
        tail_window_buy=args.tail_window_buy,
        tail_volume_unit=args.tail_volume_unit,
    )
    try:
        validate_minute_stop_trigger(args.minute_stop_trigger, normalize_csv_strategy(args.strategy), args.fix_s11_exit_domain)
        validate_topk_exec(args.topk_exec, args.strategy, args.limit_walkdown, args.topk_limit_rule)
    except ValueError as exc:
        ap.error(str(exc))
    pool_dir = resolve_research_pool_dir(args.strategy, args.pool_dir, repo=REPO)
    minute_source = "qlib_1min" if args.qlib_1min_root else args.minute_source
    daily_source = "qlib_day" if args.qlib_day_root else args.daily_source

    audit = [] if args.execution_audit_file else None
    st = run(
        args.start,
        args.end,
        total_cash=args.cash_total,
        daily_quota=resolve_daily_quota(
            args.strategy,
            args.daily_quota,
            cash_total=args.cash_total,
            fallback_quota=DEFAULT_DAILY_QUOTA,
        ),
        workers=args.workers,
        pool_dir=pool_dir,
        require_signal_bundle=args.require_signal_bundle,
        use_cache=not args.no_cache,
        rebuild_cache=args.rebuild_cache,
        minute_source=minute_source,
        daily_source=daily_source,
        dividend_type=args.dividend_type,
        fix_s12_price_domain=args.fix_s12_price_domain,
        s12_price_transform_file=args.s12_price_transform_file,
        qlib_1min_root=Path(args.qlib_1min_root) if args.qlib_1min_root else None,
        qlib_day_root=Path(args.qlib_day_root) if args.qlib_day_root else None,
        buy_cost_rate=QLIB_OPEN_COST if args.qlib_cost else None,
        sell_cost_rate=QLIB_CLOSE_COST if args.qlib_cost else None,
        min_cost=QLIB_MIN_COST if args.qlib_cost else None,
        strict_pool=args.strict_pool,
        **({"participation_rate": args.participation_rate} if args.participation_rate is not None else {}),
        fix_s11_exit_domain=args.fix_s11_exit_domain,
        fix_minute_cash_order=args.fix_minute_cash_order,
        tail_window_buy=args.tail_window_buy,
        tail_volume_unit=args.tail_volume_unit,
        audit_sink=audit,
        exdiv_ref_fen=args.exdiv_ref_fen,
        minute_stop_trigger=args.minute_stop_trigger,
        topk_exec=args.topk_exec, limit_walkdown=args.limit_walkdown,
        topk_limit_rule=args.topk_limit_rule,
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
    out_dir = (
        Path(args.out_dir) if args.out_dir else Path(REPO) / "backtest_output" / tag
    )
    if out_dir.exists() and any(out_dir.iterdir()):
        raise SystemExit(
            f"refuse overwrite existing {out_dir}; pick a new stamp directory"
        )
    emit_manifest = args.emit_run_manifest or args.tail_window_buy or args.participation_rate is not None
    manifest_args = vars(args).copy()
    if args.participation_rate is None:
        manifest_args.pop("participation_rate", None)
    if not args.limit_walkdown:
        manifest_args.pop("limit_walkdown", None)
    if args.topk_exec == "close" and not args.limit_walkdown and args.topk_limit_rule == "qlib":
        manifest_args.pop("topk_limit_rule", None)
        manifest_args.pop("topk_exec", None)
    if not args.tail_window_buy:
        manifest_args.pop("tail_window_buy", None)
        manifest_args.pop("tail_volume_unit", None)
    write_run_artifacts(
        out_dir,
        st,
        text,
        help_lock_for(args.strategy, shared=HELP_LOCK)
        + (TOPK_EXEC_HELP_LOCK if args.topk_exec != "close" or args.limit_walkdown or args.topk_limit_rule != "qlib" else ""),
        emit_run_manifest=emit_manifest,
        signal_bundle_sha256=st.stats.get("signal_bundle_sha256"),
        manifest_config=(
            {**manifest_args, "pool_dir": pool_dir, "out_dir": out_dir,
             "minute_source": minute_source, "daily_source": daily_source,
             **getattr(st, "run_metadata", {})}
            if emit_manifest else None
        ),
    )
    if args.topk_exec != "close" or args.limit_walkdown or args.topk_limit_rule != "qlib":
        write_topk_exec_audit(out_dir, st)
    if normalize_csv_strategy(args.strategy) == "version12":
        price_domain_audit = (
            {key: st.stats[key] for key in (
                "fix_s12_price_domain", "daily_signal_domain", "signal_comparison_domain",
                "minute_fill_domain", "mark_domain", "reference_adjustment", "transform_model",
                "implicit_exdiv_map", "economics_enabled", "nav_comparability",
                "total_return_complete", "pit_anchor_validation", "source_hashes",
                "validation_version", "cache_policy", "transform_metadata_sha256",
                "transform_evidence_sha256", "source_snapshot_id", "source_file_hashes",
                "source_paths", "provenance", "optional_factor", "input_price_tolerance",
                "input_price_tolerance_mode", "input_coefficient_tolerance",
                "real_lake_precision_validated", "front_representation",
                "decision_precision_check",
            ) if key in st.stats}
            if args.fix_s12_price_domain else {
                "fix_s12_price_domain": False,
                "daily_signal_domain": "front",
                "signal_comparison_domain": "legacy_unconverted",
                "minute_fill_domain": args.dividend_type,
                "mark_domain": "front",
                "implicit_exdiv_map": False,
                "economics_enabled": False,
                "total_return_complete": False,
                "nav_comparability": (
                    "invalid_mixed_price_domains" if args.dividend_type == "none"
                    else "legacy_adjusted_account_not_raw_nav"
                ),
            }
        )
        (out_dir / "price_domain_audit.json").write_text(
            json.dumps(price_domain_audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    if args.execution_audit_file:
        write_audit(args.execution_audit_file, audit, engine=engine,
                    enabled=args.fix_minute_cash_order or args.topk_exec != "close" or args.limit_walkdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
