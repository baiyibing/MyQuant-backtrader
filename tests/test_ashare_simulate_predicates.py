"""Shared gates at simulate call sites; preserve each ledger's known behavior."""

from datetime import date
from dataclasses import asdict, replace

import pandas as pd
import pytest

from backtest.research import csv_daily_backtest as daily
from backtest.research import csv_minute_backtest as minute
from backtest.research import csv_minute_backtest_v7 as v7
from backtest.research.ashare_session import (
    defer_sell_at_limit,
    flatten_pool_names,
    session_limit_prices,
    session_prev_close,
    skip_buy_at_limit,
    t1_sellable,
)
from backtest.research.csv_ledger import Position, SimState
from backtest.research.csv_simulate_loop import run_chase_due_day
from backtest.research.csv_strategy_books import BOOKS


CODE = "600000.SH"  # All bars/positions in this module are synthetic.
ANCHOR = "600001.SH"
UNKNOWN = "999999.SZ"
D0, D1, D2, D3 = (date(2026, 9, n) for n in (1, 2, 3, 4))

# Examples for later host reason-bucket comparison; this does not run slice D.
REASON_BUCKET_EXAMPLES = {
    "book": {"stop_loss:gap_open": "stop", "stop_loss:touch": "stop",
             "trail:T+2": "profit", "profit_take:target": "profit",
             "skip_limit_up": "limit_up", "defer_sell_limit_down": "limit_down"},
    "v7": {"stop:trial_a090": "stop", "stop:four_avg095": "stop",
           "exit:timer10": "timer", "skip_limit_up": "limit_up",
           "defer_limit_down": "limit_down"},
}


def frames(prices):
    return pd.DataFrame({key: list(prices.values()) for key in ("open", "high", "low", "close")},
                        index=pd.to_datetime(list(prices)), dtype=float)


def minutes(prices):
    frame = frames(prices)
    frame.index += pd.Timedelta(hours=14, minutes=55)
    return frame.assign(ymd=frame.index.strftime("%Y%m%d"), hm=895)


def seed(monkeypatch, engine, code, buy_date, entry_idx=0):
    if engine == "v7":
        result_type = v7.SimResult

        def initial(cash):
            pos = v7.Position(code, 100, avg_cost=100,
                              lots=[v7.Lot(100, buy_date, 100, "trial")])
            return result_type(cash, positions={code: pos})

        monkeypatch.setattr(v7, "SimResult", initial)
    else:
        module = daily if engine == "daily" else minute
        init = module.init_sim_state

        def initial(*args, **kwargs):
            state, pending, names = init(*args, **kwargs)
            state.positions[code] = [Position(code, 100, 100, entry_idx, 100)]
            return state, pending, names

        monkeypatch.setattr(module, "init_sim_state", initial)


def run(engine, prices, start, end, *, code=CODE, pool=None, anchor=None, **kwargs):
    pool = {} if pool is None else pool
    if engine == "v7":
        return v7.simulate_v7(
            {code: minutes({d: px for d, px in prices.items() if start <= d <= end})},
            {code: prices}, pool, list(anchor or sorted(d for d in prices if start <= d <= end)),
            start=start, end=end, **kwargs,
        )
    bars = {code: frames(prices)}
    if anchor:
        bars[ANCHOR] = frames({d: 100 for d in anchor})
    pools = {d.strftime("%Y%m%d"): codes for d, codes in pool.items()}
    args = (bars, pools, start.strftime("%Y%m%d"), end.strftime("%Y%m%d"))
    if engine == "minute":
        args = ({code: minutes(prices)},) + args
    return (daily if engine == "daily" else minute).simulate(*args, strategy="version6", **kwargs)


def sells(state):
    return [trade for trade in state.trades if trade["side"].lower() == "sell"]


