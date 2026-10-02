"""Price adds use actual 14:55 cash; tail parents do not reserve future cash."""

import pytest
from backtest.research.csv_ledger import InsufficientCashError
from backtest.research.tail_window_buy import TAIL_MINUTES

from tests.test_tail_window_allocation_regressions import A, _assert_cash_error, _bar, _simulate

LADDER_BOOKS = ("version8", "version8_4", "version8_5")


def _rising_rows(*, last_children_have_volume=True):
    rows = [_bar(hm, 9.05 if hm < 895 else 10.998, open_px=9.05)
            for hm in TAIL_MINUTES]
    if not last_children_have_volume:
        for row in rows[-2:]:
            row["volume"] = 0
    return {A: rows}


@pytest.mark.parametrize("strategy", LADDER_BOOKS)
@pytest.mark.parametrize("minimum_fee", [0, 5])
def test_1455_step_spends_actual_cash_then_next_child_reports_shortfall(strategy, minimum_fee):
    trace = []
    with pytest.raises(InsufficientCashError) as caught:
        _simulate(_rising_rows(), pool=[A], strategy=strategy, total_cash=51_800,
                  min_cost=minimum_fee, audit_sink=trace)
    # 25 cheap children, the 14:55 child and then the ordinary price step.
    available = 51_800 - 25 * (905 + minimum_fee) - (1099.8 + minimum_fee) - (27_495 + minimum_fee)
    _assert_cash_error(caught.value, code=A, needed=1099.8 + minimum_fee, available=available)
    steps = [row for row in trace if row["side"] == "BUY" and row["reason"] == "add:step20"]
    assert [(row["hm"], row["shares"], row["price"]) for row in steps] == [(895, 2500, 10.998)]
    children = [row for row in trace if row["side"] == "BUY" and row["reason"] == "pool:tail_window"]
    assert [row["hm"] for row in children] == list(range(870, 896))
    assert all(row["shares"] == 100 for row in children)
    assert steps[0]["position_id"] == children[0]["position_id"] == f"{A}@20260901"


@pytest.mark.parametrize("strategy", LADDER_BOOKS)
def test_1455_step_does_not_withhold_cash_for_later_zero_volume_children(strategy):
    state = _simulate(_rising_rows(last_children_have_volume=False), pool=[A],
                      strategy=strategy, total_cash=51_800, min_cost=5, audit_sink=(trace := []))
    steps = [row for row in trace if row["side"] == "BUY" and row["reason"] == "add:step20"]
    assert [(row["hm"], row["shares"]) for row in steps] == [(895, 2500)]
    assert state.cash == pytest.approx(445.2)
    lots = state.positions[A]
    assert [(lot.lot_id, lot.shares, lot.position_id) for lot in lots] == [
        (0, 2600, f"{A}@20260901"), (1, 2500, f"{A}@20260901"),
    ]


@pytest.mark.parametrize("strategy", LADDER_BOOKS)
def test_1455_step_and_all_28_children_complete_with_sufficient_cash(strategy):
    state = _simulate(_rising_rows(), pool=[A], strategy=strategy, total_cash=60_000,
                      min_cost=5, audit_sink=(trace := []))
    children = [row for row in state.trades if row.get("reason") == "pool:tail_window"]
    assert [row["shares"] for row in children] == [100] * 28
    assert [(row["hm"], row["shares"]) for row in trace
            if row["side"] == "BUY" and row["reason"] == "add:step20"] == [(895, 2500)]
    assert state.cash == pytest.approx(6435.6)
    assert [(lot.lot_id, lot.shares) for lot in state.positions[A]] == [(0, 2800), (1, 2500)]


@pytest.mark.parametrize("last_children_have_volume", [False, True])
def test_83_off_pool_confirmation_uses_1455_cash_without_parent_reservation(last_children_have_volume):
    from tests.test_tail_window_shared import A, B, D0, D1, bar, simulate

    rows = {
        A: [bar(hm, day=D0) for hm in TAIL_MINUTES] + [bar(895, price=10.4)],
        B: [bar(hm, volume=0 if hm >= 896 and not last_children_have_volume else 1_000_000)
            for hm in TAIL_MINUTES],
    }
    options = dict(pool={D0: [A], D1: [B]}, start=D0, total_cash=82_000,
                   strategy="version8_3", name_budget=56_000, audit_sink=(trace := []))
    if last_children_have_volume:
        with pytest.raises(InsufficientCashError) as caught:
            simulate(rows, **options)
        _assert_cash_error(caught.value, code=B, needed=1000, available=960)
    else:
        state = simulate(rows, **options)
        assert state.cash == pytest.approx(960)
        assert [(lot.lot_id, lot.shares, lot.position_id) for lot in state.positions[A]] == [
            (0, 2800, f"{A}@{D0}"), (1, 2600, f"{A}@{D0}"),
        ]
    adds = [row for row in trace if row["side"] == "BUY" and row["reason"] == "add:confirm3"]
    assert [(row["hm"], row["code"], row["shares"], row["position_id"]) for row in adds] == [
        (895, A, 2600, f"{A}@{D0}"),
    ]
    children = [row for row in trace if row["side"] == "BUY" and row["code"] == B]
    assert [row["hm"] for row in children] == list(range(870, 896))
