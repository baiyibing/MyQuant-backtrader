"""Frozen 8.1 allocations and actual cash funding after the #212 stack."""

import pandas as pd
import pytest
from backtest.research import csv_minute_backtest as minute
from backtest.research.csv_ledger import InsufficientCashError, Position
from backtest.research.tail_window_buy import TAIL_MINUTES

A, B, C = "600000.SH", "600001.SH", "600002.SH"
D0, D1 = "20260831", "20260901"


def _bar(hm, price=10.0, open_px=None):
    opening = price if open_px is None else open_px
    return {
        "ymd": D1, "hm": hm, "open": opening, "close": price,
        "high": max(opening, price), "low": min(opening, price),
        "volume": 1_000_000,
    }


def _simulate(rows, *, pool, start=D1, **kwargs):
    minutes, daily = {}, {}
    for code, values in rows.items():
        frame = pd.DataFrame(values)
        frame.index = pd.to_datetime(frame["ymd"]) + pd.to_timedelta(frame["hm"], unit="m")
        minutes[code] = frame
        daily[code] = pd.DataFrame(
            {"open": 10.0, "high": 10.0, "low": 10.0, "close": 10.0},
            index=pd.to_datetime(["20260828", D0, D1]),
        )
    options = {
        "strategy": "version8", "total_cash": 30_000, "name_budget": 28_000,
        "fix_minute_cash_order": True, "tail_window_buy": True,
        "tail_volume_unit": "shares", "buy_cost_rate": 0,
        "sell_cost_rate": 0, "min_cost": 0,
    }
    options.update(kwargs)
    return minute.simulate(minutes, daily, {D1: pool}, start, D1, **options)


@pytest.fixture
def held_a(monkeypatch):
    original = minute.init_sim_state

    def seed(*args, **kwargs):
        state, pending, names = original(*args, **kwargs)
        state.positions[A] = [Position(A, 100, 10, 0, 10)]
        return state, pending, names

    monkeypatch.setattr(minute, "init_sim_state", seed)


def _buy_shares(state, code):
    return sum(row["shares"] for row in state.trades
               if row["side"] == "BUY" and row["code"] == code)


@pytest.mark.parametrize("raw_order", [[A, B], [B, A]])
@pytest.mark.parametrize("ration,seed", [
    ("file_order", 0), ("seeded_shuffle", 0), ("seeded_shuffle", 1),
])
def test_grok_56000_daily_quota_is_frozen_before_early_slices(
    held_a, raw_order, ration, seed,
):
    """The reported 1500 A + 2800 B + idle 13000 must become 2800 each."""
    rows = {code: [_bar(hm) for hm in TAIL_MINUTES] for code in (A, B)}
    options = {
        "pool": raw_order, "strategy": "version8_1", "total_cash": 56_000,
        "daily_quota": 56_000, "ration": ration, "ration_seed": seed,
    }
    for fix_cash in (False, True):
        off = _simulate(rows, **options, tail_window_buy=False,
                        fix_minute_cash_order=fix_cash)
        assert (_buy_shares(off, A), _buy_shares(off, B)) == (2800, 2800)
        assert off.cash == pytest.approx(0)
        assert off.daily_quota_used == pytest.approx(56_000)
    on = _simulate(rows, **options)
    assert (_buy_shares(on, A), _buy_shares(on, B)) == (2800, 2800)
    assert on.cash == pytest.approx(0)
    assert on.daily_quota_used == pytest.approx(56_000)


def test_later_proceeds_expand_original_add_budget_but_not_frozen_new_parent(monkeypatch):
    original = minute.init_sim_state

    def seed(*args, **kwargs):
        state, pending, names = original(*args, **kwargs)
        state.positions[A] = [Position(A, 100, 10, 0, 10)]
        state.positions[C] = [Position(C, 6000, 10, 0, 10)]
        return state, pending, names

    monkeypatch.setattr(minute, "init_sim_state", seed)
    yesterday = {**_bar(570), "ymd": D0}
    rows = {
        A: [yesterday] + [_bar(hm) for hm in TAIL_MINUTES],
        B: [_bar(hm) for hm in TAIL_MINUTES],
        C: [yesterday, _bar(880, 9.4, open_px=10)],
    }
    state = _simulate(rows, pool=[A, B], start=D0, strategy="version8_1",
                      total_cash=56_000, daily_quota=112_000, stop_pct=.05)
    # The 14:40 sale returns 56400. Original 14:55 quota is min(112000, 112400)/2.
    assert _buy_shares(state, A) == 5600
    assert _buy_shares(state, B) == 2800
    assert state.daily_quota_used == pytest.approx(84_000)
    assert state.cash == pytest.approx(28_400)


