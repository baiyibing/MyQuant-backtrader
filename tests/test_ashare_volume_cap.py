"""P3 δ5 C/A/A/A: real book/v7 capacity wiring, synthetic records only."""

from dataclasses import asdict
from datetime import date
import hashlib
import json

import pandas as pd
import pytest

from backtest.research import csv_daily_backtest as daily
from backtest.research import csv_minute_backtest as book
from backtest.research import csv_minute_backtest_v7 as v7
from backtest.research.ashare_fees import QLIB_PORTANA, trade_commission
from backtest.research.ashare_volume_cap import BucketVolume, VolumeCap
from backtest.research.csv_ledger import Position, SimState, _sell, execute_buy
from backtest.research.csv_simulate_loop import run_chase_due_day, run_pool_buys_day, run_step_adds_day

CODE = "600000.SH"
D1, D2, D3 = date(2026, 9, 1), date(2026, 9, 2), date(2026, 9, 3)
UNIT = "raw_shares_incremental"


def volume(shares, hm=895, unit=UNIT):
    return BucketVolume(shares, hm, unit)


def key(day=D1, hm=895, code=CODE):
    return code, day.strftime("%Y%m%d"), hm


def bars(rows):
    """(day, hm, open, close) -> unchanged book OHLC/ymd/hm frame."""
    return {CODE: pd.DataFrame([
        {"open": op, "high": max(op, cl), "low": min(op, cl), "close": cl,
         "ymd": day.strftime("%Y%m%d"), "hm": hm}
        for day, hm, op, cl in rows
    ], index=pd.DatetimeIndex([pd.Timestamp(day) + pd.Timedelta(minutes=hm)
                               for day, hm, _, _ in rows]))}


def daily_bars(closes=(10.0, 10.0, 10.0, 10.0)):
    return {CODE: pd.DataFrame({name: closes for name in ("open", "high", "low", "close")},
                              index=pd.to_datetime([date(2026, 8, 31), D1, D2, D3]))}


def records(rows):
    return {CODE: [{"date": day, "hm": hm, "open": op, "close": cl,
                    "high": max(op, cl)} for day, hm, op, cl in rows]}


def book_run(rows, lookup=None, *, pools=None, end="20260902", **kwargs):
    return book.simulate(bars(rows), daily_bars(), pools or {"20260901": [CODE]},
                         "20260901", end, strategy="version6", daily_quota=5000,
                         stop_pct=0.02, participation_rate=0.1,
                         volume_for_bucket=lookup, **kwargs)


def fills(state):
    return [t for t in state.trades if t["side"].lower() in ("buy", "sell")]


def _off_run(engine, raw_volume, lookup=None):
    ds = daily_bars()
    ms = bars([(D1, 895, 10, 10), (D2, 895, 10, 9.7)])
    ds[CODE]["volume"] = raw_volume
    ms[CODE]["volume"] = raw_volume
    if engine == "daily":
        return daily.simulate(ds, {"20260901": [CODE]}, "20260901", "20260902",
                              strategy="version6", daily_quota=5000, stop_pct=0.02)
    if engine == "book":
        return book.simulate(ms, ds, {"20260901": [CODE]}, "20260901", "20260902",
                             strategy="version6", daily_quota=5000, stop_pct=0.02,
                             volume_for_bucket=lookup)
    return v7.simulate_v7(ms, ds, {D1: [CODE]}, [D1, D2], volume_for_bucket=lookup)


def _snapshot(state):
    out = {"cash": state.cash, "trades": state.trades, "equity_curve": state.equity_curve,
           "positions": {code: ([asdict(p) for p in pos] if isinstance(pos, list) else asdict(pos))
                         for code, pos in state.positions.items()}}
    if hasattr(state, "stats"):
        out.update(stats=state.stats, daily_quota_used=state.daily_quota_used,
                   supplementary_used=state.supplementary_used)
    return json.dumps(out, sort_keys=True, separators=(",", ":"), default=str).encode()


