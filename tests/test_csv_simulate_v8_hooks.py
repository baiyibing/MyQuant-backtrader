from datetime import date

from backtest.research.csv_simulate_loop import (
    init_sim_state,
    run_pool_buys_day,
    run_step_adds_day,
)
from backtest.research.csv_strategy_books import apply_csv_strategy
from backtest.research.strategy8_rules import (
    INDEX_BLOCKS_ADD,
    lot_budget,
    may_add,
    step_add_due,
)


def _hooks(**extra):
    return apply_csv_strategy("version8", **extra)


def _state(hooks, cash=21_000_000):
    return init_sim_state(hooks, total_cash=cash, bars_loaded=2, pool_days={})[0]


def _buy(st, hooks, codes, *, px=10.0, day="2025-11-03", ds="20251103", day_i=0):
    run_pool_buys_day(
        st,
        {},
        day_i=day_i,
        day=day,
        ds=ds,
        pool_days={ds: codes},
        daily_quota=1_000_000,
        names={},
        allow_add=hooks["allow_add"],
        buy_gate=None,
        buy_quote_for=lambda code: (px, [px]),
        sizing=hooks["sizing"],
        name_budget=hooks["name_budget"],
        allow_new_name=hooks.get("allow_new_name"),
        add_gate=hooks.get("add_gate"),
        name_lot_budget=hooks.get("name_lot_budget"),
        index_blocks_add=hooks.get("index_blocks_add", True),
    )


def test_book_wires_reserve_add_helpers():
    hooks = _hooks()
    assert hooks["allow_add"] is True
    assert hooks["add_gate"] is may_add
    assert hooks.get("step_add") is step_add_due
    assert hooks["name_lot_budget"] is lot_budget
    assert hooks["allow_new_name"] is None
    assert hooks["index_blocks_add"] is False
    assert INDEX_BLOCKS_ADD is False
    assert hooks["reserve_limit_up"] is True
    assert hooks["defer_limit_up"] is False
    assert hooks["daily_same_bar_prefixes"] == ("open_board",)
    assert hooks["peak_gap_min"] == 15


def test_first_lot_is_full_name_budget():
    hooks = _hooks()
    st = _state(hooks)
    _buy(st, hooks, ["600000.SH"])
    assert st.trades[0]["notional"] == 1_000_000
    assert st.stats["buys"] == 1


def test_index_gate_blocks_new_names_when_map_passed():
    blocked = date(2025, 11, 3)
    hooks = _hooks(index_block_new={blocked: True})
    st = _state(hooks)
    _buy(st, hooks, ["600000.SH", "000001.SZ"], day=blocked)
    assert hooks["allow_new_name"] is not None
    assert st.stats["buys"] == 0
    assert st.stats.get("skip_index_gate", 0) == 2


def test_index_block_still_adds_held_name():
    blocked = date(2025, 11, 4)
    hooks = _hooks(index_block_new={blocked: True})
    st = _state(hooks)
    _buy(st, hooks, ["600000.SH"], px=10.0)
    _buy(st, hooks, ["600000.SH"], px=10.00, day=blocked, ds="20251104", day_i=1)
    assert st.stats["add_lots"] == 1
    assert st.stats["skip_held"] == 0
    assert st.stats.get("skip_index_gate", 0) == 0
    assert len(st.positions["600000.SH"]) == 2


def test_relist_loser_adds():
    hooks = _hooks()
    st = _state(hooks)
    _buy(st, hooks, ["600000.SH"], px=10.0)
    _buy(st, hooks, ["600000.SH"], px=9.90, day="2025-11-04", ds="20251104", day_i=1)
    assert st.stats["add_lots"] == 1
    assert st.stats["skip_held"] == 0
    assert len(st.positions["600000.SH"]) == 2


def test_relist_winner_adds():
    hooks = _hooks()
    st = _state(hooks)
    _buy(st, hooks, ["600000.SH"], px=10.0)
    _buy(st, hooks, ["600000.SH"], px=10.10, day="2025-11-04", ds="20251104", day_i=1)
    assert st.stats["skip_held"] == 0
    assert st.stats["add_lots"] == 1
    assert len(st.positions["600000.SH"]) == 2


def test_step_add_hook_fires_at_20pct():
    hooks = _hooks()
    st = _state(hooks, cash=5_000_000)
    from backtest.research.csv_ledger import execute_buy

    execute_buy(st, "600000.SH", 10.0, 1_000_000, 0, "2025-11-03")
    run_step_adds_day(
        st,
        day_i=1,
        day="2025-11-04",
        ds="20251104",
        names={},
        buy_quote_for=lambda _c: (12.0, [12.0]),
        sizing="per_name",
        name_budget=1_000_000,
        step_add=hooks.get("step_add"),
        name_lot_budget=hooks.get("name_lot_budget"),
    )
    lots = st.positions["600000.SH"]
    assert [p.lot_id for p in lots] == [0, 1]
    assert [t for t in st.trades if t.get("reason") == "add:step20"]
