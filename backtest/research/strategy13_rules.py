"""Beidou A-only book. Human 2026-10-17 cuts; manual performance is not validated."""
from dataclasses import asdict, dataclass, field
import math

BOOK_TAG = "v13"
BASE_BUDGET = 10_000.0
NAME_CAP = 0.20
TP_LEVELS = (0.20, 0.40, 0.60, 0.80, 1.00, 1.50, 2.00)
TP_FRACTIONS = (0.15, 0.20, 0.20, 0.25, 0.25, 0.30, 0.30)
BASE_FLOOR = 0.10
CLEAR_DRAWDOWN = 0.25
STOP_PCT = 0.15
MA_SESSIONS = 3
EARLY_SESSIONS = 30
EARLY_LOSS = 0.05
FIRST_ADD = 1.60
NEXT_ADD = 1.10
FIRST_MULTIPLIER = 42
NEXT_MULTIPLIER = 35
MAX_ADDS = 10
SKIM_STEP = 0.20
SKIM_RATIO = 1.00
PARKING_SYMBOL = "600036.SH"
INDEX_GATE_ON = True
INDEX_SYMBOL = "000300.SH"
INDEX_MAS = (60, 120)
INDEX_CAPS = (0.50, 0.30)


@dataclass(frozen=True)
class Params:
    base_budget: float = BASE_BUDGET
    stop_pct: float = STOP_PCT
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
        for key in ("stop_pct", "clear_drawdown", "early_loss", "base_floor", "skim_step"):
            if getattr(self, key) >= 1:
                raise ValueError(f"{key} must be below one")
        for key in ("ma_sessions", "early_sessions", "first_multiplier", "next_multiplier", "max_adds"):
            if int(getattr(self, key)) != getattr(self, key):
                raise ValueError(f"{key} must be integral")
        if self.max_adds > MAX_ADDS or self.first_add <= 1 or self.next_add <= 1:
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
    buy_fees: dict = field(default_factory=dict)


def tp_shares(held, base, fraction, floor=BASE_FLOOR):
    keep = math.ceil(base * floor)
    return max(0, min(int(held * fraction) // 100 * 100,
                      (held - keep) // 100 * 100))


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
  首加买价×1.6，底仓×42；以后实际加仓价每 +10% 加底仓×35，最多 10 次。
  浮盈 20/40/60/80/100/150/200% 各一次卖当前 15/20/20/25/25/30/30%，留底仓≥10%。
  高点回撤≥25% 全清；收盘<买价×0.85、破 MA20 三日不收回、持有≤30日浮亏≥5% 止损。
  累计已实现策略净收益每 +总投入20%，全部该增量锁入 600036；现金分红再买 600036。
  HS300 前收盘<MA60/MA120：新开/加仓后总仓≤50%/30%，不强卖。
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
        raise ValueError("HS300 requires 120 preload sessions and a run session")
    ma60 = values.rolling(INDEX_MAS[0]).mean().shift()
    ma120 = values.rolling(INDEX_MAS[1]).mean().shift()
    prev = values.shift()
    out = {}
    for day in values.index[max(INDEX_MAS):]:
        cap = 1.0
        if prev.loc[day] < ma60.loc[day]:
            cap = INDEX_CAPS[0]
        if prev.loc[day] < ma120.loc[day]:
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
        raise FileNotFoundError(f"missing HS300 daily partition: {directory}")
    frame = pd.concat([pd.read_parquet(p) for p in files], ignore_index=True)
    column = next((c for c in ("date", "datetime", "timestamp", "time") if c in frame), None)
    if column is None or "close" not in frame:
        raise ValueError("HS300 requires date/time and close")
    days = frame[column].map(_as_date)
    if days.duplicated().any():
        raise ValueError("duplicate HS300 sessions")
    lo, hi = pd.Timestamp(start).date(), pd.Timestamp(end).date()
    closes = {d: float(c) for d, c in zip(days, frame.close) if d <= hi}
    caps = build_index_caps(closes)
    window = [d for d in closes if lo <= d <= hi]
    if not window or any(d not in caps for d in window):
        raise ValueError("HS300 lacks 120 preload sessions or requested window")
    return {d: caps[d] for d in window}
