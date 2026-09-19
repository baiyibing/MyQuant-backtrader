# -*- coding: utf-8 -*-
from datetime import date, timedelta
from dataclasses import asdict

import pytest

import backtest.research.csv_minute_backtest_v7 as v7
from backtest.research.ashare_session import session_limit_prices, session_prev_close
from backtest.research.ashare_session import flatten_pool_names
from backtest.research.csv_minute_backtest_v7 import (
    _as_date,
    _as_datetime,
    load_pool_days,
    main,
    simulate_v7,
)


SYMBOL = "600000.SH"
D1 = date(2026, 9, 1)
D2 = date(2026, 9, 2)
D3 = date(2026, 9, 3)


def test_load_pool_days_adds_exchange_suffix(tmp_path):
    p = tmp_path / "20260804.csv"
    p.write_text("000739,普洛药业\n600326,西藏天路\n", encoding="utf-8", newline="\n")
    days = load_pool_days(tmp_path, date(2026, 8, 4), date(2026, 8, 4))
    assert days[date(2026, 8, 4)] == ["000739.SZ", "600326.SH"]


def test_as_date_reads_lake_utc_millis_and_yyyymmdd():
    assert _as_date(661564800000) == date(1990, 12, 19)
    assert _as_date(1735810200000) == date(2025, 1, 2)
    assert _as_datetime(1735810200000).hour == 9
    assert _as_datetime(1735810200000).minute == 30
    assert _as_date(20260804) == date(2026, 8, 4)
    assert _as_date("2026-08-04") == date(2026, 8, 4)


def bar(day, hm, close, open=None):
    return {
        "date": day,
        "hm": hm,
        "open": close if open is None else open,
        "high": max(close, close if open is None else open),
        "low": min(close, close if open is None else open),
        "close": close,
    }


def reasons(state):
    return [trade["reason"] for trade in state.trades]


def daily():
    return {SYMBOL: {date(2026, 8, 31): 100.0, D1: 100.0}}


def index_closes(values):
    first = date(2026, 8, 17)
    return {
        first + timedelta(days=offset): value for offset, value in enumerate(values)
    }


def test_symbol_frame_path_buys_at_1455():
    import pandas as pd

    idx = pd.DatetimeIndex([pd.Timestamp("2026-09-01 14:55:00")])
    frame = pd.DataFrame(
        {
            "open": [100.0],
            "high": [100.0],
            "low": [100.0],
            "close": [100.0],
            "ymd": ["20260901"],
            "hm": [895],
        },
        index=idx,
    )
    state = simulate_v7({SYMBOL: frame}, daily(), {D1: [SYMBOL]}, [D1])
    assert reasons(state).count("buy:trial") == 1


def test_7_trial_bought_at_1455_cannot_stop_same_day_but_can_next_day():
    minutes = {SYMBOL: [bar(D1, 895, 100), bar(D1, 896, 89), bar(D2, 570, 89)]}
    path_daily = {SYMBOL: {date(2026, 8, 31): 100.0, D1: 98.0}}
    state = simulate_v7(minutes, path_daily, {D1: [SYMBOL]}, [D1, D2])
    assert reasons(state).count("buy:trial") == 1
    assert reasons(state).count("stop:trial_a090") == 1
    sell = next(t for t in state.trades if t["reason"] == "stop:trial_a090")
    assert sell["date"] == D2.isoformat()


def test_8_four_clears_on_avg095_add_only_in_1445_1455():
    morning = simulate_v7(
        {SYMBOL: [bar(D1, 895, 100), bar(D2, 570, 104)]},
        daily(), {D1: [SYMBOL]}, [D1, D2],
    )
    assert "buy:add_a104" not in reasons(morning)
    assert morning.positions[SYMBOL].stage == "trial"

    minutes = {SYMBOL: [bar(D1, 895, 100), bar(D2, 885, 104), bar(D3, 570, 96)]}
    state = simulate_v7(minutes, daily(), {D1: [SYMBOL]}, [D1, D2, D3])
    assert "buy:add_a104" in reasons(state)
    assert "stop:four_avg095" in reasons(state)
    assert state.positions == {}

    after_window = simulate_v7(
        {SYMBOL: [bar(D1, 895, 100), bar(D1, 896, 104)]},
        daily(), {D1: [SYMBOL]}, [D1],
    )
    assert "buy:add_a104" not in reasons(after_window)
    assert after_window.positions[SYMBOL].stage == "trial"


