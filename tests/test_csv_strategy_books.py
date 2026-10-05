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
        "version6_1",
        "version6_2",
        "version6_3",
        "version6_4",
        "version6_5",
        "version6_6",
        "version6_7",
        "version6_8",
        "version6_9",
        "version6_10",
        "version6_11",
        "version6_12",
        "version6_13",
        "version8",
        "version8_1",
        "version8_2",
        "version8_3",
        "version8_4",
        "version8_5",
        "version8_6",
        "version9",
        "version9_2",
        "version10",
        "version11",
        "version12",
        "topk_dropout",
        "topk_score_exit",
        "version9_1",
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


def test_apply_version6_1_registers_per_name_ladder_book():
    hooks = apply_csv_strategy("v6.1")
    assert hooks["name"] == "version6_1"
    assert hooks["book"] == "v6_1"
    assert hooks["sizing"] == "per_name"
    assert hooks["name_budget"] == pytest.approx(1_000_000.0)
    assert hooks["allow_add"] is True
    assert hooks["peak_gap_min"] == 15
    assert hooks["stop_pct"] == pytest.approx(0.05)
    assert hooks["name_lot_budget"](1_000_000.0, object()) == pytest.approx(1_000_000.0)
    # Q1=G：离场价 = 峰值 − 成本×B；A=10% 落 [10,15%) 档 → B=9% → 11 − 0.9。
    assert hooks["take_profit"](10.10, 10.0, 11.0, 1) == "trail:ladder:10"
    assert hooks["take_profit"](10.11, 10.0, 11.0, 1) is None
    # Q2：首档离场线可在成本下方触发。
    assert hooks["take_profit"](9.70, 10.0, 10.20, 1) == "trail:ladder:0"
    assert hooks["take_profit"](9.71, 10.0, 10.20, 1) is None


def test_apply_version6_2_band0_breakeven_and_half_step():
    hooks = apply_csv_strategy("v6.2")
    assert hooks["name"] == "version6_2"
    assert hooks["sizing"] == "per_name"
    assert hooks["stop_pct"] == pytest.approx(0.10)
    assert hooks["add_step"] == pytest.approx(0.10)
    assert hooks["step_frac"] == pytest.approx(0.5)
    # band0 保本锚：成本触发、上方不触发。
    assert hooks["take_profit"](10.00, 10.0, 10.20, 1) == "trail:ladder:0"
    assert hooks["take_profit"](10.01, 10.0, 10.20, 1) is None
    # band≥1 沿用 6.1 公式。
    assert hooks["take_profit"](10.10, 10.0, 11.00, 1) == "trail:ladder:10"


def test_version6_1_cli_stop_override():
    book = get_book("version6_1")
    assert book.run_kwargs(argparse.Namespace(stop_pct=None)) == {
        "strategy": "version6_1",
        "stop_pct": None,
    }
    assert book.run_kwargs(argparse.Namespace(stop_pct=0.07)) == {
        "strategy": "version6_1",
        "stop_pct": 0.07,
    }
    with pytest.raises(SystemExit, match="--stop-pct"):
        book.run_kwargs(argparse.Namespace(stop_pct=1.5))


def test_apply_version6_3_widens_give_step_to_3pct():
    hooks = apply_csv_strategy("v6.3")
    assert hooks["name"] == "version6_3"
    assert hooks["sizing"] == "per_name"
    assert hooks["stop_pct"] == pytest.approx(0.05)
    assert hooks["add_step"] == pytest.approx(0.20)
    assert hooks["step_frac"] == pytest.approx(1.0)
    # 档 2（A=10%）：B=11% → 线 = 11 − 1.10；首档不变。
    assert hooks["take_profit"](9.90, 10.0, 11.00, 1) == "trail:ladder:10"
    assert hooks["take_profit"](9.70, 10.0, 10.20, 1) == "trail:ladder:0"


