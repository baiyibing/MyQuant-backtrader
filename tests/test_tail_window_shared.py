"""X-04 shared-engine integration: causal first entries and unchanged other buys."""

from dataclasses import asdict
from types import SimpleNamespace

import pandas as pd
import pytest
from backtest.research import csv_minute_backtest as minute
from backtest.research.csv_ledger import InsufficientCashError, Position
from backtest.research.tail_window_buy import TAIL_MINUTES

A, B, C = "600000.SH", "600001.SH", "600002.SH"
D0, D1, D2 = "20260831", "20260901", "20260902"


def bar(hm, *, day=D1, price=10.0, open_px=None, volume=1_000_000, amount=None):
    row = {"ymd": day, "hm": hm, "open": price if open_px is None else open_px,
           "close": price, "high": max(price, price if open_px is None else open_px),
           "low": min(price, price if open_px is None else open_px), "volume": volume}
    if amount is not None:
        row["amount"] = amount
    return row


def inputs(rows):
    minutes, daily = {}, {}
    for code, values in rows.items():
        frame = pd.DataFrame(values)
        frame.index = pd.to_datetime(frame["ymd"]) + pd.to_timedelta(frame["hm"], unit="m")
        minutes[code] = frame
        daily[code] = pd.DataFrame(
            {"open": 10., "high": 10., "low": 10., "close": 10.},
            index=pd.to_datetime(["20260828", D0, D1, D2]),
        )
    return minutes, daily


def simulate(rows, *, pool=None, start=D1, end=D1, **kwargs):
    minutes, daily = inputs(rows)
    options = {"strategy": "version8", "total_cash": 1_000_000,
               "name_budget": 28_000, "fix_minute_cash_order": True,
               "tail_window_buy": True,
               "buy_cost_rate": 0, "sell_cost_rate": 0, "min_cost": 0}
    options.update(kwargs)
    return minute.simulate(minutes, daily, pool or {D1: [A]}, start, end, **options)


def buys(state, code=A):
    return [row for row in state.trades if row["side"] == "BUY" and row["code"] == code]


@pytest.fixture
def synthetic_run(monkeypatch):
    minutes, daily = inputs({A: [bar(hm) for hm in TAIL_MINUTES]})
    requests = []
    monkeypatch.setattr(minute, "warn_stale_period_env", lambda: None)
    monkeypatch.setattr(minute, "load_pool_day_map", lambda *args, **kwargs: {D1: [A]})
    monkeypatch.setattr(minute, "load_pool_names_by_day", lambda *args: {})
    monkeypatch.setattr(minute, "load_daily_ohlc", lambda *args, **kwargs: daily)
    monkeypatch.setattr(minute, "load_exdiv_ratios", lambda *args, **kwargs: None)
    monkeypatch.setattr(minute, "time", SimpleNamespace(perf_counter=lambda: 0.0))

    def load(*args, **kwargs):
        requests.append(kwargs)
        return minutes

    monkeypatch.setattr(minute, "load_minute_bars", load)
    return requests


@pytest.mark.parametrize("unit_options", [{}, {"tail_volume_unit": None}], ids=["omitted", "none"])
def test_simulate_default_volume_unit_equals_explicit_shares(unit_options):
    rows = {A: [bar(hm, volume=1000, amount=10_200) for hm in TAIL_MINUTES]}
    actual = simulate(rows, name_budget=56_000, audit_sink=(actual_trace := []), **unit_options)
    explicit = simulate(rows, name_budget=56_000, tail_volume_unit="shares",
                        audit_sink=(explicit_trace := []))
    assert asdict(actual) == asdict(explicit)
    assert actual_trace == explicit_trace
    assert [row["shares"] for row in buys(actual)] == [100] * 28


@pytest.mark.parametrize("strategy", ["version8", "version8_1", "version8_2", "version8_3",
                                      "version8_4", "version8_5", "version8_6"])
def test_all_8x_first_entries_have_28_equal_children_and_one_t1_lot(strategy):
    trace = []
    budget = 56_000 if strategy == "version8_3" else 28_000
    state = simulate({A: [bar(hm) for hm in TAIL_MINUTES]}, strategy=strategy,
                     name_budget=budget, daily_quota=28_000, audit_sink=trace)
    assert [row["hm"] for row in trace if row["side"] == "BUY"] == list(TAIL_MINUTES)
    assert [row["shares"] for row in buys(state)] == [100] * 28
    assert len(state.positions[A]) == 1
    lot = state.positions[A][0]
    assert (lot.shares, lot.cost, lot.entry_idx) == (2800, 10, 0)
    assert len({row["lot"] for row in buys(state)}) == 1
    assert not [row for row in state.trades if row["side"] == "SELL"]
    assert sum(row["notional"] for row in buys(state)) == 28_000


