# -*- coding: utf-8 -*-
"""CSV 策略书注册表：必须显式指定，无缺省策略 6。"""

from __future__ import annotations

import argparse

import pytest

from backtest.research.csv_strategy_books import (
    BOOKS,
    apply_csv_strategy,
    csv_strategy_names,
    engine_book,
    get_book,
    normalize_csv_strategy,
)


def test_registered_books_are_explicit():
    assert csv_strategy_names() == (
        "version1",
        "version2",
        "version3",
        "version4",
        "version5",
        "version6",
        "version8",
        "version8_1",
        "version8_2",
        "version8_3",
        "version8_4",
        "version8_5",
        "version8_6",
        "version9",
        "version10",
        "topk_dropout",
        "topk_score_exit",
    )
    assert get_book("version1").allow_add is False
    assert get_book("version1").peak_gap_min == 0
    assert get_book("version2").allow_add is False
    assert get_book("version2").peak_gap_min == 0
    assert get_book("version4").allow_add is False
    assert get_book("version4").peak_gap_min == 0
    assert get_book("version5").allow_add is False
    assert get_book("version5").peak_gap_min == 0
    assert get_book("version6").allow_add is True
    assert get_book("version8").allow_add is True
    assert get_book("version8").peak_gap_min == 15
    assert get_book("version9").allow_add is False
    assert get_book("version10").allow_add is False
    assert engine_book("v6") == "v6"
    assert engine_book("v8") == "v8"
    assert engine_book("v9") == "v9"
    assert engine_book("v10") == "v10"


@pytest.mark.parametrize("strategy", ["version1", "version2"])
def test_apply_early_books(strategy):
    hooks = apply_csv_strategy(strategy)
    assert hooks["stop_pct"] == pytest.approx(0.02)
    assert hooks["allow_add"] is False
    assert hooks["peak_gap_min"] == 0
    assert hooks["take_profit"](10.5, 10.0, 11.0, 1).startswith("profit_take:drawdown")
    assert hooks["take_profit"](9.9, 10.0, 11.0, 1) is None


def test_normalize_requires_strategy():
    with pytest.raises(ValueError, match="required"):
        normalize_csv_strategy("")
    with pytest.raises(ValueError, match="required"):
        normalize_csv_strategy("   ")
    with pytest.raises(ValueError, match="unsupported"):
        normalize_csv_strategy("version7")


def test_apply_version6_is_not_a_silent_fallback():
    hooks = apply_csv_strategy("version6")
    assert hooks["name"] == "version6"
    assert hooks["book"] == "v6"
    assert hooks["allow_add"] is True
    assert hooks["take_profit"] is not None
    assert hooks["stop_pct"] == pytest.approx(0.02)
    assert hooks["take_profit"](10.15, 10.0, 10.50, 0) is None
    assert hooks["take_profit"](10.15, 10.0, 10.50, 1) == "trail:band:lt6"
    assert hooks["take_profit"](10.151, 10.0, 10.50, 1) is None
    assert hooks["take_profit"](10.30, 10.0, 10.60, 1) == "trail:band:ge6"


def test_apply_version5_has_no_stop_and_has_minute_clock():
    hooks = apply_csv_strategy("version5", stop_pct=0.03)
    assert hooks["stop_pct"] is None
    assert hooks["force_sell_hm"] == 890
    assert hooks["take_profit"](10.2, 10.0, 10.2, 1) == "profit_take:target"
    assert hooks["sell_gate"] is None
    assert hooks["reserve_limit_up"] is False
    assert hooks["daily_same_bar_prefixes"] == ("open_board",)


def test_version5_cli_forbids_stop_override():
    book = get_book("version5")
    assert book.run_kwargs(argparse.Namespace(stop_pct=None)) == {
        "strategy": "version5"
    }
    with pytest.raises(SystemExit, match="not supported"):
        book.run_kwargs(argparse.Namespace(stop_pct=0.03))


def test_apply_version4_has_sma_gates_and_no_stop():
    hooks = apply_csv_strategy("v4", stop_pct=0.03)
    assert hooks["stop_pct"] is None
    assert callable(hooks["buy_gate"])
    assert callable(hooks["sell_gate"])
    assert hooks["take_profit"](1, 1, 1, 1) is None
    assert hooks["force_sell_hm"] is None
    assert hooks["reserve_limit_up"] is False