def test_apply_version6_13_scale_out_hooks():
    hooks = apply_csv_strategy("v6.13")
    assert hooks["name"] == "version6_13"
    assert hooks["step_stop_pct"] == pytest.approx(0.10)
    assert hooks["scale_out_step"] == pytest.approx(0.05)
    assert hooks["scale_out_frac"] == pytest.approx(0.05)
    assert hooks["add_step"] == pytest.approx(0.20)
    assert hooks["take_profit"](9.90, 10.0, 11.00, 1) == "trail:ladder:10"


def test_apply_version6_12_finer_add_ladder():
    hooks = apply_csv_strategy("v6.12")
    assert hooks["name"] == "version6_12"
    assert hooks["add_step"] == pytest.approx(0.05)
    assert hooks["add_offset"] == 4
    assert hooks["tranche_max"] == 4
    assert callable(hooks["breakout_day"])


def test_apply_version6_11_breakout_hooks():
    hooks = apply_csv_strategy("v6.11")
    assert hooks["name"] == "version6_11"
    assert hooks["stop_pct"] == pytest.approx(0.10)
    assert hooks["add_step"] == pytest.approx(0.10)
    assert hooks["add_offset"] == 2
    assert hooks["tranche_max"] == 4
    assert hooks["step_frac"] == pytest.approx(1.0)
    assert callable(hooks["breakout_day"])
    assert hooks["planned_for_day"]("20260101", []) == []


def test_apply_version6_10_dual_5pct_stops():
    hooks = apply_csv_strategy("v6.10")
    assert hooks["name"] == "version6_10"
    assert hooks["stop_pct"] == pytest.approx(0.05)
    assert hooks["step_stop_pct"] == pytest.approx(0.05)
    # 双梯子与 6.9 相同。
    assert hooks["add_step"] == pytest.approx(0.05)
    assert hooks["add_step2"] == pytest.approx(0.20)
    assert hooks["base_zone_caps"] == (2, 4)
    assert hooks["name_lot_budget"](1_000_000.0, []) == pytest.approx(200_000.0)


def test_apply_version6_9_dual_ladder_hooks():
    hooks = apply_csv_strategy("v6.9")
    assert hooks["name"] == "version6_9"
    assert hooks["stop_pct"] == pytest.approx(0.10)
    assert hooks["add_step"] == pytest.approx(0.05)
    assert hooks["step_frac"] == pytest.approx(0.20)
    assert hooks["add_step2"] == pytest.approx(0.20)
    assert hooks["step_frac2"] == pytest.approx(1.0)
    assert hooks["tranche_max"] == 4
    assert hooks["base_zone_caps"] == (2, 4)
    assert hooks["step_cap"] is None
    assert hooks["name_lot_budget"](1_000_000.0, []) == pytest.approx(200_000.0)
    assert hooks["take_profit"](16.00, 10.0, 20.01, 1) == "trail:peakdd20"


def test_apply_version6_8_step_stop_hook():
    hooks = apply_csv_strategy("v6.8")
    assert hooks["name"] == "version6_8"
    assert hooks["step_stop_pct"] == pytest.approx(0.10)
    assert hooks["step_cap"] == 8
    # 离场线纯函数继承 6.7。
    assert hooks["take_profit"](10.62, 10.0, 12.50, 1) == "trail:ladder:25"


def test_apply_version6_7_mid_band_peak_line():
    hooks = apply_csv_strategy("v6.7")
    assert hooks["name"] == "version6_7"
    assert hooks["sizing"] == "per_name"
    assert hooks["stop_pct"] == pytest.approx(0.05)
    assert hooks["add_step"] == pytest.approx(0.10)
    assert hooks["step_cap"] == 8
    # 中段：A=25% 线 = 峰值×0.85 = 10.625。
    assert hooks["take_profit"](10.62, 10.0, 12.50, 1) == "trail:ladder:25"
    assert hooks["take_profit"](10.63, 10.0, 12.50, 1) is None
    # >100%：峰值×0.80。
    assert hooks["take_profit"](16.00, 10.0, 20.01, 1) == "trail:peakdd20"


