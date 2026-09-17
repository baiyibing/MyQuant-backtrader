from datetime import date, timedelta

import pandas as pd

from backtest.research import strategy8_rules as s8
from backtest.research import unified_exit_modea as a
from backtest.research import unified_exit_modeb as b

CODE = "600998.SH"
OTHER = "000089.SZ"
SESS = [f"202510{d:02d}" for d in range(23, 32)]
INST = a.Instance(CODE, "synthetic", SESS[0], 100.0, True)
CHAMP = a.StrategySpec(2, 10, 10, None)
SSE = a.StrategySpec(6, 10, 10, None)


def frames(rows, code=CODE):
    df = pd.DataFrame(rows, columns=["day", "hm", "open", "high", "low", "close"])
    df["ymd"] = df.pop("day").map(lambda i: SESS[i])
    return {code: df}


def daily(code=CODE, n=None):
    n = n or len(SESS)
    px = [100.0] * n
    return {code: pd.DataFrame({"close": px, "open": px}, index=pd.to_datetime(SESS[:n]))}


def run(rows, spec=SSE, index_block=None, **kw):
    return b.evaluate_exit_modeb(
        INST, spec, daily(), frames(rows), SESS, end=SESS[-1],
        index_block=index_block, **kw,
    )


def test_overlay_label_is_marketwide_champ_plus_gate():
    assert SSE.label() == "r2_x10_yinf_n10_sse_ma10"
    assert SSE.label() == a.StrategySpec(6, 10, 10, None).label()
    assert SSE.label() != CHAMP.label()


def test_block_ymd_keeps_v8_lagged_two_below_gate():
    days = [date(2025, 10, 23) + timedelta(days=i) for i in range(15)]
    values = [100.0] * 9 + [90.0, 89.0, 120.0, 120.0, 120.0, 120.0]
    gate = s8.build_sse_ma10_block_new(dict(zip(days, values)))
    ymd = b._block_ymd(gate)
    assert ymd[days[11].strftime("%Y%m%d")] is True
    assert ymd[days[12].strftime("%Y%m%d")] is False


def test_tape_break_sells_at_open_same_day():
    rows = [(1, 600, 101, 102, 100, 101), (2, 600, 102, 103, 101, 102)]
    er = run(rows, index_block={SESS[1]: True})
    assert er.is_trade
    assert (er.reason, er.sell_price, er.sell_date, er.sell_hm) == (
        "force_sell:sse_ma10", 101, SESS[1], 600,
    )


def test_missing_session_does_not_block():
    rows = [(1, 600, 101, 102, 100, 101)]
    er = run(rows, index_block={})
    champ = run(rows, CHAMP, index_block={})
    assert (er.reason, er.sell_price, er.sell_date) == (
        champ.reason, champ.sell_price, champ.sell_date,
    )


def test_open_tp_beats_index():
    er = run([(1, 600, 111, 111, 100, 111)], index_block={SESS[1]: True})
    assert (er.reason, er.sell_price) == ("take_profit", 111)


def test_index_at_open_does_not_wait_for_close_tp():
    er = run([(1, 600, 100, 111, 99, 111)], index_block={SESS[1]: True})
    assert (er.reason, er.sell_price) == ("force_sell:sse_ma10", 100)
    assert run([(1, 600, 100, 111, 99, 111)], CHAMP).reason == "take_profit"


def test_limit_down_open_defers_index():
    rows = [(1, 600, 90, 90, 90, 90), (2, 600, 101, 102, 100, 101)]
    er = run(rows, index_block={SESS[1]: True, SESS[2]: True})
    assert (er.reason, er.sell_date, er.sell_price) == ("force_sell:sse_ma10", SESS[2], 101)


def test_same_gate_exits_every_name_on_the_same_session():
    rows = [(1, 600, 101, 102, 100, 101)]
    insts = [
        INST,
        a.Instance(OTHER, "synthetic", SESS[0], 100.0, True),
    ]
    minutes = {**frames(rows), **frames(rows, OTHER)}
    bars = {**daily(), **daily(OTHER)}
    matrix = b.evaluate_matrix(
        insts, [SSE], bars, minutes, SESS, end=SESS[-1],
        index_block={SESS[1]: True},
    )
    exits = matrix[SSE.label()]
    assert {er.reason for er in exits.values()} == {"force_sell:sse_ma10"}
    assert {er.sell_date for er in exits.values()} == {SESS[1]}


def test_fast_matches_ref_index_overlay():
    cases = [
        ([(1, 600, 101, 102, 100, 101)], {SESS[1]: True}),
        ([(1, 600, 111, 111, 100, 111)], {SESS[1]: True}),
        ([(1, 600, 100, 111, 99, 111)], {SESS[1]: True}),
        ([(1, 600, 90, 90, 90, 90), (2, 600, 101, 102, 100, 101)], {SESS[1]: True, SESS[2]: True}),
        ([(1, 600, 101, 102, 100, 101)], {}),
    ]
    for rows, gate in cases:
        fast = run(rows, index_block=gate, impl="fast")
        ref = run(rows, index_block=gate, impl="ref")
        assert (fast.reason, fast.sell_price, fast.sell_date, fast.is_trade) == (
            ref.reason, ref.sell_price, ref.sell_date, ref.is_trade
        )
