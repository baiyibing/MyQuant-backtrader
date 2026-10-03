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
                level=1.0,
            )
        assert raised.value.missing_field == entry.missing_field
        assert raised.value.name == entry.name
    # 一个 score 比不出整日 bottom / SX0，不把单分当成卖点。
    assert seen == {"topk_dropout": "score", "topk_score_exit": "score"}


@pytest.mark.parametrize("name", wired_names())
def test_wired_strategy_skips_a_quiet_bar(name: str):
    # high 只抬到 10.01，回撤不到 50%；low 9.96 不触及 2% 止损。
    # level/stage 传了也不该在这根上卖。
    result = invoke_minute_strategy(
        name,
        OhlcBar(10.0, 10.01, 9.96, 10.008),
        cost=10.0,
        peak=10.0,
        n_days=1,
        level=9.0,
        stage="trial",
        entry_a=10.0,
    )
    assert result.decision == "skip"
    assert result.fill_price is None


@pytest.mark.parametrize(
    "name",
    ["version1", "version2", "version3", "version6", "version6_1", "version8_6"],
)
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


# 每本书一根会卖的 K、一根不卖的 K。原因字符串来自策略书，不新造。
_FILL = [
    ("version3", OhlcBar(11.5, 12.2, 11.0, 12.0), {}, "fill", 12.0, "profit_take:target"),
    ("version4", OhlcBar(10.2, 10.3, 10.0, 10.04), {"level": 10.5}, "fill", 10.04, "ma_signal:MA5"),
    ("version5", OhlcBar(10.1, 10.3, 10.0, 10.2), {}, "fill", 10.2, "profit_take:target"),
    ("version6", OhlcBar(10.4, 10.5, 10.05, 10.10), {"peak": 10.5}, "fill", 10.10, "trail:band:lt6"),
    ("version6_1", OhlcBar(10.5, 11.0, 10.0, 10.0), {"peak": 11.0}, "fill", 10.0, "trail:ladder:10"),
    ("version8", OhlcBar(10.9, 11.0, 10.5, 10.7), {"peak": 11.0}, "fill", 10.7, "trail:max101_80"),
    ("version8_1", OhlcBar(10.5, 11.0, 10.1, 10.15), {"peak": 11.0}, "fill", 10.15, "trail:band:2"),
    ("version8_2", OhlcBar(10.2, 10.3, 10.0, 10.05), {"peak": 10.3, "n_days": 2}, "fill", 10.05, "trail:band:1"),
    ("version8_3", OhlcBar(10.5, 11.0, 10.1, 10.15), {"peak": 11.0}, "fill", 10.15, "trail:band:2"),
    ("version8_4", OhlcBar(11.0, 12.1, 10.5, 12.0), {}, "fill", 12.0, "profit_take:target"),
    ("version8_5", OhlcBar(10.2, 10.5, 10.1, 10.4), {}, "fill", 10.4, "profit_take:target"),
    ("version8_6", OhlcBar(10.6, 11.0, 10.4, 10.5), {"peak": 11.0}, "fill", 10.5, "trail:max1004_80"),
    ("version9", OhlcBar(10.0, 10.05, 9.95, 10.04), {"n_days": 20}, "fill", 10.04, "force_sell:max_hold"),
    ("version10", OhlcBar(10.5, 11.0, 10.2, 10.30), {"peak": 11.0}, "fill", 10.30, "trail:T+1"),
    ("version11", OhlcBar(10.2, 10.3, 10.0, 10.0), {"level": 10.5}, "fill", 10.0, "ma_signal:SMA5"),
    ("version12", OhlcBar(10.2, 10.3, 10.0, 10.0), {"level": 10.5}, "fill", 10.0, "ma_signal:MA10-stop"),
    ("version7", OhlcBar(8.9, 9.2, 8.8, 9.1), {"stage": "trial", "entry_a": 10.0}, "fill", 8.9, "stop:trial_a090"),
    (
        "topk_app_dropout",
        OhlcBar(9.6, 9.7, 9.3, 9.4),
        {"stage": "four"},
        "fill",
        9.4,
        "stop:four_avg095",
    ),
]

