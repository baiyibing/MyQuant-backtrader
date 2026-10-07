"""V7 event contracts and the main-owned schedules."""
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
                                fix_minute_cash_order=chronological,
                                rule_profile="legacy")
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


@pytest.mark.parametrize("chronological", [False, True])
def test_both_schedules_delegate_to_main_and_return_identical_object(monkeypatch, chronological):
    import ast
    import inspect
    from backtest.research import csv_minute_backtest as main
    from backtest.research import minute_cash_order as scheduler
    from backtest.research.minute_engine_policies import MinutePolicyContext

    calls = []
    days = []
    original = main.simulate
    schedule = "run_v7_chronological_day" if chronological else "run_symbol_major_day"
    run_day = getattr(scheduler, schedule)
    def spy(*args, **kwargs):
        result = original(*args, **kwargs)
        calls.append((args, kwargs, result))
        return result
    def day_spy(*args, **kwargs):
        days.append(args[1])
        return run_day(*args, **kwargs)
    monkeypatch.setattr(main, 'simulate', spy)
    monkeypatch.setattr(scheduler, schedule, day_spy)
    assert not hasattr(native, '_run_chronological_day')
    assert not hasattr(native, '_DayCursor')
    bars = {S: [dict(datetime=D.isoformat(), hm=895, open=10, close=10)]}
    closes = {S: {D - timedelta(days=1): 10}}
    result = native.simulate_v7(bars, closes, {D: [S]}, [D], fee=FEE,
                                fix_minute_cash_order=chronological,
                                rule_profile="legacy")
    assert len(calls) == 1 and calls[0][2] is result
    assert type(result) is native.SimResult is engine.SimResult
    assert calls[0][1]['fix_minute_cash_order'] is chronological
    assert calls[0][1]['strategy'] == 'version7'
    assert days == [D]
    direct = original(bars, closes, {D: [S]}, None, None, strategy='version7',
                      total_cash=21_000_000, fix_minute_cash_order=chronological,
                      policy_context=MinutePolicyContext(index_days=[D], fee_schedule=FEE),
                      rule_profile="legacy")
    assert asdict(direct) == asdict(result)
    tree = ast.parse(inspect.getsource(native.simulate_v7))
    assert not any(isinstance(node, (ast.For, ast.While)) for node in ast.walk(tree))
    def failing(*args, **kwargs):
        raise RuntimeError('main failed')
    monkeypatch.setattr(main, 'simulate', failing)
    with pytest.raises(RuntimeError, match='main failed'):
        native.simulate_v7(bars, closes, {D: [S]}, [D],
                           fix_minute_cash_order=chronological,
                           rule_profile="legacy")


def test_no_production_traversal_in_native_shim_or_book():
    import ast
    import inspect

    # Only input conversion and aggregate lot settlement may contain loops.
    # Keep this list explicit: a new production day/row runner must fail here.
    conversion_and_ledger = {
        '_record_stamp', '_minute_records', '_iter_records', '_daily_closes',
        '_sell_lots',
    }
    for module in (native, engine):
        assert not hasattr(module, '_DayCursor')
        assert not hasattr(module, '_run_chronological_day')
    tree = ast.parse(inspect.getsource(engine))
    for definition in tree.body:
        if isinstance(definition, (ast.FunctionDef, ast.ClassDef)):
            if definition.name not in conversion_and_ledger:
                assert not any(isinstance(node, (ast.For, ast.While, ast.AsyncFor))
                               for node in ast.walk(definition)), definition.name
    shim = ast.parse(inspect.getsource(native.simulate_v7))
    assert not any(isinstance(node, (ast.For, ast.While, ast.AsyncFor, ast.comprehension))
                   for node in ast.walk(shim))


@pytest.mark.parametrize('chronological', [False, True])
def test_shim_normalizes_tail_unit_before_main(monkeypatch, chronological):
    import inspect

    # Signature/defaults match the conversion adapter, plus legacy unknown-option rejection.
    shim = inspect.signature(native.simulate_v7)
    adapter = inspect.signature(engine.simulate_native)
    assert [p for p in shim.parameters.values() if p.name != 'unsupported_options'] == list(
        adapter.parameters.values())
    sentinel = engine.SimResult(1)
    calls = []
    def spy(*args, **kwargs):
        calls.append((args, kwargs))
        return sentinel
    from backtest.research import csv_minute_backtest as main
    monkeypatch.setattr(main, 'simulate', spy)
    bars, closes, pools, index = {}, {}, {}, []
    assert native.simulate_v7(
        bars, closes, pools, index, fix_minute_cash_order=chronological,
        tail_window_buy=chronological, tail_volume_unit=None,
        rule_profile="legacy") is sentinel
    assert calls[0][0][:3] == (bars, closes, pools)
    assert calls[0][1]['policy_context'].index_days is index
    assert calls[0][1]['fix_minute_cash_order'] is chronological
    assert calls[0][1]['tail_volume_unit'] == ('shares' if chronological else None)


def test_registered_v7_cash_binding_is_skip_with_and_without_explicit_default():
    from backtest.research import csv_ledger
    from backtest.research.csv_strategy_books import get_minute_book
    from backtest.research import csv_minute_backtest as main
    for explicit in (True, False):
        hooks = get_minute_book('version7').apply()
        if not explicit:
            hooks.pop('on_short_cash')
        state = csv_ledger.SimState()
        csv_ledger.configure_s8(state, hooks)
        assert not csv_ledger.uses_s8_independent('version7', 'per_name')
        assert csv_ledger.s8_policy(state) is None
        assert state.on_short_cash == 'skip'
    result = main.simulate(
        {S: [dict(datetime=D.isoformat(), hm=895, open=10, close=10)]},
        {S: {D - timedelta(days=1): 10}}, {D: [S]}, None, None,
        strategy='version7', total_cash=1, rule_profile="legacy")
    assert result.on_short_cash == 'skip'
    assert result.trades[-1]['reason'] == 'skip_cash'