def test_8_ladder_reaches_full_then_avg098_clears():
    minutes = {SYMBOL: [
        bar(D1, 895, 100),
        bar(D2, 885, 104),
        bar(D2, 888, 108),
        bar(D2, 891, 112),
        bar(D2, 895, 116),
        bar(D3, 570, 105),
    ]}
    path_daily = {SYMBOL: {date(2026, 8, 31): 100.0, D1: 110.0, D2: 108.0}}
    state = simulate_v7(minutes, path_daily, {D1: [SYMBOL]}, [D1, D2, D3])
    assert reasons(state) == [
        "buy:trial",
        "buy:add_a104",
        "buy:add_a108",
        "buy:add_a112",
        "buy:add_a116",
        "stop:full_avg098",
    ]
    assert state.positions == {}


def test_9_exact_1455_limit_up_and_open_limit_down_rules():
    missing = simulate_v7({SYMBOL: [bar(D1, 894, 100)]}, daily(), {D1: [SYMBOL]}, [D1])
    assert "buy:trial" not in reasons(missing)
    assert "skip_no_1455" in reasons(missing)

    limit_up = simulate_v7({SYMBOL: [bar(D1, 895, 110)]}, daily(), {D1: [SYMBOL]}, [D1])
    assert "skip_limit_up" in reasons(limit_up)
    assert "buy:trial" not in reasons(limit_up)

    stopped = simulate_v7(
        {SYMBOL: [bar(D1, 895, 100), bar(D2, 570, 90, open=90)]},
        daily(),
        {D1: [SYMBOL]},
        [D1, D2],
    )
    assert "defer_limit_down" in reasons(stopped)
    assert "stop:trial_a090" not in reasons(stopped)
    assert stopped.positions[SYMBOL].shares > 0


def test_10_index_gate_blocks_new_open_but_does_not_freeze_existing_stop():
    index = index_closes([100.0] * 9 + [90.0, 89.0, 88.0, 87.0])
    gate_day = sorted(index)[11]
    stock_daily = {SYMBOL: {gate_day - timedelta(days=1): 100.0, gate_day: 100.0}}

    blocked = simulate_v7(
        {SYMBOL: [bar(gate_day, 895, 100)]},
        stock_daily,
        {gate_day: [SYMBOL]},
        index,
        start=gate_day,
        end=gate_day,
    )
    assert "buy:trial" not in reasons(blocked)
    assert "skip_index_gate" in reasons(blocked)

    # Seed on the recovery-output session by keeping its preceding closes healthy,
    # then make the following gate output blocked while the held lot remains sellable.
    held_index = index_closes([100.0] * 10 + [101.0, 90.0, 89.0, 88.0])
    open_day, stop_day = sorted(held_index)[11], sorted(held_index)[13]
    stock_daily = {SYMBOL: {open_day - timedelta(days=1): 100.0, open_day: 98.0}}
    stopped = simulate_v7(
        {SYMBOL: [bar(open_day, 895, 100), bar(stop_day, 570, 89)]},
        stock_daily, {open_day: [SYMBOL]}, held_index, start=open_day, end=stop_day,
    )
    assert "buy:trial" in reasons(stopped)
    assert "stop:trial_a090" in reasons(stopped)


