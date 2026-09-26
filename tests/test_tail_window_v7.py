"""X-04 v7 trial slices: causal cash, merged trial lots, unchanged ladders."""

import json
from copy import deepcopy
from dataclasses import asdict
from datetime import date, timedelta

import pytest
from backtest.research import csv_minute_backtest_v7 as v7
from backtest.research.ashare_fees import FeeSchedule
from backtest.research.tail_window_buy import TAIL_MINUTES

A, B = "600000.SH", "000001.SZ"
D1 = date(2026, 9, 1)
D2 = D1 + timedelta(days=1)
ON = {"tail_window_buy": True, "fix_minute_cash_order": True, "tail_volume_unit": "shares"}


def bar(hm, price=10.0, *, day=D1, volume=1_000_000, opening=None, **extra):
    return {"date": day, "hm": hm, "open": price if opening is None else opening,
            "high": price, "low": price, "close": price, "volume": volume, **extra}


def run(rows, **kwargs):
    return v7.simulate_v7(
        {A: rows}, {A: {D1 - timedelta(days=1): 10, D1: 9.5}}, {D1: [A]}, [D1, D2],
        **{**ON, **kwargs},
    )


def buys(state, *, symbol=A):
    return [row for row in state.trades if row["side"] == "buy" and row["symbol"] == symbol]


def seed(monkeypatch, positions):
    result_type = v7.SimResult
    monkeypatch.setattr(v7, "SimResult", lambda cash: result_type(cash, positions=deepcopy(positions)))


def test_trial_28_equal_slices_merge_one_lot_and_discard_parent_rounding():
    state = run([bar(hm) for hm in range(870, 901)])
    fills = buys(state)
    assert [row["hm"] for row in fills] == list(TAIL_MINUTES)
    assert {row["shares"] for row in fills} == {700}
    assert state.positions[A].shares == 19_600
    assert len(state.positions[A].lots) == 1
    assert state.positions[A].lots[0] == v7.Lot(19_600, D1, 10, "trial")
    assert state.positions[A].entry_A == state.positions[A].avg_cost == 10
    assert state.cash == pytest.approx(21_000_000 - 196_000 * 1.001)


def test_incremental_volume_cap_tiny_zero_missing_and_auction_no_carry():
    rows = [bar(870, volume=3500), bar(871, volume=999), bar(872, volume=0),
            bar(874, volume=2000), bar(900, volume=2500), bar(870, day=D2)]
    state = run(rows)
    assert [(row["hm"], row["shares"]) for row in buys(state)] == [(870, 300), (874, 200), (900, 200)]
    assert state.positions[A].shares == 700
    assert all(row["date"] == D1.isoformat() for row in buys(state))


def test_amount_sets_minute_price_but_auction_uses_close_and_weighted_trial_cost():
    state = run([bar(870, opening=10, amount=9_800_000),
                 bar(871, 10.1), bar(900, 10.2, volume=1500, amount=1500)])
    fills = buys(state)
    assert [(row["price"], row["shares"]) for row in fills] == [(9.8, 700), (10.1, 700), (10.2, 100)]
    position = state.positions[A]
    assert position.entry_A == 9.8
    assert position.avg_cost == pytest.approx((9.8 * 700 + 10.1 * 700 + 10.2 * 100) / 1500)
    assert len(position.lots) == 1 and position.lots[0].price == position.avg_cost


def test_parent_target_uses_start_open_without_later_price_or_cash():
    state = run([bar(870, 10, opening=5), bar(875), bar(895, 10.9)], cash_total=1_000_000)
    assert [(row["hm"], row["shares"]) for row in buys(state) if row["reason"] == "buy:trial"] == [
        (870, 1400), (875, 1400), (895, 1400)]


@pytest.mark.parametrize("opening", [None, 0, float("nan"), float("inf")])
def test_missing_or_invalid_start_open_cancels_parent(opening):
    start = bar(870)
    if opening is None:
        start.pop("open")
    else:
        start["open"] = opening
    state = run([start, bar(895), bar(900)])
    assert buys(state) == []
    assert "skip_no_tail_start" in [row["reason"] for row in state.trades]