@pytest.mark.parametrize("engine", ["daily", "book", "v7"])
def test_cap_off_byte_snapshot_with_p2_b_labels_and_ignores_volume(engine):
    # Human GO P2=B labels remain. b951bec adds minute fee stats only
    # (buy/sell_cost_rate, min_cost); capital pairing adds stats["daily_quota"].
    # Removing daily_quota reproduces the 2904e749/4b6ccf7f pins; removing the
    # fee stats too reproduces the prior 9220b164 snapshot; fill economics unchanged.
    expected = {"daily": "6b8975a899049fa694aedb60d5a68cf50dbd79db18f9ed131267d448f2e453d2", "book": "e33b5ed5120d82e9340d0f380796adbb8248d71eff22c3cd974ef2cd93305c0c", "v7": "2d3c71db7e90c4286271d4a5470235511314a05adb13fc6c54ca323e7f8044ee"}

    def forbidden_lookup(*_):
        pytest.fail("cap off must not consult the volume provider")

    for raw_volume in (0, 1, 10**12, float("nan")):
        result = _snapshot(_off_run(engine, raw_volume, forbidden_lookup))
        assert hashlib.sha256(result).hexdigest() == expected[engine]


def test_d1_public_book_lot_cash_and_force_min_cannot_breach_remainder():
    state = book_run([(D1, 895, 10, 10)], {key(): volume(2500)}, end="20260901")
    assert [t["shares"] for t in fills(state)] == [200]
    assert state.positions[CODE][0].shares == 200
    assert state.cash == 21_000_000 - 2000 - trade_commission(2000, state.buy_cost_rate, state.min_cost)
    assert state.volume_cap.used == {key(): 200}  # EOD_MARK consumes nothing
    assert not execute_buy(state, CODE, 10, 1, 0, D1, bucket_id=895)
    assert state.volume_cap.used == {key(): 200}
    assert state.stats["skip_volume_cap"] == 1
    assert state.stats["supplementary_used"] == 0


@pytest.mark.parametrize("order", [("pool", "chase"), ("chase", "pool")])
def test_d2_real_pool_chase_order_shares_one_budget(order):
    state = SimState(cash=100_000, volume_cap=VolumeCap(.1, {key(D2): volume(3000)}))
    for path in order:
        if path == "pool":
            run_pool_buys_day(state, {}, day_i=1, day=D2, ds="20260902",
                             pool_days={"20260902": [CODE]}, daily_quota=2000, names={},
                             allow_add=True, buy_gate=None, buy_quote_for=lambda _: (10, [10]),
                             volume_bucket_for=lambda _: 895)
        else:
            pending = {CODE: (2000, 0)}
            run_chase_due_day(state, pending, day_i=1, day=D2, names={}, allow_add=True,
                              buy_gate=None, quotes_for=lambda _: (9.9, 10, [10]),
                              volume_bucket_for=lambda _: 895)
            assert pending == {}  # no cap-created residual chase
    assert [(t["reason"].split(":")[0], t["shares"]) for t in fills(state)] == list(zip(order, [200, 100]))
    assert state.volume_cap.used == {key(D2): 300}


def test_d2_step_partial_has_filled_shares_and_no_residual_queue():
    state = SimState(cash=100_000, volume_cap=VolumeCap(.1, {key(D2): volume(3000)}))
    state.positions[CODE] = [Position(CODE, 100, 10, 0, 10)]
    assert execute_buy(state, CODE, 12, 2400, 1, D2, bucket_id=895)
    run_step_adds_day(state, day_i=1, day=D2, ds="20260902", names={},
                      buy_quote_for=lambda _: (12, [12]), sizing="per_name", name_budget=2400,
                      step_add=lambda lots, px: True, volume_bucket_for=lambda _: 895)
    assert [(p.shares, p.is_step) for p in state.positions[CODE]] == [(100, False), (200, False), (100, True)]
    assert state.volume_cap.used == {key(D2): 300}


