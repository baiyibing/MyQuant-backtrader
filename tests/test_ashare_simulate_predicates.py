"""Shared gates at simulate call sites; preserve each ledger's known behavior."""

from datetime import date

import pandas as pd
import pytest

from backtest.research import csv_daily_backtest as daily
from backtest.research import csv_minute_backtest as minute
from backtest.research import csv_minute_backtest_v7 as v7
from backtest.research.ashare_session import t1_sellable
from backtest.research.csv_ledger import Position


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
            start=start, end=end,
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
def test_none_limits_sell_side_records_existing_split(engine, cause, monkeypatch):
    code = UNKNOWN if cause == "unknown_board" else CODE
    prices = {D1: 89} if cause == "no_previous_close" else {D0: 100, D1: 89}
    seed(monkeypatch, engine, code, D0)
    state = run(engine, prices, D0, D1, code=code, anchor=[D0, D1])
    if engine == "v7":
        # Known fail-open sell side for BOTH None branches; no new semantics.
        assert [(t["reason"], t["price"]) for t in sells(state)] == [("stop:trial_a090", 89)]
        assert code not in state.positions
    else:
        # Missing previous close freezes upstream; unknown board is rejected first.
        assert sells(state) == [] and state.positions[code][0].shares == 100
        if cause == "unknown_board":
            assert state.stats["skip_unknown_board"] == 1


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
