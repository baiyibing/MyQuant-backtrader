"""Synthetic X-04 quantities, prices, cash limits and raw lake retention."""

from decimal import Decimal

import pandas as pd
import pytest
from backtest.research import ashare_bars
from backtest.research.ashare_fees import BILATERAL_10BP, QLIB_PORTANA
from backtest.research.tail_window_buy import (
    TAIL_MINUTES,
    TAIL_START,
    TailParent,
    TailQuote,
    affordable_shares,
    resolve_tail_volume_unit,
    tail_policy,
    tail_quote,
    validate_tail_options,
)
from oskh_data.symbol_format import to_partition_key

SYMBOL = "600000.SH"


@pytest.mark.parametrize("cash_order", [False, True])
@pytest.mark.parametrize("unit", [None, "shares", "lots", "unverified"])
def test_off_ignores_tail_dependencies(cash_order, unit):
    validate_tail_options(False, cash_order, unit)


@pytest.mark.parametrize("unit", [None, "shares", "lots"])
def test_on_requires_cash_chronology(unit):
    with pytest.raises(ValueError, match="requires --fix-minute-cash-order"):
        validate_tail_options(True, False, unit)


@pytest.mark.parametrize("unit", ["foo", "", "Shares"])
def test_on_rejects_invalid_volume_unit(unit):
    with pytest.raises(ValueError, match="--tail-volume-unit"):
        validate_tail_options(True, True, unit)
    with pytest.raises(ValueError, match="--tail-volume-unit"):
        resolve_tail_volume_unit(unit)
    with pytest.raises(ValueError, match="--tail-volume-unit"):
        tail_quote({"close": 10, "volume": 1000}, TAIL_START, unit)
    with pytest.raises(ValueError, match="--tail-volume-unit"):
        tail_policy(unit)


@pytest.mark.parametrize("unit", [None, "shares", "lots"])
def test_on_accepts_cash_order_with_default_or_explicit_unit(unit):
    validate_tail_options(True, True, unit)
    assert resolve_tail_volume_unit(unit) == ("shares" if unit is None else unit)


def test_missing_unit_quotes_and_policy_match_shares():
    row = {"close": 12, "volume": 12_000, "amount": 120_000}
    assert resolve_tail_volume_unit() == "shares"
    assert tail_quote(row, TAIL_START) == tail_quote(row, TAIL_START, None) == tail_quote(row, TAIL_START, "shares")
    assert tail_policy() == tail_policy(None) == tail_policy("shares")
    assert tail_policy()["tail_volume_unit"] == "shares"


def test_exact_28_child_clocks_and_policy():
    assert TAIL_START == 870
    assert len(TAIL_MINUTES) == 28
    assert TAIL_MINUTES[:27] == tuple(range(870, 897))
    assert TAIL_MINUTES[-1] == 900
    policy = tail_policy("shares")
    assert policy["tail_slice_count"] == 28
    assert policy["tail_parent_clock"] == "14:30_open_exact"
    assert policy["tail_participation_rate"] == 0.1


@pytest.mark.parametrize("hm", [869, 897, 898, 899, 901])
def test_outside_window_and_auction_gap_never_fill(hm):
    assert tail_quote({"close": 10, "volume": 1_000_000}, hm, "shares") is None


@pytest.mark.parametrize("hm", [870, 896, 900])
def test_missing_exact_bar_has_no_fallback(hm):
    assert tail_quote(None, hm, "shares") is None


def test_amount_price_uses_shares_and_auction_always_uses_close():
    row = {"close": 12, "volume": 12_000, "amount": 120_000}
    assert tail_quote(row, 870, "shares") == TailQuote(10, 1200)
    assert tail_quote(row, 896, "shares") == TailQuote(10, 1200)
    assert tail_quote(row, 900, "shares") == TailQuote(12, 1200)
    assert tail_quote({"close": 12, "volume": 12_000}, 870, "shares") == TailQuote(12, 1200)


def test_share_and_lot_attestations_produce_same_price_and_capacity():
    in_shares = {"close": 11, "volume": 12_340, "amount": 123_400}
    in_lots = {"close": 11, "volume": Decimal("123.40"), "amount": 123_400}
    assert tail_quote(in_shares, 870, "shares") == TailQuote(10, 1200)
    assert tail_quote(in_lots, 870, "lots") == tail_quote(in_shares, 870, "shares")


