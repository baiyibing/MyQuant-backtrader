"""A discarded equal-slice residual does not waive a strict parent's funding check."""

import pytest
from backtest.research.csv_ledger import InsufficientCashError
from backtest.research.tail_window_buy import TAIL_MINUTES

from tests.test_tail_window_allocation_regressions import (
    A, PER_NAME_STRATEGIES, _assert_cash_error, _bar, _simulate,
)


@pytest.mark.parametrize("strategy", PER_NAME_STRATEGIES)
def test_full_target_cash_check_survives_equal_slice_rounding(strategy):
    rows = {A: [_bar(hm) for hm in TAIL_MINUTES]}
    options = dict(pool=[A], strategy=strategy,
                   name_budget=59_980 if strategy == "version8_3" else 29_990,
                   min_cost=5)
    # The original 2900-share target needs 29005; 28 equal slices need 28140.
    with pytest.raises(InsufficientCashError) as caught:
        _simulate(rows, **options, total_cash=29_004)
    _assert_cash_error(caught.value, code=A, needed=29_005, available=29_004)
    state = _simulate(rows, **options, total_cash=29_005)
    buys = [row for row in state.trades if row["side"] == "BUY"]
    assert [row["shares"] for row in buys] == [100] * 28
    assert state.cash == pytest.approx(865)
