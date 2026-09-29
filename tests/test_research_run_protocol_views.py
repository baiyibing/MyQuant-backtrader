"""Hand-built evidence and synthetic native v7 projection; no lake or clock packs."""

from copy import deepcopy
from dataclasses import FrozenInstanceError, dataclass
from decimal import Decimal
import os
from pathlib import Path
import subprocess
import sys
import textwrap

import pytest

from backtest.research.run_protocol.views import (
    AccountPortfolioView, FillView, GridInstancePortfolioView,
    GridSpecPortfolioView, OrderView, project_fills, project_orders,
    project_portfolio, project_time_evidence,
)


@pytest.fixture
def jr():
    # Fields from snapshot_order / attempt / daily_nav, hand-built without
    # importing the engine. The native public replay plain() boundary may
    # already have converted numbers; projections preserve either input form.
    pair = dict(run_id="synthetic-jr", arm_id="P-BASE", fill_id="M-LAG")
    order = dict(**pair, order_id="native-order-1", intent_id="intent-1",
                 instrument="600000.SH", instance_id="instance-1", lot_id="lot-1",
                 side="BUY", status="PARTIAL", current_quantity=Decimal("300"),
                 cumulative_filled_quantity=Decimal("200"), remaining_quantity=Decimal("100"),
                 cumulative_fee=Decimal("5.0000"), decision_at="2026-09-28T15:00:00+08:00",
                 available_at="2026-09-29T09:30:00+08:00",
                 effective_at="2026-09-29T09:30:00+08:00",
                 actual_fill_at="2026-09-29T09:32:00+08:00", legal_execution_at=None,
                 transitions=[dict(status="WAITING", at="2026-09-28T15:00:00+08:00")])
    fills = [dict(order, fill_sequence=1, executed_quantity=Decimal("100"),
                  price=Decimal("10.123400"), fee=Decimal("5.0000")),
             dict(order, fill_sequence=2, executed_quantity=Decimal("100"),
                  price=Decimal("10.123400"), fee=Decimal("0.0000"))]
    daily = dict(**pair, date="2026-09-29", event="MARK", cash=Decimal("17970.3200"),
                 nav=Decimal("19995.0000"), mark_at="2026-09-29T15:00:00+08:00",
                 positions=[dict(lot_id="lot-1", instrument="600000.SH",
                                 quantity=Decimal("200"), sellable_quantity=Decimal("0"))])
    return dict(orders=[order], fills=fills, daily_nav=[daily])


def test_jr_order_fill_provenance_and_decimal_granularity(jr):
    orders = project_orders("joint_return", jr, source="orders.csv")
    order = orders.rows[0]
    assert isinstance(order, OrderView)
    assert order.order_id.value == "native-order-1" and not order.order_id.derived
    assert order.status.value == "PARTIAL"
    assert order.field("current_quantity").value == Decimal("300")
    assert order.field("cumulative_filled_quantity").value == Decimal("200")
    assert order.field("observation_id").unknown_reason == "field_missing"
    provenance = order.order_id.provenance
    assert (provenance.family, provenance.run_id, provenance.source_file, provenance.path) == (
        "joint_return", "synthetic-jr", "orders.csv", ("orders", 0, "order_id"))
    assert provenance.unknown_reasons == ()
    transition = order.field("transitions", 0, "at")
    assert transition.provenance.path == ("orders", 0, "transitions", 0, "at")
    fills = project_fills("joint_return", jr, run_id="synthetic-jr", source="fills.csv")
    assert len(fills.rows) == 2 and not fills.excluded
    for index, fill in enumerate(fills.rows):
        assert isinstance(fill, FillView)
        assert fill.quantity.value == Decimal("100")  # not cumulative 200
        assert fill.price.value is jr["fills"][index]["price"]
        assert fill.fee.value is jr["fills"][index]["fee"]
        assert fill.price.value.as_tuple().exponent == -6
        assert fill.quantity.provenance.path == ("fills", index, "executed_quantity")
        assert fill.fee.provenance.path == ("fills", index, "fee")
        assert fill.field("lot_id").value == "lot-1"


def test_fee_missing_null_and_reported_zero_remain_distinct(jr):
    del jr["fills"][0]["fee"]
    views = project_fills("joint_return", jr).rows
    assert views[0].fee.value is None
    assert views[0].fee.unknown_reason == "field_missing"
    # The available cumulative_fee must never fill the missing incremental fee.
    assert views[0].field("cumulative_fee").value == Decimal("5.0000")
    assert views[1].fee.value == Decimal("0.0000")
    assert views[1].fee.unknown_reason is None
    jr["fills"][0]["fee"] = None
    assert project_fills("joint_return", jr).rows[0].fee.unknown_reason == "native_null"