@pytest.mark.parametrize("engine", ["daily", "minute", "v7"])
def test_t1_refuses_entry_session_then_sells_next_session(engine, monkeypatch):
    seed(monkeypatch, engine, CODE, D1)
    state = run(engine, {D0: 98, D1: 89, D2: 89}, D1, D2)
    assert [(t["date"].replace("-", ""), t["price"]) for t in sells(state)] == [("20260903", 89)]


@pytest.mark.parametrize("engine", ["daily", "minute", "v7"])
def test_limit_up_skips_pool_buy(engine):
    state = run(engine, {D0: 100, D1: 110}, D1, D1, pool={D1: [CODE]})
    assert not state.positions
    if engine == "v7":
        assert [t["reason"] for t in state.trades] == ["skip_limit_up"]
    else:
        assert state.stats["skip_limit_up"] == 1
        assert not state.trades


@pytest.mark.parametrize("engine", ["daily", "minute", "v7"])
def test_limit_down_defers_then_sells_on_later_session(engine, monkeypatch):
    seed(monkeypatch, engine, CODE, D0)
    state = run(engine, {D0: 100, D1: 90, D2: 89}, D0, D2)
    assert [(t["date"].replace("-", ""), t["price"]) for t in sells(state)] == [("20260903", 89)]
    if engine == "v7":
        assert any(t["reason"] == "defer_limit_down" for t in state.trades)
    elif engine == "minute":
        # Frozen scan consumes this blocked bar internally; its outer counter
        # stays zero on 671f562 too. The next-session fill above locks deferral.
        assert state.stats["defer_sell_limit_down"] == 0
    else:
        assert state.stats["defer_sell_limit_down"] >= 1


@pytest.mark.parametrize("cause", ["no_previous_close", "unknown_board"])
@pytest.mark.parametrize("engine", ["daily", "minute", "v7"])
@pytest.mark.parametrize("sellable", [True, False], ids=["t1", "t0"])
def test_none_limits_sell_side_records_existing_split(engine, cause, sellable, monkeypatch):
    code = UNKNOWN if cause == "unknown_board" else CODE
    prices = {D1: 89} if cause == "no_previous_close" else {D0: 100, D1: 89}
    previous = session_prev_close(prices, D1, code, None)
    assert previous == (None if cause == "no_previous_close" else 100)
    assert session_limit_prices(code, previous) is None
    assert daily.apply_csv_strategy("version6")["qlib_limit_pct"] is None
    # Synthetic held initial state, not a claim that unknown-board entry can fill.
    buy_date, entry_idx = (D0, 0) if sellable else (D1, 1)
    seed(monkeypatch, engine, code, buy_date, entry_idx=entry_idx)
    state = run(engine, prices, D0, D1, code=code, anchor=[D0, D1])
    if engine == "v7" and sellable:
        assert [(t["reason"], t["price"], t["shares"]) for t in sells(state)] == [
            ("stop:trial_a090", 89, 100),
        ]
        assert code not in state.positions
        assert state.cash == pytest.approx(21_000_000 + 8_900 - 8.9)
        assert state.equity_curve[-1]["holdings"] == 0
    elif engine == "v7":
        # The real stop/gate chain runs, but T+1 leaves lots and cash intact.
        assert state.trades == [] and state.cash == 21_000_000
        pos = state.positions[code]
        assert pos.lots == [v7.Lot(100, buy_date, 100, "trial")]
        assert pos.shares == 100 and pos.stage == "trial" and pos.avg_cost == 100
        assert pos.entry_A == 100 and pos.last_add_date is None
        assert pos.peak == (100 if cause == "unknown_board" else 89)
        assert state.equity_curve[-1]["holdings"] == 8_900
    else:
        # Missing previous close freezes upstream; unknown board is rejected first.
        assert sells(state) == [] and state.cash == 21_000_000
        assert state.positions[code] == [Position(code, 100, 100, entry_idx, 100)]
        assert state.stats["skip_unknown_board"] == int(cause == "unknown_board")
        assert [(t["side"], t["shares"], t["price"]) for t in state.trades] == [
            ("EOD_MARK", 100, 89),
        ]
        assert state.equity_curve[-1][1] == 21_000_000 + 8_900


