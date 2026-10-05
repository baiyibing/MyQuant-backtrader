"""Single-event contracts while the two native schedulers remain active."""
from dataclasses import asdict
from datetime import date, timedelta

import pytest

from backtest.research import csv_minute_backtest_v7 as native
from backtest.research import strategy7_engine as engine
from backtest.research.ashare_fees import FeeSchedule
from backtest.research.ashare_volume_cap import BucketVolume, VolumeCap

D = date(2026, 9, 1)
S = "300001.SZ"
FEE = FeeSchedule(0.00001, 0.00001, 5)


def held():
    return engine.Position(S, 10, avg_cost=10, peak=10, last_add_date=D,
                           lots=[engine.Lot(100, D, 10, "trial"),
                                 engine.Lot(200, D, 10, "add_a104")])


def test_legacy_exports_are_identical():
    for name in ("Lot", "Position", "SimResult", "_minute_records", "_daily_closes",
                 "_pool", "_event", "_buy", "_sell_lots", "_buy_tail_slice",
                 "_rescale_position", "_apply_exdiv_economics", "_day_frame_records"):
        assert getattr(native, name) is getattr(engine, name)


@pytest.mark.parametrize("first,opening,closing,phase,price,at", [
    (True, 8.9, 10, "open", 8.9, 569),
    (False, 8.9, 8.8, "close", 8.8, 570),
    (True, 10, 8.8, "close", 8.8, 570),
])
def test_stop_candidate_and_aggregate_settlement(first, opening, closing, phase, price, at):
    pos = held()
    day = D + timedelta(days=1)
    # One same-day lot survives; eligible lots share one minimum sell fee.
    pos.lots.append(engine.Lot(100, day, 11, "trial"))
    state = engine.SimResult(1000, {S: pos})
    candidate = engine.MinuteSession.stop_candidate(pos, 570, first, opening, closing)
    assert (candidate.phase, candidate.price, candidate.at) == (phase, price, at)
    engine.MinuteSession.stop(state, pos, S, day, 570, first, opening, closing,
                              12, 10, (12, 8), FEE, None)
    assert pos.peak == 12
    assert state.cash == 1000 + FEE.credit_sell(300 * price)
    assert pos.lots == [engine.Lot(100, day, 11, "trial")]
    assert pos.avg_cost == 11
    assert state.trades == [dict(date=day.isoformat(), symbol=S, hm=570, side="sell",
                                 shares=300, price=price, reason="stop:trial_a090")]


def test_rejected_stop_can_retry_and_gap_uses_previous_bucket():
    day = D + timedelta(days=1)
    pos = held()
    state = engine.SimResult(0, {S: pos})
    key = (S, day.strftime("%Y%m%d"), 570)
    state.volume_cap = VolumeCap(1, {key: BucketVolume(100, 570, "raw_shares_incremental")})
    engine.MinuteSession.stop(state, pos, S, day, 570, True, 8.9, 8.9, 10,
                              10, (12, 8), FEE, None)
    assert pos.shares == 300  # gap cannot use its unfinished bucket
    engine.MinuteSession.stop(state, pos, S, day, 570, False, 8.9, 8.9, 10,
                              10, (12, 8), FEE, None)
    assert pos.shares == 200
    assert state.trades[-1]["shares"] == 100


def test_short_cash_precedes_capacity_and_does_not_advance_stage():
    pos = held()
    state = engine.SimResult(1, {S: pos})
    before = asdict(pos)
    engine.MinuteSession.add(state, pos, S, D, 895, 10.5, 10, (12, 8), FEE)
    assert asdict(pos) == before
    assert state.trades[-1]["reason"] == "skip_cash"


@pytest.mark.parametrize("chronological", [False, True])
def test_manual_trial_add_callbacks_match_native_settlement(chronological):
    day2 = D + timedelta(days=1)
    bars = {S: [dict(datetime=D.isoformat(), hm=895, open=10, close=10),
                dict(datetime=day2.isoformat(), hm=895, open=10.5, close=10.5)]}
    closes = {S: {D - timedelta(days=1): 10, D: 10}}
    actual = native.simulate_v7(bars, closes, {D: [S]}, [D, day2], fee=FEE,
                                fix_minute_cash_order=chronological)
    state = engine.SimResult(21_000_000)
    engine.MinuteSession.trial(state, S, D, 895, 10, False, 10, "", FEE)
    pos = state.positions[S]
    engine.MinuteSession.stop(state, pos, S, day2, 895, True, 10.5, 10.5,
                              10.5, 10, (12, 8), FEE, None)
    engine.MinuteSession.add(state, pos, S, day2, 895, 10.5, 10, (12, 8), FEE)
    assert state.cash == actual.cash
    assert state.trades == actual.trades
    assert asdict(state.positions[S]) == asdict(actual.positions[S])


