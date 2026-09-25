"""Audit uses actual invocation clocks and is observational only."""

from dataclasses import asdict

import pytest
from backtest.research.csv_minute_backtest import simulate

from tests.minute_cash_fixtures import chronological_case, money


@pytest.mark.parametrize("enabled", [False, True])
def test_sidecar_preserves_state_and_records_real_clock_cash(enabled):
    trace = []
    plain = simulate(**chronological_case(), fix_minute_cash_order=enabled)
    observed = simulate(**chronological_case(), fix_minute_cash_order=enabled, audit_sink=trace)
    assert asdict(observed) == asdict(plain)
    assert "fix_minute_cash_order" not in observed.stats
    assert len(trace) == 3
    assert [(row["decision_hm"], row["side"]) for row in trace] == (
        [(895, "BUY"), (895, "SKIP"), (899, "SELL")] if enabled
        else [(895, "BUY"), (899, "SELL"), (895, "BUY")]
    )
    for row in trace:
        amount = row["notional"]
        expected = (row["cash_before"] - amount - row["commission"] if row["side"] == "BUY"
                    else row["cash_before"] + amount - row["commission"])
        assert money(row["cash_after"]) == money(expected)
        assert money(row["cash_after"]) >= 0
        assert row["hm"] == row["decision_hm"] == row["quote_hm"]
        assert row["phase"] == "close"


def test_target_decision_clock_retains_earlier_quote_clock():
    trace = []
    # Capacity callback contract is tested in the chronology suite; this audit
    # control intentionally leaves capacity disabled while retaining quote_hm.
    state = simulate(**chronological_case(sell_hm=893, buy_hm=890),
                     fix_minute_cash_order=True, audit_sink=trace)
    assert money(state.cash) == money(338.46)
    assert trace[-1]["decision_hm"] == 895
    assert trace[-1]["quote_hm"] == 890
    assert trace[-1]["phase"] == "close"
