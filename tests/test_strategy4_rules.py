from backtest.research import strategy4_rules as rules


def test_sma_asof_uses_tail_and_needs_full_window():
    assert rules.sma_asof([1.0, 2.0, 3.0], 2) == 2.5
    assert rules.sma_asof([1.0, 2.0], 3) is None


def test_buy_gate_compares_price_with_yesterday_sma10():
    closes = [10.0] * 10
    assert rules.buy_gate("000001.SZ", 10.0, "20260101", closes)
    assert not rules.buy_gate("000001.SZ", 9.99, "20260101", closes)
    assert not rules.buy_gate("000001.SZ", 99.0, "20260101", closes[:9])


def test_sell_gate_compares_price_with_yesterday_sma5():
    closes = [10.0] * 5
    assert rules.sell_gate("000001.SZ", 9.99, "20260101", closes) == "ma_signal:MA5"
    assert rules.sell_gate("000001.SZ", 10.0, "20260101", closes) is None
    assert rules.sell_gate("000001.SZ", 1.0, "20260101", closes[:4]) is None


def test_record_params_tolerates_none_stop():
    class State:
        stats = {}

    rules.record_strategy4_params(State(), stop_pct=None)
    assert State.stats["sell_book"] == "v4"
    assert State.stats["stop_pct"] is None
