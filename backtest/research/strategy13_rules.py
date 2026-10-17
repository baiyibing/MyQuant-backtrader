"""Beidou A-only book. Human 2026-10-17 cuts; manual performance is not validated."""
from dataclasses import asdict, dataclass, field
import math
from backtest.research.lot_rounding import floor_board_lots, scale_out_board_lots

BOOK_TAG = "v13"
BASE_BUDGET = 10_000.0
NAME_CAP = 0.20
# Register sentinel only: real per-name cap is always cash×NAME_CAP via
# CLI clamp + init_book. Never raise this to "relax" the 20% hard cap.
NAME_BUDGET_DEFER = float("inf")
# Letting winners run: declining sell fractions keep ~30% of the position
# beyond the +200% tier; the 25% trail owns the exit. A uniform +10%/sell-10%
# ladder (r10) kept only ~12% and lost 5.1pp on the same window.
TP_LEVELS = (0.20, 0.40, 0.60, 0.80, 1.00, 1.50, 2.00)
TP_FRACTIONS = (0.20, 0.20, 0.20, 0.15, 0.15, 0.10, 0.10)
BASE_FLOOR = 0.10
CLEAR_DRAWDOWN = 0.25
STOP_PCT = 0.15
ADD_STOP_PCT = 0.10
# ATR-adaptive stops: thresholds scale linearly with the entry-time ATR14%
# around the pool median (3.8%), clamped so the median name behaves exactly
# like the fixed r9 thresholds and only the tails adapt.
ATR_WINDOW = 14
ATR_ANCHOR = 0.038
ATR_CLAMP_TRAIL = (0.18, 0.35)
ATR_CLAMP_HARD = (0.10, 0.25)
ATR_CLAMP_ADD = (0.07, 0.16)
MA_SESSIONS = 3
EARLY_SESSIONS = 30
EARLY_LOSS = 0.05
FIRST_ADD = 1.60
NEXT_ADD = 1.20
FIRST_MULTIPLIER = 42
NEXT_MULTIPLIER = 42
MAX_ADDS = 10
SKIM_STEP = 0.20
SKIM_RATIO = 1.00
PARKING_SYMBOL = "600036.SH"
PARKING_FRAC = 0.95
PARKING_BUFFER = 3_000_000
INDEX_GATE_ON = True
INDEX_SYMBOL = "000001.SH"
INDEX_MAS = (10, 60)
INDEX_CAPS = (0.50, 0.30)


@dataclass(frozen=True)
class Params:
    base_budget: float = BASE_BUDGET
    stop_pct: float = STOP_PCT
    add_stop_pct: float = ADD_STOP_PCT
    atr_anchor: float = ATR_ANCHOR
    clear_drawdown: float = CLEAR_DRAWDOWN
    ma_sessions: int = MA_SESSIONS
    early_sessions: int = EARLY_SESSIONS
    early_loss: float = EARLY_LOSS
    first_add: float = FIRST_ADD
    next_add: float = NEXT_ADD
    first_multiplier: int = FIRST_MULTIPLIER
    next_multiplier: int = NEXT_MULTIPLIER
    max_adds: int = MAX_ADDS
    base_floor: float = BASE_FLOOR
    tp_levels: tuple = TP_LEVELS
    tp_fractions: tuple = TP_FRACTIONS
    skim_step: float = SKIM_STEP

    def __post_init__(self):
        for key, value in asdict(self).items():
            values = value if isinstance(value, (tuple, list)) else [value]
            if not values or any(isinstance(v, bool) or not isinstance(v, (int, float))
                                 or not math.isfinite(v) or v <= 0 for v in values):
                raise ValueError(f"invalid Beidou parameter {key}")
        for key in ("stop_pct", "add_stop_pct", "clear_drawdown", "early_loss",
                    "base_floor", "skim_step"):
            if getattr(self, key) >= 1:
                raise ValueError(f"{key} must be below one")
        for key in ("ma_sessions", "early_sessions",
                    "first_multiplier", "next_multiplier", "max_adds"):
            if int(getattr(self, key)) != getattr(self, key):
                raise ValueError(f"{key} must be integral")
        if (self.max_adds > MAX_ADDS or self.first_add <= 1 or self.next_add <= 1):
            raise ValueError("invalid add schedule (maximum ten)")
        if (len(self.tp_levels) != len(self.tp_fractions)
                or any(a >= b for a, b in zip(self.tp_levels, self.tp_levels[1:]))
                or any(f >= 1 for f in self.tp_fractions)):
            raise ValueError("invalid take-profit tiers")


@dataclass
class Memory:
    entry: float = 0.0
    base_shares: int = 0
    peak: float = 0.0
    entry_idx: int = 0
    last_add: float = 0.0
    adds: int = 0
    tier: int = 0
    below_days: int = 0
    last_ma_day: str = ""
    entry_atr: float = 0.0
    buy_fees: dict = field(default_factory=dict)


def atr_threshold(base, atr, anchor, clamp, inverse=False):
    """Scale a stop threshold by entry ATR around the pool median; fixed when
    ATR is unknown (synthetic books, warm-up). Inverse=True tightens volatile
    names (their stop-afters deepen with ATR in the host diagnostics)."""
    if not atr or atr <= 0:
        return base
    ratio = (anchor / atr) if inverse else (atr / anchor)
    return min(clamp[1], max(clamp[0], base * ratio))


def tp_shares(held, base, fraction, floor=BASE_FLOOR):
    keep = math.ceil(base * floor)
    return max(0, min(scale_out_board_lots(held, fraction),
                      floor_board_lots(held - keep)))