@pytest.mark.parametrize("engine", ["daily", "minute"])
@pytest.mark.parametrize("cause", ["no_previous_close", "unknown_board"])
def test_d4_book_none_limits_reference_and_mark_are_not_fills(engine, cause, monkeypatch):
    code = UNKNOWN if cause == "unknown_board" else CODE
    prices = {D1: 89} if cause == "no_previous_close" else {D0: 100, D1: 89}
    seed(monkeypatch, engine, code, D0)
    assert daily.apply_csv_strategy("version6")["qlib_limit_pct"] is None
    state = run(engine, prices, D0, D1, code=code, anchor=[D0, D1],
                exdiv={code: {f"{D1:%Y%m%d}": 1.2}})
    scaled = cause == "unknown_board"
    reference = 120 if scaled else 100
    assert state.positions[code] == [Position(code, 100, reference, 0, reference)]
    assert state.stats.get("exdiv_adjusted_lots", 0) == int(scaled)
    assert state.stats["skip_unknown_board"] == int(scaled)
    assert state.cash == 21_000_000 and sells(state) == []
    assert [(t["side"], t["shares"], t["price"]) for t in state.trades] == [
        ("EOD_MARK", 100, 89),
    ]
    assert state.equity_curve[-1][1] == state.cash + 8_900


@pytest.mark.parametrize("engine", ["daily", "minute"])
def test_none_limits_buy_side_records_unknown_board_in_book_paths(engine):
    state = run(
        engine,
        {D0: 100, D1: 100},
        D1,
        D1,
        code=UNKNOWN,
        pool={D1: [UNKNOWN]},
        anchor=[D0, D1],
    )
    assert state.stats["skip_unknown_board"] == 1
    assert state.stats["buys"] == 0
    assert state.positions == {}


def test_none_limits_chase_path_rejects_unknown_board_in_shared_loop():
    state = SimState(cash=21_000_000.0)
    pending_chase = {UNKNOWN: (1_000_000.0, 0)}
    run_chase_due_day(
        state,
        pending_chase,
        day_i=1,
        day=pd.Timestamp(D1),
        names={},
        allow_add=False,
        buy_gate=None,
        quotes_for=lambda _code: (10.0, 10.1, [10.0]),
    )
    assert pending_chase == {}
    assert state.stats["skip_unknown_board"] == 1
    assert state.stats["chase_buy"] == 0
    assert state.trades == []


@pytest.mark.parametrize("cause", ["no_previous_close", "unknown_board"])
@pytest.mark.parametrize("cash", [197_797.6, 197_797.59], ids=["exact-cash", "one-fen-short"])
def test_v7_held_add_none_limits_cash_controls_fill(cause, cash, monkeypatch):
    code = UNKNOWN if cause == "unknown_board" else CODE
    closes = {D1: 104} if cause == "no_previous_close" else {D0: 100, D1: 104}
    previous = session_prev_close(closes, D1, code, None)
    assert previous == (None if cause == "no_previous_close" else 100)
    assert session_limit_prices(code, previous) is None
    # Seed the held state; natural first entry rejects these None contexts.
    seed(monkeypatch, "v7", code, D0)
    state = v7.simulate_v7(
        {code: minutes({D1: 104.0})},
        {code: closes},
        {},
        [D1],
        start=D1,
        end=D1,
        cash_total=cash,
    )
    pos = state.positions[code]
    assert pos.entry_A == 100 and pos.add1_A1 is None and pos.peak == 104
    assert pos.lots[0] == v7.Lot(100, D0, 100, "trial")
    assert sells(state) == []
    if cash == 197_797.6:
        assert state.trades == [{"date": D1.isoformat(), "symbol": code, "hm": 895,
                                 "side": "buy", "shares": 1900, "price": 104,
                                 "reason": "buy:add_a104"}]
        assert pos.lots == [v7.Lot(100, D0, 100, "trial"),
                            v7.Lot(1900, D1, 104, "add_a104")]
        assert pos.shares == 2000 and pos.stage == "four" and pos.last_add_date == D1
        assert pos.avg_cost == pytest.approx(103.8)
        assert state.cash == pytest.approx(0)
    else:
        assert state.trades == [{"date": D1.isoformat(), "symbol": code, "hm": 895,
                                 "side": "skip", "shares": 0, "price": 104,
                                 "reason": "skip_cash"}]
        assert asdict(pos) == asdict(v7.Position(
            code, 100, avg_cost=100, peak=104, lots=[v7.Lot(100, D0, 100, "trial")],
        ))
        assert state.cash == cash
    assert state.equity_curve[-1]["holdings"] == pos.shares * 104