def test_each_bar_capacity_auction_price_and_no_1457_1459():
    rows = [bar(hm, volume=999 if hm == 871 else 2500,
                price=10.5, open_px=10, amount=2500 * 10.2)
            for hm in range(870, 901)]
    state = simulate({A: rows}, name_budget=280_000, audit_sink=(trace := []))
    fills = [row for row in trace if row["side"] == "BUY"]
    assert {row["hm"] for row in fills} == set(TAIL_MINUTES) - {871}
    assert all(row["shares"] == 200 for row in fills)
    assert all(row["price"] == pytest.approx(10.2) for row in fills if row["hm"] != 900)
    assert fills[-1]["hm"] == 900 and fills[-1]["price"] == 10.5
    lot = state.positions[A][0]
    assert lot.cost == pytest.approx((26 * 200 * 10.2 + 200 * 10.5) / 5400)


@pytest.mark.parametrize("absent", [870, 875, 900])
def test_missing_exact_bar_never_uses_another_minute(absent):
    state = simulate({A: [bar(hm) for hm in TAIL_MINUTES if hm != absent]}, audit_sink=(trace := []))
    actual = [row["hm"] for row in trace if row["side"] == "BUY"]
    assert actual == ([] if absent == 870 else [hm for hm in TAIL_MINUTES if hm != absent])
    assert len(buys(state)) == len(actual)


@pytest.mark.parametrize("volume", [0, 999, float("nan")])
def test_zero_unavailable_or_sub_hand_volume_drops_children(volume):
    state = simulate({A: [bar(hm, volume=volume) for hm in TAIL_MINUTES]})
    assert not buys(state)
    assert state.stats["chase_pending_eod"] == 0


@pytest.mark.parametrize("duplicate_hm", [870, 875, 900])
def test_duplicate_library_bar_is_rejected_instead_of_doubling_capacity(duplicate_hm):
    rows = [bar(hm) for hm in TAIL_MINUTES] + [bar(duplicate_hm)]
    rows.sort(key=lambda row: row["hm"])
    state = simulate({A: rows}, audit_sink=(trace := []))
    actual = [row["hm"] for row in trace if row["side"] == "BUY"]
    assert actual == ([] if duplicate_hm == 870
                      else [hm for hm in TAIL_MINUTES if hm != duplicate_hm])
    assert sum(row["shares"] for row in buys(state)) == len(actual) * 100


def test_limit_up_blocks_only_that_slice_and_does_not_queue_next_day_chase():
    state = simulate({A: [bar(hm, price=11 if hm == 875 else 10, open_px=10)
                          for hm in TAIL_MINUTES]}, audit_sink=(trace := []))
    actual = [row["hm"] for row in trace if row["side"] == "BUY"]
    assert actual == [hm for hm in TAIL_MINUTES if hm != 875]
    assert state.stats["chase_pending_eod"] == 0


def test_explicit_lots_volume_converts_amount_and_cap_to_shares():
    state = simulate({A: [bar(hm, volume=10, amount=10_200) for hm in TAIL_MINUTES]},
                     tail_volume_unit="lots", name_budget=56_000)
    assert [row["shares"] for row in buys(state)] == [100] * 28
    assert [row["price"] for row in buys(state)] == [10.2] * 27 + [10]


def test_fixed_parent_uses_open_not_future_1455_price_and_floor_residual_expires():
    rows = [bar(hm, open_px=10, price=10.8 if hm >= 895 else 10)
            for hm in TAIL_MINUTES]
    state = simulate({A: rows}, name_budget=29_990)
    assert [row["shares"] for row in buys(state)] == [100] * 28
    assert sum(row["shares"] for row in buys(state)) == 2800
    assert sum(row["notional"] for row in buys(state)) == pytest.approx(28_240)


def test_unfilled_slices_and_auction_do_not_roll_to_tomorrow():
    rows = [bar(hm, volume=1000 if hm == 875 else 0) for hm in TAIL_MINUTES]
    rows += [bar(hm, day=D2) for hm in TAIL_MINUTES]
    state = simulate({A: rows}, end=D2)
    assert [(row["date"], row["shares"]) for row in buys(state)] == [(D1, 100)]
    assert state.stats["chase_pending_eod"] == 0


