"""X-02 v7 causal clock: actual proceeds, stable ties and post-buy timers."""

import json
from copy import deepcopy
from dataclasses import asdict
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

import pandas as pd
import pytest
from backtest.research import csv_minute_backtest_v7 as v7
from backtest.research.ashare_bars import annotate_session
from backtest.research.ashare_volume_cap import BucketVolume

A, B = "600000.SH", "000001.SZ"
D1, D2 = date(2026, 9, 1), date(2026, 9, 2)


def fen(value):
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def bar(day, hm, close, opening=None):
    opening = close if opening is None else opening
    return {"date": day, "hm": hm, "open": opening, "close": close,
            "high": max(opening, close), "low": min(opening, close)}


def v7_cross_symbol_case(*, sell_hm=900, buy_hm=885, reverse=False):
    """Frozen public-input A/B example, also consumed by the report script.

    Cash after two trials is 20,600; A's later stop releases 179,820, while
    B's earlier add needs 199,879.68. Default NAME_BUDGET and default fees.
    """
    symbols = [B, A] if reverse else [A, B]
    rows = {
        A: [bar(D1, 895, 10), bar(D2, 570, 10), bar(D2, sell_hm, 9, 10)],
        B: [bar(D1, 895, 10), bar(D2, buy_hm, 10.4), bar(D2, 900, 10.4)],
    }
    return {
        "minute_bars": {symbol: rows[symbol] for symbol in symbols},
        "daily_bars": {A: {D1 - timedelta(days=1): 10, D1: 9.5},
                    B: {D1 - timedelta(days=1): 10, D1: 10}},
        "pool_days": {D1: symbols}, "index_days": [D1, D2], "cash_total": 421_000,
    }


def chronological_case():
    """Public fixture entry for the independent X-02 A/B report."""
    return v7_cross_symbol_case()


def fills(state, side=None):
    return [row for row in state.trades if row["side"] in ("buy", "sell")
            and (side is None or row["side"] == side)]


def test_future_1500_stop_cannot_finance_1445_add_and_audit_is_real():
    off_rows, on_rows = [], []
    off = v7.simulate_v7(**v7_cross_symbol_case(), audit_sink=off_rows)
    on = v7.simulate_v7(**v7_cross_symbol_case(), fix_minute_cash_order=True, audit_sink=on_rows)
    assert fen(off.cash) == Decimal("540.32")
    assert fen(on.cash) == Decimal("200420.00")
    assert len(fills(off, "buy")) == 3 and len(fills(on, "buy")) == 2
    assert on.positions[B].shares == 20_000
    assert off.positions[B].shares == 39_200
    assert [(r["hm"], r["side"]) for r in off_rows if r["date"] == D2.isoformat()] == [
        (900, "sell"), (885, "buy")]
    assert [(r["hm"], r["side"]) for r in on_rows if r["date"] == D2.isoformat()] == [
        (885, "skip"), (900, "sell")]
    for row in on_rows:
        assert row["hm"] == row["decision_hm"] == row["quote_hm"]
        assert row["phase"] == "close"
        assert fen(row["cash_before"]) >= 0 and fen(row["cash_after"]) >= 0
        notional = row["shares"] * row["price"]
        if row["side"] == "buy":
            assert fen(row["cash_before"] - row["cash_after"]) == fen(notional + row["commission"])
        elif row["side"] == "sell":
            assert fen(row["cash_after"] - row["cash_before"]) == fen(notional - row["commission"])
    sell = next(row for row in on_rows if row["side"] == "sell")
    assert fen(sell["cash_after"] - sell["cash_before"]) == Decimal("179820.00")


def test_cross_hm_economics_do_not_depend_on_input_symbol_order():
    left = v7.simulate_v7(**v7_cross_symbol_case(), fix_minute_cash_order=True)
    right = v7.simulate_v7(**v7_cross_symbol_case(reverse=True), fix_minute_cash_order=True)
    assert fen(left.cash) == fen(right.cash)
    assert {key: asdict(value) for key, value in left.positions.items()} == {
        key: asdict(value) for key, value in right.positions.items()}
    assert left.equity_curve == right.equity_curve
    assert sorted((r["date"], r["hm"], r["symbol"], r["side"], r["shares"])
                  for r in left.trades) == sorted(
        (r["date"], r["hm"], r["symbol"], r["side"], r["shares"]) for r in right.trades)


