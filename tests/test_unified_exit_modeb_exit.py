import pandas as pd
import pytest

from backtest.research import unified_exit_modea as a
from backtest.research import unified_exit_modeb as b

CODE = "600998.SH"
SESS = ["20251023", "20251024", "20251027", "20251028"]
INST = a.Instance(CODE, "synthetic", SESS[0], 100., True)


def frames(rows):
    """Rows: session index, hm (minutes since midnight), high, low, close (invented OHLC)."""
    df = pd.DataFrame(rows, columns=["day", "hm", "high", "low", "close"])
    df["ymd"] = df.pop("day").map(lambda i: SESS[i])
    return {CODE: df}


def daily(closes=(100., 100., 100., 100.)):
    return {CODE: pd.DataFrame({"close": closes, "open": closes}, index=pd.to_datetime(SESS))}


def run(rows, spec=a.StrategySpec(2, 3, 5, 5), **kw):
    return b.evaluate_exit_modeb(INST, spec, daily(), frames(rows), SESS, end=SESS[-1], **kw)


@pytest.mark.parametrize("high,low,close,reason", [
    (106, 94, 102, "stop_loss"), (106, 99, 102, "take_profit"),
    (102, 94, 97, "stop_loss"), (105, 99, 101, "take_profit"),
    (101, 95, 98, "stop_loss"),
])
def test_thresholds_and_minute_close_fill(high, low, close, reason):
    er = run([(1, 600, high, low, close)])
    assert (er.reason, er.sell_price, er.sell_hm) == (reason, close, 600)


def test_n1_intraday_counterexample():
    rows = [(1, 600, 106, 100, 103), (1, 899, 101, 99, 100)]
    early = run(rows, a.StrategySpec(2, 1, 5, 5))
    expiry = run(rows, a.StrategySpec(1, 1))
    assert early.sell_price == 103 and expiry.sell_price == 100
    assert early.sell_hm == 600 and expiry.sell_hm == 899


def test_lake_minutes_have_coverage_and_take_profit():
    minutes = frames([(1, 600, 106, 100, 103), (1, 900, 101, 99, 100)])
    coverage = b.minute_coverage([CODE], minutes)
    assert coverage["covered_codes"] == 1 and coverage["missing_codes"] == []
    er = b.evaluate_exit_modeb(INST, a.StrategySpec(2, 1, 5, 5),
                               daily(), minutes, SESS, end=SESS[-1])
    assert er.is_trade
    assert (er.reason, er.sell_price, er.sell_hm) == ("take_profit", 103, 600)


def test_expiry_no_daily_fallback_and_off_session_ignored():
    er = run([(2, 565, 200, 1, 200), (2, 690, 102, 100, 101),
              (2, 720, 200, 1, 200), (2, 901, 200, 1, 200)], a.StrategySpec(1, 1))
    assert (er.sell_date, er.sell_hm, er.sell_price, er.hold_sessions) == (SESS[2], 690, 101, 2)


def test_buy_day_unavailable_to_trigger_or_peak():
    er = run([(0, 600, 300, 1, 200), (1, 600, 101, 99, 100)], a.StrategySpec(3, 3, y=5))
    assert not er.is_trade and er.sell_price == 100


def test_trailing_peak_close_not_high_and_halt_freezes():
    er = run([(1, 600, 200, 99, 104), (3, 600, 100, 97, 98)], a.StrategySpec(3, 3, y=5))
    assert er.reason == "trailing" and er.hold_sessions == 3


def test_limit_down_blocks_whole_day_then_rechecks_rule():
    er = run([(1, 600, 100, 89, 90), (1, 840, 110, 99, 105),
              (2, 600, 106, 100, 103)])
    assert er.sell_date == SESS[2] and er.reason == "take_profit"


def test_limit_down_expiry_postpones():
    er = run([(1, 900, 91, 89, 90), (2, 890, 99, 97, 98)], a.StrategySpec(1, 1))
    assert er.sell_date == SESS[2] and er.reason == "n_expire"


def test_hold_end_marks_last_minute_without_sell_fee():
    er = run([(1, 600, 200, 1, 103)], a.StrategySpec(0, None))
    assert not er.is_trade and er.sell_date == SESS[1]
    assert er.pnl == pytest.approx(10000 * 103 - 1001000)


def test_all_missing_minutes_freezes_at_buy():
    er = run([], a.StrategySpec(1, 1))
    assert er.sell_date == INST.list_date and er.sell_price == INST.buy_price
    assert not er.is_trade
