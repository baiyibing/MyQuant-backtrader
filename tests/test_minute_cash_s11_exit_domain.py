"""X-02/X-03 composition keeps front EOD signals and raw next-open fills."""

import numpy as np
import pandas as pd
import pytest
from backtest.research import csv_minute_backtest as minute
from backtest.research import strategy11_rules

CODE = "600000.SH"
ENTRY, EXDAY, NEXT = "20240902", "20240903", "20240904"


def _bars(closes, opens=None):
    opens = closes if opens is None else opens
    return pd.DataFrame(
        {
            "open": opens,
            "high": np.maximum(opens, closes),
            "low": np.minimum(opens, closes),
            "close": closes,
            "volume": 100_000.0,
        },
        index=pd.bdate_range("20240826", periods=len(closes)),
    )


def _minute_bars(raw):
    rows = []
    for day, row in raw.loc[ENTRY:NEXT].iterrows():
        for hm in (570, 585, 895):
            rows.append(
                {
                    "time": day + pd.Timedelta(minutes=hm),
                    "ymd": day.strftime("%Y%m%d"),
                    "hm": hm,
                    "open": row["open"] if hm == 570 else row["close"],
                    "high": row["high"],
                    "low": row["low"],
                    "close": row["close"],
                    "volume": 10_000.0,
                }
            )
    return {CODE: pd.DataFrame(rows).set_index("time")}


@pytest.mark.parametrize("fix_cash_order", [False, True], ids=["x02-off", "x02-on"])
@pytest.mark.parametrize("fix_exit_domain", [False, True], ids=["x03-off", "x03-on"])
@pytest.mark.parametrize("front_ex_close", [9.45, 8.5], ids=["front-hold", "front-break"])
def test_version11_cash_clock_uses_selected_eod_domain_and_raw_open(
    fix_cash_order, fix_exit_domain, front_ex_close, monkeypatch,
):
    raw = _bars([10.0] * 5 + [10.5, 9.45, 9.7], [10.0] * 5 + [10.2, 9.45, 9.7])
    front = _bars([9.0] * 5 + [9.45, front_ex_close, 9.7])
    observed = []
    original_eod = strategy11_rules.eod_exit

    def capture(closes, previous, hold_mode=None):
        decision = original_eod(closes, previous, hold_mode)
        observed.append((list(closes), previous, decision.reason))
        return decision

    monkeypatch.setattr(strategy11_rules, "eod_exit", capture)
    trace = []
    state = minute.simulate(
        _minute_bars(raw), {CODE: raw}, {ENTRY: [CODE]}, ENTRY, NEXT,
        strategy="version11", total_cash=100_000, daily_quota=5000,
        exdiv={CODE: {EXDAY: 0.9}}, fix_minute_cash_order=fix_cash_order,
        fix_s11_exit_domain=fix_exit_domain,
        signal_bars_front={CODE: front} if fix_exit_domain else None,
        audit_sink=trace,
    )

    exits = not fix_exit_domain or front_ex_close == 8.5
    signal = front if fix_exit_domain else raw
    expected_previous = [9.0, 9.45] if fix_exit_domain else [10.0, 10.5 * 0.9]
    expected_eod = [
        (signal.loc[:ENTRY, "close"].tolist(), expected_previous[0], ""),
        (
            signal.loc[:EXDAY, "close"].tolist(), expected_previous[1],
            "ma_signal:SMA5" if exits else "",
        ),
    ]
    if not exits:
        expected_eod.append((front["close"].tolist(), front_ex_close, ""))
    assert observed == expected_eod
    assert state.stats["daily_quota"] == 5000

    fills = [trade for trade in state.trades if trade["side"] in ("BUY", "SELL")]
    expected_fills = [(ENTRY, "BUY", 400, 10.2)]
    if exits:
        expected_fills.append((NEXT, "SELL", 400, 9.7))
    assert [(t["date"], t["side"], t["shares"], t["price"]) for t in fills] == expected_fills
    assert fills[0]["commission"] == pytest.approx(4.08)
    if exits:
        assert fills[1]["reason"] == "ma_signal:SMA5"
        assert fills[1]["commission"] == pytest.approx(3.88)
        sell = next(trade for trade in trace if trade["side"] == "SELL")
        assert (sell["date"], sell["hm"], sell["phase"]) == (NEXT, 570, "open")
        assert state.positions == {}
        assert state.cash == pytest.approx(99792.04)
    else:
        lot, = state.positions[CODE]
        assert lot.shares == 400 and lot.pending_exit == ""
        assert state.cash == pytest.approx(95915.92)
        assert state.equity_curve[-1][1] == pytest.approx(99795.92)
