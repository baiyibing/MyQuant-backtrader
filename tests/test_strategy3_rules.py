"""策略 3 的纯函数契约。"""

from types import SimpleNamespace

from backtest.research import strategy3_rules as rules


def test_target_is_four_argument_t1_rule():
    assert rules.take_profit_reason(12.0, 10.0, 99.0, 1) == "profit_take:target"
    assert rules.take_profit_reason(11.99, 10.0, 99.0, 1) is None
    assert rules.take_profit_reason(12.0, 10.0, 99.0, 0) is None


def test_reserve_window_revalues_and_clears():
    assert rules.reserve_step_minute(reserved=False, hm=575, is_limit_up=True) == (
        True,
        None,
    )
    assert rules.reserve_step_minute(reserved=True, hm=576, is_limit_up=False) == (
        False,
        None,
    )


def test_reserved_open_board_after_window_sells_and_clears():
    assert rules.reserve_step_minute(reserved=True, hm=581, is_limit_up=False) == (
        False,
        "open_board",
    )
    assert rules.reserve_step_minute(reserved=True, hm=581, is_limit_up=True) == (
        True,
        None,
    )


def test_record_params():
    st = SimpleNamespace(stats={})
    rules.record_strategy3_params(st, stop_pct=0.03)
    assert st.stats == {
        "sell_book": "v3",
        "stop_pct": 0.03,
        "profit_target": 0.20,
        "reserve_limit_up": True,
    }
