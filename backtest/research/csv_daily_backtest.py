#!/usr/bin/env python3
"""CSV 模式日线近似回测（共用买侧/资金引擎，卖点由策略书提供）。

完整滚动投资流程（分钟 Cerebro 链）的日线近似版：同口径的 CSV 每日买入名单、
每日 100 万常规额度、补充资金、T+1、涨跌停拦截、全局 2100 万资金池。必须
`--strategy` 必须从已注册策略中显式指定，无缺省。数据默认不复权日线（``--dividend-type none``，与分钟链
adjust_type='none' 对齐）；``front`` / ``back`` 改读对应湖分区。``--qlib-data-root`` 则直接读 qlib
``features/*.day.bin``（$close 后复权，不 import qlib）。佣金 0.1% 双边（与 broker.setcommission(0.001)
对齐），无最低佣金。

用法：
    python backtest/research/csv_daily_backtest.py --strategy version6 --start 20251023 --end 20260909
    python backtest/research/csv_daily_backtest.py --strategy version8 --start 20251023 --end 20260909
    python backtest/research/csv_daily_backtest.py --strategy version6 --start 20260303 --end 20260323 --out-dir backtest_output/m5_pred
    python backtest/research/csv_daily_backtest.py --strategy version9 --pool-dir exports/s9_bvot_20260303_20260908 --start 20260303 --end 20260908
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Optional

import pandas as pd

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, REPO)

from backtest.research.csv_strategy_books import (  # noqa: E402
    HELP_LOCK_V6,
    HELP_LOCK_V8,
    HELP_LOCK_V9,
    add_csv_backtest_common_args,
    add_csv_strategy_arg as add_csv_strategy_arg,
    add_strategy6_ratio_args as add_strategy6_ratio_args,
    apply_csv_strategy,
    csv_run_kwargs_from_args,
    engine_book,
    help_lock_all,
    help_lock_for as _help_lock_for,
    normalize_csv_strategy,
    resolve_research_pool_dir,
    strategy6_kwargs_from_args,
)
from backtest.research.strategy6_rules import (  # noqa: E402
    POS_TRAIL,
    PROFIT_BASE,
    STOP_PCT,
    TIER_DEFAULT,
    TIERS,
    record_strategy6_params,
    trail_hits,
)
from backtest.research.csv_ledger import (  # noqa: E402
    CHASE_HM,
    COMMISSION,
    DEFAULT_TOTAL_CASH,
    LIMIT_EPS,
    PEAK_GAP_MIN,
    QLIB_CLOSE_COST,
    QLIB_MIN_COST,
    QLIB_OPEN_COST,
    Position,
    SimState,
    _at_limit,
    _buy_size,
    _sell,
    _ymd,
    chase_decision as chase_decision,
    chase_explained as chase_explained,
    execute_buy as execute_buy,
    finish_pending_chase,
    hit_limit_down,
    hit_limit_up,
    last_close_mark as last_close_mark,
    peak_gap_blocks,
    queue_limit_up_chase as queue_limit_up_chase,
    rescale_position,
    apply_exdiv_economics,
    resolve_limit_prices,
)
from backtest.research.ashare_exdiv_economics import EconomicLookup, ExDivEconomics  # noqa: E402

from backtest.research.exdiv_map import (  # noqa: E402
    k_for,
    load_exdiv_ratios,
    mapped_prev_close,
)
from backtest.research.ashare_session import defer_sell_at_limit, t1_sellable  # noqa: E402
from backtest.research.csv_common import (  # noqa: E402
    DEFAULT_DAILY_QUOTA,
    STRATEGY4_CALENDAR_SLACK_DAYS,
    WARMUP_DAYS,
    book_limit_prices,
    build_calendar,
    day_bar_and_prev_closes,
    _named_limits as _named_limits,
    _pool_names_asof as _pool_names_asof,
    _progress as _progress,
)
from backtest.research.csv_simulate_loop import (  # noqa: E402
    append_equity_and_eod_marks,
    init_sim_state,
    prepare_strategy_hooks,
    run_chase_due_day,
    run_eod_exits,
    run_pool_buys_day,
    run_step_adds_day,
)
from backtest.research.csv_pool import (  # noqa: E402
    load_pool_day_map,
    load_pool_names_by_day,
)
from backtest.research.market_layer import (  # noqa: E402
    limit_pct,
    limit_prices,
    round_fen,
    utc_ms_range as utc_ms_range,
)
from backtest.research.csv_artifacts import (  # noqa: E402
    summarize,
    write_run_artifacts,
)
from backtest.research.ashare_bars import load_daily_ohlc  # noqa: E402
from backtest.research.csv_daily_loader import (  # noqa: E402
    warmup_start,
    warn_stale_period_env,
)

# 仅测试：pin 策略书/账本/市场层符号，供测试面属性引用（N-R9）；非引擎转发。
_ = (
    HELP_LOCK_V6,
    HELP_LOCK_V8,
    HELP_LOCK_V9,
    normalize_csv_strategy,
    strategy6_kwargs_from_args,
    PROFIT_BASE,
    STOP_PCT,
    TIER_DEFAULT,
    TIERS,
    record_strategy6_params,
    trail_hits,
    CHASE_HM,
    COMMISSION,
    LIMIT_EPS,
    PEAK_GAP_MIN,
    Position,
    _at_limit,
    _buy_size,
    peak_gap_blocks,
    limit_pct,
    limit_prices,
    round_fen,
)
from common.infra.data_root import resolve_period_root as resolve_period_root  # noqa: E402

HELP_LOCK = """
日线近似口径（相对分钟保真版的唯一失真来源）：
  买入：池 CSV 当日候选、收盘价成交（分钟版 14:55≈收盘）；买价达到或超过
        涨停价 → 当日不买，记下该票额度，次日按追买规则处理。
        per_name 是否加仓见策略书（v8 允许同码加仓、独立 lot）；daily_quota 沿用历史路径。
        daily_quota 常规额度按当日池 CSV 全部名单均分（含随后被跳过的票）。
        资金模式见策略书（v8=每股预算）。
  止损：D+1 起，触发价 = 买入价×(1-stop)。开盘 ≤ 触发价 → 开盘价成交（跳空）；
        否则日内 low 触价 → 触发价成交。
  跌停禁卖：任何卖因在成交前若开盘或成交价跌停 → 不成交、顺延（含 trail /
        profit_take / force / ma_signal / open_board / pending）。
  档位：主板 10% / 创科 20%（含 302、689）/ 北交 30%；名单第二列 ST/*ST=5%。
        未知板块且无 ST 名 → skip_unknown_board，不交易。
  止盈 / 峰值：见下方对应策略书。峰值从 T+1 起用当日 high 更新；T+0 固定为买入价。
        v8：T+1 只评止损不评止盈；日线收盘评估、次日开盘离场（隔夜间隔已 ≥ 15 分钟）。
  买侧：尾盘涨停不买。T+1 用收盘>开盘近似分钟 09:45 市价>开盘 → 收盘追买；
        否则弃买。追买日无 K 保留 pending 到下一有 K 日（仍只评一次）。
        成交价用收盘（相对 09:45 的失真）。
  停牌：冻仓；净值用最近有 K 的 close，不用成本价冒充。
  资金：2100 万全局池；daily_quota 每日 100 万均分，per_name 每码 --name-budget；
        per_name 现金不足（含佣金）整笔 skip_cash、不缩量；不足 100 股用补充资金补足
        （force_min，自主池、不占额度）；佣金默认 0.1% 双边无最低；
        --qlib-cost 改为开 5bp / 平 15bp / 最低 5（对齐 qlib PortAna）。
  配给：--ration file_order 保持 CSV 行序；seeded_shuffle 用 --ration-seed 与日期
        经 SHA-256 派生逐日稳定乱序；追买沿该次名单遍历产生的排队顺序。
  复权：E-R6 除权日参考价修正 — 持仓期除权日一次性缩放 open lot 的 cost/peak，
        并将当日 prev_close→档位换算点映射到 D 域；成交价/净值/股数仍 none。
        非除权日与 ≤0.5% 噪声带见 E-R5 收窄声明（engine-ashare-correctness.md）。
  T+1：买入日不可卖；期末持仓按最后有 K 收盘估值（eod_mark）。
  窗口：--end 是估值/离场末日。买入只发生在 stock_pool/ 有 CSV 的交易日
        （缺日不买）。分钟湖若短于 --end，用日线版接到今天。
  落盘：缺省 backtest_output/csv_daily_{book}_{start}_{end}/ 三件套 summary.txt、
        daily_equity.csv、trades.csv（与分钟版同结构）。--out-dir 指定则写入该目录。
  环境：一键 OSKH_SOURCE_PARQUET_ROOT；勿残留 OSKH_PERIOD_*（lesson 58）。
  策略：必须显式指定已注册 --strategy（无缺省）。共用引擎，策略书换卖点与加仓。
"""


def help_lock_for(strategy: str, *, shared: str = HELP_LOCK) -> str:
    return _help_lock_for(strategy, shared=shared)


_limit_prices = resolve_limit_prices


def simulate(
    bars: dict[str, pd.DataFrame],
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
    keep_buy_vacancy: bool = False,
    buy_cost_rate: Optional[float] = None,
    sell_cost_rate: Optional[float] = None,
    min_cost: Optional[float] = None,
    index_block_new=None,
    stop_fill: Optional[str] = None,
) -> SimState:
    """核心日循环。bars/pool_days 可由测试注入；run() 负责从湖与 CSV 加载。

    strategy 必填；take_profit(...) 仍可显式覆盖。
    exdiv_economics 显式接收 (engine_symbol, YYYYMMDD) -> ExDivEvent；
    默认 None 保留原行为，事件配合 raw bars 使用，不从 exdiv 的 k 推断权益。
    """
    del pos_trail
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
        keep_buy_vacancy=keep_buy_vacancy,
        index_block_new=index_block_new,
        stop_fill=stop_fill,
    )
    stop_pct = hooks["stop_pct"]
    stop_fill = str(hooks.get("stop_fill") or "touch").strip().lower()
    if stop_fill not in ("touch", "close"):
        raise SystemExit(f"--stop-fill must be touch or close, got {stop_fill}")
    take_profit = hooks["take_profit"]
    buy_gate = hooks.get("buy_gate")
    sell_gate = hooks.get("sell_gate")
    calendar = build_calendar(bars, start, end)

    st, pending_chase, names_asof = init_sim_state(
        hooks,
        total_cash=total_cash,
        bars_loaded=len(bars),
        pool_days=pool_days,
        pool_names=pool_names,
        pool_names_by_day=pool_names_by_day,
    )
    if buy_cost_rate is not None:
        st.buy_cost_rate = float(buy_cost_rate)
    if sell_cost_rate is not None:
        st.sell_cost_rate = float(sell_cost_rate)
    if min_cost is not None:
        st.min_cost = float(min_cost)
    st.stats["buy_cost_rate"] = st.buy_cost_rate
    st.stats["sell_cost_rate"] = st.sell_cost_rate
    st.stats["min_cost"] = st.min_cost
    if exdiv_economics is not None:
        st.exdiv_economics = ExDivEconomics(exdiv_economics, st.stats)
    allow_add = bool(hooks["allow_add"])
    reserve_limit_up = bool(hooks.get("reserve_limit_up"))
    defer_limit_up = bool(hooks.get("defer_limit_up"))
    close_clear = hooks.get("close_clear")
    daily_same_bar_prefixes = tuple(hooks.get("daily_same_bar_prefixes", ()))
    qlib_limit_pct = hooks.get("qlib_limit_pct")
    limit_up_chase = bool(hooks.get("limit_up_chase", True))
    limit_down_pending = bool(hooks.get("limit_down_pending", True))
    forbid_all_trade_at_limit = bool(hooks.get("forbid_all_trade_at_limit", False))
    hold_modes = {}

    for i, day in enumerate(calendar):
        ds = _ymd(day)
        day_trade_start = len(st.trades)
        if st.exdiv_economics is not None:
            st.cash += st.exdiv_economics.settle(ds)
        names = names_asof(ds)
        st.daily_quota_used = 0.0  # 每个交易日开盘重置常规额度

        if callable(hooks.get("run_daily_day")):
            hooks["run_daily_day"](
                st, pending_chase, hooks=hooks, bars=bars, pool_days=pool_days,
                day_i=i, day=day, ds=ds, names=names, daily_quota=daily_quota, exdiv=exdiv,
            )
        else:
            bind_opening = hooks.get("bind_opening_held")
            if callable(bind_opening):
                bind_opening(ds, list(st.positions.keys()))

            for code in list(st.positions):
                if code not in bars:
                    continue
                got = day_bar_and_prev_closes(bars[code], day)
                if got is None:
                    continue
                row, closes = got
                apply_exdiv_economics(st, code, ds)
                # E-R6: rescale open lots then map prev_close before limits / lot loop.
                kk = k_for(exdiv, code, ds)
                if kk is not None:
                    for pos in list(st.positions.get(code, [])):
                        rescale_position(pos, kk)
                        st.stats["exdiv_adjusted_lots"] = (
                            int(st.stats.get("exdiv_adjusted_lots", 0)) + 1
                        )
                prev_close, did_map = mapped_prev_close(exdiv, code, ds, float(closes[-1]))
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
                for pos in list(st.positions.get(code, [])):
                    if getattr(pos, "ride_with", None) is not None:
                        continue
                    n_days = i - pos.entry_idx  # 持仓交易日数（买入日=0）

                    # Date mapping serves T+1 only; sell rules keep union-calendar n_days.
                    if pos.pending_exit and t1_sellable(calendar[pos.entry_idx].date(), day.date()):
                        if defer_sell_at_limit(float(row["open"]), limits):
                            st.stats["defer_sell_limit_down"] += 1
                        else:
                            _sell(st, code, pos, float(row["open"]), day, pos.pending_exit,
                                  price_rule="daily_pending_next_open")
                        continue

                    if t1_sellable(calendar[pos.entry_idx].date(), day.date()):
                        stop_enabled = isinstance(stop_pct, float) and 0 < stop_pct < 1
                        close = float(row["close"])
                        if stop_enabled:
                            trigger = pos.cost * (1.0 - stop_pct)
                            if stop_fill == "close":
                                if close <= trigger:
                                    _sell(
                                        st,
                                        code,
                                        pos,
                                        close,
                                        day,
                                        "stop_loss:close",
                                        price_rule="daily_stop_close",
                                    )
                                    continue
                            elif float(row["open"]) <= trigger:
                                if defer_sell_at_limit(float(row["open"]), limits):
                                    st.stats["defer_sell_limit_down"] += 1
                                else:
                                    _sell(
                                        st,
                                        code,
                                        pos,
                                        float(row["open"]),
                                        day,
                                        "stop_loss:gap_open",
                                        price_rule="daily_stop_gap_open",
                                    )
                                continue
                            elif float(row["low"]) <= trigger:
                                if defer_sell_at_limit(trigger, limits):
                                    st.stats["defer_sell_limit_down"] += 1
                                    if limit_down_pending:
                                        pos.pending_exit = "stop_loss:touch"
                                else:
                                    _sell(st, code, pos, trigger, day, "stop_loss:touch",
                                          price_rule="daily_stop_touch_at_trigger")
                                continue

                        pos.peak = max(pos.peak, float(row["high"]))
                        if defer_limit_up and hit_limit_up(close, limit_up):
                            continue
                        if reserve_limit_up and hit_limit_up(float(row["open"]), limit_up):
                            pos.reserved = True
                        if reserve_limit_up and pos.reserved:
                            if hit_limit_up(close, limit_up):
                                continue
                            pos.reserved = False
                            reason = "open_board"
                        else:
                            reason = (
                                sell_gate(code, close, day, closes)
                                if callable(sell_gate)
                                else take_profit(close, pos.cost, pos.peak, n_days)
                            )
                        if not reason and callable(close_clear):
                            reason = close_clear(pos.cost, pos.peak, n_days)
                        if reason:
                            same_bar = any(
                                reason.startswith(prefix)
                                for prefix in daily_same_bar_prefixes
                            )
                            at_up = hit_limit_up(close, limit_up)
                            at_down = hit_limit_down(close, limit_down)
                            blocked = (
                                (at_up or at_down)
                                if forbid_all_trade_at_limit
                                else defer_sell_at_limit(close, limits)
                            )
                            if blocked:
                                st.stats["skip_limit_sell"] = (
                                    int(st.stats.get("skip_limit_sell", 0)) + 1
                                )
                                if str(reason).startswith(
                                    (
                                        "force_sell:t1_close",
                                        "force_sell:t2_close",
                                        "force_sell:t4_close",
                                    )
                                ):
                                    st.stats["defer_sell_limit_down"] += 1
                                elif limit_down_pending:
                                    if same_bar or at_down:
                                        st.stats["defer_sell_limit_down"] += 1
                                    pos.pending_exit = reason
                                continue
                            if same_bar:
                                _sell(st, code, pos, close, day, reason,
                                      price_rule="daily_open_board_same_close"
                                      if reason.startswith("open_board") else "")
                            else:
                                pos.pending_exit = reason

            def _chase_quotes_for(code: str):
                if code not in bars:
                    return None
                got = day_bar_and_prev_closes(bars[code], day)
                if got is None:
                    return None
                row, closes = got
                return float(row["open"]), float(row["close"]), closes

            run_chase_due_day(
                st,
                pending_chase,
                day_i=i,
                day=day,
                names=names,
                allow_add=allow_add,
                buy_gate=buy_gate,
                quotes_for=_chase_quotes_for,
                exdiv=exdiv,
                ds=ds,
                qlib_limit_pct=qlib_limit_pct,
                allow_new_name=hooks.get("allow_new_name"),
                add_gate=hooks.get("add_gate"),
                index_blocks_add=hooks.get("index_blocks_add", True),
            )

            def _pool_quote_for(code: str):
                if code not in bars:
                    return None
                got = day_bar_and_prev_closes(bars[code], day)
                if got is None:
                    return None
                row, closes = got
                return float(row["close"]), closes

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
                sold_today={t["code"] for t in st.trades[day_trade_start:] if t["side"] == "SELL"}
                if hooks.get("skip_sold_today") else None,
            )
            run_step_adds_day(
                st,
                day_i=i,
                day=day,
                ds=ds,
                names=names,
                buy_quote_for=_pool_quote_for,
                sizing=hooks.get("sizing", "daily_quota"),
                name_budget=hooks.get("name_budget", 1_000_000.0),
                exdiv=exdiv,
                qlib_limit_pct=qlib_limit_pct,
                forbid_all_trade_at_limit=forbid_all_trade_at_limit,
                buy_gate=buy_gate,
                name_lot_budget=hooks.get("name_lot_budget"),
                step_add=hooks.get("step_add"),
            )

        run_eod_exits(st, day=day, ds=ds, bars=bars, eod_exit=hooks.get("eod_exit"),
                      hold_modes=hold_modes, exdiv=exdiv)
        append_equity_and_eod_marks(
            st,
            ds=ds,
            day=day,
            calendar_last=calendar[-1],
            mark_bars=bars,
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
    pool_dir: Optional[Path] = None,
    strategy: str,
    take_profit=None,
    record_params=None,
    scores_by_day=None,
    topk=None,
    n_drop=None,
    eligible_buy=None,
    return_threshold_filter: bool = False,
    week_ma_gate: bool = False,
    ma5_gate: bool = False,
    keep_buy_vacancy: bool = False,
    dividend_type: str = "none",
    daily_root: Optional[Path] = None,
    qlib_data_root: Optional[Path] = None,
    buy_cost_rate: Optional[float] = None,
    sell_cost_rate: Optional[float] = None,
    min_cost: Optional[float] = None,
    stop_fill: Optional[str] = None,
) -> SimState:
    warn_stale_period_env()
    if normalize_csv_strategy(strategy) == "version12" and (
        dividend_type != "front" or qlib_data_root is not None
    ):
        raise ValueError("version12 requires lake --dividend-type front")
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
    warm_days = (
        STRATEGY4_CALENDAR_SLACK_DAYS
        if normalize_csv_strategy(strategy) in ("version4", "version12")
        else (20 if return_threshold_filter else WARMUP_DAYS)
    )
    if week_ma_gate:
        from backtest.research.topk_dropout_eligibility import WEEK_MA_WARMUP_DAYS

        warm_days = max(warm_days, WEEK_MA_WARMUP_DAYS)
    load_start = warmup_start(start, warm_days)
    use_qlib_bins = qlib_data_root is not None
    if normalize_csv_strategy(strategy) == "version12":
        front_root = (Path(daily_root) if daily_root is not None else resolve_period_root("1d")) / "dividend_type=front"
        if not front_root.is_dir():
            raise FileNotFoundError(f"missing front daily partition: {front_root}")
    print(
        f"loading daily bars: {len(all_codes)} codes, {load_start}..{end}; "
        f"pool {min(pool_days)}..{max(pool_days)} ({len(pool_days)} days); "
        + (
            f"qlib_bins={qlib_data_root}"
            if use_qlib_bins
            else f"dividend_type={dividend_type}"
            + (f"; daily_root={daily_root}" if daily_root is not None else "")
        ),
        flush=True,
    )
    t_daily = time.perf_counter()
    bars = load_daily_ohlc(
        all_codes,
        load_start,
        end,
        source="qlib_day" if use_qlib_bins else "lake",
        qlib_root=qlib_data_root,
        workers=workers,
        dividend_type=dividend_type,
        daily_root=daily_root,
    )
    if normalize_csv_strategy(strategy) == "version12" and (missing := all_codes - bars.keys()):
        raise ValueError(f"missing front daily bars for strategy12: {sorted(missing)}")
    t_daily = time.perf_counter() - t_daily
    print(
        f"loaded {len(bars)}/{len(all_codes)} daily series, {len(pool_days)} pool days",
        flush=True,
    )
    if week_ma_gate:
        from backtest.research.topk_dropout_eligibility import with_week_ma_gate

        eligible_buy = with_week_ma_gate(eligible_buy, bars)
    if ma5_gate:
        from backtest.research.topk_dropout_eligibility import with_ma5_gate

        eligible_buy = with_ma5_gate(eligible_buy, bars)
    if return_threshold_filter:
        from backtest.research.topk_dropout_eligibility import with_return_threshold

        eligible_buy = with_return_threshold(eligible_buy, bars)
    skipped: dict[str, int] = {}
    # lake none only: E-R6 remap. front/back/qlib $close already continuous.
    if use_qlib_bins or str(dividend_type or "none").strip().lower() != "none":
        exdiv = None
    else:
        exdiv = load_exdiv_ratios(all_codes, start, end, skipped_out=skipped)
    index_block_new = None
    gate_book = normalize_csv_strategy(strategy)
    if gate_book == "version8_4":
        from backtest.research.strategy8_4_rules import (
            INDEX_GATE_ON,
            load_sse_ma10_block_new,
        )

        if INDEX_GATE_ON:
            index_block_new = load_sse_ma10_block_new(start, end)
    elif gate_book == "version8_5":
        from backtest.research.strategy8_5_rules import (
            INDEX_GATE_ON,
            load_sse_ma10_block_new,
        )

        if INDEX_GATE_ON:
            index_block_new = load_sse_ma10_block_new(start, end)
    elif gate_book == "version8_6":
        from backtest.research.strategy8_6_rules import (
            INDEX_GATE_ON,
            load_sse_ma10_block_new,
        )

        if INDEX_GATE_ON:
            index_block_new = load_sse_ma10_block_new(start, end)
    elif gate_book in ("version8", "version8_3"):
        from backtest.research.strategy8_rules import (
            INDEX_GATE_ON,
            load_sse_ma10_block_new,
        )

        # 8.3 冻结包闸门无条件开（历史年代无开关，默认即开）。
        if INDEX_GATE_ON or gate_book == "version8_3":
            index_block_new = load_sse_ma10_block_new(start, end)
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
        name_budget=name_budget,
        ration=ration,
        ration_seed=ration_seed,
        pool_names_by_day=pool_names_by_day,
        exdiv=exdiv,
        scores_by_day=scores_by_day,
        topk=topk,
        n_drop=n_drop,
        eligible_buy=eligible_buy,
        keep_buy_vacancy=keep_buy_vacancy,
        buy_cost_rate=buy_cost_rate,
        sell_cost_rate=sell_cost_rate,
        min_cost=min_cost,
        index_block_new=index_block_new,
        stop_fill=stop_fill,
    )
    if skipped.get("exdiv_skipped_no_factor"):
        st.stats["exdiv_skipped_no_factor"] = int(skipped["exdiv_skipped_no_factor"])
    st.stats["t_pool_s"] = t_pool
    st.stats["t_daily_s"] = t_daily
    st.stats["t_sim_s"] = time.perf_counter() - t_sim
    st.stats["codes_missing"] = max(0, len(all_codes) - len(bars))
    return st


def resolve_csv_daily_out_dir(
    out_dir: Optional[Path],
    *,
    book: str,
    start: str,
    end: str,
) -> Path:
    """Explicit --out-dir wins; otherwise the historical csv_daily_{book}_{start}_{end} path."""
    if out_dir is not None:
        return Path(out_dir)
    return Path(REPO) / "backtest_output" / f"csv_daily_{book}_{start}_{end}"


def main(argv: Optional[list] = None) -> int:
    ap = argparse.ArgumentParser(
        description="CSV-mode daily-bar backtest (required --strategy)",
        epilog=help_lock_all(HELP_LOCK),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    add_csv_backtest_common_args(
        ap,
        repo=REPO,
        end_default="20260909",
        cash_total_default=DEFAULT_TOTAL_CASH,
        daily_quota_default=DEFAULT_DAILY_QUOTA,
    )
    ap.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="artifact directory; default backtest_output/csv_daily_{book}_{start}_{end}/",
    )
    ap.add_argument(
        "--dividend-type",
        choices=("none", "front", "back"),
        default="none",
        help="daily lake adjust (default none). front/back skip E-R6 exdiv remap.",
    )
    ap.add_argument(
        "--daily-root",
        type=Path,
        default=None,
        help="override 1d hive root (contains dividend_type=*). default: path-SSOT lake.",
    )
    ap.add_argument(
        "--qlib-data-root",
        type=Path,
        default=None,
        help="read qlib features/*.day.bin ($close 后复权). does not import qlib; skips lake.",
    )
    ap.add_argument(
        "--qlib-cost",
        action="store_true",
        help="align fees with qlib: buy 5bp / sell 15bp / min 5 (default is 10bp both sides, no floor).",
    )
    ap.add_argument(
        "--emit-run-manifest", action="store_true",
        help="write myquant.bt-run/1 provenance (default off)",
    )
    args = ap.parse_args(argv if argv is not None else None)
    pool_dir = resolve_research_pool_dir(args.strategy, args.pool_dir, repo=REPO)
    book = engine_book(args.strategy)
    out_dir = resolve_csv_daily_out_dir(
        args.out_dir, book=book, start=args.start, end=args.end
    )
    if out_dir.exists() and any(out_dir.iterdir()):
        raise SystemExit(
            f"refuse overwrite existing {out_dir}; pick a new stamp directory"
        )

    st = run(
        args.start,
        args.end,
        total_cash=args.cash_total,
        daily_quota=args.daily_quota,
        workers=args.workers,
        pool_dir=pool_dir,
        dividend_type=args.dividend_type,
        daily_root=args.daily_root,
        qlib_data_root=args.qlib_data_root,
        buy_cost_rate=QLIB_OPEN_COST if args.qlib_cost else None,
        sell_cost_rate=QLIB_CLOSE_COST if args.qlib_cost else None,
        min_cost=QLIB_MIN_COST if args.qlib_cost else None,
        **csv_run_kwargs_from_args(args),
    )
    engine = f"csv_daily_{book}"
    text = summarize(st, args.cash_total, args.start, args.end, engine=engine)
    print(text)
    write_run_artifacts(
        out_dir,
        st,
        text,
        help_lock_for(args.strategy),
        emit_run_manifest=args.emit_run_manifest,
        manifest_config=(
            {**vars(args), "pool_dir": pool_dir, "out_dir": out_dir}
            if args.emit_run_manifest else None
        ),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
