"""Strategy 8 per-signal positions across daily and both minute clocks.

Synthetic inputs deliberately supply enough cash except in the explicit funding
failure tests. Exit overrides in ladder tests isolate the buying state machine;
other tests exercise the registered book's unmodified exits.
"""

from __future__ import annotations

from collections import defaultdict

import pandas as pd
import pytest
from backtest.research import csv_daily_backtest as daily_engine
from backtest.research import csv_minute_backtest as minute_engine
from backtest.research.csv_ledger import (
    InsufficientCashError,
    _sell,
    configure_s8,
    exit_positions,
)
from backtest.research.csv_simulate_loop import (
    init_sim_state,
    run_chase_due_day,
    run_pool_buys_day,
    run_step_adds_day,
)
from backtest.research.csv_strategy_books import apply_csv_strategy

CODE = "300001.SZ"
BOOKS = ("version8", "version8_2", "version8_3", "version8_4", "version8_5", "version8_6")
LADDER_BOOKS = ("version8", "version8_4", "version8_5")
MODES = ("daily", "minute_off", "minute_on")
DAYS = pd.bdate_range("2025-11-03", periods=14)


def _ds(index):
    return DAYS[index].strftime("%Y%m%d")


def _pid(index, code=CODE):
    return f"{code}@{_ds(index)}"


def _no_exit(*_args):
    return None


def _run(mode, strategy, prices, signals, *, rows=None, minute_rows=None, prev_close=None, **kwargs):
    """Three real entry points share identical OHLC observations by default."""
    rows = rows or [(px, px, px, px) for px in prices]
    dates = pd.DatetimeIndex([DAYS[0] - pd.Timedelta(days=3), *DAYS[:len(rows)]])
    daily = {CODE: pd.DataFrame(
        [(prices[0] if prev_close is None else prev_close,) * 4, *rows], index=dates,
        columns=["open", "high", "low", "close"], dtype=float,
    )}
    pool = {_ds(i): [CODE] for i in signals}
    options = {"total_cash": 21_000_000, **kwargs, "strategy": strategy}
    if mode == "daily":
        return daily_engine.simulate(daily, pool, _ds(0), _ds(len(rows) - 1), **options)
    records = []
    for i, (oo, hh, ll, cc) in enumerate(rows):
        session = ((minute_rows or {}).get(i) or [
            (570, oo, oo, oo, oo), (585, oo, oo, oo, oo),
            (895, cc, hh, ll, cc), (900, cc, cc, cc, cc),
        ])
        records.extend((_ds(i), *bar) for bar in session)
    minute = {CODE: pd.DataFrame(records, columns=["ymd", "hm", "open", "high", "low", "close"])}
    return minute_engine.simulate(
        minute, daily, pool, _ds(0), _ds(len(rows) - 1),
        fix_minute_cash_order=mode == "minute_on", **options,
    )


def _buys(st, reason=None):
    return [t for t in st.trades if t["side"] == "BUY" and (reason is None or t["reason"] == reason)]


def _sells(st):
    return [t for t in st.trades if t["side"] == "SELL"]


def _state(strategy, cash=21_000_000, **kwargs):
    hooks = apply_csv_strategy(strategy, **kwargs)
    st, pending, _ = init_sim_state(hooks, total_cash=cash, bars_loaded=1, pool_days={})
    configure_s8(st, hooks)
    return st, pending, hooks


def _pool(st, pending, hooks, index, px, *, code=CODE, prev=None):
    run_pool_buys_day(
        st, pending, day_i=index, day=DAYS[index], ds=_ds(index),
        pool_days={_ds(index): [code]}, daily_quota=1_000_000, names={},
        allow_add=hooks["allow_add"], buy_gate=None,
        buy_quote_for=lambda _code: (px, [px if prev is None else prev]),
        sizing=hooks["sizing"], name_budget=hooks["name_budget"],
        allow_new_name=hooks.get("allow_new_name"),
        add_gate=hooks.get("add_gate"), name_lot_budget=hooks.get("name_lot_budget"),
        index_blocks_add=hooks.get("index_blocks_add", True),
    )