def test_apply_version6_4_floors_and_step_cap():
    hooks = apply_csv_strategy("v6.4")
    assert hooks["name"] == "version6_4"
    assert hooks["sizing"] == "per_name"
    assert hooks["stop_pct"] == pytest.approx(0.05)
    assert hooks["cost_anchor"] == "first_lot"
    assert hooks["step_cap"] == 4
    # 档 1 保底 +1%：线 = max(计算线, 10.10)。
    assert hooks["take_profit"](10.10, 10.0, 10.50, 1) == "trail:ladder:5"
    assert hooks["take_profit"](10.11, 10.0, 10.50, 1) is None
    # 档 0 与档 ≥3 无保底。
    assert hooks["take_profit"](9.70, 10.0, 10.20, 1) == "trail:ladder:0"
    assert hooks["take_profit"](10.10, 10.0, 11.50, 1) == "trail:ladder:15"


def test_version6_2_cli_stop_override():
    book = get_book("version6_2")
    assert book.run_kwargs(argparse.Namespace(stop_pct=None)) == {
        "strategy": "version6_2",
        "stop_pct": None,
    }
    assert book.run_kwargs(argparse.Namespace(stop_pct=0.12)) == {
        "strategy": "version6_2",
        "stop_pct": 0.12,
    }
    with pytest.raises(SystemExit, match="--stop-pct"):
        book.run_kwargs(argparse.Namespace(stop_pct=0.0))


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
    # CLI default is None; the money-mode pairing resolves it downstream
    # (topk family = cash_total, other books = 1,000,000/day).
    assert ns.daily_quota is None
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


