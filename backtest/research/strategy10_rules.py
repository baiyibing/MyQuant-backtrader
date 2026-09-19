"""策略 10（换手阻力名单源 B）卖点：冻结策略 6 旧公式，不跟新 6 漂移。

买点不在本模块：``export_strategy10_pool.py`` / ``source_b_tr_pool``。
禁止默认 ``stock_pool/``。
"""

from __future__ import annotations

from typing import Optional

from backtest.research.strategy6_rules import trail_hits

BOOK_TAG = "v10"
ALLOW_ADD = False
PEAK_GAP_MIN = 15
STOP_PCT = 0.06
PROFIT_BASE = 0.01
TIERS = {1: 0.30, 2: 0.40, 3: 0.50, 4: 0.60}
TIER_DEFAULT = 0.70
REQUIRES_EXPLICIT_POOL = True


def take_profit_reason(
    px: float,
    cost: float,
    peak: float,
    n_days: int = 1,
    *,
    profit_base: float = PROFIT_BASE,
    tiers: Optional[dict] = None,
    tier_default: float = TIER_DEFAULT,
) -> Optional[str]:
    ratio = float((tiers or TIERS).get(int(n_days), tier_default))
    if trail_hits(px, cost, peak, profit_base, ratio):
        return f"trail:T+{max(1, int(n_days))}"
    return None


HELP_LOCK = """
策略 10 卖点（--strategy version10）：
  买点 = resist_tr_bb_1000 名单（export_strategy10_pool.py），不是 stock_pool/。
  必须显式 --pool-dir；指向本仓 stock_pool/ 立即退出。
  卖点冻结策略 6 旧公式：止损 6%、+1% 锚后按 T+1..T+5+ 回撤。
  已持仓票跳过；peak_gap_min=15。
  落盘：backtest_output/csv_{daily|minute}_v10_{start}_{end}/
"""


def record_strategy10_params(
    st,
    *,
    stop_pct: float,
    profit_base: float = PROFIT_BASE,
    tiers: Optional[dict] = None,
    tier_default: float = TIER_DEFAULT,
) -> None:
    tier_map = dict(tiers or TIERS)
    st.stats["sell_book"] = BOOK_TAG
    st.stats["sell_logic"] = "version6_legacy"
    st.stats["stop_pct"] = float(stop_pct)
    st.stats["profit_base"] = float(profit_base)
    st.stats["trail_t1"] = float(tier_map.get(1, TIERS[1]))
    st.stats["trail_t2"] = float(tier_map.get(2, TIERS[2]))
    st.stats["trail_t3"] = float(tier_map.get(3, TIERS[3]))
    st.stats["trail_t4"] = float(tier_map.get(4, TIERS[4]))
    st.stats["trail_t5"] = float(tier_default)
