"""策略 6 卖点纯函数 — 名单加仓 + T+1 起评止盈 + 两档回撤。

止损 2 个点（T+1 起）。T+1 起评止盈：峰值涨幅 <6% 回撤 70%；≥6% 回撤 50%。
已持再进名单可加仓。买侧（尾盘涨停、T+1 09:45 追买）不在本模块。

`trail_hits` / PROFIT_BASE / TIERS 仍给引擎无 take_profit 回退和策略 10 旧公式用。
"""

from __future__ import annotations

from typing import Optional

BOOK_TAG = "v6"
ALLOW_ADD = True
PEAK_GAP_MIN = 15

STOP_PCT = 0.02
TP_MIN_DAYS = 1
BAND_SPLIT = 0.06
DD_LT6 = 0.70
DD_GE6 = 0.50

# 引擎 scan 回退 + CLI / 策略 10 旧锚档（本包 take_profit 不再用）。
PROFIT_BASE = 0.01
TIERS = {1: 0.30, 2: 0.40, 3: 0.50, 4: 0.60}
TIER_DEFAULT = 0.70
POS_TRAIL = 0.50  # 已停用：策略6不再做未过锚的正利润回撤


def trail_hits(
    px: float,
    cost: float,
    peak: float,
    profit_base: float,
    ratio: float,
) -> bool:
    """旧锚定回撤（+1% 锚）。触发价 < 买入价不执行止盈。"""
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
    **_ignored,
) -> Optional[str]:
    """T+0（n_days<1）不评。T+1 起峰值涨幅两档回撤。px<cost 不止盈。"""
    if int(n_days) < int(TP_MIN_DAYS):
        return None
    if cost <= 0 or px <= 0 or peak <= 0:
        return None
    if float(px) < float(cost):
        return None
    if float(peak) <= float(cost):
        return None
    rise = float(peak) - float(cost)
    if float(peak) + 1e-12 < float(cost) * (1.0 + BAND_SPLIT):
        keep = 1.0 - DD_LT6
        reason = "trail:band:lt6"
    else:
        keep = 1.0 - DD_GE6
        reason = "trail:band:ge6"
    line = float(cost) + keep * rise
    if float(px) <= line:
        return reason
    return None


HELP_LOCK = """
策略 6 卖点（--strategy version6）：
  止损 2 个点（T+1 起）。T+1 日起评止盈。
  峰值涨幅：<6% 回撤 70%（保留 30%）；≥6% 回撤 50%。
        触发价 < 买入价不止盈。
  已持出现在当日名单可加仓（输家也加），daily_quota 均分当日额度。
  跌停：trail / 止损等任何卖因成交前跌停则 defer，次日再评（不只 stop_loss）。
  比例：--stop-pct 可改止损。--profit-base / --trail-t1..t5 只影响策略 10 旧公式。
  落盘：backtest_output/csv_{daily|minute}_v6_{start}_{end}/
"""


def record_strategy6_params(
    st,
    *,
    stop_pct: float,
    profit_base: float = PROFIT_BASE,
    tiers: Optional[dict] = None,
    tier_default: float = TIER_DEFAULT,
) -> None:
    del profit_base, tiers, tier_default
    st.stats["sell_book"] = BOOK_TAG
    st.stats["stop_pct"] = float(stop_pct)
    st.stats["tp_min_days"] = int(TP_MIN_DAYS)
    st.stats["v6_dd_bands"] = True
    st.stats["dd_lt6"] = float(DD_LT6)
    st.stats["dd_ge6"] = float(DD_GE6)
    st.stats["allow_add"] = bool(ALLOW_ADD)