@pytest.mark.parametrize("family", ["joint_return", "csv_minute", "v7"])
@pytest.mark.parametrize("field,marker", [
    ("side", "SKIP"), ("status", "REJECTED"), ("event", "EOD_MARK"),
    ("side", "EOD_MARK"), ("reason", "skip_cash"), ("status_reason", "REJECT"),
    ("event", "MARK"), ("reason", "mark_end"),
    ("side", "skip"), ("side", "mark"), ("event", "eod_mark"),
])
def test_non_fill_markers_never_promoted(family, field, marker):
    row = dict(side="buy" if family == "v7" else "BUY", status="FILLED", executed_quantity=Decimal("100"),
               shares=100, price=10, fee=0)
    row[field] = marker
    result = project_fills(family, [row], run_id="r", source="native.csv")
    assert result.rows == ()
    assert result.excluded[0].unknown_reason == "non_fill_marker"
    assert result.excluded[0].provenance.path == (0,)


@pytest.mark.parametrize("family", ["joint_return", "csv_minute", "v7"])
@pytest.mark.parametrize("side_fields", [{}, {"side": None}, {"side": "hold"}])
def test_missing_or_non_trade_side_is_excluded(family, side_fields):
    row = dict(side_fields, status="FILLED", executed_quantity=100, shares=100, price=10)
    result = project_fills(family, [row])
    assert result.rows == ()
    assert result.excluded[0].unknown_reason == "no_native_fill_side"
    assert result.excluded[0].provenance.path == (0,)


@pytest.mark.parametrize("quantity,reason", [
    (None, "incremental_quantity_missing_or_invalid"),
    (True, "incremental_quantity_missing_or_invalid"),
    (Decimal("NaN"), "incremental_quantity_missing_or_invalid"),
    (float("inf"), "incremental_quantity_missing_or_invalid"),
    (0, "nonpositive_incremental_quantity"), (-100, "nonpositive_incremental_quantity"),
])
def test_no_cumulative_or_nonpositive_fills(jr, quantity, reason):
    jr["fills"][0]["executed_quantity"] = quantity
    result = project_fills("joint_return", jr)
    assert len(result.rows) == 1
    assert result.excluded[0].unknown_reason == reason
    del jr["fills"][0]["executed_quantity"]
    assert len(project_fills("joint_return", jr).rows) == 1


@pytest.mark.parametrize("family", ["csv_minute", "v7", "grid_modeb"])
def test_missing_orders_do_not_invent_lifecycle(family):
    native = dict(trades=[dict(side="BUY", shares=100, price=10)], instances=[{}])
    result = project_orders(family, native, run_id="r")
    assert result.rows == () and result.unknown_reason == "family_has_no_order_lifecycle"
    assert result.provenance.path == ("orders",)
    assert result.provenance.unknown_reasons == ("source_file_not_supplied",)
    # Only an explicitly supplied native orders collection can produce rows.
    native["orders"] = [dict(order_id="external-native-id", status="ACCEPTED")]
    order = project_orders(family, native).rows[0]
    assert order.order_id.value == "external-native-id"
    assert order.field("submit_at").unknown_reason == "field_missing"


@pytest.mark.parametrize("family,side,fee_key", [
    ("csv_minute", "SELL", "commission"), ("v7", "sell", "fee"), ("v7", "SELL", "fee"),
])
def test_native_trade_granularity_and_missing_v7_fee(family, side, fee_key):
    trade = dict(side=side, shares=100, price=10.25, reason="exit:timer10", lot=3,
                 position_id="600000.SH@20260928", hm=600)
    if family == "csv_minute":
        trade[fee_key] = 5.0
    fill = project_fills(family, dict(trades=[trade])).rows[0]
    assert fill.quantity.value == 100 and type(fill.price.value) is float
    assert fill.fee.provenance.path == ("trades", 0, fee_key)
    assert fill.field("position_id").value == trade["position_id"]
    assert fill.field("booked_at").unknown_reason == "field_missing"
    if family == "v7":
        assert fill.fee.value is None and fill.fee.unknown_reason == "field_missing"
    else:
        assert fill.fee.value == 5.0


