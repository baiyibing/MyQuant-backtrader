"""G6: observed frame dates must retain non-pool holding sessions."""
from datetime import date, timedelta

import pandas as pd
import pytest

from backtest.research.csv_minute_backtest_v7 import simulate_v7


SYMBOL = "600000.SH"
D1 = date(2026, 9, 1)
D2 = date(2026, 9, 2)
D3 = date(2026, 9, 3)


def inputs(days, prices):
    records = [{"date": day, "hm": 895, "open": price, "high": price,
                "low": price, "close": price} for day, price in zip(days, prices)]
    frame = pd.DataFrame(records, index=pd.DatetimeIndex(
        [f"{day} 14:55" for day in days]))
    daily = {SYMBOL: {D1 - timedelta(days=1): 100.0,
                      **dict(zip(days, prices))}}
    return {SYMBOL: frame}, {SYMBOL: records}, daily


def dates(state):
    return [row["date"] for row in state.equity_curve]


@pytest.mark.parametrize("index_days", [None, [], ()])
@pytest.mark.parametrize("cash_order", [False, True])
def test_non_pool_holding_mark_and_stop_match_records(index_days, cash_order):
    frames, records, daily = inputs([D1, D2, D3], [100, 98, 89])
    kwargs = dict(index_days=index_days, fix_minute_cash_order=cash_order)
    result = simulate_v7(frames, daily, {D1: [SYMBOL]}, **kwargs)
    reference = simulate_v7(records, daily, {D1: [SYMBOL]}, **kwargs)
    assert result == reference
    assert dates(result) == [D1.isoformat(), D2.isoformat(), D3.isoformat()]
    shares = result.trades[0]["shares"]
    assert result.equity_curve[1]["holdings"] == shares * 98
    assert [t["reason"] for t in result.trades] == ["buy:trial", "stop:trial_a090"]
    assert result.trades[-1]["date"] == D3.isoformat()
    assert result.positions == {}


@pytest.mark.parametrize("cash_order", [False, True])
def test_timer_counts_non_pool_frame_sessions(cash_order):
    days = [stamp.date() for stamp in pd.bdate_range(D1, periods=11)]
    frames, records, daily = inputs(days, [100] * len(days))
    result = simulate_v7(frames, daily, {D1: [SYMBOL]},
                         fix_minute_cash_order=cash_order)
    assert result == simulate_v7(records, daily, {D1: [SYMBOL]},
                                 fix_minute_cash_order=cash_order)
    assert result.trades[-1]["reason"] == "exit:timer10"
    assert result.trades[-1]["date"] == days[-1].isoformat()
    assert result.positions == {}


@pytest.mark.parametrize("start,end,expected", [
    (None, None, [D1, D2, D3]),
    (D2, None, [D2, D3]),
    (None, D2, [D1, D2]),
    (D2, D2, [D2]),
    (D3, D1, []),
])
def test_union_sorted_unique_all_frames_pool_only_days_and_filters(start, end, expected):
    frames, records, daily = inputs([D2, D1, D2], [100, 100, 100])
    # A second, unheld symbol contributes a date; empty frames add nothing.
    other_frames, other_records, _ = inputs([D3], [100])
    frames["600001.SH"] = other_frames[SYMBOL]
    frames["600002.SH"] = frames[SYMBOL].iloc[:0]
    records["600001.SH"] = other_records[SYMBOL]
    pools = {D1: [SYMBOL], D3: []}
    result = simulate_v7(frames, daily, pools, start=start, end=end)
    assert dates(result) == [day.isoformat() for day in expected]
    assert dates(result) == dates(simulate_v7(records, daily, pools, start=start, end=end))
    pool_only = simulate_v7({SYMBOL: frames[SYMBOL].iloc[:0]}, {}, {D3: [SYMBOL]})
    assert dates(pool_only) == [D3.isoformat()]
    assert pool_only.trades[0]["reason"] == "skip_no_1455"


@pytest.mark.parametrize("as_frames", [False, True])
def test_explicit_list_calendar_remains_authoritative(as_frames):
    frames, records, daily = inputs([D1, D2, D3], [100, 98, 89])
    bars = frames if as_frames else records
    result = simulate_v7(bars, daily, {D1: [SYMBOL]}, [D2, D1], end=D2)
    assert dates(result) == [D1.isoformat(), D2.isoformat()]
    assert result.positions[SYMBOL].shares > 0
    assert [t["reason"] for t in result.trades] == ["buy:trial"]


@pytest.mark.parametrize("as_frames", [False, True])
def test_cli_shaped_mapping_keeps_gate_and_calendar(as_frames):
    frames, records, daily = inputs([D1, D2, D3], [100, 98, 89])
    bars = frames if as_frames else records
    warmup = {D1 - timedelta(days=n): 100.0 for n in range(11, 0, -1)}
    warmup.update({D1 - timedelta(days=2): 90.0, D1 - timedelta(days=1): 90.0})
    result = simulate_v7(bars, daily, {D1: [SYMBOL]}, {**warmup, D1: 90.0},
                         start=D1, end=D3)
    assert dates(result) == [D1.isoformat()]
    assert [t["reason"] for t in result.trades] == ["skip_index_gate"]
    # Empty Mapping retains the existing explicit-index warmup error.
    with pytest.raises(ValueError, match="11 warmup"):
        simulate_v7(bars, daily, {D1: [SYMBOL]}, {})


@pytest.mark.parametrize("cash_order", [False, True])
def test_settlement_on_unheld_symbols_frame_date(cash_order):
    from backtest.research.ashare_exdiv_economics import ExDivEvent

    frames, records, daily = inputs([D1, D2], [100, 99])
    other_frames, other_records, _ = inputs([D3], [100])
    frames["600001.SH"] = other_frames[SYMBOL]
    records["600001.SH"] = other_records[SYMBOL]
    event = ExDivEvent("g6-cash", 0, 1, "20260902", "20260903")
    kwargs = dict(exdiv_economics={(SYMBOL, "20260902"): event},
                  fix_minute_cash_order=cash_order)
    result = simulate_v7(frames, daily, {D1: [SYMBOL]}, **kwargs)
    reference = simulate_v7(records, daily, {D1: [SYMBOL]}, **kwargs)
    assert result == reference
    assert dates(result) == [D1.isoformat(), D2.isoformat(), D3.isoformat()]
    shares = result.positions[SYMBOL].shares
    assert result.equity_curve[2]["cash"] - result.equity_curve[1]["cash"] == shares
    assert result.exdiv_economics.receivable_total == 0
    assert result.equity_curve[2]["equity"] == result.equity_curve[1]["equity"]
