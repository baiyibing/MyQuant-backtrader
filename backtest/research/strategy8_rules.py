"""策略 8（金榕元交易回测）卖点纯函数。

止损 20 个点（20%）。止盈以持仓最高价相对买入价的涨幅分档，回撤到
对应绝对涨幅触发；6% ≤ 涨幅 ≤ 15%（2% 档须先摸到 2%×2）再回撤到
买入价×1.02；涨幅 > 120% 时改为「最高价回撤 20%」。
买侧（尾盘涨停、T+1 09:45 追买、已持加仓）不在本模块。
"""

from __future__ import annotations

from typing import Optional

BOOK_TAG = "v8"
ALLOW_ADD = True
PEAK_GAP_MIN = 0

STOP_PCT = 0.20
PROFIT_BASE = 0.15
SMALL_FLOOR = 0.02
SMALL_ARM = 0.06  # 回撤到 +2% 前须先摸到 +6%（用户口径：2% 的两倍按 6%）
PEAK_DD_PCT = 0.20
PEAK_DD_ARM = 1.20

# (lo exclusive, hi inclusive, floor gain). 涨幅 > 120% 走峰回撤，无地板档。
# 6% ≤ 涨幅 ≤ 15% 由 SMALL_ARM / SMALL_FLOOR 单独处理（下沿含等号）。
BANDS: tuple[tuple[float, float, float], ...] = (
    (0.15, 0.40, 0.15),
    (0.40, 0.60, 0.30),
    (0.60, 0.80, 0.50),
    (0.80, 1.00, 0.70),
    (1.00, 1.20, 0.90),
)


def band_floor(peak_ret: float) -> Optional[float]:
    """峰值涨幅所在档的止盈地板；未摸到 +6% 或已过 120% 返回 None。"""
    peak_ret = float(peak_ret)
    if SMALL_ARM <= peak_ret <= PROFIT_BASE:
        return float(SMALL_FLOOR)
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
    """涨幅 > 120% 且现价 <= 最高价 * (1-20%)。"""
    if cost <= 0 or px <= 0 or peak <= 0:
        return False
    if float(peak) <= float(cost) * (1.0 + float(arm)):
        return False
    return float(px) <= float(peak) * (1.0 - float(dd_pct))


def take_profit_reason(
    px: float,
    cost: float,
    peak: float,
    n_days: int = 1,
) -> Optional[str]:
    """触发止盈则返回 reason（供 CSV `_sell` / Cerebro profit_take 前缀）。

    分档与峰回撤同时成立时记分档。触发价 < 成本不止盈。
    """
    del n_days
    if cost <= 0 or px <= 0 or peak <= 0:
        return None
    if float(px) < float(cost):
        return None
    peak_ret = float(peak) / float(cost) - 1.0
    floor = band_floor(peak_ret)
    if floor is not None and float(px) <= float(cost) * (1.0 + float(floor)):
        return f"trail:band:{int(round(floor * 100))}"
    if peak_drawdown_hits(px, cost, peak):
        return "trail:peak_dd"
    return None


HELP_LOCK = """
策略 8 卖点（--strategy version8）：
  止损 20 个点。止盈按峰值涨幅分档：
        6% ≤ 涨幅 ≤ 15%（须先摸到 2%×2）→ 回撤到买入价×1.02；
        之后 15/30/50/70/90；涨幅 > 120% 回撤到最高价×80%。
  已持仓票再次出现继续买，各笔 lot 独立算成本/峰值/止损止盈。
  落盘：backtest_output/csv_{daily|minute}_v8_{start}_{end}/
"""


def record_strategy8_params(st, *, stop_pct: float = STOP_PCT) -> None:
    st.stats["sell_book"] = BOOK_TAG
    st.stats["stop_pct"] = float(stop_pct)
    st.stats["profit_base"] = PROFIT_BASE
    st.stats["small_floor"] = SMALL_FLOOR
    st.stats["small_arm"] = SMALL_ARM
    st.stats["peak_dd_pct"] = PEAK_DD_PCT
    st.stats["peak_dd_arm"] = PEAK_DD_ARM