def _step(st, hooks, index, px):
    run_step_adds_day(
        st, day_i=index, day=DAYS[index], ds=_ds(index), names={},
        buy_quote_for=lambda _code: (px, [px]), sizing=hooks["sizing"],
        name_budget=hooks["name_budget"], step_add=hooks.get("step_add"),
        name_lot_budget=hooks.get("name_lot_budget"),
    )


def _chase(st, pending, hooks, index, quotes):
    run_chase_due_day(
        st, pending, day_i=index, day=DAYS[index], ds=_ds(index), names={},
        allow_add=hooks["allow_add"], buy_gate=None, quotes_for=lambda _code: quotes,
        allow_new_name=hooks.get("allow_new_name"), add_gate=hooks.get("add_gate"),
        index_blocks_add=hooks.get("index_blocks_add", True),
    )


def _assert_cash_error(error, index, *, available=None):
    assert isinstance(error, InsufficientCashError)
    assert error.date == _ds(index)
    assert error.code == CODE
    assert error.needed > error.available
    assert error.shortfall == pytest.approx(error.needed - error.available)
    if available is not None:
        assert error.available == pytest.approx(available)
    for token in (_ds(index), CODE, "needed", "available", "shortfall"):
        assert token in str(error)


@pytest.mark.parametrize("strategy", BOOKS)
def test_reappearance_is_new_position_even_when_older_position_loses(strategy):
    st, pending, hooks = _state(strategy)
    _pool(st, pending, hooks, 0, 10.)
    _pool(st, pending, hooks, 1, 9.95)
    buys = _buys(st)
    assert [t["position_id"] for t in buys] == [_pid(0), _pid(1)]
    assert [t["entry_signal_date"] for t in buys] == [_ds(0), _ds(1)]
    assert st.stats["skip_add_loser"] == 0
    assert len(st.positions[CODE]) == 2
    budget = 500_000 if strategy == "version8_3" else 1_000_000
    for trade in buys:
        assert trade["shares"] == int(budget / trade["price"] / 100) * 100


@pytest.mark.parametrize("mode", MODES)
def test_83_losing_reappearance_reaches_both_real_engines(mode):
    st = _run(mode, "version8_3", [10., 9.95], [0, 1])
    assert [t["position_id"] for t in _buys(st)] == [_pid(0), _pid(1)]
    assert len(st.positions[CODE]) == 2
    assert st.stats["skip_add_loser"] == 0
    marks = [t for t in st.trades if t["side"] == "EOD_MARK"]
    assert {t["position_id"] for t in marks} == {_pid(0), _pid(1)}


@pytest.mark.parametrize("strategy", tuple(s for s in BOOKS if s != "version8_2"))
@pytest.mark.parametrize("mode", MODES)
def test_reappearance_passes_new_position_index_gate(mode, strategy):
    st = _run(
        mode, strategy, [10., 9.95], [0, 1], take_profit=_no_exit,
        index_block_new={DAYS[1].date(): True},
    )
    assert [t["position_id"] for t in _buys(st)] == [_pid(0)]
    assert st.stats["skip_index_gate"] == 1


@pytest.mark.parametrize("strategy", LADDER_BOOKS)
@pytest.mark.parametrize("mode", MODES)
def test_two_costs_cross_their_own_twenty_percent_steps(mode, strategy):
    st = _run(mode, strategy, [10., 10.5, 12.1, 12.7], [0, 1], take_profit=_no_exit)
    assert [(t["date"], t["position_id"]) for t in _buys(st, "add:step20")] == [
        (_ds(2), _pid(0)), (_ds(3), _pid(1)),
    ]


@pytest.mark.parametrize("strategy", LADDER_BOOKS)
@pytest.mark.parametrize("mode", MODES)
def test_first_position_exit_does_not_disable_second_position_steps(mode, strategy):
    def exit_first(_px, cost, _peak, n_days):
        return "profit_take:test_first" if cost == 10. and n_days >= 2 else None

    st = _run(mode, strategy, [10., 10.5, 11., 12.7], [0, 1], take_profit=exit_first)
    assert [t["position_id"] for t in _sells(st)] == [_pid(0)]
    assert [(t["date"], t["position_id"]) for t in _buys(st, "add:step20")] == [
        (_ds(3), _pid(1)),
    ]


