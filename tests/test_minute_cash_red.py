"""X-02 red example committed before the chronological engine."""

import pytest

from backtest.research.csv_minute_backtest import simulate
from tests.minute_cash_fixtures import chronological_case, money


def test_legacy_borrows_1459_proceeds_for_1455_buy():
    state = simulate(**chronological_case())
    assert money(state.cash) == money(338.46)
    assert [t["side"] for t in state.trades if t["side"] in {"BUY", "SELL"}] == ["BUY", "SELL", "BUY"]


@pytest.mark.xfail(strict=True, reason="X-02 chronological engine not implemented yet")
def test_chronological_cash_cannot_borrow_future_proceeds():
    state = simulate(**chronological_case(), fix_minute_cash_order=True)
    assert money(state.cash) == money(939.06)
    assert "600001.SH" not in state.positions
