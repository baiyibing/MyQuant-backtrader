"""策略 5 的纯函数契约。"""

from types import SimpleNamespace

from backtest.research import strategy5_rules as rules


def test_target_hit_and_miss():
    assert rules.take_profit_reason(10.20, 10.0, 99.0, 1) == "profit_take:target"
    assert rules.take_profit_reason(10.19, 10.0, 99.0, 1) is None
    assert rules.take_profit_reason(9.0, 10.0, 99.0, 1) is None


def test_buy_day_has_no_take_profit():
    assert rules.take_profit_reason(12.0, 10.0, 12.0, 0) is None


def test_record_params_tolerates_none_stop():
    st = SimpleNamespace(stats={})
    rules.record_strategy5_params(st, stop_pct=None)
    assert st.stats == {
        "sell_book": "v5",
        "stop_pct": None,
        "profit_target": 0.02,
        "force_sell_hm": 890,
    }
