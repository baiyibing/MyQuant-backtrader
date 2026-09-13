"""策略 10（换手阻力名单源 B）卖点：复用策略 6，不改阈值。

买点不在本模块：``export_strategy10_pool.py`` / ``source_b_tr_pool``。
禁止默认 ``stock_pool/``。
"""

from __future__ import annotations

from backtest.research import strategy6_rules

BOOK_TAG = "v10"
ALLOW_ADD = strategy6_rules.ALLOW_ADD
PEAK_GAP_MIN = strategy6_rules.PEAK_GAP_MIN
STOP_PCT = strategy6_rules.STOP_PCT
PROFIT_BASE = strategy6_rules.PROFIT_BASE
TIERS = strategy6_rules.TIERS
TIER_DEFAULT = strategy6_rules.TIER_DEFAULT
REQUIRES_EXPLICIT_POOL = True

take_profit_reason = strategy6_rules.take_profit_reason

HELP_LOCK = """
策略 10 卖点（--strategy version10）：
  买点 = resist_tr_bb_1000 名单（export_strategy10_pool.py），不是 stock_pool/。
  必须显式 --pool-dir；指向本仓 stock_pool/ 立即退出。
  卖点与策略 6 同一套：止损 6%、+1% 锚后按 T+1..T+5+ 回撤。
  已持仓票跳过；peak_gap_min 与 version6 相同。
  落盘：backtest_output/csv_{daily|minute}_v10_{start}_{end}/
"""


def record_strategy10_params(st, **kwargs) -> None:
    strategy6_rules.record_strategy6_params(st, **kwargs)
    st.stats["sell_book"] = BOOK_TAG
    st.stats["sell_logic"] = "version6"