def test_d3_cash_and_limit_rejects_do_not_consume_or_read_capacity():
    calls = []

    def lookup(*args):
        calls.append(args)
        return volume(3000)

    state = SimState(cash=1, volume_cap=VolumeCap(.1, lookup))
    assert not execute_buy(state, CODE, 10, 2000, 0, D1, bucket_id=895)
    state.cash = 100_000
    run_pool_buys_day(state, {}, day_i=0, day=D1, ds="20260901",
                     pool_days={"20260901": [CODE]}, daily_quota=2000, names={},
                     allow_add=True, buy_gate=None, buy_quote_for=lambda _: (11, [10]),
                     volume_bucket_for=lambda _: 895)
    assert calls == [] and state.volume_cap.used == {}
    assert execute_buy(state, CODE, 10, 2000, 0, D1, bucket_id=895)
    assert calls == [key()] and state.volume_cap.used == {key(): 200}


def test_d4_public_book_partial_sell_preserves_position_and_no_buy_remainder():
    state = book_run([(D1, 895, 10, 10), (D2, 600, 10, 9.7), (D2, 895, 10, 10)],
                     {key(): volume(3000), key(D2, 600): volume(2000, 600), key(D2): volume(10**8)})
    assert [(t["side"], t["shares"]) for t in fills(state)] == [("BUY", 300), ("SELL", 200)]
    assert state.positions[CODE][0].shares == 100
    assert state.positions[CODE][0].entry_idx == 0
    assert state.volume_cap.used == {key(): 300, key(D2, 600): 200}


def test_d4_book_t1_old_partial_and_new_lot_ineligible():
    state = SimState(cash=1000, volume_cap=VolumeCap(.1, {key(D2): volume(2000)}))
    old, new = Position(CODE, 300, 10, 0, 10), Position(CODE, 200, 10, 1, 10, lot_id=1)
    state.positions[CODE] = [old, new]
    _sell(state, CODE, new, 10, D2, "stop_loss", bucket_id=895, day_i=1)
    assert state.volume_cap.used == {}
    _sell(state, CODE, old, 10, D2, "stop_loss", bucket_id=895, day_i=1)
    assert [p.shares for p in state.positions[CODE]] == [100, 200]
    assert state.volume_cap.used == {key(D2): 200}


@pytest.mark.parametrize("sample, family", [
    (volume(0), "skip_volume_cap"), (None, "skip_volume_unavailable"),
    (2500, "skip_volume_unavailable"), (volume(-1), "skip_volume_unavailable"),
    (volume(float("nan")), "skip_volume_unavailable"),
    (volume(float("inf")), "skip_volume_unavailable"),
    (volume(2500.0), "skip_volume_unavailable"), (volume(True), "skip_volume_unavailable"),
    (volume(2500, unit="lots"), "skip_volume_unavailable"),
    (volume(2500, 896), "skip_volume_unavailable"),
    (volume(2500, 894), "skip_volume_unavailable"),
])
@pytest.mark.parametrize("engine", ["book", "v7"])
def test_d5_public_zero_and_unavailable_diagnostics(engine, sample, family):
    lookup = {key(): sample}
    if engine == "book":
        state = book_run([(D1, 895, 10, 10)], lookup, end="20260901")
    else:
        state = v7.simulate_v7(records([(D1, 895, 10, 10)]), daily_bars(), {D1: [CODE]}, [D1],
                               participation_rate=.1, volume_for_bucket=lookup)
    assert fills(state) == [] and state.positions == {} and state.cash == 21_000_000
    assert state.trades[0]["reason"].startswith(family + ":")
    assert state.volume_cap.used == {}


def test_d5_bucket_switch_no_borrow_and_revisit_no_reset():
    cap = VolumeCap(.1, {key(): volume(2500), key(hm=896): volume(500, 896)})
    state = SimState(cash=100_000, volume_cap=cap)
    assert execute_buy(state, CODE, 10, 5000, 0, D1, bucket_id=895)
    assert not execute_buy(state, CODE, 10, 1, 0, D1, bucket_id=896)
    assert not execute_buy(state, CODE, 10, 1, 0, D1, bucket_id=895)
    assert cap.used == {key(): 200}