_SKIP = [
    ("version4", OhlcBar(10.2, 10.3, 10.0, 10.04), {"level": 9.0}),
    ("version4", OhlcBar(10.0, 10.1, 9.9, 10.0), {"level": 10.0}),
    ("version6", OhlcBar(10.4, 10.5, 10.3, 10.40), {"peak": 10.5}),
    ("version6_1", OhlcBar(10.5, 11.0, 10.4, 10.50), {"peak": 11.0}),
    ("version8", OhlcBar(10.9, 11.0, 10.85, 10.9), {"peak": 11.0}),
    ("version8_2", OhlcBar(10.2, 10.3, 10.0, 10.05), {"peak": 10.3, "n_days": 1}),
    ("version9", OhlcBar(10.0, 10.05, 9.95, 10.04), {"n_days": 19}),
    ("version11", OhlcBar(10.2, 10.3, 10.0, 10.0), {"level": 9.5}),
    ("version12", OhlcBar(11.0, 11.1, 10.9, 11.0), {"level": 9.0, "n_days": 20}),
    ("version7", OhlcBar(9.5, 9.6, 8.5, 9.4), {"stage": "trial", "entry_a": 10.0}),
    ("version7", OhlcBar(8.9, 9.2, 8.8, 9.1), {"stage": "trial", "entry_a": 10.0, "session_open": False}),
]


@pytest.mark.parametrize("name,bar,kwargs,decision,price,reason", _FILL)
def test_each_wired_book_fills_on_its_rule(name, bar, kwargs, decision, price, reason):
    result = invoke_minute_strategy(name, bar, cost=10.0, peak=kwargs.get("peak", 10.0), **{k: v for k, v in kwargs.items() if k != "peak"})
    assert result.decision == decision
    assert result.fill_price == pytest.approx(price)
    assert result.reason == reason


@pytest.mark.parametrize("name,bar,kwargs", _SKIP)
def test_each_wired_book_skips_when_its_rule_does_not_hit(name, bar, kwargs):
    result = invoke_minute_strategy(
        name,
        bar,
        cost=10.0,
        peak=kwargs.get("peak", 10.0),
        **{k: v for k, v in kwargs.items() if k != "peak"},
    )
    assert result.decision == "skip"
    assert result.fill_price is None


def test_version12_hold20_fills_when_ma10_is_not_hit():
    result = invoke_minute_strategy(
        "version12",
        OhlcBar(10.5, 10.6, 10.4, 10.5),
        cost=10.0,
        peak=10.0,
        n_days=20,
        level=9.0,
    )
    assert result.decision == "fill"
    assert result.fill_price == 10.5
    assert result.reason == "force_sell:hold20_below10"


def test_version3_stop_beats_profit_target_on_the_same_bar():
    result = invoke_minute_strategy(
        "version3",
        OhlcBar(9.5, 12.5, 9.4, 12.2),
        cost=10.0,
        peak=10.0,
    )
    assert result.decision == "fill"
    assert result.fill_price == 9.5
    assert result.reason == "stop_loss:gap_open"


def test_version5_next_bar_moves_the_target_fill():
    result = invoke_minute_strategy(
        "version5",
        OhlcBar(10.1, 10.3, 10.0, 10.2),
        cost=10.0,
        peak=10.0,
        timing="next_bar",
        next_bar=OhlcBar(10.05, 10.2, 10.0, 10.1),
    )
    assert result.decision == "fill"
    assert result.fill_price == 10.05
    assert result.reason == "profit_take:target:next_open"


def test_level_and_stage_are_required():
    bar = OhlcBar(10.0, 10.1, 9.9, 10.0)
    with pytest.raises(ValueError, match="sma5"):
        invoke_minute_strategy("version4", bar, cost=10.0, peak=10.0)
    with pytest.raises(ValueError, match="sma5"):
        invoke_minute_strategy("version11", bar, cost=10.0, peak=10.0)
    with pytest.raises(ValueError, match="ma10"):
        invoke_minute_strategy("version12", bar, cost=10.0, peak=10.0)
    with pytest.raises(ValueError, match="stage"):
        invoke_minute_strategy("version7", bar, cost=10.0, peak=10.0)
    with pytest.raises(ValueError, match="stage"):
        invoke_minute_strategy("topk_app_dropout", bar, cost=10.0, peak=10.0)
