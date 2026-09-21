"""Version11 ma_chip rules. Signals are front-domain, fills belong to engines."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from backtest.research.ma_infra import sma_series

BOOK_TAG = "v11"
ALLOW_ADD = False
PEAK_GAP_MIN = 0
CYQK_WINDOW = 200
CYQK_THRESHOLD = 0.70
WEEKLY_WINDOW = 20
MA_EXIT = 5
INITIAL = "entry_close"
HOLD = "hold_sma5"
EXIT = "pending_exit"

HELP_LOCK = """
策略 11 ma_chip（--strategy version11）：
  cyqk>0.70 仓内文档为抛压区，本版=框架验证非已验证多头。
  D=原信号日；T=严格晚于 D 的首根有 bar 交易日；D→T ≤4 自然日。
  front 信号仅用 ≤T-1 数据写 T 名单；周线显式 prefix-equivalent。
  D-1 NaN≠边缘/等号 fail-closed/买入日禁卖。
  a=日线契约收盘买；b=分钟 09:30 首根 open 买（以 b 为准）。
  T 收盘≤昨收→下一交易日开盘卖；否则含 T 当评 close<SMA5（含今日）。
  卖→买→EOD 写 pending_exit；跌停卖延后；卖出日不重入。
  skip_buy 消耗信号；limit_up_chase=False；单票一笔；无止损覆盖。
  必须显式 --pool-dir，拒绝 stock_pool/。
  导出 skip_buy(stale)/skip_cyqk_grid/skip_cyqk_nan/skip_cyqk_error；
  manifest 记录 adjust_type=front 与 Rust pyd __file__、版本。
"""


def _finite(*values) -> bool:
    return all(value is not None and isfinite(float(value)) for value in values)


def edge_condition(
    closes, high_series, bb_upper_series, cyqk_series, weekly_ma_series,
) -> list[bool]:
    """D true and preceding observed bar false, with *both* inputs finite.

    All indicator values include their own day. Weekly values must come from
    ma_infra's explicit prefix path. No shift to a future contract day here.
    """
    ma20 = sma_series(closes, 20)
    ma60 = sma_series(closes, 60)
    result = []
    previous_finite = previous_condition = False
    for close, high, upper, cyqk, weekly, short, long in zip(
        closes, high_series, bb_upper_series, cyqk_series, weekly_ma_series,
        ma20, ma60, strict=True,
    ):
        finite = _finite(close, high, upper, cyqk, weekly, short, long)
        condition = finite and (
            close > short and close > long and close > weekly
            and high > upper and cyqk > CYQK_THRESHOLD
        )
        result.append(bool(finite and previous_finite and condition
                           and not previous_condition))
        previous_finite, previous_condition = finite, condition
    return result


@dataclass(frozen=True)
class ExitDecision:
    hold_mode: str
    reason: str = ""


def exit_signal(t_close, prev_close, sma5, *, hold_mode=INITIAL) -> ExitDecision:
    """EOD decision only; execution is next open subject to engine T+1.

    SMA5 includes today's close. The close-vs-prev test occurs only at the
    entry close; HOLD subsequently tests SMA5 alone. Pending exits persist.
    """
    if hold_mode not in (INITIAL, HOLD, EXIT):
        raise ValueError(f"unknown version11 hold_mode: {hold_mode}")
    if hold_mode == EXIT or not _finite(t_close):
        return ExitDecision(hold_mode)
    if hold_mode == INITIAL:
        if not _finite(prev_close):
            return ExitDecision(INITIAL)
        if t_close <= prev_close:
            return ExitDecision(EXIT, "ma_signal:entry_nonpositive")
        hold_mode = HOLD
    if _finite(sma5) and t_close < sma5:
        return ExitDecision(EXIT, "ma_signal:SMA5")
    return ExitDecision(hold_mode)


def take_profit_reason(*_) -> None:
    """Intraday scanner does not evaluate version11's EOD exit FSM."""
    return None


def record_strategy11_params(st) -> None:
    st.stats.update(
        sell_book=BOOK_TAG, stop_pct=None, limit_up_chase=False,
        cyqk_window=CYQK_WINDOW, cyqk_threshold=CYQK_THRESHOLD,
        weekly_window=WEEKLY_WINDOW, weekly_prefix_equivalent=True,
        ma_sell=MA_EXIT, sma5_includes_today=True,
        skip_sold_today=0, skip_buy_volume=0, defer_sell_volume=0,
    )
