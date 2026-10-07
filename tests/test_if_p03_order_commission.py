import pytest
from backtest.research import csv_daily_backtest
from backtest.research.ashare_fees import (
    INDUSTRY_ORDER_COMMISSION,
    QLIB_PORTANA,
)
from backtest.research.ashare_volume_cap import BucketVolume, VolumeCap
from backtest.research.csv_ledger import (
    Position,
    SimState,
    _sell,
    bind_account_fee_schedule,
    configure_s8,
    execute_buy,
    exit_positions,
)
from backtest.research.ledger_math import (
    FeeAccumulator,
    allocate_order_commission,
    trade_commission,
)
from backtest.research.minute_cash_order import scale_out_exits
from scripts.research.generate_off_byte_baseline import run_p03_case

CODE = "600000.SH"


def test_industry_schedule_and_accumulator_floor_once_per_order():
    assert INDUSTRY_ORDER_COMMISSION.buy_rate == 0.0003
    assert INDUSTRY_ORDER_COMMISSION.sell_rate == 0.0003
    assert INDUSTRY_ORDER_COMMISSION.min_cost == 5.0
    assert INDUSTRY_ORDER_COMMISSION.per_order is True
    assert trade_commission(1000.0, 0.001) == 1.0

    accumulator = FeeAccumulator(0.0003, 5.0)
    first = accumulator.add_fill("order", 1000.0)
    second = accumulator.add_fill("order", 1000.0)
    assert first.fee_delta == 5.0
    assert second.fee_delta == 0.0
    assert second.allocations == (2.5, 2.5)
    assert sum(second.allocations) == second.total_fee == 5.0
    assert allocate_order_commission((10_000.0, 20_000.0), 0.0003, 5.0) == (
        3.0,
        6.0,
    )


def test_s8_group_exit_is_one_order_and_legacy_remains_per_call():
    legacy = run_p03_case("version8", "s8-group", rule_profile="legacy")
    industry = run_p03_case("version8", "s8-group", rule_profile="industry")
    legacy_sells = [row for row in legacy.trades if row["side"] == "SELL"]
    industry_sells = [row for row in industry.trades if row["side"] == "SELL"]

    assert [row["commission"] for row in legacy_sells] == [1.0, 1.0]
    assert [row["commission"] for row in industry_sells] == [2.5, 2.5]
    assert sum(row["commission"] for row in industry_sells) == 5.0
    # Later fee slices stack stamp and bilateral transfer on the P03 delta.
    assert industry.cash == pytest.approx(legacy.cash - 12.04)


def test_tail_children_are_separate_orders_even_when_the_lot_merges():
    state = SimState(cash=10_000.0)
    bind_account_fee_schedule(state, INDUSTRY_ORDER_COMMISSION)
    assert execute_buy(
        state, CODE, 10.0, 1000.0, 0, "20251103",
        reason="pool:tail_window", shares_override=100, hm=870,
    )
    lot = state.positions[CODE][0]
    assert execute_buy(
        state, CODE, 10.0, 1000.0, 0, "20251103",
        reason="pool:tail_window", shares_override=100, merge_lot=lot, hm=871,
    )
    assert [row["commission"] for row in state.trades] == [5.0, 5.0]


def test_each_scale_out_tranche_is_one_order_across_lot_rows():
    state = SimState(cash=100_000.0)
    configure_s8(
        state,
        {"name": "version6_13", "sizing": "per_name", "name_budget": 4000.0},
    )
    bind_account_fee_schedule(state, INDUSTRY_ORDER_COMMISSION)
    position_id = f"{CODE}@20251103"
    for entry_idx in range(4):
        assert execute_buy(
            state, CODE, 10.0, 1000.0, entry_idx, f"2025110{entry_idx + 3}",
            reason="pool" if entry_idx == 0 else "add:step20",
            position_id=position_id, entry_signal_date="20251103",
        )
    position = exit_positions(state, CODE, 4, day="20251107")[0]

    assert scale_out_exits(
        state, CODE, position, 10.5, "20251107", 4, (12.0, 8.0),
        scale_step=0.05, scale_frac=0.5, hm=600,
    ) == 200
    first_tranche = [row for row in state.trades if row["side"] == "SELL"]
    assert [row["commission"] for row in first_tranche] == [2.5, 2.5]

    assert scale_out_exits(
        state, CODE, position, 11.0, "20251107", 4, (12.0, 8.0),
        scale_step=0.05, scale_frac=0.5, hm=601,
    ) == 100
    sells = [row for row in state.trades if row["side"] == "SELL"]
    assert [row["commission"] for row in sells] == [2.5, 2.5, 5.0]


def test_capacity_continuation_reuses_order_and_reallocates_floor():
    day = "20251104"
    samples = {
        (CODE, day, 570): BucketVolume(100, 570, "raw_shares_incremental"),
        (CODE, day, 571): BucketVolume(100, 571, "raw_shares_incremental"),
    }
    state = SimState(cash=0.0)
    bind_account_fee_schedule(state, INDUSTRY_ORDER_COMMISSION)
    state.volume_cap = VolumeCap(1.0, samples)
    position = Position(CODE, 200, 10.0, 0, 10.0)
    state.positions[CODE] = [position]

    assert _sell(
        state, CODE, position, 10.0, day, "force_sell",
        bucket_id=570, at=570, day_i=1,
    ) == 100
    assert _sell(
        state, CODE, position, 10.0, day, "force_sell",
        bucket_id=571, at=571, day_i=1,
    ) == 100
    assert [row["commission"] for row in state.trades] == [2.5, 2.5]
    assert state.cash == 1993.98


def test_industry_rejects_explicit_legacy_cost_schedules():
    with pytest.raises(ValueError, match="conflicts with explicit legacy cost options"):
        csv_daily_backtest.simulate(
            {}, {}, "20251103", "20251104", strategy="version6",
            buy_cost_rate=0.0005, sell_cost_rate=0.0015, min_cost=5.0,
            rule_profile="industry",
        )

    from backtest.research.csv_minute_backtest_v7 import simulate_v7

    with pytest.raises(ValueError, match="QLIB_PORTANA"):
        simulate_v7({}, {}, {}, [], fee=QLIB_PORTANA, rule_profile="industry")