@pytest.mark.parametrize("engine", ["daily", "minute"])
def test_calendar_mapping_keeps_union_hold_count_across_missing_bar(engine, monkeypatch):
    seed(monkeypatch, engine, CODE, D1)
    module = daily if engine == "daily" else minute
    mapped = []
    hold_counts = []

    def eligibility(buy_date, session):
        assert type(buy_date) is date and type(session) is date
        mapped.append((buy_date, session))
        return t1_sellable(buy_date, session)

    def take_profit(close, cost, peak, n_days):
        hold_counts.append(n_days)
        return None

    monkeypatch.setattr(module, "t1_sellable", eligibility)
    state = run(engine, {D0: 100, D1: 100, D3: 100}, D1, D3,
                anchor=[D1, D2, D3], take_profit=take_profit, stop_pct=0.0)
    assert mapped == [(D1, D1), (D1, D3)]
    assert hold_counts == [2]  # The suspended symbol has no D2 bar; union calendar does.
    assert not sells(state)


def test_reason_bucket_examples_keep_two_ledgers_explicit():
    assert REASON_BUCKET_EXAMPLES["book"]["stop_loss:touch"] == REASON_BUCKET_EXAMPLES["v7"]["stop:trial_a090"]
    assert REASON_BUCKET_EXAMPLES["book"]["defer_sell_limit_down"] == REASON_BUCKET_EXAMPLES["v7"]["defer_limit_down"]


