from datetime import date

from backtest.research.csv_simulate_loop import init_sim_state, run_pool_buys_day
from backtest.research.csv_strategy_books import apply_csv_strategy
from backtest.research.strategy8_rules import lot_budget, may_add


def _hooks(**extra):
    return apply_csv_strategy("version8", **extra)


def _state(hooks, cash=21_000_000):
    return init_sim_state(hooks, total_cash=cash, bars_loaded=2, pool_days={})[0]


def _buy(st, hooks, codes, *, px=10.0, day="2025-11-03", ds="20251103", day_i=0):
    run_pool_buys_day(
        st, {}, day_i=day_i, day=day, ds=ds, pool_days={ds: codes},
        daily_quota=1_000_000, names={}, allow_add=hooks["allow_add"],
        buy_gate=None, buy_quote_for=lambda code: (px, [px]),
        sizing=hooks["sizing"], name_budget=hooks["name_budget"],
        allow_new_name=hooks.get("allow_new_name"),
        add_gate=hooks.get("add_gate"),
        name_lot_budget=hooks.get("name_lot_budget"),
    )


def test_book_wires_add_and_probe_helpers():
    hooks = _hooks()
    assert hooks["add_gate"] is may_add
    assert hooks["name_lot_budget"] is lot_budget
    assert hooks["allow_new_name"] is None


def test_probe_lot_is_half_name_budget():
    hooks = _hooks()
    st = _state(hooks)
    _buy(st, hooks, ["600000.SH"])
    assert st.trades[0]["notional"] == 500_000
    assert st.stats["buys"] == 1


def test_index_gate_blocks_every_name_the_same_day():
    blocked = date(2025, 11, 3)
    hooks = _hooks(index_block_new={blocked: True})
    st = _state(hooks)
    _buy(st, hooks, ["600000.SH", "000001.SZ"], day=blocked)
    assert st.stats["buys"] == 0
    assert st.stats["skip_index_gate"] == 2


def test_add_gate_blocks_unarmed_second_lot():
    hooks = _hooks()
    st = _state(hooks)
    _buy(st, hooks, ["600000.SH"], px=10.0)
    assert st.positions["600000.SH"][0].peak == 10.0
    _buy(st, hooks, ["600000.SH"], px=10.20, day="2025-11-04", ds="20251104", day_i=1)
    assert st.stats["add_lots"] == 0
    assert st.stats["skip_add_loser"] == 1


def test_add_gate_allows_armed_winner():
    hooks = _hooks()
    st = _state(hooks)
    _buy(st, hooks, ["600000.SH"], px=10.0)
    st.positions["600000.SH"][0].peak = 10.40
    _buy(st, hooks, ["600000.SH"], px=10.40, day="2025-11-04", ds="20251104", day_i=1)
    assert st.stats["add_lots"] == 1
    assert st.stats["skip_add_loser"] == 0
    assert st.trades[0]["notional"] == 500_000
    assert st.trades[1]["notional"] == 499_200