def test_10_timer_exit_locks_same_day_reopen_and_short_index_fails():
    index = index_closes([100.0] * 22)
    sessions = sorted(index)[11:]
    open_day, timer_day = sessions[0], sessions[10]
    stock_daily = {SYMBOL: {open_day - timedelta(days=1): 100.0, open_day: 100.0,
                            timer_day - timedelta(days=1): 100.0}}
    state = simulate_v7(
        {SYMBOL: [bar(open_day, 895, 100), bar(timer_day, 570, 100),
                  bar(timer_day, 895, 100), bar(timer_day, 900, 101)]},
        stock_daily, {open_day: [SYMBOL], timer_day: [SYMBOL]}, index,
        start=open_day, end=timer_day,
    )
    assert reasons(state).count("exit:timer10") == 1
    assert reasons(state).count("buy:trial") == 1
    timer = next(t for t in state.trades if t["reason"] == "exit:timer10")
    assert timer["hm"] == 900
    assert timer["price"] == 101
    assert state.positions == {}

    with pytest.raises(ValueError, match="11 warmup"):
        simulate_v7({}, {}, {}, index_closes([100.0] * 11))


def test_cli_empty_pool_is_legal_and_missing_pool_is_system_exit(tmp_path, monkeypatch):
    out = tmp_path / "out"
    assert (
        main(
            [
                "--start",
                "20260901",
                "--end",
                "20260902",
                "--pool-dir",
                str(tmp_path),
                "--output-dir",
                str(out),
            ]
        )
        == 0
    )
    assert (out / "summary.txt").read_text(encoding="utf-8").find("trades=0") >= 0
    assert {path.name for path in out.iterdir()} == {
        "summary.txt",
        "daily_equity.csv",
        "trades.csv",
    }

    monkeypatch.delenv("OSKH_TURTLE_POOL_DIR", raising=False)
    with pytest.raises(SystemExit):
        main(["--start", "20260901", "--end", "20260902"])


def test_exdiv_maps_official_prev_close_for_limit_up():
    minutes = {SYMBOL: [bar(D1, 895, 10.45)]}
    path_daily = {SYMBOL: {date(2026, 8, 31): 10.0}}
    mapped = simulate_v7(
        minutes, path_daily, {D1: [SYMBOL]}, [D1],
        exdiv={SYMBOL: {D1.strftime("%Y%m%d"): 0.95}},
    )
    assert "skip_limit_up" in reasons(mapped)
    assert "buy:trial" not in reasons(mapped)
    raw = simulate_v7(minutes, path_daily, {D1: [SYMBOL]}, [D1])
    assert "buy:trial" in reasons(raw)


def test_st_name_uses_five_percent_limit():
    minutes = {SYMBOL: [bar(D1, 895, 105)]}
    path_daily = {SYMBOL: {date(2026, 8, 31): 100.0}}
    st = simulate_v7(minutes, path_daily, {D1: [SYMBOL]}, [D1], names={SYMBOL: "*ST甲"})
    assert "skip_limit_up" in reasons(st)
    board = simulate_v7(minutes, path_daily, {D1: [SYMBOL]}, [D1])
    assert "buy:trial" in reasons(board)


def test_first_entry_unknown_board_rejects_trial_buy():
    code = "999999.SZ"
    state = simulate_v7(
        {code: [bar(D1, 895, 100)]},
        {code: {date(2026, 8, 31): 100.0}},
        {D1: [code]},
        [D1],
    )
    assert "skip_unknown_board" in reasons(state)
    assert "buy:trial" not in reasons(state)
    assert code not in state.positions


def test_v7_names_flatten_uses_window_end_name_for_earlier_day():
    minutes = {SYMBOL: [bar(D1, 895, 105)]}
    path_daily = {SYMBOL: {date(2026, 8, 31): 100.0, D1: 100.0}}
    baseline = simulate_v7(minutes, path_daily, {D1: [SYMBOL]}, [D1, D2])
    flattened = flatten_pool_names(
        {
            D1.strftime("%Y%m%d"): {SYMBOL: "浦发银行"},
            D2.strftime("%Y%m%d"): {SYMBOL: "*ST 浦发"},
        }
    )
    forked = simulate_v7(
        minutes,
        path_daily,
        {D1: [SYMBOL]},
        [D1, D2],
        names=flattened,
    )
    assert "buy:trial" in reasons(baseline)
    assert "buy:trial" not in reasons(forked)
    assert "skip_limit_up" in reasons(forked)