@pytest.mark.parametrize("strategy", LADDER_BOOKS)
@pytest.mark.parametrize("mode", MODES)
def test_group_exit_closes_entry_and_step_without_resetting_executed_level(mode, strategy):
    def exit_group(_px, _cost, _peak, n_days):
        return "profit_take:test_group" if n_days >= 3 else None

    st = _run(mode, strategy, [10., 11., 12.1, 12.1, 12.1], [0], take_profit=exit_group)
    steps = _buys(st, "add:step20")
    assert len(steps) == 1
    assert steps[0]["position_id"] == _pid(0)
    assert len(_sells(st)) == 2
    assert {t["lot"] for t in _sells(st)} == {0, steps[0]["lot"]}
    assert {t["position_id"] for t in _sells(st)} == {steps[0]["position_id"]}
    group = st.book_state["s8_independent"]["groups"][_pid(0)]
    assert group.executed_steps == 1
    assert group.closed


@pytest.mark.parametrize("strategy", LADDER_BOOKS)
def test_executed_steps_survive_t1_partial_exit_and_pending_group_never_adds(strategy):
    st, pending, hooks = _state(strategy)
    _pool(st, pending, hooks, 0, 10.)
    _step(st, hooks, 1, 12.1)
    first, step = st.positions[CODE]
    group_pos = exit_positions(st, CODE, day_i=1)[0]
    _sell(st, CODE, group_pos, 12.1, DAYS[1], "profit_take:test", day_i=1)
    assert st.positions[CODE] == [step]
    assert first.shares == 0
    assert group_pos.pending_exit == "profit_take:test|t1_deferred"
    _step(st, hooks, 2, 12.1)
    assert len(_buys(st, "add:step20")) == 1
    _step(st, hooks, 3, 14.1)
    assert len(_buys(st, "add:step20")) == 1
    assert group_pos.group.executed_steps == 1
    _sell(st, CODE, group_pos, 14.1, DAYS[3], group_pos.pending_exit, day_i=3)
    assert group_pos.group.closed
    assert CODE not in st.positions


@pytest.mark.parametrize("strategy", LADDER_BOOKS)
def test_closed_group_cannot_reopen_at_higher_steps(strategy):
    st, pending, hooks = _state(strategy)
    _pool(st, pending, hooks, 0, 10.)
    _step(st, hooks, 1, 12.1)
    pos = exit_positions(st, CODE, day_i=2)[0]
    _sell(st, CODE, pos, 12.1, DAYS[2], "profit_take:test_group", day_i=2)
    _step(st, hooks, 3, 14.1)
    assert [(t["position_id"], t["price"]) for t in _buys(st, "add:step20")] == [
        (_pid(0), 12.1),
    ]
    assert pos.group.closed
    assert CODE not in st.positions


@pytest.mark.parametrize("mode", MODES)
def test_exdiv_scales_group_cost_and_preserves_first_cost_step_anchor(mode):
    st = _run(
        mode, "version8", [10., 11., 12.1, 12.1, 12.1, 7.05], [0],
        take_profit=_no_exit, exdiv={CODE: {_ds(5): .5}},
    )
    assert [(t["date"], t["price"]) for t in _buys(st, "add:step20")] == [
        (_ds(2), 12.1), (_ds(5), 7.05),
    ]
    assert not _sells(st)
    assert {p.position_id for p in st.positions[CODE]} == {_pid(0)}
    assert [p.cost for p in st.positions[CODE]] == [5., 6.05, 7.05]
    lots = st.positions[CODE]
    assert exit_positions(st, CODE)[0].cost == pytest.approx(
        sum(p.cost * p.shares for p in lots) / sum(p.shares for p in lots),
    )