def test_missing_start_bar_never_backfills_from_1455():
    assert buys(run([bar(895), bar(900)])) == []


@pytest.mark.parametrize("rows", [
    [bar(870), bar(871)],
    [bar(870), bar(871), bar(900, volume=0)],
    [bar(870), bar(871), bar(900, volume=None)],
])
def test_missing_or_zero_auction_expires_without_redistribution(rows):
    assert [row["hm"] for row in buys(run(rows))] == [870, 871]


def test_bar_limit_rules_rechecked_each_child():
    state = run([bar(870, 11, opening=10), bar(871, 10), bar(872, 9), bar(900, 11)])
    assert [row["hm"] for row in buys(state)] == [871]
    assert sum(row["reason"] == "skip_limit_up" for row in state.trades) == 2


def test_future_sell_cash_unavailable_until_1440_and_same_minute_sell_first(monkeypatch):
    seed(monkeypatch, {A: v7.Position(A, 10, lots=[v7.Lot(30_000, D1 - timedelta(days=1), 10, "trial")],
                                    avg_cost=10, last_add_date=D1 - timedelta(days=1))})
    audit = []
    state = v7.simulate_v7(
        {B: [bar(hm) for hm in TAIL_MINUTES], A: [bar(870), bar(880, 9)]},
        {A: {D1 - timedelta(days=1): 9.5}, B: {D1 - timedelta(days=1): 10}},
        {D1: [B]}, [D1], cash_total=0, audit_sink=audit, **ON,
    )
    fills = buys(state, symbol=B)
    assert [row["hm"] for row in fills] == list(range(880, 897)) + [900]
    assert sum(row["shares"] for row in fills) == 12_600
    same = [row for row in audit if row["hm"] == 880 and row["side"] in ("sell", "buy")]
    assert [(row["symbol"], row["side"]) for row in same] == [(A, "sell"), (B, "buy")]
    assert same[1]["cash_before"] == pytest.approx(269_730)
    assert all(row["cash_after"] >= 0 for row in audit)


def test_same_minute_cash_competition_retains_pool_order():
    def compete(order):
        return v7.simulate_v7(
            {symbol: [bar(870)] for symbol in (A, B)},
            {symbol: {D1 - timedelta(days=1): 10} for symbol in (A, B)},
            {D1: order}, [D1], cash_total=7007, **ON,
        )
    assert set(compete([A, B]).positions) == {A}
    assert set(compete([B, A]).positions) == {B}


def test_current_cash_partial_lots_and_each_child_minimum_fee():
    fee = FeeSchedule(0, 0, 5)
    state = run([bar(870), bar(871), bar(872)], fee=fee, cash_total=14_010)
    assert [row["shares"] for row in buys(state)] == [700, 700]
    assert state.cash == 0
    partial = run([bar(870), bar(871)], fee=fee, cash_total=6505)
    assert [row["shares"] for row in buys(partial)] == [600]
    assert partial.cash == 500


def test_building_trial_is_visible_to_unchanged_same_day_ladder():
    state = run([bar(870), bar(884, 10.4), bar(885, 10.4), bar(886, 10.8), bar(896, 10.9)])
    adds = [row for row in buys(state) if row["reason"].startswith("buy:add")]
    assert [(row["hm"], row["reason"]) for row in adds] == [(885, "buy:add_a104"), (886, "buy:add_a108")]
    assert state.positions[A].stage == v7.SIX
    assert state.positions[A].entry_A == 10
    assert len([lot for lot in state.positions[A].lots if lot.kind == "trial"]) == 1
    assert len(state.positions[A].lots) == 3


def test_first_fill_during_ladder_window_exposes_current_vwap_entry():
    state = run([bar(870, volume=0), bar(885, 10.4, amount=9_900_000)])
    assert [(row["hm"], row["reason"]) for row in buys(state)] == [
        (885, "buy:trial"), (885, "buy:add_a104")]
    assert state.positions[A].entry_A == 9.9
    assert state.positions[A].stage == v7.FOUR
    assert state.positions[A].peak >= 9.9