@pytest.mark.parametrize("engine", ["daily", "minute", "v7"])
@pytest.mark.parametrize("action", ["sell", "add"])
def test_d3_held_name_chain_sell_and_add_bands(engine, action, monkeypatch):
    seed(monkeypatch, engine, CODE, D0)
    # Enable the same historical book add path used by the minute name pin.
    # There is no index/buy gate, cash is ample, and sell lots predate D2/D3.
    if action == "add" and engine != "v7":
        monkeypatch.setitem(BOOKS, "version6", replace(BOOKS["version6"], allow_add=True))
    name_chain = {
        D0.strftime("%Y%m%d"): {CODE: "浦发"},
        D1.strftime("%Y%m%d"): {CODE: "*ST 浦发"},
        D2.strftime("%Y%m%d"): {ANCHOR: "其它名"},
        D3.strftime("%Y%m%d"): {CODE: "浦发"},
    }
    prices = ({D0: 100, D1: 94, D2: 89, D3: 89} if action == "sell"
              else {D0: 100, D1: 100, D2: 105, D3: 105})
    pool = {D2: [CODE], D3: [CODE]} if action == "add" else {}
    observed = []
    module = {"daily": daily, "minute": minute, "v7": v7}[engine]
    binding = "session_limit_prices" if engine == "v7" else "book_limit_prices"
    real_limits = getattr(module, binding)

    def observe(code, previous, names, **kwargs):
        limits = real_limits(code, previous, names, **kwargs)
        name = names if engine == "v7" else names.get(code, "")
        observed.append((previous, name, limits))  # Snapshot, never retain the mutable resolver map.
        return limits

    monkeypatch.setattr(module, binding, observe)
    states, bands = [], []
    for end in (D2, D3):
        names = {day: values for day, values in name_chain.items() if day <= f"{end:%Y%m%d}"}
        kwargs = ({"names": flatten_pool_names(names), "cash_total": 21_000_000}
                  if engine == "v7" else {"pool_names_by_day": names, "total_cash": 21_000_000})
        states.append(run(engine, prices, D0, end, pool=pool, **kwargs))
        bands.append(observed[:])
        observed.clear()
    short, extended = states
    previous = 94 if action == "sell" else 100
    st_limits = (98.7, 89.3) if action == "sell" else (105, 95)
    assert (previous, "*ST 浦发", st_limits) in bands[0]
    gate = defer_sell_at_limit if action == "sell" else skip_buy_at_limit
    assert gate(prices[D2], st_limits)  # Intercept is asserted separately from no fill.
    held_shares = (short.positions[CODE].shares if engine == "v7"
                   else sum(pos.shares for pos in short.positions[CODE]))
    assert held_shares == 100
    assert short.cash == 21_000_000
    assert not [t for t in short.trades if t["side"].lower() in ("buy", "sell")]

    if engine == "v7":
        # A longer window flattens the later normal name into the earlier held decision.
        normal_limits = (103.4, 84.6) if action == "sell" else (110, 90)
        assert (previous, "浦发", normal_limits) in bands[1]
        assert not gate(prices[D2], normal_limits)
        expected_day = D2
        assert ("defer_limit_down" if action == "sell" else "skip_limit_up") in [
            t["reason"] for t in short.trades
        ]
    else:
        assert (previous, "*ST 浦发", st_limits) in bands[1]
        normal_limits = (97.9, 80.1) if action == "sell" else (115.5, 94.5)
        assert (prices[D2], "浦发", normal_limits) in bands[1]
        assert not gate(prices[D3], normal_limits)
        expected_day = D3
        if action == "add":
            assert short.stats["skip_limit_up"] == 1
        elif engine == "daily":
            assert short.stats["defer_sell_limit_down"] > 0
        # The minute scanner intercepts internally; its outer defer counter stays zero.
    side = "sell" if action == "sell" else "buy"
    fills = [t for t in extended.trades if t["side"].lower() == side]
    assert len(fills) == 1
    assert fills[0]["date"].replace("-", "") == f"{expected_day:%Y%m%d}"
    assert fills[0]["price"] == prices[expected_day]
    assert fills[0]["shares"] > 0
    if action == "sell":
        assert CODE not in extended.positions
        assert extended.cash > short.cash
    else:
        assert extended.cash < short.cash


@pytest.mark.parametrize("engine", ["daily", "minute", "v7"])
@pytest.mark.parametrize("price,blocked", [(105, True), (104, False)])
def test_d3_unknown_board_st_reaches_limit_gate_and_fill(engine, price, blocked):
    names = {UNKNOWN: "*ST甲"}
    kwargs = {"names": names} if engine == "v7" else {"pool_names": names}
    state = run(engine, {D0: 100, D1: price}, D1, D1,
                code=UNKNOWN, pool={D1: [UNKNOWN]}, **kwargs)
    fills = [t for t in state.trades if t["side"].lower() == "buy"]
    if engine == "v7":
        reasons = [t["reason"] for t in state.trades]
        assert "skip_unknown_board" not in reasons
        assert ("skip_limit_up" in reasons) is blocked
    else:
        assert state.stats["skip_unknown_board"] == 0
        assert state.stats["skip_limit_up"] == int(blocked)
    if blocked:
        assert fills == [] and state.positions == {}
        assert state.cash == 21_000_000
    else:
        assert len(fills) == 1
        assert fills[0]["price"] == 104 and fills[0]["shares"] > 0
        assert UNKNOWN in state.positions