def add_order(mem, px, params):
    line = mem.entry * params.first_add if mem.adds == 0 else mem.last_add * params.next_add
    if mem.adds >= params.max_adds or mem.entry <= 0 or px + 1e-10 < line:
        return 0
    return mem.base_shares * (params.first_multiplier if mem.adds == 0 else params.next_multiplier)


def skim_target(realized, capital, step=SKIM_STEP):
    return max(0, math.floor(realized / (capital * step) + 1e-12)) * capital * step if capital > 0 else 0.0


def take_profit_reason(*args, **kwargs):
    return None  # Stateful partial exits are hosted by the shared scheduler hooks.


HELP_LOCK = """
策略 13 北斗放量启动（--strategy version13 / v13；Human 2026-10-17）：
  A 类名单须 --pool-dir（export_beidou_pool.py；拒绝 stock_pool/）。D 收盘信号→T 开盘。
  per_name：底仓 1 万元（最低 100 股），单只硬帽 cash-total×20%；超帽/现金不足整笔 skip_cash。
  首加买价×1.6 一次加底仓×42（底仓 1 万时即 42 万元）；加仓成交价每 +20% 再加底仓×42，最多 10 次。
  加仓节奏：日线与分钟均每个交易日开盘评估一次（分钟不对盘中每个收盘重复加仓）。
  止盈/止损成交：日线收盘排队次日开盘；分钟走共享 FillConfig（可同 bar / 次开），路径不等同。
  浮盈 20/40/60/80/100/150/200% 各一次卖当前 20/20/20/15/15/10/10%（利润奔跑,留底仓≥10%）。
  高点回撤≥25% 全清；底仓收盘<买价×0.85、每笔加仓独立收盘<该笔加仓价×0.90 止损该笔、
  破 MA20 三日不收回、持有≤30日浮亏≥5% 止损。三档止损按入场 ATR14% **反向**缩放
  （高波动快砍/低波动容忍，锚池中位 3.8%：trail 18–35%/硬 10–25%/加仓 7–16%，
  中位票等同固定值，无 ATR 回退固定值）。
  闲置资金停泊：每日收盘后（现金+停泊市值−300万）×95% 买入 600036，资金池保留 300 万；
  现金不足次日收盘后卖 600036 回补。
  累计已实现策略净收益每 +总投入20%，全部该增量锁入 600036；现金分红再买 600036。
  上证指数(000001.SH)前收盘<MA10/MA60：策略仓(不含停泊)新开/加仓后≤50%/30%，不强卖。
  --beidou-params JSON 显式覆盖规则参数（硬帽20%、最多10次不可放宽）。
  无2%风险公式、主题/监管/B类；筹码单峰仅导出器可选且默认关。手册收益未验证。
"""


def build_index_caps(closes):
    """T exposure limit from completed T-1 close/MA, never today's close."""
    import pandas as pd
    values = pd.Series(closes, dtype=float).sort_index()
    if values.index.has_duplicates or not all(math.isfinite(v) and v > 0 for v in values):
        raise ValueError("HS300 closes must be unique, positive and finite")
    if len(values) <= max(INDEX_MAS):
        raise ValueError(
            f"{INDEX_SYMBOL} requires {max(INDEX_MAS)} preload sessions and a run session")
    ma_fast = values.rolling(INDEX_MAS[0]).mean().shift()
    ma_slow = values.rolling(INDEX_MAS[1]).mean().shift()
    prev = values.shift()
    out = {}
    for day in values.index[max(INDEX_MAS):]:
        cap = 1.0
        if prev.loc[day] < ma_fast.loc[day]:
            cap = INDEX_CAPS[0]
        if prev.loc[day] < ma_slow.loc[day]:
            cap = min(cap, INDEX_CAPS[1])
        out[day.date() if hasattr(day, "date") else day] = cap
    return out


def load_sse_ma10_block_new(start, end, *, root=None):
    """Compatibility entry for load_book_index_gate; returns exposure fractions."""
    from pathlib import Path
    import pandas as pd
    from common.infra.data_root import resolve_index_daily_root
    from oskh_data.symbol_format import to_partition_key
    from backtest.research.csv_minute_backtest_v7 import _as_date

    directory = (Path(root) if root is not None else resolve_index_daily_root()) / "dividend_type=none" / f"symbol={to_partition_key(INDEX_SYMBOL)}"
    files = sorted(directory.glob("*.parquet"))
    if not files:
        raise FileNotFoundError(f"missing {INDEX_SYMBOL} daily partition: {directory}")
    frame = pd.concat([pd.read_parquet(p) for p in files], ignore_index=True)
    column = next((c for c in ("date", "datetime", "timestamp", "time") if c in frame), None)
    if column is None or "close" not in frame:
        raise ValueError(f"{INDEX_SYMBOL} requires date/time and close")
    days = frame[column].map(_as_date)
    if days.duplicated().any():
        raise ValueError(f"duplicate {INDEX_SYMBOL} sessions")
    lo, hi = pd.Timestamp(start).date(), pd.Timestamp(end).date()
    # The lake carries a close=0 placeholder block (2004-2014 on the host
    # tree); trimming non-positive closes only drops far history. A zero row
    # inside the run window would leave that session out of ``caps`` and still
    # fail the preload/window check below.
    closes = {d: float(c) for d, c in zip(days, frame.close) if d <= hi and c > 0}
    caps = build_index_caps(closes)
    window = [d for d in closes if lo <= d <= hi]
    if not window or any(d not in caps for d in window):
        raise ValueError(
            f"{INDEX_SYMBOL} lacks {max(INDEX_MAS)} preload sessions or requested window")
    return {d: caps[d] for d in window}