def test_d6_public_v7_prefix_and_stage_only_advance_on_actual_fill():
    rows = [(D1, 895, 100, 100), (D2, 885, 104, 104), (D2, 888, 108, 108)]
    outputs = []
    for later in (0, 10**9):
        lookup = {key(): volume(2500), key(D2, 885): volume(500, 885),
                  key(D2, 888): volume(later, 888)}
        state = v7.simulate_v7(records(rows), {CODE: {date(2026, 8, 31): 100, D1: 100}},
                               {D1: [CODE]}, [D1, D2], participation_rate=.1,
                               volume_for_bucket=lookup)
        outputs.append(state)
    assert outputs[0].trades[:2] == outputs[1].trades[:2]
    assert outputs[0].positions[CODE].stage == "trial"
    assert outputs[0].positions[CODE].shares == 200
    assert outputs[1].positions[CODE].stage == "four"
    assert outputs[1].positions[CODE].lots[-1].kind == "add_a104"


def test_d6_book_fallback_uses_quote_bucket_not_later_volume():
    calls = []

    def lookup(*args):
        calls.append(args)
        return volume(2500, 894) if args[2] == 894 else volume(10**9)

    state = book_run([(D1, 894, 10, 10)], lookup, end="20260901")
    assert calls == [key(hm=894)]
    assert fills(state)[0]["shares"] == 200


@pytest.mark.parametrize("engine", ["book", "v7"])
def test_d6_gap_open_cannot_read_completed_same_bar_volume(engine):
    calls = []

    def lookup(*args):
        calls.append(args)
        return volume(10**9, args[2])

    if engine == "book":
        state = book_run([(D1, 895, 10, 10), (D2, 570, 9.7, 9.7)], lookup)
    else:
        state = v7.simulate_v7(records([(D1, 895, 100, 100), (D2, 570, 89, 89)]),
                               {CODE: {date(2026, 8, 31): 100, D1: 98}}, {D1: [CODE]},
                               [D1, D2], participation_rate=.1, volume_for_bucket=lookup)
    assert calls == [key()]
    assert len(fills(state)) == 1
    assert any(t.get("reason") == "skip_volume_unavailable:bucket_not_completed" for t in state.trades)


def test_public_v7_partial_buy_sell_and_same_day_ladder_lot_t1():
    # Old trial 300; D2 add 200; stop sells 200 old shares, keeps old100+new200.
    rows = [(D1, 895, 100, 100), (D2, 885, 104, 104), (D2, 888, 100, 96)]
    lookup = {key(): volume(3000), key(D2, 885): volume(2000, 885),
              key(D2, 888): volume(2000, 888)}
    state = v7.simulate_v7(records(rows), {CODE: {date(2026, 8, 31): 100, D1: 100}},
                           {D1: [CODE]}, [D1, D2], participation_rate=.1, volume_for_bucket=lookup)
    assert [(t["side"], t["shares"]) for t in fills(state)] == [("buy", 300), ("buy", 200), ("sell", 200)]
    pos = state.positions[CODE]
    assert [(lot.shares, lot.buy_date) for lot in pos.lots] == [(100, D1), (200, D2)]
    assert pos.stage == "four" and pos.last_add_date == D2
    assert pos.avg_cost == pytest.approx((100 * 100 + 200 * 104) / 300)


def test_d7_book_partial_fee_floor_per_lot_and_bidirectional_budget():
    state = SimState(cash=100_000, buy_cost_rate=QLIB_PORTANA.buy_rate,
                     sell_cost_rate=QLIB_PORTANA.sell_rate, min_cost=QLIB_PORTANA.min_cost,
                     volume_cap=VolumeCap(.1, {key(D2): volume(3000)}))
    old = [Position(CODE, 100, 10, 0, 10), Position(CODE, 300, 10, 0, 10, lot_id=1)]
    state.positions[CODE] = old[:]
    assert execute_buy(state, CODE, 10, 1000, 1, D2, bucket_id=895)
    for pos in old:
        _sell(state, CODE, pos, 10, D2, "force_sell", bucket_id=895, day_i=1)
    sold = [t for t in fills(state) if t["side"] == "SELL"]
    assert [t["shares"] for t in sold] == [100, 100]
    assert [t["commission"] for t in sold] == [QLIB_PORTANA.sell_fee(1000)] * 2 == [5, 5]
    assert state.volume_cap.used == {key(D2): 300}
    assert state.cash == 100_000 - QLIB_PORTANA.debit_buy(1000) + 2 * QLIB_PORTANA.credit_sell(1000)
    assert [p.shares for p in state.positions[CODE]] == [200, 100]


