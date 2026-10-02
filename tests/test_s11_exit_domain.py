"""X-03: front-only EOD decisions with unchanged raw execution and accounting."""

from decimal import ROUND_HALF_UP, Decimal

import numpy as np
import pandas as pd
import pytest
from backtest.research import csv_daily_backtest as daily
from backtest.research import csv_minute_backtest as minute
from backtest.research import csv_simulate_loop, strategy11_rules
from backtest.research.ashare_exdiv_economics import ExDivEvent

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


@pytest.mark.parametrize("engine", [daily, minute], ids=["daily", "minute"])
@pytest.mark.parametrize("close,reason", [(9.375, ""), (9.365, "ma_signal:SMA5")])
def test_hold_sma_equal_keeps_lot_and_true_break_sells_next_raw_open(engine, close, reason):
    raw, _ = discontinuity()
    front = bars_from_closes([9.] * 4 + [9.5, 10., close, 9.7])
    state = simulate(engine, raw, front, end=EX, exdiv={CODE: {EX: .9}})
    assert len(fills(state)) == 1
    assert state.positions[CODE][0].pending_exit == reason
    after = simulate(engine, raw, front, exdiv={CODE: {EX: .9}})
    if reason:
        assert [(t["date"], t["side"], t["price"]) for t in fills(after)][1:] == [
            (NEXT, "SELL", 9.7),
        ]
        assert fills(after)[1]["reason"] == reason
    else:
        assert len(fills(after)) == 1 and after.positions[CODE][0].pending_exit == ""


@pytest.mark.parametrize("engine", [daily, minute], ids=["daily", "minute"])
@pytest.mark.parametrize("path", ["hold", "sma_equal", "sma_break", "initial_exit"])
def test_entire_fsm_raw_fills_and_nav_are_invariant_to_front_anchor(engine, path, monkeypatch):
    raw, front = discontinuity()
    if path == "sma_equal":
        front = bars_from_closes([9.] * 4 + [9.5, 10., 9.375, 9.7])
    elif path == "sma_break":
        front.loc[EX, PRICE_COLUMNS] = 8.5
    elif path == "initial_exit":
        front.loc[T, PRICE_COLUMNS] = 9.
    original = strategy11_rules.eod_exit
    decisions = []

    def capture(*args, **kwargs):
        decision = original(*args, **kwargs)
        decisions.append((decision.hold_mode, decision.reason))
        return decision

    monkeypatch.setattr(strategy11_rules, "eod_exit", capture)
    baseline = simulate(engine, raw, front, exdiv={CODE: {EX: .9}})
    baseline_decisions = list(decisions)
    assert [t["side"] for t in fills(baseline)] == (
        ["BUY"] if path in ("hold", "sma_equal") else ["BUY", "SELL"]
    )
    for factor, offset in ((.37, 0.), (1.7, 2.3)):
        decisions.clear()
        transformed = front.copy()
        transformed[PRICE_COLUMNS] = transformed[PRICE_COLUMNS] * factor + offset
        state = simulate(engine, raw, transformed, exdiv={CODE: {EX: .9}})
        assert decisions == baseline_decisions
        assert (state.trades, state.cash, state.positions, state.equity_curve) == (
            baseline.trades, baseline.cash, baseline.positions, baseline.equity_curve,
        )


@pytest.mark.parametrize("engine", [daily, minute], ids=["daily", "minute"])
@pytest.mark.parametrize("cutoff", [T, EX])
def test_future_front_and_raw_perturbation_cannot_change_prefix(engine, cutoff):
    raw, front = discontinuity()
    baseline = simulate(engine, raw, front, end=cutoff, exdiv={CODE: {EX: .9}})
    changed_raw, changed_front = raw.copy(), front.copy()
    future = changed_raw.index > pd.Timestamp(cutoff)
    changed_raw.loc[future, PRICE_COLUMNS] *= 10
    changed_front.loc[future, PRICE_COLUMNS] = changed_front.loc[future, PRICE_COLUMNS] * .37 + 4
    state = simulate(engine, changed_raw, changed_front, end=cutoff, exdiv={CODE: {EX: .9}})
    assert (state.trades, state.cash, state.positions, state.equity_curve) == (
        baseline.trades, baseline.cash, baseline.positions, baseline.equity_curve,
    )


