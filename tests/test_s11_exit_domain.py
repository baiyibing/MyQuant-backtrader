"""X-03: front-only EOD decisions with unchanged raw execution and accounting."""

from decimal import ROUND_HALF_UP, Decimal

import numpy as np
import pandas as pd
import pytest

from backtest.research import csv_daily_backtest as daily
from backtest.research import csv_minute_backtest as minute
from backtest.research import strategy11_rules

CODE = "600000.SH"
T, EX, NEXT = "20240902", "20240903", "20240904"
PRICE_COLUMNS = ["open", "high", "low", "close"]


def money(value):
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def bars_from_closes(closes, *, opens=None, start="20240826"):
    dates = pd.bdate_range(start, periods=len(closes))
    opens = closes if opens is None else opens
    return pd.DataFrame(
        {"open": opens, "high": np.maximum(opens, closes),
         "low": np.minimum(opens, closes), "close": closes, "volume": 100_000.},
        index=dates,
    )


def minute_bars(raw):
    rows = []
    for day, row in raw.iterrows():
        for hm in (570, 585, 895):
            rows.append({"time": day + pd.Timedelta(minutes=hm),
                         "ymd": day.strftime("%Y%m%d"), "hm": hm,
                         "open": row["open"] if hm == 570 else row["close"],
                         "high": row["high"], "low": row["low"],
                         "close": row["close"], "volume": 10_000.})
    return {CODE: pd.DataFrame(rows).set_index("time")}


def discontinuity():
    raw = bars_from_closes([10.] * 5 + [10.5, 9.45, 9.7],
                          opens=[10.] * 5 + [10.2, 9.45, 9.7])
    front = bars_from_closes([9.] * 5 + [9.45, 9.45, 9.7],
                            opens=[9.] * 5 + [9.18, 9.45, 9.7])
    return raw, front


def simulate(engine, raw, front=None, *, start=T, end=NEXT, pools=None, **kwargs):
    args = ({CODE: raw},) if engine is daily else (minute_bars(raw), {CODE: raw})
    if front is not None:
        kwargs.update(fix_s11_exit_domain=True, signal_bars_front={CODE: front})
    return engine.simulate(
        *args, {T: [CODE]} if pools is None else pools, start, end,
        strategy="version11", total_cash=100_000, daily_quota=5000, **kwargs,
    )


def fills(state):
    return [trade for trade in state.trades if trade["side"] in ("BUY", "SELL")]


@pytest.mark.parametrize("engine", [daily, minute], ids=["daily", "minute"])
def test_off_raw_sma_break_and_on_front_hold_have_raw_cash_shares_fees(engine):
    raw, front = discontinuity()
    assert np.mean(raw.loc[:EX, "close"].iloc[-5:]) == pytest.approx(9.99)
    assert np.mean(front.loc[:EX, "close"].iloc[-5:]) == pytest.approx(9.18)
    exdiv = {CODE: {EX: .9}}
    off = simulate(engine, raw, exdiv=exdiv)
    assert [(t["date"], t["side"], t["shares"]) for t in fills(off)] == [
        (T, "BUY", 400), (NEXT, "SELL", 400),
    ]
    assert fills(off)[1]["reason"] == "ma_signal:SMA5"
    assert money(fills(off)[1]["price"]) == Decimal("9.70")
    buy_cash = Decimal("95795.80") if engine is daily else Decimal("95915.92")
    buy_price = Decimal("10.50") if engine is daily else Decimal("10.20")
    assert money(fills(off)[0]["price"]) == buy_price
    assert money(fills(off)[0]["commission"]) == money(400 * buy_price / 1000)
    assert money(fills(off)[1]["commission"]) == Decimal("3.88")
    assert money(off.cash) == buy_cash + Decimal("3876.12")
    assert off.positions == {}

    on = simulate(engine, raw, front, exdiv=exdiv)
    assert fills(on) == fills(off)[:1]
    assert money(on.cash) == buy_cash
    assert on.positions[CODE][0].shares == 400
    assert on.positions[CODE][0].pending_exit == ""
    assert money(on.equity_curve[-1][1]) == buy_cash + Decimal("3880.00")
    assert money(on.equity_curve[-1][1] - off.equity_curve[-1][1]) == Decimal("3.88")


@pytest.mark.parametrize("engine", [daily, minute], ids=["daily", "minute"])
@pytest.mark.parametrize("close,reason", [(9.45, ""), (9., "ma_signal:entry_nonpositive"),
                                         (8.5, "ma_signal:entry_nonpositive")])
def test_entry_exday_initial_uses_strict_front_previous_without_remapping(
    engine, close, reason, monkeypatch,
):
    raw = bars_from_closes([10.] * 5 + [close], opens=[10.] * 5 + [9.3])
    front = bars_from_closes([9.] * 5 + [close], opens=[9.] * 5 + [9.3])
    original = strategy11_rules.eod_exit
    observed = []

    def capture(closes, previous, hold_mode=None):
        observed.append((list(closes), previous, hold_mode))
        return original(closes, previous, hold_mode)

    monkeypatch.setattr(strategy11_rules, "eod_exit", capture)
    state = simulate(engine, raw, front, end=T, exdiv={CODE: {T: .9}})
    assert len(fills(state)) == 1 and fills(state)[0]["date"] == T
    assert state.positions[CODE][0].pending_exit == reason
    assert observed == [([9.] * 5 + [close], 9., None)]