@pytest.mark.parametrize("gap_open", [False, True])
def test_same_minute_sales_settle_before_tail_children(gap_open):
    rows = {
        A: [bar(hm, day=D0) for hm in TAIL_MINUTES]
           + [bar(880, price=9.4, open_px=9.4 if gap_open else 10)],
        B: [bar(hm) for hm in TAIL_MINUTES],
    }
    state = simulate(rows, pool={D0: [A], D1: [B]}, start=D0,
                     total_cash=56_000, stop_pct=.05, audit_sink=(trace := []))
    same = [row for row in trace if row["date"] == D1 and row["hm"] == 880]
    assert [row["side"] for row in same] == ["SELL", "BUY"]
    assert same[0]["phase"] == ("open" if gap_open else "close")
    assert [row["hm"] for row in buys(state, B)] == list(TAIL_MINUTES)
    assert state.cash == pytest.approx(26_320)


def test_insufficient_parent_fails_before_future_sale_proceeds():
    rows = {
        A: [bar(hm, day=D0) for hm in TAIL_MINUTES] + [bar(880, price=9.4, open_px=10)],
        B: [bar(hm) for hm in TAIL_MINUTES],
    }
    with pytest.raises(InsufficientCashError) as caught:
        simulate(rows, pool={D0: [A], D1: [B]}, start=D0, total_cash=28_000,
                 stop_pct=.05, audit_sink=(trace := []))
    error = caught.value
    assert (error.date, error.code, error.needed, error.available) == (D1, B, 28_000, 0)
    assert not [row for row in trace if row["date"] == D1 and row["side"] in {"BUY", "SELL"}]

def test_daily_quota_original_list_denominator_is_not_redistributed(monkeypatch):
    original = minute.init_sim_state

    def seed(*args, **kwargs):
        state, pending, names = original(*args, **kwargs)
        state.positions[A] = [Position(A, 100, 10, 0, 10)]
        return state, pending, names

    monkeypatch.setattr(minute, "init_sim_state", seed)
    rows = {A: [bar(hm) for hm in TAIL_MINUTES], B: [bar(hm) for hm in TAIL_MINUTES]}
    state = simulate(rows, pool={D1: [A, B]}, strategy="version8_1", daily_quota=56_000)
    assert len(buys(state, A)) == 1 and buys(state, A)[0]["notional"] == 28_000
    assert sum(row["notional"] for row in buys(state, B)) == 28_000
    assert state.daily_quota_used == 56_000


@pytest.mark.parametrize("strategy", ["version8", "version8_2", "version8_3",
                                      "version8_4", "version8_5", "version8_6"])
def test_reappearing_code_opens_a_new_independent_tail_lot(strategy):
    rows = [bar(hm) for hm in TAIL_MINUTES]
    rows += [bar(hm, day=D2, price=9.95) for hm in TAIL_MINUTES]
    state = simulate({A: rows}, pool={D1: [A], D2: [A]}, end=D2, strategy=strategy,
                     name_budget=56_000 if strategy == "version8_3" else 28_000)
    fills = buys(state)
    assert len(fills) == 56
    assert {row["reason"] for row in fills} == {"pool:tail_window"}
    for date in (D1, D2):
        signal = [row for row in fills if row["date"] == date]
        assert [row["hm"] for row in signal] == list(TAIL_MINUTES)
        assert {row["position_id"] for row in signal} == {f"{A}@{date}"}
        assert {row["entry_signal_date"] for row in signal} == {date}
        assert {row["lot"] for row in signal} == {0}
        assert [row["shares"] for row in signal] == [100] * 28
    expected_lots = [(f"{A}@{D1}", 0, 2800), (f"{A}@{D2}", 1, 2800)]
    if strategy == "version8_6":
        # Its unmodified T+1 close-clear occurs after the new parent has begun.
        expected_lots = expected_lots[1:]
        sales = [row for row in state.trades if row["side"] == "SELL"]
        assert [(row["position_id"], row["reason"]) for row in sales] == [
            (f"{A}@{D1}", "force_sell:t1_close"),
        ]
    assert [(lot.position_id, lot.entry_idx, lot.shares) for lot in state.positions[A]] == expected_lots
    assert state.stats["skip_add_loser"] == 0


def test_old_position_exit_does_not_sell_or_interrupt_t0_reappearance_children():
    rows = [bar(hm, day=D0) for hm in TAIL_MINUTES]
    rows += [bar(hm, price=9.4 if hm == 880 else 10, open_px=10) for hm in TAIL_MINUTES]
    state = simulate({A: rows}, pool={D0: [A], D1: [A]}, start=D0, stop_pct=.05)
    sales = [row for row in state.trades if row["side"] == "SELL"]
    assert [(row["position_id"], row["shares"]) for row in sales] == [(f"{A}@{D0}", 2800)]
    today = [row for row in buys(state) if row["date"] == D1]
    assert [row["hm"] for row in today] == list(TAIL_MINUTES)
    lot, = state.positions[A]
    assert (lot.position_id, lot.shares, lot.entry_idx, lot.lot_id) == (f"{A}@{D1}", 2800, 1, 0)

