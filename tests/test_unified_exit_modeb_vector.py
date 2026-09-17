import numpy as np
import pytest

from backtest.research import unified_exit_modea as a
from backtest.research import unified_exit_modeb as b
from tests.test_unified_exit_modeb_exit import CODE, INST, SESS, daily, frames


def _both(rows, spec, **kw):
    minutes = frames(rows)
    bars = daily()
    fast = b.evaluate_exit_modeb(INST, spec, bars, minutes, SESS, end=SESS[-1], impl="fast", **kw)
    ref = b.evaluate_exit_modeb(INST, spec, bars, minutes, SESS, end=SESS[-1], impl="ref", **kw)
    return fast, ref


def test_fast_matches_ref_on_threshold_and_gap():
    cases = [
        ([(1, 600, 100, 106, 94, 94)], a.StrategySpec(2, 3, 5, 5)),
        ([(1, 600, 94, 106, 94, 102)], a.StrategySpec(2, 3, 5, 5)),
        ([(1, 600, 106, 106, 99, 100)], a.StrategySpec(2, 3, 5, 5)),
        ([(1, 600, 100, 106, 94, 102)], a.StrategySpec(2, 3, 5, 5)),
        ([(1, 600, 94, 106, 94, 106)], a.StrategySpec(2, 3, 5, 5)),
        ([(1, 600, 100, 106, 100, 106), (1, 899, 100, 101, 99, 100)], a.StrategySpec(2, 1, 5, 5)),
        ([(1, 600, 100, 106, 100, 106), (1, 899, 100, 101, 99, 100)], a.StrategySpec(1, 1)),
        ([(1, 600, 104, 200, 99, 104), (3, 600, 98, 100, 97, 98)], a.StrategySpec(3, 3, y=5)),
        ([(1, 600, 100, 100, 89, 90), (1, 840, 100, 110, 99, 106),
          (2, 600, 100, 106, 100, 106)], a.StrategySpec(2, 3, 5, 5)),
        ([], a.StrategySpec(1, 1)),
        ([(1, 600, 103, 200, 1, 103)], a.StrategySpec(0, None)),
    ]
    for rows, spec in cases:
        fast, ref = _both(rows, spec)
        assert (fast.reason, fast.sell_price, fast.sell_date, fast.sell_hm, fast.is_trade) == (
            ref.reason, ref.sell_price, ref.sell_date, ref.sell_hm, ref.is_trade
        )
        assert fast.pnl == pytest.approx(ref.pnl)
        assert fast.shares == pytest.approx(ref.shares)


def test_matrix_reuses_path_and_matches_single_calls():
    minutes = frames([(1, 600, 100, 106, 100, 106), (1, 900, 100, 101, 99, 100)])
    specs = [a.StrategySpec(2, 1, 5, 5), a.StrategySpec(2, 1, 10, 10), a.StrategySpec(1, 1)]
    matrix = b.evaluate_matrix([INST], specs, daily(), minutes, SESS, end=SESS[-1])
    for spec in specs:
        single = b.evaluate_exit_modeb(INST, spec, daily(), minutes, SESS, end=SESS[-1])
        er = matrix[spec.label()][a.instance_key(INST)]
        assert (er.reason, er.sell_price, er.sell_hm) == (single.reason, single.sell_price, single.sell_hm)


def test_random_paths_match_ref():
    rng = np.random.default_rng(39)
    specs = [
        a.StrategySpec(2, 2, 5, 5),
        a.StrategySpec(2, 3, 10, None),
        a.StrategySpec(1, 2),
        a.StrategySpec(3, 3, y=5),
        a.StrategySpec(0, None),
    ]
    for _ in range(20):
        rows = []
        for day in (1, 2, 3):
            if rng.random() < 0.15:
                continue
            n = int(rng.integers(1, 5))
            for k in range(n):
                hm = 600 + k * 30
                close = float(rng.uniform(88, 112))
                opn = float(rng.uniform(88, 112))
                rows.append((day, hm, opn, max(opn, close) + 1, min(opn, close) - 1, close))
        spec = specs[int(rng.integers(0, len(specs)))]
        fast, ref = _both(rows, spec)
        assert (fast.reason, fast.sell_date, fast.sell_hm, fast.is_trade) == (
            ref.reason, ref.sell_date, ref.sell_hm, ref.is_trade
        )
        assert fast.sell_price == pytest.approx(ref.sell_price)
        assert fast.pnl == pytest.approx(ref.pnl)


def test_prepared_minutes_does_not_need_days_for_scan():
    minutes = b.PreparedMinutes(frames([(1, 600, 100, 106, 100, 106)]))
    assert minutes._days is None
    er = b.evaluate_exit_modeb(
        INST, a.StrategySpec(2, 1, 5, 5), daily(), minutes, SESS, end=SESS[-1]
    )
    assert er.reason == "take_profit"
    assert minutes._days is None
    assert minutes.last_close(CODE, SESS[1]) == 106.0