PER_NAME_STRATEGIES = (
    "version8", "version8_2", "version8_3", "version8_4", "version8_5", "version8_6",
)


def _assert_cash_error(error, *, code, needed, available):
    assert error.date == D1
    assert error.code == code
    assert error.needed == pytest.approx(needed)
    assert error.available == pytest.approx(available)
    assert error.shortfall == pytest.approx(needed - available)
    for field in (D1, code, "needed", "available", "shortfall"):
        assert field in str(error)


@pytest.mark.parametrize("strategy", PER_NAME_STRATEGIES)
@pytest.mark.parametrize("minimum_fee", [0, 5])
def test_individually_fundable_parents_raise_at_child_cash_shortfall(strategy, minimum_fee):
    """Both 14:30 parents pass; no parent claims cash ahead of its children."""
    rows = {code: [_bar(hm) for hm in TAIL_MINUTES] for code in (A, B)}
    trace = []
    child_debit = 1000 + minimum_fee
    with pytest.raises(InsufficientCashError) as caught:
        _simulate(
            rows, pool=[A, B], strategy=strategy, total_cash=30 * child_debit,
            name_budget=56_000 if strategy == "version8_3" else 28_000,
            min_cost=minimum_fee, audit_sink=trace,
        )
    _assert_cash_error(caught.value, code=A, needed=child_debit, available=0)
    fills = [row for row in trace if row["side"] == "BUY"]
    assert len(fills) == 30
    assert {row["code"] for row in fills} == {A, B}
    assert [row["hm"] for row in fills] == [hm for hm in range(870, 885) for _ in (A, B)]
    assert all(row["shares"] == 100 for row in fills)


@pytest.mark.parametrize("strategy", PER_NAME_STRATEGIES)
def test_parent_requires_cash_for_all_child_minimum_fees_without_debiting(strategy):
    rows = {A: [_bar(hm) for hm in TAIL_MINUTES]}
    options = dict(pool=[A], strategy=strategy,
                   name_budget=56_000 if strategy == "version8_3" else 28_000,
                   min_cost=5)
    with pytest.raises(InsufficientCashError) as caught:
        _simulate(rows, **options, total_cash=28_139, audit_sink=(trace := []))
    _assert_cash_error(caught.value, code=A, needed=28_140, available=28_139)
    assert not [row for row in trace if row["side"] == "BUY"]
    state = _simulate(rows, **options, total_cash=28_140)
    assert _buy_shares(state, A) == 2800
    assert state.cash == pytest.approx(0)


@pytest.mark.parametrize("daily_quota,expected_a,expected_b,expected_cash", [
    (56_000, 2800, 2700, 725),
    (112_000, 5600, 5500, 720),
])
def test_daily_quota_children_use_current_cash_including_each_fee(
    daily_quota, expected_a, expected_b, expected_cash,
):
    """8.1 shrinks the final child to an affordable hand, or skips zero hands."""
    rows = {code: [_bar(hm) for hm in TAIL_MINUTES] for code in (A, B)}
    state = _simulate(rows, pool=[A, B], strategy="version8_1",
                      total_cash=daily_quota, daily_quota=daily_quota, min_cost=5)
    assert (_buy_shares(state, A), _buy_shares(state, B)) == (expected_a, expected_b)
    assert state.cash == pytest.approx(expected_cash)
    assert state.daily_quota_used == pytest.approx((expected_a + expected_b) * 10)
    b_fills = [row for row in state.trades if row["side"] == "BUY" and row["code"] == B]
    if daily_quota == 112_000:
        assert [row["shares"] for row in b_fills] == [200] * 27 + [100]
    else:
        assert [row["shares"] for row in b_fills] == [100] * 27
        assert b_fills[-1]["hm"] == 896
