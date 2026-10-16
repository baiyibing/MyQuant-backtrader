"""策略 10.2：买点同策略 10（源 B TR 名单），卖/仓位冻结策略 6.55 栈。

买点不在本模块：``export_ta_pool.py`` / ``source_b_tr_pool``（``resist_tr_bb_1000``）。
卖点与加仓/停泊/上证闸门等复用 ``strategy6_55_rules``；不改 6.55 书。
禁止默认 ``stock_pool/``。
"""

from __future__ import annotations

from backtest.research.strategy6_55_rules import (  # noqa: F401
    ALLOW_ADD,
    GIVE_STEP,
    NAME_BUDGET,
    PEAK_GAP_MIN,
    STOP_PCT,
    exit_line,
    take_profit_reason,
)
from backtest.research.strategy6_55_rules import (
    record_strategy6_55_params as _record_655,
)

BOOK_TAG = "v10_2"
REQUIRES_EXPLICIT_POOL = True

HELP_LOCK = """
策略 10.2 卖点（--strategy version10_2 / 10.2）：
  买点 = resist_tr_bb_1000 名单（export_ta_pool.py），同策略 10；不是 stock_pool/。
  必须显式 --pool-dir；指向本仓 stock_pool/ 立即退出。
  卖/仓位冻结策略 6.55 栈（give 5%+4%×档、均价减仓、停泊、抽离、上证闸门、
  延续档止损买回、现金分红买 600036 等）；不改 6.55 书。
  sizing=per_name；name_budget 同 6.55（默认 100 万/名）。
  落盘：backtest_output/csv_{daily|minute}_v10_2_{start}_{end}/
"""


def record_strategy10_2_params(st, *, stop_pct: float) -> None:
    _record_655(st, stop_pct=stop_pct)
    st.stats["sell_book"] = BOOK_TAG
    st.stats["buy_book"] = "v10"
    st.stats["sell_logic"] = "version6_55"