@pytest.mark.parametrize("sell_hm,bought", [(884, True), (885, True), (886, False)])
def test_close_sell_boundary_and_b11_same_close_can_finance_add(sell_hm, bought):
    rows = []
    state = v7.simulate_v7(**v7_cross_symbol_case(sell_hm=sell_hm, reverse=True),
                           fix_minute_cash_order=True, audit_sink=rows)
    assert any(row["reason"] == "buy:add_a104" for row in fills(state)) is bought
    if sell_hm == 885:
        same = [r for r in rows if r["date"] == D2.isoformat() and r["hm"] == 885]
        assert [(r["side"], r["phase"]) for r in same] == [("sell", "close"), ("buy", "close")]
        assert fen(same[1]["cash_before"]) == Decimal("200420.00")


@pytest.mark.parametrize("volume", [None, 0, 10_000, 20_000])
def test_only_actual_net_proceeds_from_close_sell_are_spendable(volume):
    case = v7_cross_symbol_case(sell_hm=885)
    volumes = {(symbol, "20260901", 895): BucketVolume(20_000, 895, "raw_shares_incremental")
               for symbol in (A, B)}
    volumes[(B, "20260902", 885)] = BucketVolume(20_000, 885, "raw_shares_incremental")
    if volume is not None:
        volumes[(A, "20260902", 885)] = BucketVolume(volume, 885, "raw_shares_incremental")
    rows = []
    state = v7.simulate_v7(**case, fix_minute_cash_order=True, participation_rate=1,
                           volume_for_bucket=volumes, audit_sink=rows)
    sold = sum(r["shares"] for r in fills(state, "sell"))
    assert sold == (volume or 0)
    bought = any(r["reason"] == "buy:add_a104" for r in fills(state))
    assert bought is (volume == 20_000)
    assert sum(pos.shares for pos in state.positions.values()) == 40_000 - sold + (19_200 if bought else 0)
    expected = 20_600 + v7.DEFAULT_SCHEDULE.credit_sell(sold * 9)
    if bought:
        expected -= v7.DEFAULT_SCHEDULE.debit_buy(19_200 * 10.4)
    assert fen(state.cash) == fen(expected)
    assert all(fen(r["cash_after"]) >= 0 for r in rows)


def test_limit_down_defer_does_not_create_cash():
    case = v7_cross_symbol_case(sell_hm=885)
    case["daily_bars"][A][D1] = 10
    state = v7.simulate_v7(**case, fix_minute_cash_order=True)
    assert not fills(state, "sell")
    assert fen(state.cash) == Decimal("20600.00")
    assert state.positions[A].shares == state.positions[B].shares == 20_000
    assert [r["reason"] for r in state.trades][-2:] == ["defer_limit_down", "skip_cash"]


def _seed(monkeypatch, positions):
    result_type = v7.SimResult
    monkeypatch.setattr(v7, "SimResult", lambda cash: result_type(cash, positions=deepcopy(positions)))


def _position(symbol, *, shares=20_000, stage=v7.TRIAL, anchor=D1):
    return v7.Position(symbol, 10, stage=stage, lots=[v7.Lot(shares, D1, 10, "trial")],
                       avg_cost=10, peak=10, last_add_date=anchor)


@pytest.mark.parametrize("cash,bought", [(200_000, True), (0, False)])
def test_last_bar_timer_observes_buy_then_never_retries_failed_buy(monkeypatch, cash, bought):
    calendar = [D1 + timedelta(days=n) for n in range(11)]
    timer_day = calendar[-1]
    _seed(monkeypatch, {A: _position(A)})
    rows = []
    state = v7.simulate_v7(
        {A: [bar(timer_day, 895, 10.4)]}, {A: {timer_day - timedelta(days=1): 10}}, {}, calendar,
        cash_total=cash, fix_minute_cash_order=True, audit_sink=rows,
    )
    if bought:
        assert [r["reason"] for r in state.trades] == ["buy:add_a104"]
        assert state.positions[A].last_add_date == timer_day
        assert state.positions[A].stage == v7.FOUR
        assert state.positions[A].shares == 39_200
    else:
        assert [r["reason"] for r in state.trades] == ["skip_cash", "exit:timer10"]
        assert fen(state.cash) == Decimal("207792.00")
        assert state.positions == {}
        assert [(r["side"], r["hm"]) for r in rows] == [("skip", 895), ("sell", 895)]


def test_same_hm_other_stock_timer_also_follows_all_buy_attempts(monkeypatch):
    calendar = [D1 + timedelta(days=n) for n in range(11)]
    timer_day = calendar[-1]
    _seed(monkeypatch, {A: _position(A), B: _position(B, anchor=D2)})
    rows = []
    state = v7.simulate_v7(
        {A: [bar(timer_day, 895, 10)], B: [bar(timer_day, 895, 10.4)]},
        {symbol: {timer_day - timedelta(days=1): 10} for symbol in (A, B)}, {}, calendar,
        cash_total=0, fix_minute_cash_order=True, audit_sink=rows,
    )
    assert [(r["symbol"], r["reason"]) for r in rows] == [(B, "skip_cash"), (A, "exit:timer10")]
    assert state.positions[B].shares == 20_000 and A not in state.positions