def test_minimum_commission_applies_per_child_and_cash_is_never_negative():
    state = simulate({A: [bar(hm) for hm in TAIL_MINUTES]}, total_cash=28_140,
                     buy_cost_rate=.001, min_cost=5)
    assert [row["commission"] for row in buys(state)] == [5] * 28
    assert state.cash == 0


def test_tail_option_dependency_errors_precede_data_loading():
    with pytest.raises(ValueError, match="requires --fix-minute-cash-order"):
        minute.run(D1, D1, strategy="version8", tail_window_buy=True,
                   fix_minute_cash_order=False)


@pytest.mark.parametrize("unit", ["foo", "", "Shares"])
@pytest.mark.parametrize("entry", ["run", "simulate"])
def test_invalid_volume_units_raise_value_error_before_data_loading(unit, entry):
    with pytest.raises(ValueError, match="tail-volume-unit"):
        if entry == "run":
            minute.run(D1, D1, strategy="version8", tail_window_buy=True,
                       fix_minute_cash_order=True, tail_volume_unit=unit)
        else:
            simulate({A: [bar(hm) for hm in TAIL_MINUTES]}, tail_volume_unit=unit)


@pytest.mark.parametrize("unit", ["foo", "", "Shares"])
def test_cli_invalid_volume_unit_is_argparse_error(unit, capsys):
    with pytest.raises(SystemExit) as exc:
        minute.main(["--strategy", "version8", "--start", D1, "--end", D1,
                     "--tail-window-buy", "--fix-minute-cash-order", "--tail-volume-unit", unit])
    assert exc.value.code == 2
    assert "invalid choice" in capsys.readouterr().err


@pytest.mark.parametrize("strategy", ["version12", "version11", "version6"])
def test_unsupported_books_reject_on_before_data_loading(strategy):
    with pytest.raises(ValueError, match="applies only to version8"):
        minute.run(D1, D1, strategy=strategy, tail_window_buy=True,
                   fix_minute_cash_order=True, tail_volume_unit="shares")


@pytest.mark.parametrize("unit_options", [{}, {"tail_volume_unit": None}], ids=["omitted", "none"])
def test_run_default_volume_unit_equals_explicit_shares_with_metadata(synthetic_run, unit_options):
    options = {"strategy": "version8_2", "name_budget": 28_000,
               "tail_window_buy": True, "fix_minute_cash_order": True}
    actual = minute.run(D1, D1, **options, **unit_options)
    explicit = minute.run(D1, D1, **options, tail_volume_unit="shares")
    assert asdict(actual) == asdict(explicit)
    assert actual.run_metadata == explicit.run_metadata
    assert actual.run_metadata["tail_window_buy"]["tail_volume_unit"] == "shares"
    assert len(buys(actual)) == 28


def test_run_tail_loader_requests_volume_amount_and_outer_only_metadata(synthetic_run):
    state = minute.run(D1, D1, strategy="version8_2", name_budget=28_000,
                       tail_window_buy=True, tail_volume_unit="shares", fix_minute_cash_order=True)
    assert synthetic_run[0]["include_volume"] and synthetic_run[0]["include_amount"]
    assert state.run_metadata["tail_window_buy"]["tail_slice_count"] == 28
    assert not any(key.startswith("tail_") for key in state.stats)


def test_cli_default_volume_unit_matches_shares_results_and_manifest(
    monkeypatch, tmp_path, synthetic_run, capsys,
):
    captured = []

    def capture(out_dir, state, summary, help_lock, **kwargs):
        captured.append((asdict(state), state.run_metadata, summary, kwargs))

    monkeypatch.setattr(minute, "maybe_compare_daily", lambda *args, **kwargs: None)
    monkeypatch.setattr(minute, "write_run_artifacts", capture)
    argv = ["--strategy", "version8_2", "--start", D1, "--end", D1,
            "--name-budget", "28000", "--out-dir", str(tmp_path / "run"),
            "--tail-window-buy", "--fix-minute-cash-order"]
    assert minute.main(argv) == 0
    default_output = capsys.readouterr().out
    assert minute.main([*argv, "--tail-volume-unit", "shares"]) == 0
    assert capsys.readouterr().out == default_output
    assert captured[0] == captured[1]
    state, metadata, _, written = captured[0]
    assert sum(row["side"] == "BUY" for row in state["trades"]) == 28
    assert metadata["tail_window_buy"]["tail_volume_unit"] == "shares"
    assert written["emit_run_manifest"] is True
    assert written["manifest_config"]["tail_volume_unit"] == "shares"
    assert written["manifest_config"]["tail_window_buy"] == metadata["tail_window_buy"]


