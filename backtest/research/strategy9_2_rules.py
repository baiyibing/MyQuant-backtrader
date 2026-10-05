"""Paper turtle rules; SCAN pool comes exclusively from export_strategy9_pool.py."""
from dataclasses import dataclass
from math import prod

from backtest.research.strategy9_rules import RANGE_BARS, mean_true_range

BOOK_TAG = "v9_2"
ALLOW_ADD = True
PEAK_GAP_MIN = 0
INIT_POS_RATIO = 0.40
TURTLE_ADD_BANDS = ((0.04, 0.30), (0.10, 0.20))
MAX_UNITS = 3
SELL_BANDS = (1.3, 1.5, 1.8, 2.0)
SELL_RATIOS = (0.30, 0.20, 0.30, 0.20)
HOLD_DAYS = 20
GIVEBACK_BANDS = ((0.20, 0.50), (0.50, 0.40), (float("inf"), 0.20))
HELP_LOCK = """
version9_2: OSkhQuant1.3 paper turtle; SCAN export_strategy9_pool.py only.
Explicit --pool-dir required; stock_pool/ and --stop-pct refused.
Budget 1_000_000: first 40%, adds 30%/20% at first-fill ×1.04/1.10;
max 3 units, multiple touched adds per session. No touch means no add.
Whole-position stop: weighted cost minus the simple mean of the prior 20 true ranges,
recomputed each day from 21 bars strictly before T; no 10% line.
Missing or invalid window means no stop that day.
At cost ×1.3/1.5/1.8/2.0 sell 30%/20%/30%/20% of remaining shares.
Newly crossed bands merge frac = 1 - product(1 - ratios); highest dispatched
band never re-fires. Partial quantity rounds down to 100 shares.
Held >=20 trading days since first/last add, units<3, price<next line: flatten.
After 3 units profit giveback thresholds: peak gain <=20%:50%, <=50%:40%, else:20%.
Daily SCAN first buy fills open; then high-touched adds fill max(open, line).
Daily stops: open <= trigger fills open, else low <= trigger fills trigger.
Other daily close exits fill next open; OHLC assumes open -> high -> close.
Minute buys first at 14:55 (existing fallback), adds evaluate highs of subsequent bars at max(open, line);
Minute stops: open <= trigger fills open, else close <= trigger fills close.
Stops precede scale-out, hold flatten and giveback; peak uses observed high after entry.
Limit-up buys skip; limit-down pending and T+1 residual retry next session.
"""

@dataclass
class Memory:
    units: int = 0
    entry: float = 0.0
    last_add_price: float = 0.0
    anchor_idx: int = 0
    sell_band_seq: int = 0
    peak: float = 0.0
    cost: float = 0.0


def next_add_line(entry, units):
    return entry * (1 + TURTLE_ADD_BANDS[max(0, units - 1)][0]) if units < MAX_UNITS else None


def add_due(entry, units, price):
    line = next_add_line(entry, units)
    return units > 0 and line is not None and price >= line


def lot_budget(budget, units):
    return budget * (INIT_POS_RATIO if units == 0 else TURTLE_ADD_BANDS[units - 1][1]) if units < MAX_UNITS else 0.0


def chosen_stop(cost, frame, day):
    """Weighted cost minus the daily recomputed mean true range; no fallback."""
    distance = mean_true_range(frame, day)
    return None if distance is None else cost - distance


def scale_out(price, cost, seq=0):
    target = max([seq] + [i + 1 for i, band in enumerate(SELL_BANDS) if price >= cost * band])
    return target, round(1 - prod(1 - x for x in SELL_RATIOS[seq:target]), 4)


def time_stop(price, entry, units, held):
    return held >= HOLD_DAYS and units < MAX_UNITS and price < next_add_line(entry, units)


def giveback(price, cost, high, units):
    if units < MAX_UNITS or high <= cost or cost <= 0:
        return False
    gain = (high - cost) / cost
    threshold = next(ratio for ceiling, ratio in GIVEBACK_BANDS if gain <= ceiling)
    return (high - price) / (high - cost) >= threshold - 1e-12


def record_strategy9_2_params(st):
    st.stats.update(sell_book=BOOK_TAG, stop_pct=None, stop_mode="cost_minus_mean_true_range_20_trailing",
                    init_pos_ratio=INIT_POS_RATIO, turtle_add_bands=TURTLE_ADD_BANDS,
                    max_units=MAX_UNITS, range_bars=RANGE_BARS,
                    sell_bands=SELL_BANDS, sell_ratios=SELL_RATIOS, hold_days=HOLD_DAYS,
                    giveback_bands=GIVEBACK_BANDS, scale_merge="1-product(1-ratios)")


def take_profit_reason(*args, **kwargs):
    """Compatibility hook: exits require position-aware exit_plan."""
    return None