def test_d3_v7_unst_window_extension_changes_earlier_fill(tmp_path):
    from backtest.research.csv_pool import load_pool_names_by_day

    for day, text in [(D1, "600000,*ST 浦发\n"), (D2, "600000,浦发\n"),
                      (D3, "000001,平安\n")]:
        (tmp_path / f"{day:%Y%m%d}.csv").write_text(text, encoding="utf-8")
    minutes = {SYMBOL: [bar(D1, 895, 105)]}
    path_daily = {SYMBOL: {date(2026, 8, 31): 100}}
    states = []
    for end, expected_name, expected_limits in [
        (D1, "*ST 浦发", (105, 95)), (D3, "浦发", (110, 90)),
    ]:
        names = flatten_pool_names(load_pool_names_by_day(tmp_path, D1, end))
        assert names[SYMBOL] == expected_name
        assert session_limit_prices(SYMBOL, 100, names[SYMBOL]) == expected_limits
        states.append(simulate_v7(
            minutes, path_daily, {D1: [SYMBOL]}, [D1, D2, D3],
            start=D1, end=end, names=names, cash_total=21_000_000,
        ))
    short, extended = states
    assert reasons(short) == ["skip_limit_up"]
    assert short.positions == {} and short.cash == 21_000_000
    assert reasons(extended) == ["buy:trial"]
    trade = extended.trades[0]
    assert (trade["date"], trade["price"]) == (D1.isoformat(), 105)
    assert trade["shares"] > 0
    assert extended.positions[SYMBOL].shares == trade["shares"]
    assert extended.cash < short.cash


def test_exdiv_rescales_trial_stop_into_none_domain():
    # Historical wiring vector: D1 minute=100 vs daily=50 is mixed-domain.
    # The d2 public vectors below independently pin same-domain held state.
    minutes = {SYMBOL: [bar(D1, 895, 100), bar(D2, 570, 48)]}
    path_daily = {SYMBOL: {date(2026, 8, 31): 100.0, D1: 50.0}}
    mapped = simulate_v7(
        minutes, path_daily, {D1: [SYMBOL]}, [D1, D2],
        exdiv={SYMBOL: {D2.strftime("%Y%m%d"): 0.5}},
    )
    assert "buy:trial" in reasons(mapped)
    assert "stop:trial_a090" not in reasons(mapped)
    raw = simulate_v7(minutes, path_daily, {D1: [SYMBOL]}, [D1, D2])
    assert "stop:trial_a090" in reasons(raw)


@pytest.mark.parametrize("k", [0.5, 1.2])
def test_d2_v7_helper_full_field_scope_including_compat_add1(k):
    # add1_A1 is a compatibility branch, not assigned by natural public adds.
    pos = v7.Position(SYMBOL, 10, stage="four", add1_A1=10.4,
                      lots=[v7.Lot(100, D1, 10, "trial"), v7.Lot(200, D2, 10.4, "add_a104")],
                      avg_cost=10.2, peak=12, last_add_date=D2)
    before = asdict(pos)
    v7._rescale_position(pos, k)
    expected = {**before, **{key: before[key] * k
                            for key in ("entry_A", "avg_cost", "peak", "add1_A1")},
                "lots": [{**lot, "price": lot["price"] * k} for lot in before["lots"]]}
    assert asdict(pos) == expected
    assert pos.shares == 300


