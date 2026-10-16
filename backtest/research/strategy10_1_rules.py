"""策略 10.1：买点同策略 10（源 B TR 名单），卖点冻结策略 9 原书。

买点不在本模块：``export_ta_pool.py`` / ``source_b_tr_pool``（``resist_tr_bb_1000``）。
卖点复用 ``strategy9_rules``：滚动 20 日振幅止损 + 成本 +10% 止盈；不加仓。
可选只强平：``--max-hold-days N --no-range-stop --no-profit-take``。
禁止默认 ``stock_pool/``。
"""

from __future__ import annotations

from typing import Optional

from backtest.research.strategy9_rules import (  # noqa: F401
    ALLOW_ADD,
    MAX_HOLD,
    PEAK_GAP_MIN,
    RANGE_BARS,
    RANGE_LOOKBACK_CALENDAR_DAYS,
    TAKE_PROFIT_PCT,
    evaluate_stop_range,
    evaluate_version9_exit,
    plan_close_reason,
    plan_stop_price,
    stop_range_amplitude,
    stop_range_status,
    take_profit_reason,
    validate_sell_mode,
    version9_exit,
)

BOOK_TAG = "v10_1"
REQUIRES_EXPLICIT_POOL = True

HELP_LOCK = """
策略 10.1 卖点（--strategy version10_1 / 10.1）：
  买点 = resist_tr_bb_1000 名单（export_ta_pool.py），同策略 10；不是 stock_pool/。
  必须显式 --pool-dir；指向本仓 stock_pool/ 立即退出。
  卖点冻结策略 9 原书：止损幅度每个交易日从此前 20 根日线重算，不在入场锁定。
  幅度=(20 根最高 high - 最低 low)/窗口前一根 close；触发价=成本*(1-幅度)。
  缺窗口当天不止损、不回落固定比例；--stop-pct 不接受。
  盈利达到成本的 10% 返回 profit_take:target，次日开盘卖。无分档回撤止盈；不加仓。
  强平默认 OFF；--max-hold 等价 --max-hold-days 20；也可 --max-hold-days N。
  --no-range-stop 关振幅止损；--no-profit-take 关 10% 止盈（可只留强平）。
  可选 --version9-sell 实验臂与策略 9 相同；peak_gap_min=0。
  落盘：backtest_output/csv_{daily|minute}_v10_1_{start}_{end}/
"""


def record_strategy10_1_params(
    st,
    *,
    max_hold: bool = False,
    max_hold_days: Optional[int] = None,
    range_stop: bool = True,
    profit_take: bool = True,
) -> None:
    st.stats["sell_book"] = BOOK_TAG
    st.stats["buy_book"] = "v10"
    limit = (
        int(max_hold_days)
        if max_hold_days is not None
        else (MAX_HOLD if max_hold else None)
    )
    if limit is not None and not range_stop and not profit_take:
        st.stats["sell_logic"] = "max_hold_only"
    else:
        st.stats["sell_logic"] = "version9_original"
    st.stats["stop_pct"] = None
    st.stats["stop_mode"] = "range_amp_20_trailing" if range_stop else "off"
    st.stats["range_bars"] = RANGE_BARS if range_stop else None
    st.stats["profit_target"] = TAKE_PROFIT_PCT if profit_take else None
    st.stats["max_hold"] = limit
