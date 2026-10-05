"""Strategy 12: yesterday's MA5/MA10, actual-fill memory and cycle re-entry.

Pure rules: no ledger, data loader or engine imports. The caller supplies
T+1/bonus-filtered sellable lots and owns the per-run Memory instances.
"""

from __future__ import annotations

from backtest.research import strategy_book_helpers as _book_helpers

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from math import isfinite
from typing import Callable, Mapping, Optional

from backtest.research.ma_infra import sma_asof
from backtest.research.market_layer import as_date
from backtest.research.strategy7_rules import build_index_gate

BOOK_TAG = "v12"
ALLOW_ADD = True
PEAK_GAP_MIN = 0
ADD_STEP = 0.20
STOP_FACTOR = 1.0
REDUCE = "ma_signal:MA5-derisk"
STOP = "ma_signal:MA10-stop"
RECLAIM5 = "ma_signal:MA5-reclaim"
RECLAIM10 = "ma_signal:MA10-reclaim"
RECLAIM_FIRST = "reclaim:first_px"
HOLD20 = "force_sell:hold20_below10"
HOLD_DAYS = 20
HOLD_GAIN = 0.10
INDEX_SYMBOL = "000001.SH"
INDEX_MA = 10
INDEX_BELOW_SESSIONS = 2
INDEX_BLOCKS_ADD = False
INDEX_GATE_ON = True


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
    first_px: float | None = None  # First fill. Later adds do not replace it.

    def fresh_buy(self) -> None:
        """Pool/chase cancels unrecovered stop shares. The first price stays."""
        self.reduced = Memory()
        self.stopped = Memory()


@dataclass(frozen=True)
class SellLot:
    lot_id: int
    shares: int
    sellable: int  # Caller has applied T+1 and subtracted locked bonus shares.
    is_step: bool = False
    n_days: int = 0  # Buy day is 0, same clock as T+N.
    cost: float = 0.0


def _ma(closes, n: int) -> float | None:
    value = sma_asof(closes, n)
    return value if value is not None and isfinite(value) and value > 0 else None


def stop_line(ma10: float | None) -> float | None:
    return ma10 * STOP_FACTOR if ma10 is not None and ma10 > 0 else None


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


def clamp_exit(lots, orders, *, keep_anchor: bool) -> list[tuple[int, int]]:
    """Clamp planned lots to current capacity, retaining lot0's derisk floor."""
    by_id = {lot.lot_id: lot for lot in lots}
    result = []
    for lot_id, shares in orders:
        lot = by_id.get(lot_id)
        if lot is None:
            continue
        available = max(0, min(lot.shares, lot.sellable))
        if keep_anchor and lot_id == 0:
            available = min(available, max(0, lot.shares - 100))
        amount = min(int(shares), available)
        if amount:
            result.append((lot_id, amount))
    return result


def hold20_orders(lots, px: float) -> list[tuple[int, int]]:
    """Lots held 20 trading days whose gain is below 10%. Exactly +10% stays.

    Gain is (px - cost) / cost on that lot. Cost 10 clears at 10.99 and stays at 11.00.
    """
    if not isfinite(px) or px <= 0:
        return []
    orders = []
    for lot in lots:
        available = max(0, min(lot.shares, lot.sellable))
        if (
            available
            and lot.n_days >= HOLD_DAYS
            and lot.cost > 0
            and px < lot.cost * (1.0 + HOLD_GAIN)
        ):
            orders.append((lot.lot_id, available))
    return orders


def exit_plan(code, px, day, closes, lots, *, memory: CodeMemory) -> tuple[str, int] | None:
    del code, day, memory
    available = sum(max(0, min(lot.shares, lot.sellable)) for lot in lots)
    line = stop_line(_ma(closes, 10))
    # Inclusive: yesterday MA10=10 triggers at 10.00, not only below it.
    if line is not None and 0 < px <= line and available:
        return STOP, available
    orders = hold20_orders(lots, px)
    wanted = sum(shares for _, shares in orders)
    return (HOLD20, wanted) if wanted else None


def stop_buyback_shares(px: float, first_px: float | None, stopped: Memory) -> int:
    """Stop buyback is closed. Returning to the first fill does not resize an order."""
    del px, first_px, stopped
    return 0


def buyback_plan(px, closes, memory: Memory, *, channel: str = "reduced") -> int:
    """MA5 buyback and stop buyback are both closed."""
    del px, closes, memory, channel
    return 0


def build_sse_ma10_block_new(
    closes: Mapping[date, float], *, symbol: str = INDEX_SYMBOL
) -> dict[date, bool]:
    """上证连续两日收于十日线下 → 次日（第三日）起 `True`=停买新票。"""
    return _book_helpers.build_sse_ma10_block_new(closes, symbol=symbol)


def allow_new_name_from_gate(
    block_new: Optional[Mapping[date, bool]],
) -> Optional[Callable]:
    """`allow_new_name(day) -> bool`。关闸只挡未持仓的新开，已持仓加仓不挡。"""
    return _book_helpers.allow_new_name_from_gate(block_new, INDEX_GATE_ON=INDEX_GATE_ON)


