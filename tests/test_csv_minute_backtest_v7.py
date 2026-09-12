# -*- coding: utf-8 -*-
from datetime import date, timedelta

import pytest

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
    return {"date": day, "hm": hm, "open": close if open is None else open,
            "high": max(close, close if open is None else open), "low": min(close, close if open is None else open),
            "close": close}


def reasons(state):
    return [trade["reason"] for trade in state.trades]


def daily():
    return {SYMBOL: {date(2026, 8, 31): 100.0, D1: 100.0}}


def index_closes(values):
    first = date(2026, 8, 17)
    return {first + timedelta(days=offset): value for offset, value in enumerate(values)}


def test_7_trial_bought_at_1455_cannot_stop_same_day_but_can_next_day():
    minutes = {SYMBOL: [bar(D1, 895, 100), bar(D1, 896, 95), bar(D2, 570, 95)]}
    state = simulate_v7(minutes, daily(), {D1: [SYMBOL]}, [D1, D2])
    assert reasons(state).count("buy:trial") == 1
    assert reasons(state).count("stop:trial_a096") == 1
    sell = next(t for t in state.trades if t["reason"] == "stop:trial_a096")
    assert sell["date"] == D2.isoformat()


def test_8_prior_trial_can_chop_same_day_add_but_new_lots_are_t_plus_one():
    minutes = {SYMBOL: [bar(D1, 895, 100), bar(D2, 570, 104), bar(D2, 571, 99), bar(D2, 572, 99)]}
    state = simulate_v7(minutes, daily(), {D1: [SYMBOL]}, [D1, D2])
    assert "buy:add_a104" in reasons(state)
    assert "stop:chop_trial_a099" in reasons(state)
    assert "stop:three_a1_096" not in reasons(state)
    assert state.positions[SYMBOL].stage == "three_after_chop"
    assert state.positions[SYMBOL].shares > 0

    same_day = simulate_v7({SYMBOL: [bar(D1, 895, 100), bar(D1, 896, 104), bar(D1, 897, 99)]},
                           daily(), {D1: [SYMBOL]}, [D1])
    assert "buy:add_a104" in reasons(same_day)
    assert "stop:chop_trial_a099" not in reasons(same_day)


def test_8_chop_next_minute_three_stop_cascades_only_when_residual_is_sellable():
    minutes = {SYMBOL: [
        bar(D1, 895, 100),
        bar(D2, 570, 104),
        bar(D3, 570, 99),
        bar(D3, 571, 99),
    ]}
    state = simulate_v7(minutes, daily(), {D1: [SYMBOL]}, [D1, D2, D3])
    assert reasons(state) == [
        "buy:trial",
        "buy:add_a104",
        "stop:chop_trial_a099",
        "stop:three_a1_096",
    ]
    assert state.positions == {}
    chop, clear = state.trades[-2:]
    assert chop["date"] == clear["date"] == D3.isoformat()
    assert chop["hm"] == 570
    assert clear["hm"] == 571


def test_8_full_chop_readd_path_reaches_nine_with_locked_reasons():
    minutes = {SYMBOL: [
        bar(D1, 895, 100),
        bar(D2, 570, 104),
        bar(D2, 571, 99),
        bar(D2, 572, 108.16),
        bar(D2, 573, 114.40),
    ]}
    path_daily = {SYMBOL: {date(2026, 8, 31): 100.0, D1: 107.0}}
    state = simulate_v7(minutes, path_daily, {D1: [SYMBOL]}, [D1, D2])
    assert reasons(state) == [
        "buy:trial",
        "buy:add_a104",
        "stop:chop_trial_a099",
        "buy:readd_a1_104",
        "buy:readd_a1_110",
    ]
    assert state.positions[SYMBOL].stage == "nine"


