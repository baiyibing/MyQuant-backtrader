"""X-02 red example committed before the chronological engine."""

import pytest
from backtest.research.csv_ledger import InsufficientCashError
from backtest.research.csv_minute_backtest import simulate

from tests.minute_cash_fixtures import chronological_case, money
from tests.test_minute_cash_chronology import assert_insufficient_cash


def test_group_exit_off_scan_cannot_borrow_1459_proceeds_for_1455_buy():
    # Price-add groups resume their exit scan after the 14:55 add boundary.
    with pytest.raises(InsufficientCashError) as exc:
        simulate(**chronological_case())
    assert_insufficient_cash(exc.value, date="20251105")


def test_chronological_cash_cannot_borrow_future_proceeds():
    trace = []
    with pytest.raises(InsufficientCashError) as exc:
        simulate(**chronological_case(), fix_minute_cash_order=True, audit_sink=trace)
    assert_insufficient_cash(exc.value, date="20251105")
    assert [(t["code"], t["side"], t["decision_hm"]) for t in trace] == [
        ("600000.SH", "BUY", 895)
    ]
    assert money(trace[-1]["cash_after"]) == 0
