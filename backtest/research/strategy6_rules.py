"""策略 6 卖点纯函数。

止损 6 个点。止盈：峰值须先过 +1% 锚，再按 T+1..T+5+ 回撤比例。
买侧（尾盘涨停、T+1 09:45 追买、已持跳过）不在本模块。
"""

from __future__ import annotations

from typing import Optional

BOOK_TAG = "v6"
ALLOW_ADD = False
PEAK_GAP_MIN = 15

STOP_PCT = 0.06
PROFIT_BASE = 0.01
TIERS = {1: 0.30, 2: 0.40, 3: 0.50, 4: 0.60}
TIER_DEFAULT = 0.70
POS_TRAIL = 0.50  # 已停用：策略6不再做未过锚的正利润回撤

HELP_LOCK = """
策略 6 卖点（--strategy version6）：
  止损 6 个点。止盈：基础锚 +1%，仅当峰值超过买入价×1.01 后评估。
        公式 (市价/买价-1.01)/(峰值/买价-1.01) ≤
        T+1=0.3 / T+2=0.4 / T+3=0.5 / T+4=0.6 / T+5+=0.7。
        触发价 < 买入价不止盈。未过 +1% 锚不止盈。
  已持仓票跳过，不叠加 lot。
  比例：--stop-pct / --profit-base / --trail-t1..t5 可改。
  落盘：backtest_output/csv_{daily|minute}_v6_{start}_{end}/
"""


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


def record_strategy6_params(
    st,
    *,
    stop_pct: float,
    profit_base: float,
    tiers: dict,
    tier_default: float,
) -> None:
    st.stats["sell_book"] = BOOK_TAG
    st.stats["stop_pct"] = float(stop_pct)
    st.stats["profit_base"] = float(profit_base)
    st.stats["trail_t1"] = float(tiers.get(1, TIERS[1]))
    st.stats["trail_t2"] = float(tiers.get(2, TIERS[2]))
    st.stats["trail_t3"] = float(tiers.get(3, TIERS[3]))
    st.stats["trail_t4"] = float(tiers.get(4, TIERS[4]))
    st.stats["trail_t5"] = float(tier_default)