def test_preexisting_position_keeps_original_ladder_actions(monkeypatch):
    initial = v7.Position(A, 10, lots=[v7.Lot(20_000, D1 - timedelta(days=1), 10, "trial")],
                          avg_cost=10, last_add_date=D1 - timedelta(days=1))
    seed(monkeypatch, {A: initial})
    rows = [bar(870), bar(884, 10.4), bar(885, 10.4), bar(886, 10.8), bar(896, 10.9)]
    on = run(rows)
    off = run(rows, tail_window_buy=False)
    assert asdict(on) == asdict(off)


def test_all_new_trial_slices_t_plus_one_then_sell_once_next_day():
    state = run([bar(870), bar(871), bar(896, 9), bar(900, 9), bar(570, 8.9, day=D2)])
    sells = [row for row in state.trades if row["side"] == "sell"]
    assert [(row["date"], row["shares"]) for row in sells] == [(D2.isoformat(), 1400)]
    assert state.positions == {}


@pytest.mark.parametrize("cash_order", [False, True])
def test_off_and_omitted_match_entire_state_and_writer(tmp_path, cash_order):
    args = {"minute_bars": {A: [bar(895)]}, "daily_bars": {A: {D1 - timedelta(days=1): 10}},
                "pool_days": {D1: [A]}, "index_days": [D1], "fix_minute_cash_order": cash_order}
    omitted = v7.simulate_v7(**args)
    explicit = v7.simulate_v7(**args, tail_window_buy=False)
    assert asdict(omitted) == asdict(explicit)
    v7.write_run_artifacts(omitted, tmp_path / "omitted")
    v7.write_run_artifacts(explicit, tmp_path / "explicit")
    for filename in ("summary.txt", "trades.csv", "daily_equity.csv"):
        assert (tmp_path / "omitted" / filename).read_bytes() == (tmp_path / "explicit" / filename).read_bytes()


def test_switch_errors_precede_data_access():
    with pytest.raises(ValueError, match="fix-minute-cash-order"):
        v7.simulate_v7(None, None, None, tail_window_buy=True)
    argv = ["--start", "20260901", "--end", "20260901", "--tail-window-buy"]
    with pytest.raises(SystemExit, match="fix-minute-cash-order"):
        v7.main(argv)
    with pytest.raises(SystemExit, match="minute-source lake"):
        v7.main([*argv, "--fix-minute-cash-order", "--minute-source", "qlib_1min"])
    with pytest.raises(SystemExit, match="daily-source lake"):
        v7.main([*argv, "--fix-minute-cash-order", "--daily-source", "qlib_day"])


@pytest.mark.parametrize("unit_kwargs", [{}, {"tail_volume_unit": None}], ids=["omitted", "none"])
def test_on_default_volume_unit_matches_explicit_shares(unit_kwargs):
    args = {"minute_bars": {A: [bar(hm, volume=3500, amount=35_000) for hm in TAIL_MINUTES]},
            "daily_bars": {A: {D1 - timedelta(days=1): 10}},
            "pool_days": {D1: [A]}, "index_days": [D1],
            "tail_window_buy": True, "fix_minute_cash_order": True}
    default_audit, shares_audit = [], []
    default = v7.simulate_v7(**args, **unit_kwargs, audit_sink=default_audit)
    shares = v7.simulate_v7(**args, tail_volume_unit="shares", audit_sink=shares_audit)
    assert buys(default)
    assert asdict(default) == asdict(shares)
    assert default_audit == shares_audit


@pytest.mark.parametrize("unit", ["foo", "", "Shares"])
def test_invalid_volume_unit_errors_before_data_access(unit, capsys):
    with pytest.raises(ValueError, match="tail-volume-unit"):
        v7.simulate_v7(None, None, None, tail_window_buy=True,
                       fix_minute_cash_order=True, tail_volume_unit=unit)
    with pytest.raises(SystemExit) as exc:
        v7.main(["--start", "20260901", "--end", "20260901", "--tail-window-buy",
                 "--fix-minute-cash-order", "--tail-volume-unit", unit])
    assert exc.value.code == 2
    assert "--tail-volume-unit: invalid choice" in capsys.readouterr().err