@pytest.mark.parametrize("strategy", LADDER_BOOKS)
def test_at_most_one_price_step_per_position_per_day(strategy):
    st, pending, hooks = _state(strategy)
    _pool(st, pending, hooks, 0, 10.)
    _pool(st, pending, hooks, 1, 11.)
    _step(st, hooks, 2, 16.)
    _step(st, hooks, 2, 16.)
    assert [t["position_id"] for t in _buys(st, "add:step20")] == [_pid(0), _pid(1)]
    _step(st, hooks, 3, 16.)
    assert len(_buys(st, "add:step20")) == 4


@pytest.mark.parametrize("mode", MODES)
def test_83_three_reappearances_each_receive_one_off_pool_half_topup(mode):
    st = _run(
        mode, "version8_3", [10., 9.95, 9.9, 10.25, 10.25, 10.25], [0, 1, 2],
        rows=[(10., 10., 10., 10.), (9.95,) * 4, (9.9,) * 4,
              (10.25, 10.35, 10.25, 10.25), (10.25,) * 4, (10.25,) * 4],
    )
    groups = defaultdict(list)
    for trade in _buys(st):
        groups[trade["position_id"]].append(trade)
    assert set(groups) == {_pid(0), _pid(1), _pid(2)}
    assert len(_buys(st)) == 6
    for index in range(3):
        initial, topup = groups[_pid(index)]
        assert initial["reason"] == "pool"
        assert topup["reason"] != "pool"
        assert topup["date"] == _ds(3)
        assert initial["entry_signal_date"] == topup["entry_signal_date"] == _ds(index)
        for trade in (initial, topup):
            assert trade["shares"] == int(500_000 / trade["price"] / 100) * 100


@pytest.mark.parametrize("mode", MODES)
def test_83_confirmation_uses_each_positions_cost_and_peak(mode):
    st = _run(
        mode, "version8_3", [10., 9.8, 10., 10.], [0, 1],
        rows=[(10.,) * 4, (9.8,) * 4, (10., 10.2, 10., 10.), (10., 10.31, 10., 10.)],
    )
    adds = [t for t in _buys(st) if t["reason"] != "pool"]
    assert [(t["date"], t["position_id"]) for t in adds] == [
        (_ds(2), _pid(1)), (_ds(3), _pid(0)),
    ]


@pytest.mark.parametrize("strategy", ("version8_2", "version8_6"))
@pytest.mark.parametrize("mode", MODES)
def test_books_without_price_adds_still_have_none(mode, strategy):
    st = _run(mode, strategy, [10., 11., 12.1], [0], take_profit=_no_exit)
    assert [t["reason"] for t in _buys(st)] == ["pool"]


def test_pending_chases_coexist_by_signal_date_and_keep_83_half_budget():
    code = "600000.SH"
    st, pending, hooks = _state("version8_3")
    _pool(st, pending, hooks, 0, 11., code=code, prev=10.)
    _chase(st, pending, hooks, 1, None)
    _pool(st, pending, hooks, 1, 12.1, code=code, prev=11.)
    assert set(pending) == {_pid(0, code), _pid(1, code)}
    assert st.stats["chase_overwrite"] == 0
    _chase(st, pending, hooks, 2, (12., 12.2, [12.1]))
    buys = _buys(st, "chase:T+1")
    assert [t["position_id"] for t in buys] == [_pid(0, code), _pid(1, code)]
    assert all(t["shares"] == int(500_000 / 12.2 / 100) * 100 for t in buys)
    assert not pending
    assert {p.entry_idx for p in st.positions[code]} == {2}


@pytest.mark.parametrize("mode", ("minute_off", "minute_on"))
def test_two_pending_signal_dates_chase_together_in_minute_engines(mode):
    st = _run(
        mode, "version8_3", [12., 14.4, 14.5], [0, 1], prev_close=10.,
        rows=[(12.,) * 4, (14.4,) * 4, (14.4, 14.5, 14.4, 14.5)],
        minute_rows={
            # No morning observation: keep yesterday's chase while today's
            # independent signal queues at its own +20% upper limit.
            1: [(895, 14.4, 14.4, 14.4, 14.4), (900, 14.4, 14.4, 14.4, 14.4)],
            2: [(570, 14.4, 14.4, 14.4, 14.4), (585, 14.4, 14.5, 14.4, 14.5),
                (895, 14.5, 14.5, 14.5, 14.5), (900, 14.5, 14.5, 14.5, 14.5)],
        },
    )
    buys = _buys(st)
    assert [t["position_id"] for t in buys] == [_pid(0), _pid(1)]
    assert all(t["reason"] == "chase:T+1" and t["date"] == _ds(2) for t in buys)
    assert all(t["shares"] == int(500_000 / 14.5 / 100) * 100 for t in buys)
    assert {p.entry_idx for p in st.positions[CODE]} == {2}
    assert st.stats["chase_overwrite"] == 0
    assert st.stats["chase_pending_eod"] == 0


