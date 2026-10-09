from __future__ import annotations

from backtest.research.csv_ledger import (
    IndependentGroup,
    IndependentPosition,
    Position,
    SimState,
    configure_s8,
    held_codes,
    held_position_items,
    is_parking_lot,
    is_principal_lot,
    register_principal_lot,
    s8_open_groups,
)


def test_held_codes_ignores_insertion_order():
    st = SimState()
    st.positions["600000.SH"] = [Position("600000.SH", 100, 10.0, 0, 10.0)]
    st.positions["000001.SZ"] = [Position("000001.SZ", 100, 10.0, 0, 10.0)]
    assert list(st.positions) == ["600000.SH", "000001.SZ"]
    assert held_codes(st) == ["000001.SZ", "600000.SH"]
    assert [code for code, _ in held_position_items(st)] == ["000001.SZ", "600000.SH"]


def test_s8_open_groups_sorts_by_position_id_not_lot_list():
    st = SimState()
    configure_s8(
        st, {"name": "version6_53", "sizing": "per_name", "name_budget": 10_000.0}
    )
    code = "600000.SH"
    late = IndependentPosition(
        code,
        100,
        10.0,
        2,
        10.0,
        lot_id=0,
        position_id=f"{code}@20251110",
        entry_signal_date="20251110",
    )
    early = IndependentPosition(
        code,
        100,
        10.0,
        0,
        10.0,
        lot_id=1,
        position_id=f"{code}@20251103",
        entry_signal_date="20251103",
    )
    st.positions[code] = [late, early]
    groups = st.book_state["s8_independent"]["groups"]
    groups[late.position_id] = IndependentGroup(code, "20251110", 10_000.0, late)
    groups[early.position_id] = IndependentGroup(code, "20251103", 10_000.0, early)
    assert [pid for pid, _ in s8_open_groups(st, code)] == [
        f"{code}@20251103",
        f"{code}@20251110",
    ]


def test_parking_tag_is_object_identity_not_recycled_id():
    st = SimState()
    parked = Position("600036.SH", 100, 10.0, 0, 10.0)
    other = Position("600000.SH", 100, 10.0, 0, 10.0)
    register_principal_lot(st, parked)
    assert is_parking_lot(st, parked)
    assert is_principal_lot(st, parked)
    assert not is_parking_lot(st, other)
    del parked
    import gc

    gc.collect()
    twins = [Position("600000.SH", 100, 10.0, 0, 10.0) for _ in range(64)]
    assert not any(is_parking_lot(st, pos) for pos in twins)


def test_bonus_locks_use_object_identity():
    from backtest.research.ashare_exdiv_economics import ExDivEconomics

    account = ExDivEconomics({})
    lot = Position("600000.SH", 100, 10.0, 0, 10.0)
    account.locks_for(lot)["20251105"] = 50
    assert account.peek_locks(lot) == {"20251105": 50}
    del lot
    import gc

    gc.collect()
    twins = [Position("600000.SH", 100, 10.0, 0, 10.0) for _ in range(64)]
    assert all(account.peek_locks(pos) == {} for pos in twins)