@pytest.mark.parametrize(
    "volume,unit,capacity",
    [(1, "shares", 0), (999, "shares", 0), (1000, "shares", 100),
     (1999, "shares", 100), (2000, "shares", 200),
     ("9.99", "lots", 0), (10, "lots", 100)],
)
def test_ten_percent_capacity_floors_to_whole_buy_lots(volume, unit, capacity):
    assert tail_quote({"close": 10, "volume": volume}, 870, unit) == TailQuote(10, capacity)


@pytest.mark.parametrize("volume", [None, 0, -1, float("nan"), float("inf"), "bad", True, 1000.5])
def test_invalid_or_zero_volume_fails_closed(volume):
    assert tail_quote({"close": 10, "volume": volume}, 870, "shares") is None


def test_missing_volume_and_unknown_units_fail_closed():
    assert tail_quote({"close": 10}, 870, "shares") is None
    with pytest.raises(ValueError, match="volume unit"):
        tail_quote({"close": 10, "volume": 1000}, 870, "guess")


@pytest.mark.parametrize("amount", [None, 0, -1, float("nan"), float("inf"), "bad"])
def test_present_invalid_amount_does_not_fall_back_to_close(amount):
    row = {"close": 10, "volume": 1000, "amount": amount}
    assert tail_quote(row, 870, "shares") is None
    assert tail_quote(row, 900, "shares") == TailQuote(10, 100)


@pytest.mark.parametrize("price", [None, 0, -1, float("nan"), float("inf"), "bad"])
def test_invalid_close_rejects_close_execution(price):
    assert tail_quote({"close": price, "volume": 1000}, 900, "shares") is None


@pytest.mark.parametrize(
    "budget,price,target,slice_shares,unallocated",
    [(28_000, 10, 2800, 100, 0), (29_999, 10, 2900, 100, 100),
     (27_999, 10, 2700, 0, 2700), (56_000, 10, 5600, 200, 0),
     (280, 0.1, 2800, 100, 0), (0, 10, 0, 0, 0)],
)
def test_parent_fixed_equal_lots_discards_rounding_residual(
    budget, price, target, slice_shares, unallocated,
):
    parent = TailParent.from_budget(budget, price)
    assert (parent.target_shares, parent.slice_shares) == (target, slice_shares)
    assert parent.target_shares - 28 * parent.slice_shares == unallocated


@pytest.mark.parametrize(
    "budget,price", [(-1, 10), (float("nan"), 10), (float("inf"), 10),
                     (1000, 0), (1000, -1), (1000, float("nan")), (1000, float("inf"))],
)
def test_parent_rejects_invalid_start_information(budget, price):
    with pytest.raises(ValueError, match="finite budget and positive 14:30 open"):
        TailParent.from_budget(budget, price)


def test_skipped_child_never_enlarges_later_children():
    parent = TailParent.from_budget(29_000, 10)
    first = parent.allocation(TailQuote(10, 0), 100_000, BILATERAL_10BP.debit_buy)
    assert first == 0
    subsequent = []
    for _ in TAIL_MINUTES[1:]:
        shares = parent.allocation(TailQuote(10, 100_000), 100_000, BILATERAL_10BP.debit_buy)
        subsequent.append(shares)
        parent.book(shares, 10)
    assert subsequent == [100] * 27
    assert parent.filled_shares == 2700
    assert parent.spent == 27_000
    assert parent.target_shares - parent.filled_shares == 200


@pytest.mark.parametrize("cash,expected", [(1004.99, 0), (1005, 100), (2004.99, 100), (2005, 200)])
def test_available_cash_includes_each_child_minimum_commission(cash, expected):
    assert affordable_shares(10_000, 10, cash, QLIB_PORTANA.debit_buy) == expected


@pytest.mark.parametrize("price,cash", [(0, 1000), (float("nan"), 1000),
                                       (10, 0), (10, float("nan")), (10, float("inf"))])
def test_invalid_cash_or_price_cannot_afford_child(price, cash):
    assert affordable_shares(100, price, cash, BILATERAL_10BP.debit_buy) == 0