@pytest.mark.parametrize("engine", [daily, minute], ids=["daily", "minute"])
def test_natural_sma_warmup_is_not_extended_or_filled_from_future(engine):
    raw = bars_from_closes([10., 10.5, 9.45, 9.7], start="20240830")
    front = bars_from_closes([9., 9.45, 9.1, 9.2], start="20240830")
    state = simulate(engine, raw, front, exdiv={CODE: {EX: .9}})
    # Only four genuine observations exist; lower HOLD closes are not INITIAL retests.
    assert len(fills(state)) == 1
    assert state.positions[CODE][0].pending_exit == ""


@pytest.mark.parametrize("engine", [daily, minute], ids=["daily", "minute"])
def test_exdiv_exec_reference_once_and_front_previous_never_remapped(engine, monkeypatch):
    raw, front = discontinuity()
    execution_map = engine.mapped_prev_close
    execution_calls = []
    signal_previous = []
    original_eod = strategy11_rules.eod_exit

    def capture_map(exdiv, code, day, previous):
        result = execution_map(exdiv, code, day, previous)
        if day == EX:
            execution_calls.append((previous, result))
        return result

    def capture_eod(closes, previous, hold_mode=None):
        signal_previous.append(previous)
        return original_eod(closes, previous, hold_mode)

    # This helper also maps pool references, but there is no EX-day pool here.
    # A call during EX EOD would prove a forbidden second signal-domain map.
    helper_map = csv_simulate_loop.mapped_prev_close

    def guard_helper(exdiv, code, day, previous):
        assert day != EX, "front EOD previous must never use execution exdiv mapping"
        return helper_map(exdiv, code, day, previous)

    monkeypatch.setattr(engine, "mapped_prev_close", capture_map)
    monkeypatch.setattr(csv_simulate_loop, "mapped_prev_close", guard_helper)
    monkeypatch.setattr(strategy11_rules, "eod_exit", capture_eod)
    state = simulate(engine, raw, front, end=EX, exdiv={CODE: {EX: .9}})
    assert len(execution_calls) == 1
    assert execution_calls[0][0] == 10.5
    assert execution_calls[0][1][0] == pytest.approx(9.45)
    assert execution_calls[0][1][1] is True
    assert signal_previous == [9., 9.45]
    assert state.stats["exdiv_adjusted_lots"] == 1
    assert state.stats["exdiv_prev_close_mapped"] == 1
    lot, = state.positions[CODE]
    assert lot.cost == pytest.approx((10.5 if engine is daily else 10.2) * .9)
    assert lot.shares == 400