def test_real_native_v7_buy_and_sell_projection_preserves_evidence():
    from backtest.research.csv_minute_backtest_v7 import simulate_v7
    from tests.test_csv_minute_backtest_v7 import D1, D2, D3, SYMBOL, bar, daily

    result = simulate_v7(
        {SYMBOL: [bar(D1, 895, 100), bar(D2, 885, 104), bar(D2, 895, 108), bar(D3, 570, 96)]},
        {SYMBOL: {**daily()[SYMBOL], D2: 100.0}}, {D1: [SYMBOL]}, [D1, D2, D3],
    )
    before = deepcopy(result)
    assert [trade["side"] for trade in result.trades] == ["buy", "buy", "buy", "sell"]
    projection = project_fills("v7", result, run_id="synthetic-v7", source="native-result")
    assert len(projection.rows) == 4 and projection.excluded == ()
    for index, (fill, trade) in enumerate(zip(projection.rows, result.trades)):
        assert isinstance(fill, FillView)
        assert dict(fill.native_fields) == trade
        assert fill.quantity.value == trade["shares"]
        assert fill.price.value == trade["price"]
        assert fill.fee.value is None and fill.fee.unknown_reason == "field_missing"
        side = fill.field("side")
        assert side.value == trade["side"] and not side.derived
        assert (side.provenance.family, side.provenance.run_id,
                side.provenance.source_file, side.provenance.path) == (
            "v7", "synthetic-v7", "native-result", ("trades", index, "side"))
        assert side.provenance.unknown_reasons == ()
        assert fill.quantity.provenance.path == ("trades", index, "shares")
    assert result == before


def test_jr_portfolio_keeps_arm_fill_lot_identity(jr):
    second = deepcopy(jr["daily_nav"][0])
    second.update(arm_id="P-CHASE", fill_id="M-REF")
    jr["daily_nav"].append(second)
    rows = project_portfolio("joint_return", jr, source="daily_nav.csv").rows
    assert len(rows) == 2 and all(isinstance(row, AccountPortfolioView) for row in rows)
    assert [(row.field("arm_id").value, row.field("fill_id").value) for row in rows] == [
        ("P-BASE", "M-LAG"), ("P-CHASE", "M-REF")]
    assert rows[0].field("nav").value is jr["daily_nav"][0]["nav"]
    sellable = rows[0].field("positions", 0, "sellable_quantity")
    assert sellable.value == Decimal("0") and sellable.unknown_reason is None
    assert sellable.provenance.path == ("daily_nav", 0, "positions", 0, "sellable_quantity")


@pytest.mark.parametrize("family", ["csv_minute", "v7"])
def test_account_snapshot_copies_native_positions_without_regrouping(family):
    @dataclass
    class Lot:
        shares: int
        position_id: str

    @dataclass
    class State:
        cash: float
        positions: dict
        equity_curve: list
        callback: object
        run_id: str = "r"

    lots = [Lot(100, "600000.SH@20260927"), Lot(200, "600000.SH@20260928")]
    native = State(0.0, {"600000.SH": lots}, [{"equity": 3000.0}], object())
    result = project_portfolio(family, native, run_id="r", source="memory-state")
    row = result.rows[0]
    assert row.field("cash").value == 0.0 and row.field("cash").unknown_reason is None
    assert [row.field("positions", "600000.SH", i, "position_id").value for i in range(2)] == [
        lot.position_id for lot in lots]
    assert row.field("sellable_quantity").unknown_reason == "field_missing"
    assert project_portfolio(family, native).rows[0].provenance.run_id == "r"
    with pytest.raises(ValueError, match="conflicts"):
        project_portfolio(family, native, run_id="other-run")
    lots[0].shares = 999
    assert row.field("positions", "600000.SH", 0, "shares").value == 100


def test_grid_portfolio_is_typed_per_spec_and_instance_without_shared_cash():
    @dataclass
    class Exit:
        shares: int
        pnl: float
        is_trade: bool

    native = dict(matrix={"hold": {"600000.SH@20260928": Exit(100, 30., False)},
                          "stop": {"600000.SH@20260928": Exit(100, -10., True)}},
                  ranked=[dict(label="hold", total_return=0.1), dict(label="stop", total_return=-0.1)],
                  instances=[dict(symbol="600000.SH", list_date="20260928", buy_price=10., opened=True)])
    before = deepcopy(native)
    result = project_portfolio("grid_modeb", native, run_id="grid", source="native-result")
    assert len(result.rows) == 5
    assert not any(isinstance(row, AccountPortfolioView) for row in result.rows)
    instance_rows = [row for row in result.rows if isinstance(row, GridInstancePortfolioView)]
    assert [row.spec_id.value for row in instance_rows] == ["hold", "stop", None]
    assert instance_rows[0].instance_id.value == "600000.SH@20260928"
    assert not instance_rows[0].instance_id.derived
    assert instance_rows[0].field("pnl").provenance.path == ("matrix", "hold", "600000.SH@20260928", "pnl")
    assert instance_rows[2].instance_id.unknown_reason == "native_instance_id_not_reported"
    spec_rows = [row for row in result.rows if isinstance(row, GridSpecPortfolioView)]
    assert [row.spec_id.value for row in spec_rows] == ["hold", "stop"]
    assert all(row.field("cash").unknown_reason == "field_missing" for row in result.rows)
    assert project_fills("grid_modeb", native).rows == ()
    assert native == before