def load_sse_ma10_block_new(start: str, end: str, *, root=None) -> dict[date, bool]:
    """从指数日线湖装载上证收盘并生成停买表。缺数据即失败。"""
    return _book_helpers.load_sse_ma10_block_new(start, end, root=root, build_sse_ma10_block_new=build_sse_ma10_block_new)


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
    """One more 20% step only while shares are still held.

    The anchor is the first fill. Later adds do not replace it. The step count
    never decreases, so a flat name does not buy a step and a later re-entry
    does not restart the count.
    """
    if not lots or not isfinite(px) or px <= 0:
        return False
    anchor = memory.first_px
    if anchor is None or not isfinite(anchor) or anchor <= 0:
        parent = next((lot for lot in lots if lot.lot_id == 0), None)
        anchor = float(parent.cost) if parent is not None else None
    if anchor is None or not isfinite(anchor) or anchor <= 0:
        return False
    allowed = int((px / anchor - 1.0) / ADD_STEP + 1e-12)
    return allowed > memory.steps


def take_profit_reason(*_args) -> None:
    return None


HELP_LOCK = """
策略 12 金榕元均线减仓书（--strategy version12；12/v12 别名）：
  人裁（#151 follow-up，LOCKED）行业约定：
  1) 分钟成交域默认 none（--dividend-type none）；front 仅可选且缺 1m/front 时 fail-closed。
  2) 日线信号域（MA/形态）固定用 daily dividend_type=front。
  3) 分钟成交仍用分钟原始价（none 域）。
  4) 除权只走显式 economics/文档路径；front 日线 + none 分钟下禁止静默双重调整。
  front 缺分区/缺代码行情即失败。MA 序列严格截至昨收。
  分钟逐根 close 评估、当根成交；日线收盘评估、次日开盘卖。
  日线排队卖单锁定信号收盘当时可卖的 lot；信号后同日池/追买/台阶新仓不顶替。
  价格判断以日线均线为准，序列严格截至昨收。5 日线减仓关闭，不再按 MA5 卖出或买回。
  现价 ≤ 昨收 MA10 先止损（含等于；昨收 MA10=10 元时现价到 10.00 元即止损），卖掉可卖股。
  止损买回关闭：价格回到第一次成交价也不再买回止损卖出的股份。
  持有满 20 个交易日且该 lot 涨幅低于 10% 清仓：买入日为 0，n_days>=20，每个 lot 用自己的成本。
  涨幅 = (现价-成本)/成本。涨幅 < 10% 卖可卖股；正好 +10% 不清。成本 10 元时 10.99 清、11.00 留。
  原因 force_sell:hold20_below10。这笔不买回。同一根已触及止损线时仍算止损。
  名单再现：池或追买先成交并清掉尚未买回的止损股数。reduced/stopped 记忆仍在。
  residual=2 / memory<100 / 禁止等归零 只留在减仓记忆类型上；5 日减仓关闭后不再触发。无每日锁。
  latch=A 不再驱动卖出。
  池/chase 成功新买清零止损记忆但保留第一次买入价；台阶计数单调，不因卖掉 is_step lot 而重加。
  per_name 每笔默认 100 万，名单再现输赢都加。
  台阶：相对第一笔成交价每上涨 20% 且当时仍持仓，加一笔 100 万。仓位卖光不加。
  第一笔成交价不因台阶或后来的名单加仓而改变。台阶次数只增不减，每天每只最多一笔。
  上证闸：000001.SH 日线收盘，十日线截至昨收。连续两日都收在各自十日线下方，次日起停买新票；
  任一日收盘 >= 当日十日线，再下一日恢复开新仓。只低一日不关闸。缺指数数据则失败。
  关闸只挡未持仓的池买入和追买，记 skip_index_gate，被挡的追买不再留到下一天。
  已持仓的名单加仓、追买加仓和 +20% 台阶照常。止损和 20 日清仓不受闸影响。
  单码单日买向：池 1 + chase 1 + 台阶 N，可能 5+ 笔。
  chase px==open 时 abandon。
  50% 是计划上限，容量/locked bonus 可使实际卖量不整百；记忆只计实际成交。
  多 lot 分拆卖单会重复最低佣金，可能高估费用；研究费用模型不含印花税。
  送转仅显式 exdiv_economics 开启时按股数倍数缩放，floor100 + 残余 stats；
  现金红利不缩放记忆。该送转取整独立于 residual=2 的成交残余保留规则。
  reserve_limit_up=False / defer_limit_up=False / daily_same_bar_prefixes=()；
  书侧自管止损，MA peak_gap_min=0。默认 stock_pool/；v7 仍用独立入口及必填池。
"""


def record_strategy12_params(st) -> None:
    # price_domain here documents strategy-level signal-domain baseline ("front").
    # Minute run() stamps the realized fill domain after dividend_type routing.
    st.stats.update(sell_book=BOOK_TAG, stop_pct=None, allow_add=True,
                    peak_gap_min=0, index_gate_on=True, add_step=ADD_STEP,
                    latch="A", residual=2, price_domain="front")