@pytest.mark.parametrize("mode", MODES)
def test_83_chase_keeps_signal_identity_half_budget_and_actual_entry_day(mode):
    st = _run(
        mode, "version8_3", [12., 12.2], [0], prev_close=10.,
        rows=[(10., 12., 10., 12.), (12., 12.2, 12., 12.2)],
        minute_rows={1: [(570, 12., 12., 12., 12.), (585, 12., 12.2, 12., 12.2),
                         (895, 12.2, 12.2, 12.2, 12.2), (900, 12.2, 12.2, 12.2, 12.2)]},
    )
    buys = _buys(st)
    assert len(buys) == 1
    assert buys[0]["date"] == _ds(1)
    assert buys[0]["reason"] == "chase:T+1"
    assert buys[0]["position_id"] == _pid(0)
    assert buys[0]["entry_signal_date"] == _ds(0)
    assert buys[0]["shares"] == int(500_000 / buys[0]["price"] / 100) * 100
    assert st.positions[CODE][0].entry_idx == 1


@pytest.mark.parametrize("mode", ("minute_off", "minute_on"))
def test_83_confirmation_is_scanned_at_1455_not_at_1500(mode):
    st = _run(
        mode, "version8_3", [10., 10.4, 10.4], [0],
        rows=[(10.,) * 4, (10., 10.4, 10., 10.4), (10.4,) * 4],
        minute_rows={1: [(570, 10., 10., 10., 10.), (585, 10., 10., 10., 10.),
                         (895, 10.01, 10.01, 10.01, 10.01), (900, 10.4, 10.4, 10.4, 10.4)]},
    )
    assert [(t["date"], t["position_id"]) for t in _buys(st, "add:confirm3")] == [
        (_ds(2), _pid(0)),
    ]


@pytest.mark.parametrize("mode", MODES)
def test_independent_stale_clock_keeps_younger_losing_position(mode):
    prices = [10.] * 7 + [9.9, 9.9, 9.9]
    st = _run(mode, "version8_3", prices, [0, 7])
    assert [t["position_id"] for t in _sells(st)] == [_pid(0)]
    assert _sells(st)[0]["reason"] == "force_sell:stale"
    survivor = st.positions[CODE][0]
    assert survivor.position_id == _pid(7)
    assert survivor.cost == 9.9
    assert survivor.peak == 9.9


@pytest.mark.parametrize("mode", MODES)
def test_limit_down_defers_each_lot_and_later_sale_preserves_other_position(mode):
    st = _run(mode, "version8_3", [10., 9.5, 7.6, 8.7], [0, 1])
    sells = _sells(st)
    assert len(sells) == 1
    assert sells[0]["date"] == _ds(3)
    assert sells[0]["position_id"] == _pid(0)
    survivor = st.positions[CODE][0]
    assert survivor.position_id == _pid(1)
    assert (survivor.cost, survivor.peak) == (9.5, 9.5)


@pytest.mark.parametrize("mode", MODES)
def test_sell_day_reappearance_is_allowed_and_new_position_keeps_t1(mode):
    st = _run(
        mode, "version8_3", [10., 8.9], [0, 1],
        rows=[(10.,) * 4, (8.9, 11., 8.9, 8.9)],
    )
    assert [t["position_id"] for t in _sells(st)] == [_pid(0)]
    assert [t["position_id"] for t in _buys(st)] == [_pid(0), _pid(1)]
    survivor = st.positions[CODE][0]
    assert survivor.position_id == _pid(1)
    assert (survivor.cost, survivor.peak) == (8.9, 8.9)


