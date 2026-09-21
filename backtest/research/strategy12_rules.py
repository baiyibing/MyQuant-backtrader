"""Strategy 12: yesterday's MA5/MA10, actual-fill memory and cycle re-entry.

Pure rules: no ledger, data loader or engine imports. The caller supplies
T+1/bonus-filtered sellable lots and owns the per-run Memory instances.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from math import isfinite

from backtest.research.ma_infra import sma_asof

BOOK_TAG = "v12"
ALLOW_ADD = True
PEAK_GAP_MIN = 0
ADD_STEP = 0.20
REDUCE = "ma_signal:MA5-derisk"
STOP = "ma_signal:MA10-stop"
RECLAIM5 = "ma_signal:MA5-reclaim"
RECLAIM10 = "ma_signal:MA10-reclaim"


@dataclass
class Memory:
    """One channel's actual unbought shares; residual=2, never write off dust.

    MA5 uses latched to gate reduction. MA10 still stops every eligible lot;
    its latch records an outstanding reclaim, never suppresses a stop.
    """

    shares: int = 0
    latched: bool = False

    def sold(self, shares: int) -> None:
        if shares > 0:
            self.shares += int(shares)
            self.latched = True

    def reclaimed(self, filled: int = 0) -> None:
        """Call only on a qualified reclaim, even with no buy for <100 shares."""
        if not 0 <= filled <= self.shares:
            raise ValueError("buyback fill must be within channel memory")
        self.shares -= int(filled)
        if self.shares < 100:
            self.latched = False


@dataclass
class CodeMemory:
    reduced: Memory = field(default_factory=Memory)
    stopped: Memory = field(default_factory=Memory)
    steps: int = 0  # Monotonic, independent of surviving is_step lots.

    def fresh_buy(self) -> None:
        """Successful pool/chase buys cancel both outstanding buyback channels."""
        self.reduced = Memory()
        self.stopped = Memory()


@dataclass(frozen=True)
class SellLot:
    lot_id: int
    shares: int
    sellable: int  # Caller has applied T+1 and subtracted locked bonus shares.
    is_step: bool = False


def _ma(closes, n: int) -> float | None:
    value = sma_asof(closes, n)
    return value if value is not None and isfinite(value) and value > 0 else None


def stop_line(ma10: float | None) -> float | None:
    return ma10 * 0.90 if ma10 is not None and ma10 > 0 else None


def de_risk_signal(px: float, closes) -> str | None:
    ma5 = _ma(closes, 5)
    return REDUCE if ma5 is not None and 0 < px < ma5 else None


def reclaim_signal(px: float, closes, *, channel: str = "reduced") -> str | None:
    n, reason = {"reduced": (5, RECLAIM5), "stopped": (10, RECLAIM10)}[channel]
    ma = _ma(closes, n)
    return reason if ma is not None and isfinite(px) and px >= ma else None


def allocate_exit(lots, shares: int, *, keep_anchor: bool) -> list[tuple[int, int]]:
    """Step lots first, other ids ascending, lot0 last with >=100 on derisk."""
    ordered = sorted(lots, key=lambda lot: (2 if lot.lot_id == 0 else 0 if lot.is_step else 1, lot.lot_id))
    result = []
    remaining = shares
    for lot in ordered:
        available = max(0, min(lot.shares, lot.sellable))
        if keep_anchor and lot.lot_id == 0:
            available = min(available, max(0, lot.shares - 100))
        amount = min(available, remaining)
        if amount:
            result.append((lot.lot_id, amount))
            remaining -= amount
        if remaining == 0:
            break
    return result


def exit_plan(code, px, day, closes, lots, *, memory: CodeMemory) -> tuple[str, int] | None:
    del code, day
    available = sum(max(0, min(lot.shares, lot.sellable)) for lot in lots)
    line = stop_line(_ma(closes, 10))
    if line is not None and 0 < px < line and available:
        return STOP, available
    if memory.reduced.latched or not de_risk_signal(px, closes):
        return None
    wanted = available // 200 * 100
    capacity = sum(q for _, q in allocate_exit(lots, wanted, keep_anchor=True))
    wanted = capacity // 100 * 100
    return (REDUCE, wanted) if wanted else None


def buyback_plan(px, closes, memory: Memory, *, channel: str = "reduced") -> int:
    if not reclaim_signal(px, closes, channel=channel):
        return 0
    return memory.shares // 100 * 100


def scale_memory(memory: CodeMemory, share_factor) -> dict[str, float]:
    """P9③ exdiv only: floor100 and report discarded scaled residuals.

    This explicit exdiv rounding cut is distinct from retained fill residuals.
    Cash dividends (factor=1) leave both memories untouched.
    """
    factor = Decimal(str(share_factor))
    if not factor.is_finite() or factor <= 0:
        raise ValueError("share factor must be finite and positive")
    residuals = {}
    if factor == 1:
        return residuals
    for channel in ("reduced", "stopped"):
        item = getattr(memory, channel)
        scaled = Decimal(item.shares) * factor
        item.shares = int(scaled // 100) * 100
        residuals[channel] = float(scaled - item.shares)
    return residuals


def step_add_due(lots, px: float, *, memory: CodeMemory) -> bool:
    parent = next((lot for lot in lots if lot.lot_id == 0), None)
    if parent is None or parent.cost <= 0 or not isfinite(px) or px <= 0:
        return False
    allowed = int((px / parent.cost - 1.0) / ADD_STEP + 1e-12)
    return allowed > memory.steps


def take_profit_reason(*_args) -> None:
    return None


HELP_LOCK = """
策略 12 金榕元均线减仓书（--strategy version12；12/v12 别名）：
  价域 front；MA5/MA10 序列严格截至昨收，现价不混入均线。
  分钟逐根 close 评估、当根成交；日线收盘评估、次日开盘卖。
  MA10×0.90 下方先止损；MA5 下方减 t1_sellable 的 50%，floor100。
  is_step 先卖、中间 lot_id 升序、lot0 最后且减仓保留至少 100 股。
  latch=A：只有周期锁；成功收复后立即再武装，同日可再次减仓，无每日锁。
  residual=2：reduced/stopped 两通道均保留 <100 股买回残余，合入下一轮。
  memory<100 且无买入时，合格 reclaim 也保留残余并 re-arm；禁止等归零。
  买回分别要求现价 >= 昨收 MA5/MA10，上限为对应记忆，整百股，按实际成交扣减。
  买回仍过涨跌停、费用、容量门；当日买回股份 T+1 才可卖，现金不足 skip_cash。
  池/chase 成功新买清零双记忆；台阶计数单调，不因卖掉 is_step lot 而重加。
  per_name 每笔默认 100 万，名单再现输赢都加，+20% 台阶；无上证闸。
  单码单日买向不加闸：池 1 + chase 1 + 台阶 N + 双通道买回，可能 5+ 笔；
  周期可同日重复，买回总笔数没有每日上限。chase px==open 时 abandon。
  50% 是计划上限，容量/locked bonus 可使实际卖量不整百；记忆只计实际成交。
  多 lot 分拆卖单会重复最低佣金，可能高估费用；研究费用模型不含印花税。
  送转仅显式 exdiv_economics 开启时按股数倍数缩放，floor100 + 残余 stats；
  现金红利不缩放记忆。该送转取整独立于 residual=2 的成交残余保留规则。
  reserve_limit_up=False / defer_limit_up=False / daily_same_bar_prefixes=()；
  书侧自管止损，MA peak_gap_min=0。默认 stock_pool/；v7 仍用独立入口及必填池。
"""


def record_strategy12_params(st) -> None:
    st.stats.update(sell_book=BOOK_TAG, stop_pct=None, allow_add=True,
                    peak_gap_min=0, index_gate_on=False, add_step=ADD_STEP,
                    latch="A", residual=2, price_domain="front")
