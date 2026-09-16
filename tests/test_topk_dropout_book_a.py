"""BT-A: book registration, planned_for_day hook, fail-closed scores, v6 untouched."""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from backtest.research.csv_strategy_books import (
    BOOKS,
    apply_csv_strategy,
    get_book,
    normalize_csv_strategy,
)
from backtest.research.topk_dropout_rules import decide_topk_dropout


def test_topk_book_registered_and_aliases():
    assert normalize_csv_strategy("topk") == "topk_dropout"
    assert normalize_csv_strategy("version_topk") == "topk_dropout"
    book = get_book("topk_dropout")
    assert book.allow_add is False
    assert book.tag == "topk_dropout"
    assert "qlib" in book.help_lock.lower() or "TopkDropout" in book.help_lock


def test_apply_topk_requires_scores_fail_closed():
    with pytest.raises(SystemExit, match="fail-closed"):
        apply_csv_strategy("topk_dropout")


def test_apply_topk_hooks_and_record_params():
    scores = {"20260106": {"600000.SH": 1.0, "600001.SH": 0.9, "600002.SH": 0.8}}
    hooks = apply_csv_strategy(
        "topk_dropout",
        scores_by_day=scores,
        topk=2,
        n_drop=1,
    )
    assert hooks["name"] == "topk_dropout"
    assert hooks["stop_pct"] is None
    assert hooks["take_profit"](1, 1, 1, 1) is None
    assert callable(hooks["sell_gate"])
    assert callable(hooks["planned_for_day"])
    assert callable(hooks["bind_opening_held"])

    class St:
        stats = {}

    hooks["record_params"](St())
    assert St.stats["sell_book"] == "topk_dropout"
    assert St.stats["topk"] == 2
    assert St.stats["n_drop"] == 1
    assert St.stats["stop_pct"] is None


def test_planned_for_day_matches_decide_buy():
    universe = [f"60000{i}.SH" for i in range(10)]
    scores_map = {c: float(10 - i) for i, c in enumerate(universe)}
    day = "20260106"
    hooks = apply_csv_strategy(
        "topk_dropout",
        scores_by_day={day: scores_map},
        topk=5,
        n_drop=1,
    )
    held = universe[:5]
    planned = hooks["planned_for_day"](day, held)
    buy, _sell = decide_topk_dropout(held, scores_map, topk=5, n_drop=1)
    assert planned == buy


def test_planned_for_day_missing_scores_raises():
    hooks = apply_csv_strategy(
        "topk_dropout",
        scores_by_day={"20260106": {"600000.SH": 1.0}},
        topk=1,
        n_drop=1,
    )
    with pytest.raises(RuntimeError, match="missing scores"):
        hooks["planned_for_day"]("20260107", [])


def test_sell_gate_uses_opening_held():
    scores_map = {
        "600000.SH": 5.0,
        "600001.SH": 4.0,
        "600002.SH": 0.1,  # dog
        "600003.SH": 3.0,
        "600004.SH": 2.5,
    }
    day = "20260106"
    hooks = apply_csv_strategy(
        "topk_dropout",
        scores_by_day={day: scores_map},
        topk=2,
        n_drop=1,
    )
    opening = ["600000.SH", "600001.SH", "600002.SH"]
    hooks["bind_opening_held"](day, opening)
    assert hooks["sell_gate"]("600002.SH", 1.0, day, []) == "topk_drop:bottom"
    assert hooks["sell_gate"]("600000.SH", 1.0, day, []) is None


def test_run_pool_buys_day_hook_replaces_pool_default_none_unchanged():
    from backtest.research.csv_simulate_loop import init_sim_state, run_pool_buys_day

    # Old book path: planned_for_day=None → pool file order
    v6 = apply_csv_strategy("version6")
    st, pending, _ = init_sim_state(v6, total_cash=10_000_000, bars_loaded=1, pool_days={})
    ds = "20260106"
    codes = ["600000.SH", "600001.SH"]
    run_pool_buys_day(
        st,
        pending,
        day_i=0,
        day="2026-01-06",
        ds=ds,
        pool_days={ds: codes},
        daily_quota=1_000_000,
        names={},
        allow_add=False,
        buy_gate=None,
        buy_quote_for=lambda code: (10.0, [10.0]),
        planned_for_day=None,
    )
    assert [t["code"] for t in st.trades] == codes

    # Hook replaces planned
    st2, pending2, _ = init_sim_state(v6, total_cash=10_000_000, bars_loaded=1, pool_days={})

    def only_second(ds_, held):
        del ds_, held
        return ["600001.SH"]

    run_pool_buys_day(
        st2,
        pending2,
        day_i=0,
        day="2026-01-06",
        ds=ds,
        pool_days={ds: codes},
        daily_quota=1_000_000,
        names={},
        allow_add=False,
        buy_gate=None,
        buy_quote_for=lambda code: (10.0, [10.0]),
        planned_for_day=only_second,
    )
    assert [t["code"] for t in st2.trades] == ["600001.SH"]


def test_version6_golden_stop_pct_unchanged():
    hooks = apply_csv_strategy("version6")
    assert hooks["stop_pct"] == pytest.approx(0.06)
    assert BOOKS["version6"].name == "version6"


def test_run_kwargs_fail_closed_without_scores(tmp_path: Path):
    book = get_book("topk_dropout")
    ns = argparse.Namespace(
        pred_csv=None,
        scores_dir=None,
        stop_pct=None,
        topk=50,
        n_drop=5,
    )
    with pytest.raises(SystemExit, match="pred-csv|scores-dir"):
        book.run_kwargs(ns)

    scores_dir = tmp_path / "scores"
    scores_dir.mkdir()
    (scores_dir / "20260106.csv").write_text("code,score\n600000,1.0\n", encoding="utf-8")
    ns.scores_dir = scores_dir
    kw = book.run_kwargs(ns)
    assert "600000.SH" in kw["scores_by_day"]["20260106"]
    assert kw["stop_pct"] is None