def test_version4_cli_forbids_stop_override():
    book = get_book("version4")
    assert book.run_kwargs(argparse.Namespace(stop_pct=None)) == {
        "strategy": "version4"
    }
    with pytest.raises(SystemExit, match="not supported"):
        book.run_kwargs(argparse.Namespace(stop_pct=0.03))


def test_missing_cli_strategy_exits():
    ap = argparse.ArgumentParser()
    from backtest.research.csv_strategy_books import add_csv_strategy_arg

    add_csv_strategy_arg(ap)
    with pytest.raises(SystemExit):
        ap.parse_args([])


def test_add_csv_backtest_common_args_defaults_and_end_help(tmp_path):
    from backtest.research.csv_ledger import DEFAULT_TOTAL_CASH
    from backtest.research.csv_strategy_books import add_csv_backtest_common_args

    ap = argparse.ArgumentParser()
    add_csv_backtest_common_args(
        ap,
        repo=tmp_path,
        end_default="20260909",
        cash_total_default=DEFAULT_TOTAL_CASH,
        daily_quota_default=1_000_000.0,
    )
    with pytest.raises(SystemExit):
        ap.parse_args([])
    ns = ap.parse_args(["--strategy", "version6"])
    assert ns.start == "20251023"
    assert ns.end == "20260909"
    assert ns.cash_total == DEFAULT_TOTAL_CASH
    assert ns.daily_quota == 1_000_000.0
    assert ns.ration == "file_order"
    assert ns.ration_seed == 0
    assert ns.workers == 16
    assert ns.pool_dir == tmp_path / "stock_pool"

    ap2 = argparse.ArgumentParser()
    add_csv_backtest_common_args(
        ap2,
        repo=tmp_path,
        end_default="20260909",
        end_help="minute lake last day is 20260909; short parity window: 20251104",
        cash_total_default=DEFAULT_TOTAL_CASH,
        daily_quota_default=1_000_000.0,
    )
    assert "minute lake last day is 20260909" in ap2.format_help()


def test_books_are_separate_modules():
    assert BOOKS["version1"].apply is not BOOKS["version2"].apply
    assert BOOKS["version6"].apply is not BOOKS["version8"].apply
    assert BOOKS["version8"].apply is not BOOKS["version9"].apply
    assert BOOKS["version9"].apply is not BOOKS["version10"].apply
    assert "策略 6" in BOOKS["version6"].help_lock
    assert "策略 8" in BOOKS["version8"].help_lock
    assert "策略 9" in BOOKS["version9"].help_lock
    assert "策略 10" in BOOKS["version10"].help_lock


@pytest.mark.parametrize("strategy", ["version1", "version2"])
def test_early_book_run_kwargs_stop_override(strategy):
    book = get_book(strategy)
    assert book.run_kwargs(argparse.Namespace(stop_pct=None)) == {
        "strategy": strategy,
        "stop_pct": None,
    }
    assert book.run_kwargs(argparse.Namespace(stop_pct=0.03))[
        "stop_pct"
    ] == pytest.approx(0.03)
    with pytest.raises(SystemExit, match="in \\(0, 1\\)"):
        book.run_kwargs(argparse.Namespace(stop_pct=1.0))


@pytest.fixture
def per_name_hooks(monkeypatch):
    from dataclasses import replace

    monkeypatch.setitem(
        BOOKS,
        "version8",
        replace(BOOKS["version8"], sizing="per_name", allow_add=True),
    )
    hooks = apply_csv_strategy("version8")
    hooks["add_gate"] = lambda _lots, _px: True
    return hooks


def _money_state(hooks, cash=21_000_000):
    from backtest.research.csv_simulate_loop import init_sim_state

    return init_sim_state(hooks, total_cash=cash, bars_loaded=2, pool_days={})[0]


def _pool_buy(
    st,
    hooks,
    codes,
    *,
    day_i=0,
    px=10,
    prev=10,
    pending=None,
    ration="file_order",
    ration_seed=0,
    ds="20251103",
):
    from backtest.research.csv_simulate_loop import run_pool_buys_day

    run_pool_buys_day(
        st,
        {} if pending is None else pending,
        day_i=day_i,
        day="2025-11-03",
        ds=ds,
        pool_days={ds: codes},
        daily_quota=1_000_000,
        names={},
        allow_add=hooks["allow_add"],
        buy_gate=None,
        buy_quote_for=lambda code: (px, [prev]),
        sizing=hooks["sizing"],
        name_budget=hooks["name_budget"],
        ration=ration,
        ration_seed=ration_seed,
    )