def test_volume_lots_require_explicit_conversion():
    shares = run([bar(870, volume=3500, amount=35_000)])
    lots = run([bar(870, volume=35, amount=35_000)], tail_volume_unit="lots")
    assert asdict(shares) == asdict(lots)


def test_duplicate_minute_cannot_retry_or_double_its_equal_share():
    state = run([bar(870), bar(871), bar(871), bar(872)])
    assert [(row["hm"], row["shares"]) for row in buys(state)] == [(870, 700), (872, 700)]
    assert "skip_duplicate_tail_bar" in [row["reason"] for row in state.trades]
    duplicate_start = run([bar(870), bar(870), bar(871), bar(900)])
    assert buys(duplicate_start) == []
    assert "skip_duplicate_tail_start" in [row["reason"] for row in duplicate_start.trades]


def test_cli_default_off_keeps_run_config_and_on_records_policy(tmp_path):
    argv = ["--start", "20260901", "--end", "20260901", "--pool-dir", str(tmp_path)]
    parsed = v7.build_parser().parse_args(argv)
    assert parsed.tail_window_buy is False and parsed.tail_volume_unit == "shares"
    off_dir, on_dir = tmp_path / "off", tmp_path / "on"
    assert v7.main([*argv, "--output-dir", str(off_dir)]) == 0
    off_config = json.loads((off_dir / "run-config.json").read_text())
    assert not any(key.startswith("tail_") for key in off_config)
    assert v7.main([*argv, "--output-dir", str(on_dir), "--tail-window-buy",
                   "--fix-minute-cash-order"]) == 0
    config = json.loads((on_dir / "run-config.json").read_text())
    assert config["tail_window_buy"] is True and config["tail_slice_count"] == 28
    assert config["tail_parent_clock"] == "14:30_open_exact"
    assert config["tail_volume_unit"] == "shares"


def test_cli_on_default_volume_unit_matches_explicit_shares(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(v7, "load_pool_days", lambda *args: {D1: [A]})
    monkeypatch.setattr(v7, "_load_cli_bars", lambda *args, **kwargs: (
        {A: [bar(hm, volume=3500, amount=35_000) for hm in TAIL_MINUTES]},
        {A: {D1 - timedelta(days=1): 10}},
    ))
    monkeypatch.setattr(v7, "load_limit_context", lambda *args: ({}, {}))
    monkeypatch.setattr(v7, "load_index_daily", lambda *args: [D1])
    monkeypatch.setattr(v7.time, "perf_counter", lambda: 0.0)
    output = tmp_path / "run"
    argv = ["--start", "20260901", "--end", "20260901", "--pool-dir", str(tmp_path),
            "--output-dir", str(output), "--execution-audit-file", str(output / "audit.json"),
            "--tail-window-buy", "--fix-minute-cash-order"]
    assert v7.main(argv) == 0
    default_stdout = capsys.readouterr().out
    default_files = {path.name: path.read_bytes() for path in output.iterdir()}
    config = json.loads(default_files["run-config.json"])
    assert config["tail_volume_unit"] == "shares"
    assert config["tail_window_buy"] is True
    assert len(default_files["trades.csv"].splitlines()) == len(TAIL_MINUTES) + 1
    assert v7.main([*argv, "--tail-volume-unit", "shares"]) == 0
    assert capsys.readouterr().out == default_stdout
    assert {path.name: path.read_bytes() for path in output.iterdir()} == default_files


def test_cli_tail_loads_volume_amount_directly_and_keeps_raw_units(monkeypatch):
    from backtest.research import ashare_bars

    calls = []
    frame = {A: [bar(870, volume=35, amount=35_000)]}

    def load_minutes(symbols, start, end, **kwargs):
        calls.append((set(symbols), start, end, kwargs))
        return frame

    monkeypatch.setattr(ashare_bars, "load_minute_from_lake", load_minutes)
    monkeypatch.setattr(ashare_bars, "load_daily_closes", lambda *args, **kwargs: {})
    minute, daily = v7._load_cli_bars({D1: [A]}, D1, D1, tail_window_buy=True)
    assert minute is frame and daily == {}
    assert calls == [({A}, "20260901", "20260901", {"include_volume": True, "include_amount": True})]