def test_unknown_sources_empty_records_and_conflicting_identity(jr):
    unknown = project_orders("v7", [dict(order_id="o", status=None)]).rows[0]
    assert unknown.provenance.run_id is None and unknown.provenance.source_file is None
    assert unknown.provenance.unknown_reasons == ("run_id_not_supplied", "source_file_not_supplied")
    assert unknown.status.unknown_reason == "native_null"
    assert unknown.field("qty").unknown_reason == "field_missing"
    assert project_orders("joint_return", {}).unknown_reason == "native_orders_missing"
    empty = project_fills("joint_return", {"fills": []})
    assert empty.rows == () and empty.unknown_reason is None
    for projector in (project_orders, project_fills, project_portfolio):
        with pytest.raises(ValueError, match="conflicts"):
            projector("joint_return", jr, run_id="wrong-run")
        with pytest.raises(ValueError, match="unknown projection family"):
            projector("unknown-backend", {})
        with pytest.raises(TypeError, match="native mapping/dataclass"):
            projector("joint_return", Path("unread-native-output"))


def test_clock_evidence_never_infers_off_legacy_or_booking(jr):
    evidence = project_time_evidence("csv_minute", dict(fix_minute_cash_order=False,
                                     price_rule="open", topk_exec="open"), run_id="r", source="config.json")
    off = evidence.schedule_parameters["fix_minute_cash_order"]
    assert off.value is False and off.unknown_reason is None
    assert off.provenance.path == ("fix_minute_cash_order",)
    assert evidence.schedule_parameters["tail_window_buy"].unknown_reason == "field_missing"
    assert all(clock.unknown_reason == "field_missing" for clock in evidence.effective_clocks.values())
    row = project_orders("joint_return", jr).rows[0]
    clocks = project_time_evidence("joint_return", row).effective_clocks
    assert clocks["actual_fill_at"].value == jr["orders"][0]["actual_fill_at"]
    assert clocks["actual_fill_at"].provenance.path == ("orders", 0, "actual_fill_at")
    assert clocks["legal_execution_at"].unknown_reason == "native_null"
    assert clocks["booked_at"].unknown_reason == clocks["match_at"].unknown_reason == "field_missing"


def test_projection_is_detached_deeply_read_only_and_context_inert(jr):
    before = deepcopy(jr)
    lists = (jr["orders"], jr["fills"], jr["daily_nav"])
    native_order = jr["orders"][0]
    cwd, env = os.getcwd(), dict(os.environ)
    order = project_orders("joint_return", jr).rows[0]
    fill = project_fills("joint_return", jr).rows[0]
    portfolio = project_portfolio("joint_return", jr).rows[0]
    assert jr == before
    assert all(jr[key] is value for key, value in zip(("orders", "fills", "daily_nav"), lists))
    assert jr["orders"][0] is native_order
    assert (os.getcwd(), dict(os.environ)) == (cwd, env)
    with pytest.raises(FrozenInstanceError):
        order.provenance = None
    with pytest.raises(TypeError):
        order.native_fields["status"] = "CHANGED"
    with pytest.raises(TypeError):
        portfolio.field("positions").value[0]["quantity"] = 999
    with pytest.raises(TypeError):
        fill.field("transitions").value[0]["status"] = "CHANGED"
    jr["orders"][0]["transitions"][0]["status"] = "CHANGED"
    assert order.field("transitions", 0, "status").value == "WAITING"
    assert fill.field("transitions", 0, "status").value == "WAITING"


def test_package_and_lazy_views_load_no_engines_or_facade():
    code = textwrap.dedent("""
        import os
        import sys
        sys.path.insert(0, sys.argv[1])
        before = set(sys.modules)
        context = os.getcwd(), dict(os.environ)
        import backtest.research.run_protocol as protocol
        assert 'backtest.research.run_protocol.views' not in sys.modules
        from backtest.research.run_protocol import OrderView, project_orders
        import backtest.research.run_protocol.views as views
        assert OrderView is views.OrderView
        assert set(protocol._VIEW_EXPORTS) == set(views.__all__)
        for name in views.__all__:
            assert getattr(protocol, name) is getattr(views, name)
        assert project_orders('joint_return', {'orders': []}).rows == ()
        allowed = {'backtest', 'backtest.research', 'backtest.research.run_protocol',
                   'backtest.research.run_protocol.types', 'backtest.research.run_protocol.views'}
        unexpected = {name for name in set(sys.modules) - before
                      if name not in allowed and name.split('.')[0] not in sys.stdlib_module_names}
        assert not unexpected, sorted(unexpected)
        assert (os.getcwd(), dict(os.environ)) == context
    """)
    result = subprocess.run([sys.executable, "-I", "-S", "-c", code,
                             str(Path(__file__).resolve().parents[1])],
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