def test_sell_limit_checks_fill_only_even_when_open_is_at_limit():
    state = engine.SimResult(0, {S: held()})
    day = D + timedelta(days=1)
    # A non-first open at the lower limit must not veto a valid close stop.
    engine.MinuteSession.stop(state, state.positions[S], S, day, 571, False,
                              8, 8.9, 10, 10, (12, 8), FEE, None)
    assert state.trades[-1]['side'] == 'sell'
    assert state.trades[-1]['price'] == 8.9


@pytest.mark.parametrize('case', [
    'default', 'short_cash', 'participation', 'exdiv', 'economics',
    'index_gate', 'frame_calendar', 'names', 'names_by_day', 'audit', 'sell_fill_only',
    'chronological', 'tail_default', 'tail_none', 'tail_shares', 'tail_lots',
])
def test_direct_main_matches_frozen_native_cases(case, monkeypatch, tmp_path):
    import json
    from backtest.research import csv_minute_backtest as main
    from backtest.research.minute_engine_policies import MinutePolicyContext
    from scripts.research.generate_v7_app_baseline import FIXTURE, capture_case

    def direct(minute_bars, daily_bars, pool_days, index_days=None, **kwargs):
        kwargs.setdefault("rule_profile", "legacy")
        return main.simulate(
            minute_bars, daily_bars, pool_days,
            kwargs.pop('start', None), kwargs.pop('end', None), strategy='version7',
            total_cash=kwargs.pop('cash_total', 21_000_000),
            pool_names=kwargs.pop('names', None),
            pool_names_by_day=kwargs.pop('names_by_day', None),
            policy_context=MinutePolicyContext(index_days=index_days,
                                               fee_schedule=kwargs.pop('fee', None)),
            **kwargs)
    monkeypatch.setattr(native, 'simulate_v7', direct)
    actual = capture_case(case, tmp_path / case)
    expected = json.loads(FIXTURE.read_text(encoding='utf-8'))['cases'][case]
    assert actual == expected


@pytest.mark.parametrize("chronological", [False, True])
def test_v7_policy_selects_schedule_and_callbacks_do_not_traverse(chronological):
    import ast
    import inspect
    from backtest.research.csv_strategy_books import get_minute_book
    hooks = get_minute_book("version7").apply(fix_minute_cash_order=chronological)
    assert hooks["minute_policy"].schedule == (
        "chronological" if chronological else "symbol_major")
    for name in ("chronological_stop", "chronological_parent", "chronological_buy",
                 "chronological_timer", "chronological_observe"):
        callback = getattr(hooks["minute_session"], name)
        tree = ast.parse(inspect.getsource(callback))
        assert not any(isinstance(node, (ast.For, ast.While)) for node in ast.walk(tree))


@pytest.mark.parametrize("chronological", [False, True])
def test_main_v7_never_applies_open_and_fill_sell_limit_gate(monkeypatch, chronological):
    from backtest.research import csv_minute_backtest as main
    from backtest.research.minute_engine_policies import MinutePolicyContext
    result_type = engine.SimResult
    monkeypatch.setattr(engine, "SimResult", lambda cash: result_type(cash, {S: held()}))
    day = D + timedelta(days=1)
    result = main.simulate(
        {S: [dict(datetime=day.isoformat(), hm=570, open=10, close=10),
             dict(datetime=day.isoformat(), hm=571, open=8, close=8.9)]},
        {S: {D: 10}}, {}, None, None, strategy="version7", total_cash=0,
        fix_minute_cash_order=chronological,
        policy_context=MinutePolicyContext(index_days=[day], fee_schedule=FEE),
        rule_profile="legacy")
    assert result.trades == [dict(date=day.isoformat(), symbol=S, hm=571,
                                 side="sell", shares=300, price=8.9,
                                 reason="stop:trial_a090")]


@pytest.mark.parametrize('entry', ['shim', 'app'])
@pytest.mark.parametrize('chronological,unit,message', [
    (True, 'invalid', 'tail volume unit (--tail-volume-unit) must be shares or lots'),
    (False, 'shares', '--tail-window-buy requires --fix-minute-cash-order'),
    (False, 'invalid', '--tail-window-buy requires --fix-minute-cash-order'),
])
def test_native_tail_error_parity_before_main(monkeypatch, entry, chronological, unit, message):
    from backtest.research import csv_minute_backtest as main
    from backtest.research import csv_minute_backtest_topk_app_dropout as app
    from backtest.research.tail_window_buy import validate_tail_options, resolve_tail_volume_unit

    # Exact pre-PR6 sequence from origin/master: validate, then resolve when enabled.
    with pytest.raises(ValueError) as old:
        validate_tail_options(True, chronological, unit)
        resolve_tail_volume_unit(unit)
    assert str(old.value) == message

    def forbidden(*args, **kwargs):
        pytest.fail('invalid tail options reached main simulate')
    monkeypatch.setattr(main, 'simulate', forbidden)
    call = native.simulate_v7 if entry == 'shim' else app.simulate_native
    with pytest.raises(type(old.value)) as current:
        call({}, {}, {}, [], tail_window_buy=True,
             fix_minute_cash_order=chronological, tail_volume_unit=unit,
             rule_profile="legacy")
    assert str(current.value) == str(old.value)
