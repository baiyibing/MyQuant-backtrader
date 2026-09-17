import pandas as pd
import pytest

from backtest.research import unified_exit_modea as a
from backtest.research import unified_exit_modeb as b

CODE = "600998.SH"
SESS = ["20251023", "20251024", "20251027", "20251028"]
INST = a.Instance(CODE, "synthetic", SESS[0], 100., True)


def frames(rows):
    """Rows: (day, hm, high, low, close) or (day, hm, open, high, low, close)."""
    if rows and len(rows[0]) == 6:
        df = pd.DataFrame(rows, columns=["day", "hm", "open", "high", "low", "close"])
    else:
        df = pd.DataFrame(rows, columns=["day", "hm", "high", "low", "close"])
        if not df.empty:
            df["open"] = df["close"]
    df["ymd"] = df.pop("day").map(lambda i: SESS[i])
    return {CODE: df}


def daily(closes=(100., 100., 100., 100.)):
    return {CODE: pd.DataFrame({"close": closes, "open": closes}, index=pd.to_datetime(SESS))}


def run(rows, spec=a.StrategySpec(2, 3, 5, 5), **kw):
    return b.evaluate_exit_modeb(INST, spec, daily(), frames(rows), SESS, end=SESS[-1], **kw)


@pytest.mark.parametrize("opn,high,low,close,reason,fill", [
    (100, 106, 94, 94, "stop_loss", 94),
    (100, 106, 99, 106, "take_profit", 106),
    (94, 106, 94, 102, "stop_loss", 94),
    (106, 106, 99, 100, "take_profit", 106),
    (100, 101, 95, 95, "stop_loss", 95),
])
def test_thresholds_open_then_close_fill(opn, high, low, close, reason, fill):
    er = run([(1, 600, opn, high, low, close)])
    assert (er.reason, er.sell_price, er.sell_hm) == (reason, fill, 600)


def test_wick_only_does_not_trigger():
    er = run([(1, 600, 100, 106, 94, 102)])
    assert not er.is_trade and er.sell_price == 102


def test_open_stop_beats_later_close_tp():
    er = run([(1, 600, 94, 106, 94, 106)])
    assert (er.reason, er.sell_price) == ("stop_loss", 94)


def test_n1_intraday_counterexample():
    rows = [(1, 600, 100, 106, 100, 106), (1, 899, 100, 101, 99, 100)]
    early = run(rows, a.StrategySpec(2, 1, 5, 5))
    expiry = run(rows, a.StrategySpec(1, 1))
    assert early.sell_price == 106 and expiry.sell_price == 100
    assert early.sell_hm == 600 and expiry.sell_hm == 899


def test_lake_minutes_have_coverage_and_take_profit():
    minutes = frames([(1, 600, 100, 106, 100, 106), (1, 900, 100, 101, 99, 100)])
    coverage = b.minute_coverage([CODE], minutes)
    assert coverage["covered_codes"] == 1 and coverage["missing_codes"] == []
    er = b.evaluate_exit_modeb(INST, a.StrategySpec(2, 1, 5, 5),
                               daily(), minutes, SESS, end=SESS[-1])
    assert er.is_trade
    assert (er.reason, er.sell_price, er.sell_hm) == ("take_profit", 106, 600)


def test_expiry_no_daily_fallback_and_off_session_ignored():
    er = run([(2, 565, 200, 200, 1, 200), (2, 690, 101, 102, 100, 101),
              (2, 720, 200, 200, 1, 200), (2, 901, 200, 200, 1, 200)], a.StrategySpec(1, 1))
    assert (er.sell_date, er.sell_hm, er.sell_price, er.hold_sessions) == (SESS[2], 690, 101, 2)


def test_buy_day_unavailable_to_trigger_or_peak():
    er = run([(0, 600, 200, 300, 1, 200), (1, 600, 100, 101, 99, 100)], a.StrategySpec(3, 3, y=5))
    assert not er.is_trade and er.sell_price == 100


def test_trailing_peak_close_not_high_and_halt_freezes():
    er = run([(1, 600, 104, 200, 99, 104), (3, 600, 98, 100, 97, 98)], a.StrategySpec(3, 3, y=5))
    assert er.reason == "trailing" and er.hold_sessions == 3


def test_limit_down_blocks_whole_day_then_rechecks_rule():
    er = run([(1, 600, 100, 100, 89, 90), (1, 840, 100, 110, 99, 106),
              (2, 600, 100, 106, 100, 106)])
    assert er.sell_date == SESS[2] and er.reason == "take_profit"


def test_limit_down_open_blocks_later_close():
    er = run([(1, 600, 90, 100, 89, 90), (1, 840, 100, 110, 99, 106),
              (2, 600, 100, 106, 100, 106)])
    assert er.sell_date == SESS[2] and er.reason == "take_profit"


def test_limit_down_expiry_postpones():
    er = run([(1, 900, 90, 91, 89, 90), (2, 890, 98, 99, 97, 98)], a.StrategySpec(1, 1))
    assert er.sell_date == SESS[2] and er.reason == "n_expire"


def test_hold_end_marks_last_minute_without_sell_fee():
    er = run([(1, 600, 103, 200, 1, 103)], a.StrategySpec(0, None))
    assert not er.is_trade and er.sell_date == SESS[1]
    assert er.pnl == pytest.approx(10000 * 103 - 1001000)


def test_all_missing_minutes_freezes_at_buy():
    er = run([], a.StrategySpec(1, 1))
    assert er.sell_date == INST.list_date and er.sell_price == INST.buy_price
    assert not er.is_trade