def test_seeded_shuffle_is_stable_per_day_and_changes_cash_allocation(per_name_hooks):
    from backtest.research.csv_simulate_loop import apply_capital_ration

    codes = ["600000.SH", "000001.SZ", "000002.SZ", "600001.SH", "600002.SH"]
    file_state = _money_state(per_name_hooks, 1_500_000)
    _pool_buy(file_state, per_name_hooks, codes)
    assert [t["code"] for t in file_state.trades] == ["600000.SH"]

    shuffled_state = _money_state(per_name_hooks, 1_500_000)
    _pool_buy(
        shuffled_state,
        per_name_hooks,
        codes,
        ration="seeded_shuffle",
        ration_seed=0,
    )
    assert [t["code"] for t in shuffled_state.trades] == ["600002.SH"]

    order = apply_capital_ration(
        codes, ration="seeded_shuffle", ration_seed=0, ds="20251103"
    )
    assert order == apply_capital_ration(
        codes, ration="seeded_shuffle", ration_seed=0, ds="20251103"
    )
    assert order != apply_capital_ration(
        codes, ration="seeded_shuffle", ration_seed=2, ds="20251103"
    )
    assert order != apply_capital_ration(
        codes, ration="seeded_shuffle", ration_seed=0, ds="20251104"
    )
    assert codes == ["600000.SH", "000001.SZ", "000002.SZ", "600001.SH", "600002.SH"]


def test_per_name_each_code_gets_full_budget(per_name_hooks):
    st = _money_state(per_name_hooks)
    _pool_buy(st, per_name_hooks, ["600000.SH", "000001.SZ"])
    assert [t["notional"] for t in st.trades] == [1_000_000, 1_000_000]
    assert st.daily_quota_used == 0
    assert st.stats["sizing"] == "per_name"
    assert st.stats["name_budget"] == 1_000_000


def test_per_name_cash_short_skips_entire_second_order(per_name_hooks):
    st = _money_state(per_name_hooks, 1_500_000)
    _pool_buy(st, per_name_hooks, ["600000.SH", "000001.SZ"])
    assert [t["code"] for t in st.trades] == ["600000.SH"]
    assert st.stats["skip_cash"] == 1
    assert st.stats["skip_cash_notional"] == pytest.approx(1_000_000)
    assert st.cash == pytest.approx(499_000)


def test_per_name_commission_short_also_skips(per_name_hooks):
    st = _money_state(per_name_hooks, 1_000_000)
    _pool_buy(st, per_name_hooks, ["600000.SH"])
    assert not st.trades
    assert st.stats["skip_cash"] == 1


def test_per_name_adds_held_code_as_new_lot(per_name_hooks):
    assert per_name_hooks["allow_add"] is True
    st = _money_state(per_name_hooks)
    _pool_buy(st, per_name_hooks, ["600000.SH"])
    _pool_buy(st, per_name_hooks, ["600000.SH"], day_i=1)
    assert st.stats["skip_held"] == 0
    assert st.stats["add_lots"] == 1
    assert len(st.positions["600000.SH"]) == 2


def test_per_name_force_min_cli_budget(per_name_hooks, tmp_path):
    from backtest.research.csv_strategy_books import (
        add_csv_backtest_common_args,
        csv_run_kwargs_from_args,
    )

    ap = argparse.ArgumentParser()
    add_csv_backtest_common_args(
        ap,
        repo=tmp_path,
        end_default="20260909",
        cash_total_default=21_000_000,
        daily_quota_default=1_000_000,
    )
    args = ap.parse_args(["--strategy", "version8", "--name-budget", "3000"])
    hooks = apply_csv_strategy(**csv_run_kwargs_from_args(args))
    st = _money_state(hooks)
    _pool_buy(st, hooks, ["600000.SH"], px=40, prev=40)
    assert st.trades[0]["shares"] == 100
    assert st.stats["supplementary_used"] == 1000
    assert st.stats["name_budget"] == 3000
    assert st.daily_quota_used == 0


