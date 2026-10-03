"""每本分钟策略要么能被扫线调用，要么缺一个字段。合成 K，不读湖。"""

from pathlib import Path

import pytest

from backtest.research.bar_scan_exit import OhlcBar
from backtest.research.csv_strategy_books import csv_strategy_names
from backtest.research.minute_true_core_wire import (
    EXTRA_MINUTE_STRATEGIES,
    MinuteStrategyNotOnBarScan,
    blocked_entries,
    invoke_minute_strategy,
    minute_strategy_entries,
    minute_strategy_names,
    wired_names,
)

ROOT = Path(__file__).resolve().parents[1]


def test_entries_are_every_minute_cli_strategy():
    names = minute_strategy_names()
    assert names == csv_strategy_names() + EXTRA_MINUTE_STRATEGIES
    assert [entry.name for entry in minute_strategy_entries()] == list(names)
    assert set(wired_names()).isdisjoint(entry.name for entry in blocked_entries())
    assert set(wired_names()) | {entry.name for entry in blocked_entries()} == set(names)


def test_old_minute_entry_is_still_present():
    text = (ROOT / "backtest/research/csv_minute_backtest.py").read_text(encoding="utf-8")
    assert "def scan_held_day_python(" in text
    v7 = (ROOT / "backtest/research/csv_minute_backtest_v7.py").read_text(encoding="utf-8")
    assert "def simulate_v7(" in v7
    app = (ROOT / "backtest/research/csv_minute_backtest_topk_app_dropout.py").read_text(
        encoding="utf-8"
    )
    assert "topk_app_dropout" in app


def test_blocked_names_each_have_one_field():
    seen: dict[str, str] = {}
    for entry in blocked_entries():
        assert entry.missing_field
        assert entry.missing_field not in {"", "stop_pct", "drawdown_take_profit"}
        seen[entry.name] = entry.missing_field
        with pytest.raises(MinuteStrategyNotOnBarScan) as raised:
            invoke_minute_strategy(
                entry.name,
                OhlcBar(10.0, 10.2, 9.9, 10.1),
                cost=10.0,
                peak=10.0,
            )
        assert raised.value.missing_field == entry.missing_field
        assert raised.value.name == entry.name
    assert seen["version7"] == "stage"
    assert seen["topk_app_dropout"] == "stage"
    assert seen["topk_dropout"] == "score"
    assert seen["version12"] == "ma10"
    assert seen["version4"] == "sma5"


@pytest.mark.parametrize("name", wired_names())
def test_wired_strategy_skips_a_quiet_bar(name: str):
    # 止损 2%。low 9.90 未触及 9.80；high 只到 10.05，回撤 20%，不到 50%。
    result = invoke_minute_strategy(
        name,
        OhlcBar(10.0, 10.05, 9.95, 10.04),
        cost=10.0,
        peak=10.0,
        n_days=1,
    )
    assert result.decision == "skip"
    assert result.fill_price is None


@pytest.mark.parametrize("name", wired_names())
def test_wired_strategy_gap_fills_at_open(name: str):
    result = invoke_minute_strategy(
        name,
        OhlcBar(9.50, 9.70, 9.40, 9.60),
        cost=10.0,
        peak=10.0,
        n_days=1,
        timing="same_bar",
    )
    assert result.decision == "fill"
    assert result.fill_price == 9.50
    assert result.reason == "stop_loss:gap_open"


def test_version2_uses_hold_day_drawdown_inside_the_scan():
    # 峰值 12、收盘 11.70：回撤 15%。T+1 阈值 50% 跳过；T+5 阈值 10% 按收盘成交。
    bar = OhlcBar(11.90, 12.00, 11.50, 11.70)
    first = invoke_minute_strategy("version2", bar, cost=10.0, peak=12.0, n_days=1)
    assert first.decision == "skip"
    later = invoke_minute_strategy("version2", bar, cost=10.0, peak=12.0, n_days=5)
    assert later.decision == "fill"
    assert later.fill_price == 11.70
    assert later.reason == "profit_take:drawdown:10"
    same = invoke_minute_strategy("version1", bar, cost=10.0, peak=12.0, n_days=5)
    assert same.decision == "skip"


def test_version1_drawdown_fills_at_close():
    # (12-11)/(12-10) = 50%，按收盘成交。
    result = invoke_minute_strategy(
        "version1",
        OhlcBar(11.50, 12.00, 10.80, 11.00),
        cost=10.0,
        peak=12.0,
        n_days=1,
    )
    assert result.decision == "fill"
    assert result.fill_price == 11.00
    assert result.reason == "profit_take:drawdown:50"


def test_next_bar_timing_is_passed_through():
    result = invoke_minute_strategy(
        "version1",
        OhlcBar(9.50, 9.70, 9.40, 9.60),
        cost=10.0,
        peak=10.0,
        timing="next_bar",
        next_bar=OhlcBar(9.40, 9.55, 9.30, 9.50),
    )
    assert result.decision == "fill"
    assert result.fill_price == 9.40
    assert result.reason == "stop_loss:gap_open:next_open"


def test_unsellable_bar_is_refused():
    with pytest.raises(ValueError, match="n_days"):
        invoke_minute_strategy(
            "version1",
            OhlcBar(9.50, 9.70, 9.40, 9.60),
            cost=10.0,
            peak=10.0,
            n_days=0,
        )