@pytest.mark.parametrize("engine", [daily, minute], ids=["daily", "minute"])
@pytest.mark.parametrize("bonus,cash,ex_price", [(0, 1., 9.), (1, 0., 5.), (1, 1., 4.5)])
def test_reference_mapping_creates_no_rights_and_explicit_economics_applies_once(
    engine, bonus, cash, ex_price,
):
    raw = bars_from_closes([9.9] * 5 + [10., ex_price, ex_price])
    front = bars_from_closes([ex_price * .99] * 5 + [ex_price] * 3)
    exdiv = {CODE: {EX: ex_price / 10.}}
    off = simulate(engine, raw, front, exdiv=exdiv)
    lot, = off.positions[CODE]
    assert (lot.shares, money(off.cash)) == (500, Decimal("94995.00"))
    assert off.exdiv_economics is None
    assert money(off.equity_curve[-1][1]) == money(off.cash + 500 * ex_price)
    events = {(CODE, EX): ExDivEvent("s11-rights", bonus, cash, EX, NEXT)}
    on_ex = simulate(engine, raw, front, end=EX, exdiv=exdiv, exdiv_economics=events)
    assert on_ex.exdiv_economics.receivable_total == 500 * cash
    assert money(on_ex.cash) == Decimal("94995.00")
    paid = simulate(engine, raw, front, exdiv=exdiv, exdiv_economics=events)
    assert paid.positions[CODE][0].shares == 500 * (1 + bonus)
    assert money(paid.cash) == money(94995 + 500 * cash)
    assert paid.exdiv_economics.receivable_total == 0
    assert paid.exdiv_economics.applied_ids == {"s11-rights"}
    assert paid.stats["exdiv_adjusted_lots"] == 1
    assert fills(paid) == fills(off)
    assert money(sum(t["commission"] for t in paid.trades)) == Decimal("5.00")
    assert all(money(equity) == Decimal("99995.00") for _, equity in paid.equity_curve)


@pytest.mark.parametrize("engine", [daily, minute], ids=["daily", "minute"])
@pytest.mark.parametrize("defect", ["code", "today", "history", "nan", "duplicate", "extra_date"])
def test_simulate_rejects_bad_front_before_any_account_or_fill(engine, defect, monkeypatch):
    raw, front = discontinuity()
    signal = {CODE: front}
    if defect == "code":
        signal.clear()
    elif defect in ("today", "history"):
        signal[CODE] = front.drop(pd.Timestamp(T) if defect == "today" else front.index[0])
    elif defect == "nan":
        front.loc[T, "close"] = np.nan
    elif defect == "duplicate":
        signal[CODE] = pd.concat([front, front.loc[[pd.Timestamp(T)]]]).sort_index()
    elif defect == "extra_date":
        signal[CODE] = front.rename(index={front.index[0]: pd.Timestamp("20240825")})

    def forbidden(*_args, **_kwargs):
        pytest.fail("bad front must fail before account initialization or first trade")

    monkeypatch.setattr(engine, "init_sim_state", forbidden)
    args = ({CODE: raw},) if engine is daily else (minute_bars(raw), {CODE: raw})
    with pytest.raises(ValueError, match="s11 exit domain"):
        engine.simulate(*args, {T: [CODE]}, T, NEXT, strategy="version11",
                        fix_s11_exit_domain=True, signal_bars_front=signal)


@pytest.mark.parametrize("engine", [daily, minute], ids=["daily", "minute"])
@pytest.mark.parametrize("strategy,enabled,supplied", [
    ("version1", True, True), ("version1", False, True),
    ("version11", False, True), ("version11", True, False),
])
def test_simulate_rejects_signal_without_version11_and_on(engine, strategy, enabled, supplied):
    raw, front = discontinuity()
    args = ({CODE: raw},) if engine is daily else (minute_bars(raw), {CODE: raw})
    with pytest.raises(ValueError, match="version11|signal_bars_front"):
        engine.simulate(*args, {T: [CODE]}, T, NEXT, strategy=strategy,
                        fix_s11_exit_domain=enabled,
                        signal_bars_front={CODE: front} if supplied else None)


@pytest.mark.parametrize("engine", [daily, minute], ids=["daily", "minute"])
def test_explicit_off_keeps_legacy_trades_equity_positions_and_stats(engine):
    raw, _ = discontinuity()
    omitted = simulate(engine, raw, exdiv={CODE: {EX: .9}})
    explicit = simulate(engine, raw, exdiv={CODE: {EX: .9}}, fix_s11_exit_domain=False)
    assert (explicit.trades, explicit.cash, explicit.positions, explicit.equity_curve, explicit.stats) == (
        omitted.trades, omitted.cash, omitted.positions, omitted.equity_curve, omitted.stats,
    )
    assert "fix_s11_exit_domain" not in explicit.stats
    assert "exit_signal_domain" not in explicit.stats
