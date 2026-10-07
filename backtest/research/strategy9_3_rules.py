"""Strategy 9.3: delay SCAN entries by three sessions, then use fixed exits."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import pandas as pd

from backtest.research import strategy9_rules

BOOK_TAG = "v9_3"
ALLOW_ADD = False
PEAK_GAP_MIN = 0
DELAY_DAYS = 3
MAX_HOLD = 20
STOP_FRAC = 0.90
REQUIRES_EXPLICIT_POOL = True

HELP_LOCK = """
version9_3 / v9.3: export_strategy9_pool.py SCAN pool only; explicit
--pool-dir is required and the repository stock_pool/ is refused.
Pool filename date T is the signal day. Only pool files with T in [start, end]
are read; buy on the third engine trading day after T (T+3).
Daily fills at the T+3 open; minute fills through the existing 14:55 first-buy
fallback. A T+3 limit-up, missing name bar, held name, or target outside the
backtest calendar is skipped without retry. Colliding signal days are stable-unioned.
No adds, no chase, and no 20-bar range stop. Profit reaching weighted entry
cost ×1.10 returns profit_take:target, the same as version9: daily decides at
the close and sells at the next open; minute sells intraday at the target.
Whole-position stop = weighted entry cost ×0.90. Daily gap fills at open and
touch fills at the line; minute uses the shared absolute-exit cursor convention.
T+1 and limit-down deferral apply. --hold-days {20,30} (default 20) selects
the maximum hold. At n_days>=hold_days, decide force_sell:max_hold at the close
and sell at the next open, deferring limit-down sessions. --stop-pct is refused.
Output for 20: csv_{daily|minute}_v9_3_{start}_{end}/; for 30 the path includes
_h30_: csv_{daily|minute}_v9_3_h30_{start}_{end}/.
"""


@dataclass(frozen=True)
class ShiftedPool:
    pool_days: dict[str, list[str]]
    pool_names_by_day: dict[str, dict[str, str]] | None
    stats: dict[str, int]


def _ymd(value) -> str:
    return pd.Timestamp(value).strftime("%Y%m%d")


def _frame_days(frame) -> set[str]:
    if frame is None or getattr(frame, "empty", True):
        return set()
    if "ymd" in frame.columns:
        return {str(value).replace("-", "")[:8] for value in frame["ymd"]}
    return {_ymd(value) for value in frame.index}


def shift_pool_days(
    pool_days: Mapping[object, list[str]],
    calendar,
    bars: Mapping[str, object],
    pool_names_by_day: Mapping[object, Mapping[str, str]] | None = None,
) -> ShiftedPool:
    """Pure T -> T+3 remap over the engine calendar with deterministic unioning."""
    days = [_ymd(day) for day in calendar]
    day_index = {day: index for index, day in enumerate(days)}
    available = {code: _frame_days(frame) for code, frame in bars.items()}
    shifted: dict[str, list[str]] = {}
    shifted_names: dict[str, dict[str, str]] | None = {} if pool_names_by_day is not None else None
    counts = {
        "skip_v9_3_delay_out_of_window": 0,
        "skip_v9_3_no_bar": 0,
    }
    names_by_signal = {_ymd(day): dict(names) for day, names in (pool_names_by_day or {}).items()}

    normalized = sorted(
        ((_ymd(signal_day), list(codes)) for signal_day, codes in pool_days.items()),
        key=lambda item: item[0],
    )
    for signal_day, raw_codes in normalized:
        codes = list(dict.fromkeys(raw_codes))
        signal_index = day_index.get(signal_day)
        if signal_index is None or signal_index + DELAY_DAYS >= len(days):
            counts["skip_v9_3_delay_out_of_window"] += len(codes)
            continue
        buy_day = days[signal_index + DELAY_DAYS]
        accepted = shifted.setdefault(buy_day, [])
        accepted_set = set(accepted)
        target_names = shifted_names.setdefault(buy_day, {}) if shifted_names is not None else None
        source_names = names_by_signal.get(signal_day, {})
        for code in codes:
            if buy_day not in available.get(code, set()):
                counts["skip_v9_3_no_bar"] += 1
                continue
            if code not in accepted_set:
                accepted.append(code)
                accepted_set.add(code)
            if target_names is not None and code in source_names:
                target_names.setdefault(code, source_names[code])

    return ShiftedPool(
        pool_days={day: codes for day, codes in shifted.items() if codes},
        pool_names_by_day=(
            {day: names for day, names in shifted_names.items() if names}
            if shifted_names is not None
            else None
        ),
        stats=counts,
    )


def max_hold_reason(px, cost, peak, n_days, *, hold_days: int = MAX_HOLD):
    """At the configured held-session close, queue the existing next-open reason."""
    del px, cost, peak
    return "force_sell:max_hold" if int(n_days) >= hold_days else None


def weighted_entry_cost(lots) -> float | None:
    live = [(float(lot.cost), int(lot.shares)) for lot in lots if int(lot.shares) > 0]
    shares = sum(quantity for _, quantity in live)
    return sum(cost * quantity for cost, quantity in live) / shares if shares > 0 else None


def stop_line(lots) -> float | None:
    cost = weighted_entry_cost(lots)
    return None if cost is None else cost * STOP_FRAC


def bind_absolute_exit(st, frames):
    """Bind the shared absolute-exit hook to current weighted entry cost."""
    del frames

    def line(code, day):
        del day
        return stop_line(st.positions.get(code, ()))

    return line


def record_strategy9_3_params(st, *, hold_days: int = MAX_HOLD) -> None:
    st.stats.update(
        sell_book=BOOK_TAG,
        stop_pct=None,
        stop_mode="weighted_entry_cost_fixed_10pct",
        stop_frac=STOP_FRAC,
        delay_days=DELAY_DAYS,
        max_hold=hold_days,
        profit_target=strategy9_rules.TAKE_PROFIT_PCT,
        skip_v9_3_delay_out_of_window=0,
        skip_v9_3_no_bar=0,
    )