def test_9_exact_1455_limit_up_and_open_limit_down_rules():
    missing = simulate_v7({SYMBOL: [bar(D1, 894, 100)]}, daily(), {D1: [SYMBOL]}, [D1])
    assert "buy:trial" not in reasons(missing)
    assert "skip_no_1455" in reasons(missing)

    limit_up = simulate_v7({SYMBOL: [bar(D1, 895, 110)]}, daily(), {D1: [SYMBOL]}, [D1])
    assert "skip_limit_up" in reasons(limit_up)
    assert "buy:trial" not in reasons(limit_up)

    stopped = simulate_v7({SYMBOL: [bar(D1, 895, 100), bar(D2, 570, 90, open=90)]},
                          daily(), {D1: [SYMBOL]}, [D1, D2])
    assert "defer_limit_down" in reasons(stopped)
    assert "stop:trial_a096" not in reasons(stopped)
    assert stopped.positions[SYMBOL].shares > 0


def test_10_index_gate_blocks_new_open_but_does_not_freeze_existing_stop():
    index = index_closes([100.0] * 9 + [90.0, 89.0, 88.0, 87.0])
    gate_day = sorted(index)[11]
    stock_daily = {SYMBOL: {gate_day - timedelta(days=1): 100.0, gate_day: 100.0}}

    blocked = simulate_v7(
        {SYMBOL: [bar(gate_day, 895, 100)]}, stock_daily,
        {gate_day: [SYMBOL]}, index, start=gate_day, end=gate_day,
    )
    assert "buy:trial" not in reasons(blocked)
    assert "skip_index_gate" in reasons(blocked)

    # Seed on the recovery-output session by keeping its preceding closes healthy,
    # then make the following gate output blocked while the held lot remains sellable.
    held_index = index_closes([100.0] * 10 + [101.0, 90.0, 89.0, 88.0])
    open_day, stop_day = sorted(held_index)[11], sorted(held_index)[13]
    stock_daily = {SYMBOL: {open_day - timedelta(days=1): 100.0, open_day: 100.0}}
    stopped = simulate_v7(
        {SYMBOL: [bar(open_day, 895, 100), bar(stop_day, 570, 95)]},
        stock_daily, {open_day: [SYMBOL]}, held_index, start=open_day, end=stop_day,
    )
    assert "buy:trial" in reasons(stopped)
    assert "stop:trial_a096" in reasons(stopped)


def test_10_timer_exit_locks_same_day_reopen_and_short_index_fails():
    index = index_closes([100.0] * 17)
    sessions = sorted(index)[11:]
    open_day, timer_day = sessions[0], sessions[5]
    stock_daily = {SYMBOL: {open_day - timedelta(days=1): 100.0, open_day: 100.0,
                            timer_day - timedelta(days=1): 100.0}}
    state = simulate_v7(
        {SYMBOL: [bar(open_day, 895, 100), bar(timer_day, 570, 100),
                  bar(timer_day, 895, 100)]},
        stock_daily, {open_day: [SYMBOL], timer_day: [SYMBOL]}, index,
        start=open_day, end=timer_day,
    )
    assert reasons(state).count("exit:timer5") == 1
    assert reasons(state).count("buy:trial") == 1
    assert state.positions == {}

    with pytest.raises(ValueError, match="11 warmup"):
        simulate_v7({}, {}, {}, index_closes([100.0] * 11))


def test_cli_empty_pool_is_legal_and_missing_pool_is_system_exit(tmp_path, monkeypatch):
    out = tmp_path / "out"
    assert main(["--start", "20260901", "--end", "20260902", "--pool-dir", str(tmp_path),
                 "--output-dir", str(out)]) == 0
    assert (out / "summary.txt").read_text(encoding="utf-8").find("trades=0") >= 0
    assert {path.name for path in out.iterdir()} == {"summary.txt", "daily_equity.csv", "trades.csv"}

    monkeypatch.delenv("OSKH_TURTLE_POOL_DIR", raising=False)
    with pytest.raises(SystemExit):
        main(["--start", "20260901", "--end", "20260902"])
