"""T6-SX0 book: registered separately; dropout control book unchanged."""

from __future__ import annotations

import pandas as pd

from backtest.research.csv_daily_backtest import simulate
from backtest.research.csv_strategy_books import (
    apply_csv_strategy,
    get_book,
    normalize_csv_strategy,
)
from backtest.research.topk_dropout_rules import decide_topk_dropout
from backtest.research.topk_score_exit_rules import SX0_REASON, decide_topk_score_exit


def test_score_exit_registered_and_dropout_untouched():
    assert normalize_csv_strategy("topk_score_exit") == "topk_score_exit"
    book = get_book("topk_score_exit")
    assert book.tag == "topk_score_exit"
    assert book.allow_add is False
    drop = get_book("topk_dropout")
    assert drop.tag == "topk_dropout"
    assert "model_exit" not in drop.help_lock


def test_apply_score_exit_hooks():
    scores = {"20260106": {"600000.SH": 1.0, "600001.SH": -0.2, "600002.SH": 0.8}}
    hooks = apply_csv_strategy(
        "topk_score_exit",
        scores_by_day=scores,
        topk=2,
        n_drop=1,
        stop_pct=0,
    )
    assert hooks["name"] == "topk_score_exit"
    assert hooks["stop_pct"] is None
    assert hooks["daily_same_bar_prefixes"] == ("open_board", "topk_drop", "model_exit")
    assert callable(hooks["sell_gate"])
    assert callable(hooks["planned_for_day"])
    assert callable(hooks["bind_opening_held"])

    class St:
        stats = {}

    hooks["record_params"](St())
    assert St.stats["sell_book"] == "topk_score_exit"
    assert St.stats["topk"] == 2
    assert St.stats["n_drop"] == 1


def test_opening_plan_keeps_dropout_buy_and_tags_sx0():
    universe = [f"60000{i}.SH" for i in range(8)]
    scores_map = {c: float(8 - i) for i, c in enumerate(universe)}
    scores_map[universe[4]] = -0.3
    day = "20260106"
    hooks = apply_csv_strategy(
        "topk_score_exit",
        scores_by_day={day: scores_map},
        topk=5,
        n_drop=1,
        stop_pct=0,
    )
    opening = universe[:5]
    buy_c, sell_c = decide_topk_dropout(opening, scores_map, topk=5, n_drop=1)
    plan = decide_topk_score_exit(opening, scores_map, topk=5, n_drop=1)
    hooks["bind_opening_held"](day, opening)
    assert hooks["planned_for_day"](day, opening) == list(plan.buy)
    assert list(plan.buy_bottom) == buy_c
    assert list(plan.sell_bottom) == sell_c
    assert hooks["sell_gate"](universe[4], 1.0, day, []) == SX0_REASON


def test_daily_simulate_extra_sell_same_bar():
    days = pd.bdate_range("2026-01-05", periods=6)
    codes = [f"60000{i}.SH" for i in range(8)]
    bars = {
        c: pd.DataFrame(
            {
                "open": [10.0] * len(days),
                "high": [10.2] * len(days),
                "low": [9.8] * len(days),
                "close": [10.0] * len(days),
                "volume": [1e6] * len(days),
            },
            index=days,
        )
        for c in codes
    }
    ymd = [d.strftime("%Y%m%d") for d in days]
    rank = {c: float(8 - i) for i, c in enumerate(codes)}
    scores = {}
    for i, d in enumerate(ymd):
        day_rank = dict(rank)
        if i >= 2:
            day_rank[codes[0]] = -0.4
        scores[d] = day_rank
    pool = {d: codes[:5] for d in ymd}
    names = {d: {c: "测" for c in codes} for d in ymd}
    st = simulate(
        bars,
        pool,
        ymd[0],
        ymd[-1],
        total_cash=10_000_000,
        daily_quota=10_000_000,
        strategy="topk_score_exit",
        scores_by_day=scores,
        topk=5,
        n_drop=1,
        stop_pct=0,
        pool_names_by_day=names,
    )
    sx0 = [t for t in st.trades if t["side"] == "SELL" and t["reason"] == SX0_REASON]
    assert sx0, st.trades
    assert all(t["code"] == codes[0] for t in sx0)