@pytest.mark.parametrize("outcome", ["held", "cash", "buy", "shares"])
def test_per_name_chase_budget_and_terminal_outcomes(per_name_hooks, outcome):
    from backtest.research.csv_simulate_loop import run_chase_due_day

    st = _money_state(per_name_hooks)
    pending = {}
    _pool_buy(st, per_name_hooks, ["600000.SH", "000001.SZ"], px=11, pending=pending)
    assert pending == {"600000.SH": (1_000_000, 0), "000001.SZ": (1_000_000, 0)}
    pending.pop("000001.SZ")
    if outcome == "held":
        _pool_buy(st, per_name_hooks, ["600000.SH"])
    elif outcome == "cash":
        st.cash = 500_000
    elif outcome == "shares":
        pending["600000.SH"] = (0, 0)
    run_chase_due_day(
        st,
        pending,
        day_i=1,
        day="2025-11-04",
        names={},
        allow_add=per_name_hooks["allow_add"],
        buy_gate=None,
        quotes_for=lambda code: (9.9, 10, [10]),
    )
    assert not pending
    assert st.daily_quota_used == 0
    if outcome == "held":
        assert st.stats["chase_skip_held"] == 0
        assert st.stats["add_lots"] == 1
    elif outcome == "buy":
        assert st.stats["chase_buy"] == 1
        assert st.trades[0]["notional"] == 1_000_000
    else:
        assert st.stats["chase_buy_fail"] == 1
        assert st.stats[f"chase_buy_fail_{outcome}"] == 1
        assert st.stats["chase_buy_fail_cash"] + st.stats["chase_buy_fail_shares"] == 1


@pytest.mark.parametrize("strategy", ["version1"])
def test_daily_quota_trades_byte_identical(strategy):
    """Anchors captured at 9f4303c, before slice A; never regenerate pre_er1.

    version6 已改为名单加仓 + 两档回撤，不再对照这份旧 golden。
    Human GO P2=B 只给 live version1 golden 追加标签列；旧列逐字节不变。
    """
    from pathlib import Path
    import runpy
    import pandas as pd

    fixture = Path(__file__).parent / "fixtures"
    helpers = runpy.run_path(str(fixture / "csv_engine_pre_er1/generate_snapshot.py"))
    rows = {
        c: [
            (10, 10.1, 9.95, 10),
            (10.4, 10.6, 10.2, 10.45),
            (10.3, 10.5, 10, 10.05),
            (10, 10.1, 9.7, 9.8),
            (9.8, 9.9, 9.6, 9.7),
        ]
        for c in ("600000.SH", "000001.SZ")
    }
    st = helpers["_run"](
        strategy, rows, {"20251103": list(rows), "20251104": list(rows)}
    )
    actual = pd.DataFrame(st.trades).to_csv(index=False).encode("utf-8")
    assert (
        actual
        == (fixture / "money_modes_daily_quota" / f"{strategy}_trades.csv").read_bytes()
    )
    assert apply_csv_strategy(strategy, name_budget=3000)["name_budget"] == 1_000_000
    assert st.stats["sizing"] == "daily_quota"


def test_money_mode_summary_is_self_describing(per_name_hooks):
    from backtest.research.csv_artifacts import summarize

    st = _money_state(per_name_hooks)
    text = summarize(st, 21_000_000, "20251103", "20251103", engine="csv_daily_v8")
    assert "sizing=per_name | name_budget=1,000,000" in text
    assert "skip_cash=0 | skip_cash_notional=0" in text
    assert "chase_buy_fail_cash=0 | chase_buy_fail_shares=0" in text


def test_v8_daily_quota_history_keeps_allow_add(monkeypatch):
    from dataclasses import replace

    assert BOOKS["version8"].sizing == "per_name"
    monkeypatch.setitem(
        BOOKS,
        "version8",
        replace(BOOKS["version8"], sizing="daily_quota", allow_add=True),
    )
    hooks = apply_csv_strategy("version8", stop_pct=0.20)
    hooks["add_gate"] = lambda _lots, _px: True
    assert hooks["allow_add"] is True
    assert hooks["stop_pct"] == 0.20
    st = _money_state(hooks)
    _pool_buy(st, hooks, ["600000.SH"])
    _pool_buy(st, hooks, ["600000.SH"], day_i=1)
    assert st.stats["add_lots"] == 1
    assert st.stats["skip_held"] == 0
    assert [t["lot"] for t in st.trades] == [0, 1]
