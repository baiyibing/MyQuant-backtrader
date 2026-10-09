"""Wind st_daily membership: positive rows exclude, missing rows pass."""

from __future__ import annotations

import pandas as pd
from backtest.research.csv_ledger import SimState, execute_buy
from backtest.research.st_status import (
    bind_st_gate,
    drop_st_names,
    is_st_on,
    membership_from_frame,
    st_blocks_buy,
)


def _table():
    frame = pd.DataFrame(
        {
            "trade_date": ["2026-06-10", "2026-06-11"],
            "code": ["600180.SH", "000001.SZ"],
            "is_st": [True, False],
        }
    )
    return membership_from_frame(frame)


def test_positive_row_is_st_and_missing_row_is_not():
    table = _table()
    assert is_st_on("600180", "20260610", table) is True
    assert is_st_on("600180.SH", "2026-06-11", table) is False
    assert is_st_on("605499", "20260610", table) is False


def test_drop_st_names_keeps_days_that_still_have_a_name():
    table = _table()
    days = {"20260610": ["600180.SH", "605499.SH"], "20260611": ["000001.SZ"]}
    kept, dropped = drop_st_names(days, table)
    assert dropped == 1
    assert kept["20260610"] == ["605499.SH"]
    assert kept["20260611"] == ["000001.SZ"]


def test_unbound_state_does_not_block_or_read_the_lake(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("unbound execute_buy must not load the lake")

    monkeypatch.setattr("backtest.research.st_status.load_st_membership", forbidden)
    st = SimState()
    assert st_blocks_buy(st, "600180.SH", "20260610") is False
    assert execute_buy(st, "600000.SH", 10.0, 2_000.0, 0, "20251103")


def test_bound_table_blocks_buy_and_counts_skip_st():
    st = SimState()
    bind_st_gate(st, {"20251103": frozenset({"600000.SH"})})
    assert st.stats["st_gate"] == "lake"
    assert not execute_buy(st, "600000.SH", 10.0, 2_000.0, 0, "20251103")
    assert st.stats["skip_st"] == 1
    assert st.trades == []
    assert execute_buy(st, "000001.SZ", 10.0, 2_000.0, 0, "20251103")


def test_empty_table_is_a_waiver():
    st = SimState()
    bind_st_gate(st, {})
    assert st.stats["st_gate"] == "waiver"
    assert execute_buy(st, "600180.SH", 10.0, 2_000.0, 0, "20251103")


def test_init_sim_state_stays_unbound_until_product_asks():
    from backtest.research.csv_simulate_loop import init_sim_state

    st, _, _ = init_sim_state(
        {"record_params": lambda _st: None},
        total_cash=10_000.0,
        bars_loaded=1,
        pool_days={},
    )
    assert getattr(st, "st_membership", None) is None
    assert "st_gate" not in st.stats


def test_init_sim_state_binds_the_engine_gate(monkeypatch):
    from backtest.research.csv_simulate_loop import init_sim_state

    monkeypatch.setattr(
        "backtest.research.st_status.load_st_membership",
        lambda *args, **kwargs: {"20251103": frozenset({"600180.SH"})},
    )
    st, _, _ = init_sim_state(
        {"record_params": lambda _st: None},
        total_cash=10_000.0,
        bars_loaded=1,
        pool_days={},
        st_gate=True,
    )
    assert st.stats["st_gate"] == "lake"
    assert st_blocks_buy(st, "600180.SH", "20251103")
    assert not st_blocks_buy(st, "600000.SH", "20251103")


def test_oskh_st_gate_off_unbinds(monkeypatch):
    monkeypatch.setenv("OSKH_ST_GATE", "0")
    st = SimState()
    bind_st_gate(st, {"20251103": frozenset({"600000.SH"})})
    assert st.stats["st_gate"] == "off"
    assert execute_buy(st, "600000.SH", 10.0, 2_000.0, 0, "20251103")


def test_shared_daily_pool_buy_uses_engine_gate(monkeypatch):
    import backtest.research.csv_daily_backtest as daily
    import numpy as np

    monkeypatch.setattr(
        "backtest.research.st_status.load_st_membership",
        lambda *args, **kwargs: {"20251103": frozenset({"600000.SH"})},
    )
    idx = pd.to_datetime(["2025-10-31", "2025-11-03", "2025-11-04"])
    frame = pd.DataFrame(
        {
            "open": [10.0, 10.0, 10.0],
            "high": [10.1, 10.1, 10.1],
            "low": [9.9, 9.9, 9.9],
            "close": [10.0, 10.0, 10.0],
        },
        index=idx,
    ).astype(np.float64)
    st = daily.simulate(
        {"600000.SH": frame},
        {"20251103": ["600000.SH"]},
        "20251103",
        "20251104",
        strategy="version6",
        rule_profile="legacy",
        name_budget=10_000.0,
        st_gate=True,
    )
    assert st.stats["skip_st"] == 1
    assert st.stats["buys"] == 0
    assert st.trades == []


def test_library_simulate_does_not_read_the_lake(monkeypatch):
    import backtest.research.csv_daily_backtest as daily
    import numpy as np

    def forbidden(*args, **kwargs):
        raise AssertionError("library simulate() must not load the ST lake")

    monkeypatch.setattr("backtest.research.st_status.load_st_membership", forbidden)
    idx = pd.to_datetime(["2025-10-31", "2025-11-03", "2025-11-04"])
    frame = pd.DataFrame(
        {
            "open": [10.0, 10.0, 10.0],
            "high": [10.1, 10.1, 10.1],
            "low": [9.9, 9.9, 9.9],
            "close": [10.0, 10.0, 10.0],
        },
        index=idx,
    ).astype(np.float64)
    st = daily.simulate(
        {"600000.SH": frame},
        {"20251103": ["600000.SH"]},
        "20251103",
        "20251104",
        strategy="version6",
        rule_profile="legacy",
        name_budget=10_000.0,
    )
    assert st.stats.get("skip_st", 0) == 0
    assert st.stats["buys"] == 1
    assert getattr(st, "st_membership", None) is None