def test_d7_v7_partial_fee_floor_once_across_eligible_lots_and_shared_sides():
    state = v7.SimResult(100_000, volume_cap=VolumeCap(.1, {key(D2): volume(3000)}))
    pos = v7.Position(CODE, 10, avg_cost=10,
                      lots=[v7.Lot(100, D1, 10, "trial"), v7.Lot(300, D1, 10, "trial")])
    state.positions[CODE] = pos
    assert v7._buy(state, pos, CODE, D2, 895, 10, .001, "buy:add", "add", fee=QLIB_PORTANA)
    assert v7._sell_lots(state, pos, D2, 895, 10, "exit", fee=QLIB_PORTANA) == 200
    assert state.cash == 100_000 - QLIB_PORTANA.debit_buy(1000) + QLIB_PORTANA.credit_sell(2000)
    assert QLIB_PORTANA.sell_fee(2000) == 5
    assert [(p.shares, p.buy_date) for p in pos.lots] == [(200, D1), (100, D2)]
    assert state.volume_cap.used == {key(D2): 300}


@pytest.mark.parametrize("budget, child_idx, expected", [(2000, 0, False), (5000, 1, False), (5000, 0, True)])
def test_ride_group_atomic_exit_never_orphans_child(budget, child_idx, expected):
    state = SimState(cash=0, volume_cap=VolumeCap(.1, {key(D2): volume(budget)}))
    parent = Position(CODE, 300, 10, 0, 10)
    child = Position(CODE, 200, 10, child_idx, 10, lot_id=1, ride_with=0)
    state.positions[CODE] = [parent, child]
    _sell(state, CODE, parent, 10, D2, "force_sell", bucket_id=895, day_i=1)
    assert bool(fills(state)) is expected
    if expected:
        assert state.positions == {} and state.volume_cap.used == {key(D2): 500}
    else:
        assert [p.shares for p in state.positions[CODE]] == [300, 200]
        assert state.volume_cap.used == {}


def test_pending_exit_atomic_reject_keeps_reason_and_shares():
    state = SimState(cash=0, volume_cap=VolumeCap(.1, {key(D2): volume(2000)}))
    pos = Position(CODE, 300, 10, 0, 10, pending_exit="trail")
    state.positions[CODE] = [pos]
    _sell(state, CODE, pos, 10, D2, "trail", bucket_id=895, day_i=1)
    assert pos.shares == 300 and pos.pending_exit == "trail"
    assert state.trades[0]["reason"] == "skip_volume_cap:atomic_exit"
    assert state.cash == 0 and state.volume_cap.used == {}


@pytest.mark.parametrize("rate", [-.1, 1.1, float("nan"), float("inf"), True])
def test_invalid_participation_rate_is_configuration_error(rate):
    with pytest.raises(ValueError, match="participation_rate"):
        VolumeCap(rate, {})


def test_decimal_boundary_zero_rate_and_frozen_sample():
    source = {key(): volume(10**30 + 100)}
    cap = VolumeCap(.29, source)
    wanted = 10**40
    assert cap.clamp(key(), 895, wanted)[0] == 29 * (10**30 + 100) // 100
    source[key()] = volume(10**40)
    assert cap.clamp(key(), 895, wanted)[0] == 29 * (10**30 + 100) // 100
    assert VolumeCap(0, source).clamp(key(), 895, 100) == (0, "skip_volume_cap:zero_or_exhausted")


