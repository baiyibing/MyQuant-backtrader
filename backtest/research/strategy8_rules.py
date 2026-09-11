"""策略 8（金榕元交易回测）卖点纯函数。

止损 15 个点（15%）。止盈以持仓最高价相对买入价的涨幅分档，回撤到
对应绝对涨幅触发；涨幅 > 50% 时另加「最高价回撤 20%」。
买侧（尾盘涨停、T+1 09:45 追买）不在本模块。
"""

from __future__ import annotations

from typing import Optional

STOP_PCT = 0.15
PROFIT_BASE = 0.20
PEAK_DD_PCT = 0.20
PEAK_DD_ARM = 0.50

# (lo exclusive, hi inclusive, floor gain). Last hi is +inf.
BANDS: tuple[tuple[float, float, float], ...] = (
    (0.20, 0.40, 0.20),
    (0.40, 0.60, 0.30),
    (0.60, 0.80, 0.50),
    (0.80, 1.00, 0.70),
    (1.00, 1.20, 0.90),
    (1.20, float("inf"), 1.10),
)


def band_floor(peak_ret: float) -> Optional[float]:
    """峰值涨幅所在档的止盈地板；未过基础 20% 返回 None。"""
    peak_ret = float(peak_ret)
    if peak_ret <= PROFIT_BASE:
        return None
    for lo, hi, floor in BANDS:
        if lo < peak_ret <= hi:
            return float(floor)
    return None


def stop_hits(px: float, cost: float, stop_pct: float = STOP_PCT) -> bool:
    if cost <= 0 or px <= 0:
        return False
    return float(px) / float(cost) - 1.0 <= -float(stop_pct)


def peak_drawdown_hits(
    px: float,
    cost: float,
    peak: float,
    *,
    arm: float = PEAK_DD_ARM,
    dd_pct: float = PEAK_DD_PCT,
) -> bool:
    """涨幅 > 50% 且现价 <= 最高价 * (1-20%)。"""
    if cost <= 0 or px <= 0 or peak <= 0:
        return False
    if float(peak) / float(cost) - 1.0 <= float(arm):
        return False
    return float(px) <= float(peak) * (1.0 - float(dd_pct))


def take_profit_reason(
    px: float,
    cost: float,
    peak: float,
    n_days: int = 1,
) -> Optional[str]:
    """触发止盈则返回 reason（供 CSV `_sell` / Cerebro profit_take 前缀）。

    分档与峰回撤同时成立时记分档（用户条文顺序）。触发价 < 成本不止盈。
    """
    del n_days
    if cost <= 0 or px <= 0 or peak <= 0:
        return None
    if float(px) < float(cost):
        return None
    peak_ret = float(peak) / float(cost) - 1.0
    ret = float(px) / float(cost) - 1.0
    floor = band_floor(peak_ret)
    if floor is not None and ret <= floor:
        return f"trail:band:{int(round(floor * 100))}"
    if peak_drawdown_hits(px, cost, peak):
        return "trail:peak_dd"
    return None


def record_strategy8_params(st, *, stop_pct: float = STOP_PCT) -> None:
    st.stats["sell_book"] = "v8"
    st.stats["stop_pct"] = float(stop_pct)
    st.stats["profit_base"] = PROFIT_BASE
    st.stats["peak_dd_pct"] = PEAK_DD_PCT
    st.stats["peak_dd_arm"] = PEAK_DD_ARM
