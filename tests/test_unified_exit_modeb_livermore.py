import pandas as pd

from backtest.research import livermore_exit_rules as s8
from backtest.research import unified_exit_modea as a
from backtest.research import unified_exit_modeb as b

CODE = "600998.SH"
# Buy on first session; T+1.. need 8 market days after buy for stale.
SESS = [f"202510{d:02d}" for d in range(23, 32)]  # 23..31 → 9 calendar labels
INST = a.Instance(CODE, "synthetic", SESS[0], 100., True)
L1 = a.StrategySpec(4, 8, 10, 10)
L2 = a.StrategySpec(4, 8, None, 10)
L3 = a.StrategySpec(5, 8, None, 10)


def frames(rows):
    df = pd.DataFrame(rows, columns=["day", "hm", "open", "high", "low", "close"])
    df["ymd"] = df.pop("day").map(lambda i: SESS[i])
    return {CODE: df}


def daily(n=None):
    n = n or len(SESS)
    px = [100.0] * n
    return {CODE: pd.DataFrame({"close": px, "open": px}, index=pd.to_datetime(SESS[:n]))}


def run(rows, spec, **kw):
    return b.evaluate_exit_modeb(INST, spec, daily(), frames(rows), SESS, end=SESS[-1], **kw)


def test_labels_are_marketwide_not_per_name():
    assert L1.label() == "livermore_l1_x10_stale8_y10"
    assert L2.label() == "livermore_l2_stale8_y10"
    assert L3.label() == "livermore_l3_stale8_y10"
    assert L1.label() == a.StrategySpec(4, 8, 10, 10).label()


def test_l1_stale_clears_unarmed_on_day_8():
    rows = [(d, 600, 100, 101, 99, 100) for d in range(1, 9)]
    er = run(rows, L1)
    assert er.is_trade and er.reason == "force_sell:stale"
    assert er.hold_sessions == 8 and er.sell_price == 100


def test_l1_armed_is_not_cut_by_stale():
    rows = [(1, 600, 107, 107, 100, 107)]
    rows += [(d, 600, 104, 104, 103, 104) for d in range(2, 9)]
    er = run(rows, L1)
    assert er.reason == "mark_end"
    assert er.hold_sessions == 8


def test_l1_hard_tp_still_fires():
    er = run([(1, 600, 111, 111, 100, 111)], L1)
    assert (er.reason, er.sell_price) == ("take_profit", 111)


def test_l2_uses_band_not_ten_percent_tp():
    # Peak 107 is band 2; close 103 > buy*1.02 so no trail; not +10% TP.
    rows = [(1, 600, 107, 107, 100, 107), (2, 600, 103, 103, 102, 103)]
    er = run(rows, L2)
    assert not er.is_trade or er.reason != "take_profit"
    # Drop through 1.02 after arm → trail:band:2
    rows[-1] = (2, 600, 101.5, 101.5, 101, 101.5)
    er = run(rows, L2)
    assert er.reason == "trail:band:2" and er.sell_price == 101.5


def test_l2_stop_ten_still_first():
    # Main-board 10% stop sits on the limit-down line; use a 20% board.
    inst = a.Instance("300001.SZ", "synthetic", SESS[0], 100., True)
    minutes = frames([(1, 600, 89, 100, 89, 89)])
    bars = {"300001.SZ": daily()[CODE]}
    minutes = {"300001.SZ": minutes[CODE]}
    er = b.evaluate_exit_modeb(inst, L2, bars, minutes, SESS, end=SESS[-1])
    assert (er.reason, er.sell_price) == ("stop_loss", 89)


def test_fast_matches_ref_livermore():
    cases = [
        ([(d, 600, 100, 101, 99, 100) for d in range(1, 9)], L1),
        ([(1, 600, 107, 107, 100, 107)] + [(d, 600, 104, 104, 103, 104) for d in range(2, 9)], L1),
        ([(1, 600, 107, 107, 100, 107), (2, 600, 101.5, 101.5, 101, 101.5)], L2),
        ([(1, 600, 111, 111, 100, 111)], L1),
        ([(1, 600, 111, 111, 100, 111)] + [(d, 600, 108, 108, 107, 108) for d in range(2, 9)], L3),
        ([(d, 600, 100, 101, 99, 100) for d in range(1, 9)], L3),
    ]
    for rows, spec in cases:
        fast = run(rows, spec, impl="fast")
        ref = run(rows, spec, impl="ref")
        assert (fast.reason, fast.sell_price, fast.sell_date, fast.is_trade) == (
            ref.reason, ref.sell_price, ref.sell_date, ref.is_trade
        )


def test_l3_lets_armed_run_past_ten_and_band2():
    rows = [(1, 600, 111, 111, 100, 111)]
    rows += [(d, 600, 108, 108, 107, 108) for d in range(2, 9)]
    er = run(rows, L3)
    assert er.reason == "mark_end"
    assert er.sell_price == 108
    assert run(rows, L1).reason == "take_profit"
    assert run([(1, 600, 107, 107, 100, 107), (2, 600, 101.5, 101.5, 101, 101.5)], L2).reason == "trail:band:2"
    assert run([(1, 600, 107, 107, 100, 107), (2, 600, 101.5, 101.5, 101, 101.5)], L3).reason == "mark_end"


def test_l3_still_stales_unarmed():
    rows = [(d, 600, 100, 101, 99, 100) for d in range(1, 9)]
    er = run(rows, L3)
    assert er.reason == "force_sell:stale" and er.hold_sessions == 8


def test_l2_reason_matches_frozen_livermore():
    cost, peak, px = 100.0, 107.0, 101.5
    assert s8.take_profit_reason(px, cost, peak, 2) == "trail:band:2"
    assert s8.never_armed(100.0, 105.0)
    assert not s8.never_armed(100.0, 107.0)