def test_d2_v7_public_multilot_fields_once_and_economic_delta(monkeypatch):
    minutes = {SYMBOL: [bar(D1, 895, 10), bar(D1, 900, 10),
                        bar(D2, 885, 10.4), bar(D2, 900, 10.4),
                        bar(D3, 570, 5.2), bar(D3, 900, 5.2)]}
    closes = {SYMBOL: {D1 - timedelta(days=1): 10, D1: 10, D2: 10.4, D3: 5.2}}
    before = simulate_v7(minutes, closes, {D1: [SYMBOL]}, [D1, D2])
    assert reasons(before) == ["buy:trial", "buy:add_a104"]
    snapshots = []
    real = v7._rescale_position

    def observe(pos, k):
        old = asdict(pos)
        real(pos, k)
        snapshots.append((old, asdict(pos)))

    monkeypatch.setattr(v7, "_rescale_position", observe)
    after = simulate_v7(minutes, closes, {D1: [SYMBOL]}, [D1, D2, D3],
                        exdiv={SYMBOL: {"20260903": 0.5}})
    assert len(snapshots) == 1
    old, scaled = snapshots[0]
    assert old == asdict(before.positions[SYMBOL])
    for key in ("entry_A", "avg_cost", "peak"):
        assert scaled[key] == old[key] * 0.5
    assert scaled["add1_A1"] is None  # Natural add does not assign the compat field.
    assert scaled["lots"] == [{**lot, "price": lot["price"] * 0.5} for lot in old["lots"]]
    assert asdict(after.positions[SYMBOL]) == scaled  # No second scale during scan.
    shares = before.positions[SYMBOL].shares
    assert after.positions[SYMBOL].shares == shares and after.cash == before.cash
    assert after.trades == before.trades
    assert before.equity_curve[-1]["equity"] - after.equity_curve[-1]["equity"] == pytest.approx(shares * 5.2)
    previous = session_prev_close(closes[SYMBOL], D3, SYMBOL, {SYMBOL: {"20260903": 0.5}})
    assert previous == 5.2
    assert session_limit_prices(SYMBOL, previous) == (5.72, 4.68)


def test_d2_v7_exday_add_then_stop_sells_only_old_lot():
    closes = {SYMBOL: {D1 - timedelta(days=1): 10, D1: 10, D2: 4.8}}
    exdiv = {SYMBOL: {"20260902": 0.5}}
    # Same-domain D1 close=10; event-day raw prices 5 / 5.2 / 4.8.
    prefix = [bar(D1, 895, 10), bar(D1, 900, 10), bar(D2, 570, 5)]
    held = simulate_v7({SYMBOL: prefix}, closes, {D1: [SYMBOL]}, [D1, D2], exdiv=exdiv)
    state = simulate_v7(
        {SYMBOL: prefix + [bar(D2, 885, 5.2), bar(D2, 886, 4.8)]},
        closes, {D1: [SYMBOL]}, [D1, D2], exdiv=exdiv,
    )
    assert held.positions[SYMBOL].entry_A == held.positions[SYMBOL].avg_cost == 5
    assert reasons(state) == ["buy:trial", "buy:add_a104", "stop:four_avg095"]
    buy, add, sell = state.trades
    assert sell["date"] == D2.isoformat() and sell["hm"] == 886 and sell["price"] == 4.8
    assert sell["shares"] == buy["shares"]  # T+1: the event-day add is ineligible.
    pos = state.positions[SYMBOL]
    assert pos.entry_A == 5 and pos.avg_cost == 5.2 and pos.peak == 5.2
    assert pos.add1_A1 is None
    assert [asdict(lot) for lot in pos.lots] == [
        {"shares": add["shares"], "buy_date": D2, "price": 5.2, "kind": "add_a104"},
    ]
    expected_cash = (held.cash - v7.DEFAULT_SCHEDULE.debit_buy(add["shares"] * 5.2)
                     + v7.DEFAULT_SCHEDULE.credit_sell(sell["shares"] * 4.8))
    assert state.cash == pytest.approx(expected_cash)  # Only actual fills change cash.


def test_d2_v7_new_trial_on_exday_is_not_rescaled():
    state = simulate_v7(
        {SYMBOL: [bar(D1, 895, 5), bar(D1, 900, 5)]},
        {SYMBOL: {D1 - timedelta(days=1): 10, D1: 5}}, {D1: [SYMBOL]}, [D1],
        exdiv={SYMBOL: {"20260901": 0.5}},
    )
    assert reasons(state) == ["buy:trial"]
    pos = state.positions[SYMBOL]
    assert pos.entry_A == pos.avg_cost == pos.peak == pos.lots[0].price == 5
