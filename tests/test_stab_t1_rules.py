"""stab_t1 书规则与钩子契约测试。"""

from __future__ import annotations

import argparse

from backtest.research import stab_t1_rules
from backtest.research.csv_strategy_books import apply_csv_strategy, get_book


def test_close_clear_reason_first_sellable_close():
    # T+0 不卖；T+1（首个可卖收盘）触发。
    assert stab_t1_rules.close_clear_reason(10.0, 10.5, 0) is None
    assert stab_t1_rules.close_clear_reason(10.0, 10.5, 1) == "stab_t1:exit"
    assert stab_t1_rules.close_clear_reason(9.0, 9.5, 3) == "stab_t1:exit"


def test_take_profit_stub_never_fires():
    # 分钟引擎逐 bar 评估 take_profit，必须恒 None（真逻辑在 close_clear）。
    for px, cost, peak, n in ((10.0, 9.0, 11.0, 1), (8.0, 9.0, 9.5, 1), (10.0, 9.0, 11.0, 5)):
        assert stab_t1_rules.never_take_profit(px, cost, peak, n) is None


def test_apply_stab_t1_hooks():
    hooks = apply_csv_strategy("stab_t1")
    assert hooks["name"] == "stab_t1"
    assert hooks["sizing"] == "daily_quota"
    assert hooks["stop_pct"] is None  # 纯信号 v0：无止损
    assert hooks["daily_same_bar_prefixes"] == ("stab_t1",)  # 日线 T+1 收盘 same-bar 成交
    assert hooks["close_clear"](10.0, 10.5, 1) == "stab_t1:exit"
    assert hooks["take_profit"](10.0, 9.0, 11.0, 1) is None
    assert callable(hooks["record_params"])


def test_stab_t1_book_registration():
    book = get_book("stab_t1")
    assert book.allow_add is False
    assert book.peak_gap_min == 0
    assert "stab_t1" in (book.name, *book.aliases)


def test_stab_t1_run_kwargs_passes_through():
    ns = argparse.Namespace(stop_pct=None)
    assert get_book("stab_t1").run_kwargs(ns) == {"strategy": "stab_t1", "stop_pct": None}