def test_public_book_pool_step_share_actual_quote_bucket(monkeypatch):
    original = book.init_sim_state

    def initialized(*args, **kwargs):
        state, pending, names = original(*args, **kwargs)
        state.positions[CODE] = [Position(CODE, 100, 10, 0, 10)]
        return state, pending, names

    monkeypatch.setattr(book, "init_sim_state", initialized)
    state = book.simulate(bars([(D1, 894, 12, 12)]), daily_bars((12, 12, 12, 12)),
                          {"20260901": [CODE]}, "20260901", "20260901",
                          strategy="version8", name_budget=2400, participation_rate=.1,
                          volume_for_bucket={key(hm=894): volume(3000, 894)})
    assert [(t["reason"], t["shares"]) for t in fills(state)] == [("pool", 200), ("add:step20", 100)]
    assert state.positions[CODE][-1].is_step
    assert state.volume_cap.used == {key(hm=894): 300}


def test_public_book_chase_fallback_and_volume_failure_diagnosis():
    # First day's limit-up queues the pre-existing chase; next day's fallback
    # closes it once, even when the cap cannot allocate a lot.
    for capacity, expected in ((0, []), (2500, [200])):
        state = book_run([(D1, 895, 11, 11), (D2, 570, 10, 10), (D2, 584, 10, 10.1)],
                         {key(D2, 584): volume(capacity, 584)})
        assert [t["shares"] for t in fills(state)] == expected
        assert state.stats["chase_pending_eod"] == 0
        if capacity == 0:
            assert state.stats["chase_buy_fail_volume"] == 1
            assert state.stats["chase_buy_fail_cash"] == 0
        else:
            assert state.volume_cap.used == {key(D2, 584): 200}


def test_v7_cash_t1_and_kind_gates_consume_zero():
    def forbidden(*_):
        pytest.fail("rejected cash/T+1/kind attempt cannot consult capacity")

    state = v7.SimResult(1, volume_cap=VolumeCap(.1, forbidden))
    assert v7._buy(state, None, CODE, D2, 895, 10, .001, "buy", "trial") is None
    pos = v7.Position(CODE, 10, avg_cost=10, lots=[v7.Lot(200, D2, 10, "trial")])
    assert v7._sell_lots(state, pos, D2, 895, 10, "stop") == 0
    assert v7._sell_lots(state, pos, D3, 895, 10, "stop", kind="add") == 0
    assert state.volume_cap.used == {} and pos.shares == 200


@pytest.mark.parametrize("hm, at", [(None, None), (895, float("nan")), (895, float("inf")),
                                   (895, True), (895, 894), (1440, 1440), (-1, 0)])
def test_unavailable_clock_never_reads_future_bucket(hm, at):
    def forbidden(*_):
        pytest.fail("invalid/incomplete clock must reject before lookup")

    cap = VolumeCap(.1, forbidden)
    assert cap.clamp(key(hm=hm), at, 100) == (0, "skip_volume_unavailable:bucket_not_completed")
    assert cap.used == {}


def test_public_book_held_sell_and_pool_buy_share_same_bucket():
    state = book_run([(D1, 895, 10, 10), (D2, 895, 10, 9.7)],
                     {key(): volume(3000), key(D2): volume(4000)},
                     pools={"20260901": [CODE], "20260902": [CODE]})
    assert [(t["side"], t["shares"]) for t in fills(state)] == [("BUY", 300), ("SELL", 300), ("BUY", 100)]
    assert state.volume_cap.used == {key(): 300, key(D2): 400}
    assert [(p.shares, p.entry_idx) for p in state.positions[CODE]] == [(100, 1)]


def test_nested_ride_tree_rejects_before_parent_booking():
    state = SimState(cash=0, volume_cap=VolumeCap(.1, {key(D2): volume(2000)}))
    parent = Position(CODE, 100, 10, 0, 10)
    child = Position(CODE, 100, 10, 0, 10, lot_id=1, ride_with=0)
    grandchild = Position(CODE, 100, 10, 0, 10, lot_id=2, ride_with=1)
    state.positions[CODE] = [parent, child, grandchild]
    _sell(state, CODE, parent, 10, D2, "force_sell", bucket_id=895, day_i=1)
    assert state.trades[0]["reason"] == "skip_volume_cap:unsupported_ride_tree"
    assert [p.shares for p in state.positions[CODE]] == [100, 100, 100]
    assert state.cash == 0 and state.volume_cap.used == {}