@pytest.mark.parametrize("schedule,fees", [(BILATERAL_10BP, 28), (QLIB_PORTANA, 140)])
def test_28_independent_child_fees_are_charged_from_cash(schedule, fees):
    parent = TailParent.from_budget(28_000, 10)
    initial_cash = cash = 28_000 + fees
    for _ in TAIL_MINUTES:
        shares = parent.allocation(TailQuote(10, 100_000), cash, schedule.debit_buy)
        assert shares == 100
        cash -= schedule.debit_buy(shares * 10)
        parent.book(shares, 10)
    assert parent.filled_shares == 2800
    assert parent.spent == 28_000
    assert initial_cash - parent.spent - cash == pytest.approx(fees)
    assert cash == pytest.approx(0)


def test_rising_prices_cannot_expand_parent_notional_budget():
    parent = TailParent.from_budget(28_000, 10)
    fills = []
    for _ in TAIL_MINUTES:
        shares = parent.allocation(TailQuote(20, 100_000), 100_000, BILATERAL_10BP.debit_buy)
        fills.append(shares)
        parent.book(shares, 20)
    assert fills == [100] * 14 + [0] * 14
    assert parent.spent == 28_000
    assert parent.filled_shares == 1400


def test_falling_prices_do_not_reinvest_unused_parent_budget():
    parent = TailParent.from_budget(28_000, 10)
    for _ in TAIL_MINUTES:
        shares = parent.allocation(TailQuote(5, 100_000), 100_000, BILATERAL_10BP.debit_buy)
        assert shares == 100
        parent.book(shares, 5)
    assert parent.filled_shares == 2800
    assert parent.spent == 14_000
    assert parent.allocation(TailQuote(5, 100_000), 100_000, BILATERAL_10BP.debit_buy) == 0


def _write_raw_lake(root, *, amount=True, volume=True):
    frame = pd.DataFrame({
        "time": [pd.Timestamp("2026-09-01 14:30", tz="UTC").value // 1_000_000,
                 pd.Timestamp("2026-09-01 15:00", tz="UTC").value // 1_000_000],
        "open": [9.0, 11.0], "high": [11.0, 11.0], "low": [9.0, 11.0],
        "close": [10.0, 11.0],
    })
    if volume:
        frame["volume"] = [123.4, 0.0]
    if amount:
        frame["amount"] = [123_400.0, 0.0]
    directory = root / f"symbol={to_partition_key(SYMBOL)}"
    directory.mkdir(parents=True)
    frame.to_parquet(directory / "data.parquet", index=False)


@pytest.mark.parametrize("has_amount", [False, True])
def test_tail_lake_loader_retains_raw_volume_optional_amount_and_zero_bar(tmp_path, has_amount):
    _write_raw_lake(tmp_path, amount=has_amount)
    frame = ashare_bars.read_lake_minute_ohlc(
        SYMBOL, tmp_path, "20260901", "20260901", include_amount=True,
    )
    assert frame is not None
    assert frame["hm"].tolist() == [870, 900]
    assert frame["volume"].tolist() == [123.4, 0.0]
    assert ("amount" in frame) is has_amount
    if has_amount:
        assert frame["amount"].tolist() == [123_400.0, 0.0]
    quote = tail_quote(frame.iloc[0], 870, "lots")
    assert quote == TailQuote(10, 1200)
    assert tail_quote(frame.iloc[1], 900, "lots") is None


def test_tail_lake_loader_bypasses_legacy_cache(tmp_path, monkeypatch):
    lake = tmp_path / "lake"
    _write_raw_lake(lake)

    def forbidden(*args, **kwargs):
        pytest.fail("tail amount/volume reads must bypass the old price-only cache")

    for name in ("read_minute_cache", "write_minute_cache", "minute_cache_path"):
        monkeypatch.setattr(ashare_bars, name, forbidden)
    frames = ashare_bars.load_minute_ohlc(
        [SYMBOL], "20260901", "20260901", workers=1, use_cache=True,
        lake_root=lake, include_amount=True,
    )
    assert frames[SYMBOL]["volume"].tolist() == [123.4, 0.0]
    assert frames[SYMBOL]["amount"].tolist() == [123_400.0, 0.0]


def test_tail_lake_loader_requires_volume_and_existing_partition(tmp_path):
    _write_raw_lake(tmp_path, volume=False)
    with pytest.raises(ValueError, match="minute volume required"):
        ashare_bars.read_lake_minute_ohlc(
            SYMBOL, tmp_path, "20260901", "20260901", include_amount=True,
        )
    with pytest.raises(FileNotFoundError):
        ashare_bars.read_lake_minute_ohlc(
            "600001.SH", tmp_path, "20260901", "20260901", include_amount=True,
        )