@pytest.mark.parametrize("strategy", [
    "version8", "version8_2", "version8_3", "version8_4", "version8_5", "version8_6",
])
def test_s8_help_locks_independent_positions_group_exits_and_strict_cash(strategy):
    help_lock = BOOKS[strategy].help_lock
    for sentence in (
        "名单每个代码+信号日期各开独立持仓（position_id）",
        "后日再现是新仓",
        "按持仓加权成本整体评估止损/止盈/trail/stale（成本不含佣金）",
        "peak 初始为首买价，T+1 起跟踪行情，加仓不重置；stale 从首买日计算",
        "退出卖出该持仓全部可卖股",
        "今日新增股遵守 T+1，次交易日首个可卖时机按原卖因加 |t1_deferred 卖出",
        "跌停仍顺延，已挂起退出的持仓不再加仓；不同信号日期持仓互不连带",
        "任一买单所需现金（含费用）不足即 InsufficientCashError，停止回测",
    ):
        assert sentence in help_lock
    assert "上限2笔" not in "".join(help_lock.split())
    if strategy in ("version8", "version8_4", "version8_5"):
        assert "相对各持仓自己的首笔成本每满 +20% 加 100 万；名单外也评" in help_lock
        assert "每持仓每日最多一级" in help_lock
        assert "成交后记录历史级数，step lot 卖出不回退；全部 lots 卖完即关闭" in help_lock
    elif strategy == "version8_3":
        assert "各首买 50 万试探，不受旧仓亏损或旧仓 add_gate 限制" in help_lock
        assert "现价≥自身首笔成本且自身峰值≥自身首笔成本×1.03 时，补剩余 50 万一次" in help_lock
        assert "与名单无关；分钟 14:55 扫描" in help_lock
        assert "追买绑定原信号身份且预算固定为 50 万" in help_lock
    else:
        assert "无价格加仓，单 lot 沿用原退出规则" in help_lock
        assert help_lock.count("追买保留原信号身份和预算") == 1


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
    ds=None,
):
    import pandas as pd
    from backtest.research.csv_simulate_loop import run_pool_buys_day

    ds = ds or (pd.Timestamp("2025-11-03") + pd.offsets.BDay(day_i)).strftime("%Y%m%d")
    run_pool_buys_day(
        st,
        {} if pending is None else pending,
        day_i=day_i,
        day=pd.Timestamp(ds),
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


def _assert_per_name_cash_error(error, *, date, code, needed, available):
    from backtest.research.csv_ledger import InsufficientCashError

    assert isinstance(error, InsufficientCashError)
    assert error.date == date
    assert error.code == code
    assert error.needed == pytest.approx(needed)
    assert error.available == pytest.approx(available)
    assert error.shortfall == pytest.approx(needed - available)
    for token in (date, code, "needed", "available", "shortfall"):
        assert token in str(error)


def test_seeded_shuffle_is_stable_per_day_and_changes_cash_allocation(per_name_hooks):
    from backtest.research.csv_ledger import InsufficientCashError
    from backtest.research.csv_simulate_loop import apply_capital_ration

    codes = ["600000.SH", "000001.SZ", "000002.SZ", "600001.SH", "600002.SH"]
    file_state = _money_state(per_name_hooks, 1_500_000)
    with pytest.raises(InsufficientCashError) as caught:
        _pool_buy(file_state, per_name_hooks, codes)
    _assert_per_name_cash_error(
        caught.value, date="20251103", code="000001.SZ", needed=1_001_000, available=499_000,
    )
    assert [t["code"] for t in file_state.trades] == ["600000.SH"]

    shuffled_state = _money_state(per_name_hooks, 1_500_000)
    order = apply_capital_ration(codes, ration="seeded_shuffle", ration_seed=0, ds="20251103")
    with pytest.raises(InsufficientCashError) as caught:
        _pool_buy(
            shuffled_state,
            per_name_hooks,
            codes,
            ration="seeded_shuffle",
            ration_seed=0,
        )
    _assert_per_name_cash_error(
        caught.value, date="20251103", code=order[1], needed=1_001_000, available=499_000,
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


def test_per_name_cash_short_raises_before_entire_second_order(per_name_hooks):
    from backtest.research.csv_ledger import InsufficientCashError

    st = _money_state(per_name_hooks, 1_500_000)
    with pytest.raises(InsufficientCashError) as caught:
        _pool_buy(st, per_name_hooks, ["600000.SH", "000001.SZ"])
    _assert_per_name_cash_error(
        caught.value, date="20251103", code="000001.SZ", needed=1_001_000, available=499_000,
    )
    assert [t["code"] for t in st.trades] == ["600000.SH"]
    assert st.stats["skip_cash"] == 0
    assert st.cash == pytest.approx(499_000)


def test_per_name_commission_short_also_raises(per_name_hooks):
    from backtest.research.csv_ledger import InsufficientCashError

    st = _money_state(per_name_hooks, 1_000_000)
    with pytest.raises(InsufficientCashError) as caught:
        _pool_buy(st, per_name_hooks, ["600000.SH"])
    _assert_per_name_cash_error(
        caught.value, date="20251103", code="600000.SH", needed=1_001_000, available=1_000_000,
    )
    assert not st.trades
    assert st.stats["skip_cash"] == 0


def test_per_name_adds_held_code_as_new_lot(per_name_hooks):
    assert per_name_hooks["allow_add"] is True
    st = _money_state(per_name_hooks)
    _pool_buy(st, per_name_hooks, ["600000.SH"])
    _pool_buy(st, per_name_hooks, ["600000.SH"], day_i=1)
    assert st.stats["skip_held"] == 0
    assert st.stats["add_lots"] == 0
    assert len(st.positions["600000.SH"]) == 2
    assert [t["position_id"] for t in st.trades] == [
        "600000.SH@20251103", "600000.SH@20251104",
    ]


@pytest.fixture
def budget_parser(tmp_path):
    from backtest.research.csv_strategy_books import add_csv_backtest_common_args

    ap = argparse.ArgumentParser()
    add_csv_backtest_common_args(
        ap,
        repo=tmp_path,
        end_default="20260909",
        cash_total_default=21_000_000,
        daily_quota_default=1_000_000,
    )
    return ap


@pytest.mark.parametrize("strategy", ["version6", "version8_1", "version9"])
def test_daily_quota_default_name_budget(budget_parser, strategy):
    from backtest.research.csv_strategy_books import csv_run_kwargs_from_args

    args = budget_parser.parse_args(["--strategy", strategy])
    assert args.name_budget is None
    kwargs = csv_run_kwargs_from_args(args)
    assert kwargs["strategy"] == strategy
    assert "name_budget" not in kwargs


@pytest.mark.parametrize("strategy", ["version6", "version8_1", "version9"])
def test_daily_quota_explicit_name_budget_rejected(budget_parser, strategy):
    from backtest.research.csv_strategy_books import csv_run_kwargs_from_args

    args = budget_parser.parse_args(["--strategy", strategy, "--name-budget", "1000000"])
    with pytest.raises(SystemExit, match=f"--name-budget applies only to per_name books; {strategy} is daily_quota"):
        csv_run_kwargs_from_args(args)


@pytest.mark.parametrize("strategy", [name for name, book in BOOKS.items() if book.sizing == "per_name"])
def test_per_name_default_budget_is_float(budget_parser, strategy):
    from backtest.research.csv_strategy_books import csv_run_kwargs_from_args

    args = budget_parser.parse_args(["--strategy", strategy])
    budget = csv_run_kwargs_from_args(args)["name_budget"]
    assert type(budget) is float
    assert budget == 1_000_000.0


@pytest.mark.parametrize("budget", ["0", "-1"])
def test_nonpositive_name_budget_rejected(budget_parser, budget):
    from backtest.research.csv_strategy_books import csv_run_kwargs_from_args

    args = budget_parser.parse_args(["--strategy", "version8", "--name-budget", budget])
    with pytest.raises(SystemExit, match="--name-budget must be positive"):
        csv_run_kwargs_from_args(args)


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
    from backtest.research.csv_ledger import InsufficientCashError
    from backtest.research.csv_simulate_loop import run_chase_due_day

    st = _money_state(per_name_hooks)
    pending = {}
    _pool_buy(st, per_name_hooks, ["600000.SH", "000001.SZ"], px=11, pending=pending)
    assert pending == {"600000.SH@20251103": (1_000_000, 0), "000001.SZ@20251103": (1_000_000, 0)}
    pending.pop("000001.SZ@20251103")
    if outcome == "held":
        _pool_buy(st, per_name_hooks, ["600000.SH"], day_i=1)
    elif outcome == "cash":
        st.cash = 500_000
    elif outcome == "shares":
        pending["600000.SH@20251103"] = (0, 0)

    def chase():
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

    if outcome == "cash":
        with pytest.raises(InsufficientCashError) as caught:
            chase()
        _assert_per_name_cash_error(
            caught.value, date="20251104", code="600000.SH", needed=1_001_000, available=500_000,
        )
        assert st.stats["chase_buy_fail_cash"] == 0
        assert not st.trades
        return
    chase()
    assert not pending
    assert st.daily_quota_used == 0
    if outcome == "held":
        assert st.stats["chase_skip_held"] == 0
        assert st.stats["add_lots"] == 0
        assert {t["position_id"] for t in st.trades} == {
            "600000.SH@20251103", "600000.SH@20251104",
        }
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


def test_resolve_daily_quota_pairs_topk_family_with_cash():
    from backtest.research.csv_strategy_books import resolve_daily_quota

    assert resolve_daily_quota("topk_dropout", None, cash_total=1e8) == 1e8
    assert resolve_daily_quota("topk", None, cash_total=5e7) == 5e7
    assert resolve_daily_quota("topk_score_exit", None, cash_total=1e8) == 1e8


def test_resolve_daily_quota_keeps_stock_pool_quota_default():
    from backtest.research.csv_strategy_books import resolve_daily_quota

    assert resolve_daily_quota("version8", None, cash_total=1e8) == 1_000_000.0
    assert (
        resolve_daily_quota("version12", None, cash_total=1e8, fallback_quota=2e6)
        == 2e6
    )


def test_resolve_daily_quota_explicit_flag_wins():
    from backtest.research.csv_strategy_books import resolve_daily_quota

    assert resolve_daily_quota("topk_dropout", 2e6, cash_total=1e8) == 2e6
    assert resolve_daily_quota("version8", 5e7, cash_total=1e8) == 5e7