@pytest.mark.parametrize("fix_cash", [False, True])
def test_explicit_off_equals_omitted_for_both_cash_modes(fix_cash):
    minutes, daily = inputs({A: [bar(hm) for hm in TAIL_MINUTES]})
    kwargs = {"strategy": "version8", "total_cash": 1_000_000, "name_budget": 28_000,
              "fix_minute_cash_order": fix_cash}
    omitted = minute.simulate(minutes, daily, {D1: [A]}, D1, D1, **kwargs)
    off = minute.simulate(minutes, daily, {D1: [A]}, D1, D1, tail_window_buy=False, **kwargs)
    assert asdict(omitted) == asdict(off)


def test_0945_chase_keeps_original_quantity_and_clock(monkeypatch):
    original = minute.init_sim_state

    def seed(*args, **kwargs):
        state, pending, names = original(*args, **kwargs)
        pending[f"{A}@{D0}"] = (10_000, -1)
        return state, pending, names

    monkeypatch.setattr(minute, "init_sim_state", seed)
    rows = {A: [bar(570, price=9.9), bar(585)]}
    state = simulate(rows, pool={D1: []}, audit_sink=(trace := []))
    assert [(row["reason"], row["shares"]) for row in buys(state)] == [("chase:T+1", 1000)]
    assert [(row["hm"], row["side"]) for row in trace] == [(585, "BUY")]


def test_seeded_ration_at_each_minute_uses_original_full_list_order():
    from backtest.research.csv_simulate_loop import apply_capital_ration

    order = apply_capital_ration([A, B, C], ration="seeded_shuffle", ration_seed=7, ds=D1)
    rows = {code: [bar(hm) for hm in TAIL_MINUTES] for code in [A, B, C]}
    state = simulate(rows, pool={D1: [A, B, C]}, total_cash=84_000,
                     ration="seeded_shuffle", ration_seed=7)
    assert [row["code"] for row in state.trades if row["side"] == "BUY"] == order * 28


def test_duplicate_pool_name_cannot_repeat_1455_slice_or_volume_budget():
    simulate({A: [bar(hm, volume=1000) for hm in TAIL_MINUTES]},
             pool={D1: [A, A]}, audit_sink=(trace := []))
    assert [(row["hm"], row["shares"]) for row in trace if row["side"] == "BUY"] == [
        (hm, 100) for hm in TAIL_MINUTES]


@pytest.mark.parametrize("tail_enabled", [False, True])
@pytest.mark.parametrize("explicit_manifest", [False, True])
def test_main_tail_automatically_emits_existing_manifest_and_off_keeps_old_config(
    monkeypatch, tmp_path, tail_enabled, explicit_manifest,
):
    from backtest.research.csv_ledger import SimState
    from backtest.research.tail_window_buy import tail_policy

    state = SimState(cash=1_000_000)
    if tail_enabled:
        state.run_metadata = {"tail_window_buy": tail_policy("shares")}
    captured = []
    run_options = []

    def run(*args, **kwargs):
        run_options.append(kwargs)
        return state

    monkeypatch.setattr(minute, "run", run)
    monkeypatch.setattr(minute, "summarize", lambda *args, **kwargs: "summary")
    monkeypatch.setattr(minute, "maybe_compare_daily", lambda *args, **kwargs: None)
    monkeypatch.setattr(minute, "write_run_artifacts", lambda *args, **kwargs: captured.append(kwargs))
    argv = ["--strategy", "version8_2", "--start", D1, "--end", D1,
            "--out-dir", str(tmp_path / "run")]
    if tail_enabled:
        argv.extend(["--tail-window-buy", "--fix-minute-cash-order", "--tail-volume-unit", "shares"])
    if explicit_manifest:
        argv.append("--emit-run-manifest")
    assert minute.main(argv) == 0
    assert run_options[0]["tail_volume_unit"] == "shares"
    written = captured[0]
    assert written["emit_run_manifest"] == (tail_enabled or explicit_manifest)
    config = written["manifest_config"]
    if tail_enabled:
        assert config["tail_window_buy"] == tail_policy("shares")
        assert config["tail_volume_unit"] == "shares"
    elif explicit_manifest:
        assert "tail_window_buy" not in config and "tail_volume_unit" not in config
    else:
        assert config is None
    assert not any(key.startswith("tail_") for key in state.stats)
