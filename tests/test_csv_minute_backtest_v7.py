# -*- coding: utf-8 -*-
from datetime import date

import pytest

from backtest.research.csv_minute_backtest_v7 import main, simulate_v7


SYMBOL = "600000.SH"
D1 = date(2026, 9, 1)
D2 = date(2026, 9, 2)
D3 = date(2026, 9, 3)


def bar(day, hm, close, open=None):
    return {"date": day, "hm": hm, "open": close if open is None else open,
            "high": max(close, close if open is None else open), "low": min(close, close if open is None else open),
            "close": close}


def reasons(state):
    return [trade["reason"] for trade in state.trades]


def daily():
    return {SYMBOL: {date(2026, 8, 31): 100.0, D1: 100.0}}


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


def test_cli_empty_pool_is_legal_and_missing_pool_is_system_exit(tmp_path, monkeypatch):
    out = tmp_path / "out"
    assert main(["--start", "20260901", "--end", "20260902", "--pool-dir", str(tmp_path),
                 "--output-dir", str(out)]) == 0
    assert (out / "summary.txt").read_text(encoding="utf-8").find("trades=0") >= 0
    assert {path.name for path in out.iterdir()} == {"summary.txt", "daily_equity.csv", "trades.csv"}

    monkeypatch.delenv("OSKH_TURTLE_POOL_DIR", raising=False)
    with pytest.raises(SystemExit):
        main(["--start", "20260901", "--end", "20260902"])
