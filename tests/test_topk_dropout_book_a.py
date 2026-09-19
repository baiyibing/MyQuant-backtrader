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
    assert hooks["stop_pct"] == pytest.approx(0.10)
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
    assert St.stats["stop_pct"] == pytest.approx(0.10)


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
    assert hooks["daily_same_bar_prefixes"] == ("open_board", "topk_drop")
    assert hooks["cash_deploy_frac"] == pytest.approx(0.95)
    assert hooks["qlib_limit_pct"] == pytest.approx(0.095)
    assert hooks["limit_up_chase"] is False
    assert hooks["limit_down_pending"] is False
    assert hooks["forbid_all_trade_at_limit"] is True


def test_planned_for_day_uses_opening_decide_not_post_sell_held():
    """qlib one-shot: buy list is decide(opening), not decide(after dropout sells)."""
    universe = [f"60000{i}.SH" for i in range(10)]
    scores_map = {c: float(10 - i) for i, c in enumerate(universe)}
    # Two weak held names: opening sells the worst one; after that sell,
    # decide(post) wants two replacements (the overshoot we must not take).
    scores_map[universe[3]] = 0.2
    scores_map[universe[4]] = 0.1
    day = "20260106"
    hooks = apply_csv_strategy(
        "topk_dropout",
        scores_by_day={day: scores_map},
        topk=5,
        n_drop=1,
    )
    opening = universe[:5]
    buy_open, sell_open = decide_topk_dropout(opening, scores_map, topk=5, n_drop=1)
    assert len(sell_open) == 1
    post_sell = [c for c in opening if c not in sell_open]
    buy_post, _ = decide_topk_dropout(post_sell, scores_map, topk=5, n_drop=1)
    assert len(buy_post) > len(buy_open)

    hooks["bind_opening_held"](day, opening)
    planned = hooks["planned_for_day"](day, post_sell)
    assert planned == buy_open
    assert hooks["sell_gate"](sell_open[0], 1.0, day, []) == "topk_drop:bottom"


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


def test_daily_simulate_holds_topk_after_fill():
    """Stable ranks + one-shot decide + same-bar dropout → hold topk, not topk+n_drop."""
    import pandas as pd
    from backtest.research.csv_daily_backtest import simulate

    days = pd.bdate_range("2026-01-05", periods=8)
    codes = [f"60000{i}.SH" for i in range(8)]
    rank = {c: float(8 - i) for i, c in enumerate(codes)}
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
    pool = {d: codes[:5] for d in ymd}
    scores = {d: dict(rank) for d in ymd}
    names = {d: {c: "测试" for c in codes} for d in ymd}
    st = simulate(
        bars,
        pool,
        ymd[0],
        ymd[-1],
        total_cash=10_000_000,
        daily_quota=10_000_000,
        strategy="topk_dropout",
        scores_by_day=scores,
        topk=5,
        n_drop=1,
        stop_pct=0,
        pool_names_by_day=names,
    )
    held: set[str] = set()
    eod: list[int] = []
    by_day: dict[str, list] = {}
    for t in st.trades:
        by_day.setdefault(str(t["date"]), []).append(t)
    for d in ymd:
        for t in by_day.get(d, []):
            if t["side"] == "SELL":
                held.discard(t["code"])
            elif t["side"] == "BUY":
                held.add(t["code"])
        if held:
            eod.append(len(held))
    assert eod, st.trades
    assert max(eod) == 5
    assert eod[-1] == 5


def test_topk_limit_skip_has_no_chase():
    """+12% on ChiNext: v6/board would allow; qlib 9.5% skips and does not chase."""
    import pandas as pd
    from backtest.research.csv_daily_backtest import simulate

    days = pd.DatetimeIndex(
        [
            pd.Timestamp("2026-01-05"),
            pd.Timestamp("2026-01-06"),
            pd.Timestamp("2026-01-07"),
            pd.Timestamp("2026-01-08"),
        ]
    )
    code = "300001.SZ"
    bars = {
        code: pd.DataFrame(
            {
                "open": [10.0, 10.0, 11.2, 11.1],
                "high": [10.2, 11.3, 11.3, 11.2],
                "low": [9.8, 10.0, 11.0, 11.0],
                "close": [10.0, 11.2, 11.1, 11.1],
                "volume": [1e6] * 4,
            },
            index=days,
        ),
    }
    ymd = [d.strftime("%Y%m%d") for d in days]
    scores = {d: {code: 1.0} for d in ymd}
    names = {d: {code: "创业板测试"} for d in ymd}
    pool = {d: [code] for d in ymd}
    st = simulate(
        bars,
        pool,
        ymd[0],
        ymd[-1],
        total_cash=2_000_000,
        daily_quota=2_000_000,
        strategy="topk_dropout",
        scores_by_day=scores,
        topk=1,
        n_drop=1,
        stop_pct=0,
        pool_names_by_day=names,
    )
    assert st.stats["skip_limit_up"] >= 1
    assert not any(t["reason"] == "chase:T+1" for t in st.trades)
    assert not any(
        t["side"] == "BUY" and str(t["date"]) == "20260106" for t in st.trades
    )


def test_version6_keeps_limit_up_chase_hook():
    v6 = apply_csv_strategy("version6")
    assert v6["limit_up_chase"] is True
    assert v6["qlib_limit_pct"] is None
    assert v6["limit_down_pending"] is True


def test_version6_golden_stop_pct_unchanged():
    hooks = apply_csv_strategy("version6")
    assert hooks["stop_pct"] == pytest.approx(0.02)
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
    assert kw["stop_pct"] == pytest.approx(0.10)