@pytest.mark.parametrize("strategy", BOOKS)
@pytest.mark.parametrize("mode", MODES)
def test_pool_cash_shortfall_raises_with_fee_and_context(mode, strategy):
    budget = 500_000 if strategy == "version8_3" else 1_000_000
    with pytest.raises(InsufficientCashError) as caught:
        _run(mode, strategy, [10.], [0], total_cash=budget)
    _assert_cash_error(caught.value, 0, available=budget)
    assert caught.value.needed == pytest.approx(budget * 1.001)
    assert caught.value.shortfall == pytest.approx(budget * .001)


@pytest.mark.parametrize("strategy", ("version8", "version8_3"))
def test_reprocessing_same_signal_does_not_raise_after_original_order_used_cash(strategy):
    budget = 500_000 if strategy == "version8_3" else 1_000_000
    st, pending, hooks = _state(strategy, cash=budget + budget * .001)
    _pool(st, pending, hooks, 0, 10.)
    assert st.cash == pytest.approx(0.)
    _pool(st, pending, hooks, 0, 10.)
    assert len(_buys(st)) == 1
    assert [t["position_id"] for t in _buys(st)] == [_pid(0)]


@pytest.mark.parametrize("strategy", (*LADDER_BOOKS, "version8_3"))
@pytest.mark.parametrize("mode", MODES)
def test_price_add_cash_shortfall_raises_in_every_clock(mode, strategy):
    budget = 500_000 if strategy == "version8_3" else 1_000_000
    prices = [10., 10.4] if strategy == "version8_3" else [10., 11., 12.1]
    with pytest.raises(InsufficientCashError) as caught:
        _run(mode, strategy, prices, [0], total_cash=budget * 1.001 + 100, take_profit=_no_exit)
    _assert_cash_error(caught.value, len(prices) - 1, available=100)


@pytest.mark.parametrize("strategy", BOOKS)
def test_chase_cash_shortfall_raises_in_shared_path(strategy):
    st, pending, hooks = _state(strategy, cash=100.)
    _pool(st, pending, hooks, 0, 12., prev=10.)
    with pytest.raises(InsufficientCashError) as caught:
        _chase(st, pending, hooks, 1, (12., 12.2, [12.]))
    _assert_cash_error(caught.value, 1, available=100.)


@pytest.mark.parametrize("strategy", BOOKS)
@pytest.mark.parametrize("mode", MODES)
def test_chase_cash_shortfall_raises_in_every_clock(mode, strategy):
    with pytest.raises(InsufficientCashError) as caught:
        _run(
            mode, strategy, [12., 12.2], [0], total_cash=100., prev_close=10.,
            rows=[(12.,) * 4, (12., 12.2, 12., 12.2)],
            minute_rows={1: [(570, 12., 12., 12., 12.), (585, 12., 12.2, 12., 12.2),
                             (895, 12.2, 12.2, 12.2, 12.2), (900, 12.2, 12.2, 12.2, 12.2)]},
        )
    _assert_cash_error(caught.value, 1, available=100.)
    budget = 500_000 if strategy == "version8_3" else 1_000_000
    notional = int(budget / 12.2 / 100) * 100 * 12.2
    assert caught.value.needed == pytest.approx(notional * 1.001)


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("strategy", ("version8_1", "version1"))
def test_unrelated_books_keep_cash_skip_and_no_identity_columns(mode, strategy):
    st = _run(mode, strategy, [10.], [0], total_cash=1_000.)
    assert not _buys(st)
    assert not st.positions
    assert all("position_id" not in t and "entry_signal_date" not in t for t in st.trades)


@pytest.mark.parametrize("mode", MODES)
def test_81_reappearance_preserves_legacy_lots_and_output_columns(mode):
    st = _run(mode, "version8_1", [10., 9.95], [0, 1])
    assert [t["lot"] for t in _buys(st)] == [0, 1]
    assert len(st.positions[CODE]) == 2
    assert all("position_id" not in t and "entry_signal_date" not in t for t in st.trades)