def test_finish_and_minute_close_observation():
    state = engine.SimResult(1)
    marks = {}
    assert engine.MinuteSession.observe_row(state, S, {"close": 11, "high": 12}, marks) == (11, 11, 12)
    assert marks == {S: 11}
    engine.MinuteSession.finish_symbol(state, S, D, True, False, [])
    assert state.trades[-1]["reason"] == "skip_no_1455"


def test_empty_explicit_index_mapping_and_calendar_bounds():
    with pytest.raises(ValueError, match="warmup"):
        engine.prepare_calendar({}, None, {D: {}}, {D: [S]})
    assert engine.prepare_calendar(None, None, {D: {}, D + timedelta(days=1): {}},
                                   {}, D + timedelta(days=1)) == ([D + timedelta(days=1)], {})


def test_timer_settlement_matches_native_primitive():
    calendar = [D + timedelta(days=i) for i in range(11)]
    day = calendar[-1]
    pos = held()
    state = engine.SimResult(100, {S: pos})
    expected = engine.SimResult(100, {S: engine.Position(**{
        **vars(pos), "lots": list(pos.lots)})})
    native._sell_lots(expected, expected.positions[S], day, 900, 10,
                      "exit:timer10", fee=FEE)
    cleared = set()
    engine.MinuteSession.timer(state, S, day, 900, 10, calendar, 10,
                               (12, 8), FEE, cleared)
    assert asdict(state) == asdict(expected)
    assert cleared == {S}


def test_tail_callback_merges_children_and_preserves_initial_peak():
    from backtest.research.tail_window_buy import TailParent

    state = engine.SimResult(1_000_000)
    parent = TailParent.from_budget(200_000, 10)
    for hm, price in [(870, 10), (871, 11)]:
        engine.MinuteSession.buy_tail_slice(
            state, parent, S, D, hm, {"close": price, "volume": 100_000}, "shares", FEE)
    pos = state.positions[S]
    assert len(pos.lots) == 1
    assert pos.lots[0].buy_date == D and pos.lots[0].kind == "trial"
    assert pos.shares == 1400
    assert pos.avg_cost == pos.lots[0].price == 10.5
    assert pos.peak == 10
    assert state.cash == 1_000_000 - FEE.debit_buy(7000) - FEE.debit_buy(7700)


def test_accounting_keeps_mark_fallback_and_receivable_order():
    from backtest.research.ashare_exdiv_economics import ExDivEconomics

    state = engine.SimResult(100, {S: held()})
    state.exdiv_economics = ExDivEconomics({})
    engine.AccountingPolicy.settle_day(state, D)
    engine.AccountingPolicy.append_equity(state, D, {})
    assert state.equity_curve == [dict(date=D.isoformat(), cash=100,
                                      holdings=3000, equity=3100)]


@pytest.mark.parametrize("in_pool,has_position,open_checked", [
    (False, False, False), (True, True, False), (True, False, True),
])
def test_finish_symbol_does_not_read_rows_outside_original_guard(
    in_pool, has_position, open_checked
):
    state = engine.SimResult(1, {S: held()} if has_position else {})
    engine.MinuteSession.finish_symbol(state, S, D, in_pool, open_checked, [{}])
    assert state.trades == []


def test_finish_symbol_reads_target_only_when_needed():
    state = engine.SimResult(1)
    with pytest.raises(KeyError, match="hm"):
        engine.MinuteSession.finish_symbol(state, S, D, True, False, [{}])
    engine.MinuteSession.finish_symbol(state, S, D, True, False, [{"hm": 895}, {}])
    assert state.trades == []


@pytest.mark.parametrize("first", [False, True])
def test_nan_close_does_not_trigger_stop(first):
    assert engine.MinuteSession.stop_candidate(held(), 570, first, 10, float("nan")) is None
