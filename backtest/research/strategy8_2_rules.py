"""策略 8 里程碑 8.2 卖点纯函数 — 241b607「规则 v2 比例回撤阶梯」冻结包。

历史包在现行引擎上的复活本：卖点半身与当年逐行一致，买侧由共享引擎
管理；引擎行为跟随现行宿主。对应提交 241b607「v8 rules v2 band ladder
+ T+1 TP gate (slice A)」；当年已切 per_name（12d1910 切片B），本书
sizing=per_name、单票预算 100 万。

止损 30%。止盈为涨幅比例回撤阶梯：档位用价格比较
（peak vs cost×(1+arm)），g≥15% 起全局底 cost×1.15；
T+1（n_days<2）只评止损不评止盈；峰值从 T+1 累计。
共同前置 px≥cost。档 1 在 g→0 时线→cost，允许保本乃至费用后微亏退出。
"""

from __future__ import annotations

from typing import Optional

BOOK_TAG = "v8_2"
ALLOW_ADD = True
PEAK_GAP_MIN = 0

STOP_PCT = 0.30

# arm 上界：档1 <6%、档2 <15%、档3 ≤50%、档4 ≤100%、档5 >100%
BAND_ARMS: tuple[float, ...] = (0.06, 0.15, 0.50, 1.00)
# keep 比例：档1/3/4/5（档2 走绝对底）
BAND_KEEPS: tuple[float, ...] = (0.30, 0.60, 0.70, 0.80)
BAND2_ABS_MULT = 1.02
BAND3_GLOBAL_MULT = 1.15


def stop_hits(px: float, cost: float, stop_pct: float = STOP_PCT) -> bool:
    if cost <= 0 or px <= 0:
        return False
    return float(px) / float(cost) - 1.0 <= -float(stop_pct)


def band_of(cost: float, peak: float) -> Optional[int]:
    """峰值所在档 1..5；peak≤cost 返回 None。

    价格比较（plan §1）：(0,6%) / [6%,15%) / [15%,50%] / (50%,100%] / (100%,∞)。
    """
    c = float(cost)
    p = float(peak)
    if c <= 0 or p <= c:
        return None
    if p < c * (1.0 + BAND_ARMS[0]):
        return 1
    if p < c * (1.0 + BAND_ARMS[1]):
        return 2
    if p <= c * (1.0 + BAND_ARMS[2]):
        return 3
    if p <= c * (1.0 + BAND_ARMS[3]):
        return 4
    return 5


def trigger_line(cost: float, peak: float, band: int) -> float:
    """档位触发线（px ≤ 线则止盈）。"""
    c = float(cost)
    p = float(peak)
    if band == 1:
        return c + BAND_KEEPS[0] * (p - c)
    if band == 2:
        return c * BAND2_ABS_MULT
    if band == 3:
        return max(c * BAND3_GLOBAL_MULT, c + BAND_KEEPS[1] * (p - c))
    if band == 4:
        return c + BAND_KEEPS[2] * (p - c)
    return c + BAND_KEEPS[3] * (p - c)


def take_profit_reason(
    px: float,
    cost: float,
    peak: float,
    n_days: int = 1,
) -> Optional[str]:
    """触发止盈则返回 reason（供 CSV `_sell` 使用）。

    n_days<2（T+1）不评估止盈。px<cost 不止盈。reason=`trail:band:{1..5}`。
    """
    if int(n_days) < 2:
        return None
    if cost <= 0 or px <= 0 or peak <= 0:
        return None
    if float(px) < float(cost):
        return None
    band = band_of(cost, peak)
    if band is None:
        return None
    line = trigger_line(cost, peak, band)
    if float(px) <= line:
        return f"trail:band:{band}"
    return None


HELP_LOCK = """
策略 8.2 卖点（--strategy version8_2，241b607 冻结包）规则 v2：
  止损 30 个点（T+1 起）。止盈按峰值涨幅比例回撤阶梯（价格比较分档）：
        (0,6%)→保留涨幅 30%（回撤 70%；g→0 线→cost，允许保本/费用后微亏）；
        [6%,15%)→买入价×1.02；
        [15%,50%]→max(买入价×1.15, 保留涨幅 60%)；
        (50%,100%]→保留 70%；>100%→保留 80%。
  T+1（持仓第 1 个交易日）只评止损不评止盈；峰值从 T+1 累计。
  per_name（默认）：名单每个代码+信号日期各开独立持仓（position_id），各预算 100 万。
        后日再现是新仓，不受旧仓盈亏影响；无价格加仓、无指数 gate。
        追买保留原信号身份和预算；各 lot 自身成本、峰值、T+1 和退出互不连带。
        任一买单所需现金（含费用）不足即 InsufficientCashError，停止回测。
  落盘：backtest_output/csv_{daily|minute}_v8_2_{start}_{end}/
"""


def record_strategy8_2_params(st, *, stop_pct: float = STOP_PCT) -> None:
    st.stats["sell_book"] = BOOK_TAG
    st.stats["stop_pct"] = float(stop_pct)
    st.stats["band_arms"] = list(BAND_ARMS)
    st.stats["band_keeps"] = list(BAND_KEEPS)
    st.stats["band2_abs_mult"] = float(BAND2_ABS_MULT)
    st.stats["band3_global_mult"] = float(BAND3_GLOBAL_MULT)