def test_open_stop_volume_reject_is_not_retried_at_close_same_bar(monkeypatch):
    _seed(monkeypatch, {A: _position(A)})
    volumes = {(A, "20260902", 570): BucketVolume(10_000, 570, "raw_shares_incremental")}
    rows = []
    state = v7.simulate_v7(
        {A: [bar(D2, 570, 8.9, 9)]}, {A: {D1: 9.5}}, {}, [D1, D2], cash_total=0,
        participation_rate=1, volume_for_bucket=volumes, fix_minute_cash_order=True, audit_sink=rows,
    )
    assert [(r["phase"], r["shares"], r["price"]) for r in rows] == [("open", 0, 9)]
    assert rows[0]["reason"] == "skip_volume_unavailable:bucket_not_completed"
    assert state.positions[A].shares == 20_000 and state.positions[A].peak == 10


def test_same_hm_cash_competition_keeps_original_pool_order():
    for symbols in ([A, B], [B, A]):
        state = v7.simulate_v7(
            {symbol: [bar(D1, 895, 10)] for symbol in (A, B)},
            {symbol: {D1 - timedelta(days=1): 10} for symbol in (A, B)},
            {D1: symbols}, [D1], cash_total=200_200, fix_minute_cash_order=True,
        )
        assert list(state.positions) == [symbols[0]]
        assert fen(state.cash) == Decimal("0.00")


def test_lunch_rows_match_production_filter_and_never_emit_events(monkeypatch):
    _seed(monkeypatch, {A: _position(A)})
    hms = [570, 600, 690, 691, 720, 780, 900]
    frame = pd.DataFrame({"open": [10, 10, 10, 8.9, 8.9, 10, 10],
                          "close": [10, 10, 10, 8.9, 8.9, 10, 10]},
                         index=pd.DatetimeIndex([pd.Timestamp(D2) + pd.Timedelta(minutes=hm) for hm in hms]))
    filtered = annotate_session(frame)
    assert filtered.hm.tolist() == [570, 600, 690, 780, 900]
    raw = frame.assign(hm=hms, ymd=D2.strftime("%Y%m%d"))
    rows = []
    unfiltered = v7.simulate_v7({A: raw}, {A: {D1: 9.5}}, {}, [D1, D2],
                                fix_minute_cash_order=True, audit_sink=rows)
    reference = v7.simulate_v7({A: filtered}, {A: {D1: 9.5}}, {}, [D1, D2],
                               fix_minute_cash_order=True)
    assert asdict(unfiltered) == asdict(reference)
    assert rows == [] and unfiltered.positions[A].shares == 20_000


def test_omitted_and_explicit_off_state_and_writer_bytes_match(tmp_path):
    implicit = v7.simulate_v7(**v7_cross_symbol_case())
    explicit = v7.simulate_v7(**v7_cross_symbol_case(), fix_minute_cash_order=False)
    assert asdict(implicit) == asdict(explicit)
    v7.write_run_artifacts(implicit, tmp_path / "implicit")
    v7.write_run_artifacts(explicit, tmp_path / "explicit")
    for name in ("trades.csv", "daily_equity.csv"):
        assert (tmp_path / "implicit" / name).read_bytes() == (tmp_path / "explicit" / name).read_bytes()


def test_single_symbol_ample_cash_keeps_legacy_trade_tuples_and_state():
    case = v7_cross_symbol_case()
    case["minute_bars"] = {B: case["minute_bars"][B]}
    case["pool_days"] = {D1: [B]}
    case["cash_total"] = 1_000_000
    off = v7.simulate_v7(**case)
    on = v7.simulate_v7(**case, fix_minute_cash_order=True)
    assert asdict(off) == asdict(on)


def test_cli_flag_defaults_off_and_records_independent_run_config(tmp_path):
    argv = ["--start", "20260901", "--end", "20260901", "--pool-dir", str(tmp_path)]
    assert v7.build_parser().parse_args(argv).fix_minute_cash_order is False
    output = tmp_path / "out"
    assert v7.main([*argv, "--output-dir", str(output), "--fix-minute-cash-order"]) == 0
    config = json.loads((output / "run-config.json").read_text())
    assert config["fix_minute_cash_order"] is True
    assert config["same_hm_policy"] == "open_stop_then_close_stop_then_buy_then_timer"
