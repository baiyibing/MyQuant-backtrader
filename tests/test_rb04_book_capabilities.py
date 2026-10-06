"""Data-free RB-04 equivalence and admission guards."""

import inspect

import pytest

from backtest.research import book_capabilities as caps, csv_ledger
from backtest.research.csv_strategy_books import BOOKS, MINUTE_ONLY_BOOKS

FROZEN_PRICE_ADD_BOOKS = frozenset({
    "version6_1",
    "version6_10",
    "version6_11",
    "version6_12",
    "version6_13",
    "version6_14",
    "version6_15",
    "version6_16",
    "version6_17",
    "version6_18",
    "version6_19",
    "version6_2",
    "version6_20",
    "version6_21",
    "version6_22",
    "version6_23",
    "version6_24",
    "version6_25",
    "version6_26",
    "version6_27",
    "version6_28",
    "version6_29",
    "version6_3",
    "version6_30",
    "version6_31",
    "version6_32",
    "version6_33",
    "version6_34",
    "version6_35",
    "version6_36",
    "version6_37",
    "version6_38",
    "version6_39",
    "version6_4",
    "version6_40",
    "version6_41",
    "version6_42",
    "version6_43",
    "version6_44",
    "version6_45",
    "version6_46",
    "version6_47",
    "version6_5",
    "version6_6",
    "version6_7",
    "version6_8",
    "version6_9",
    "version8",
    "version8_3",
    "version8_4",
    "version8_5",
})


@pytest.mark.parametrize("name", [*BOOKS, *MINUTE_ONLY_BOOKS, None, ""])
@pytest.mark.parametrize("sizing", ["per_name", None, "", "daily_quota"])
def test_tip_capability_equivalence(name, sizing):
    # Freeze the old independent predicate once for registered-book equivalence.
    old = bool(sizing == "per_name" and name and (
        name.startswith("version6_") or name == "version8"
        or (name.startswith("version8_") and name != "version8_1")
    ))
    assert caps.uses_s8_independent(name, sizing) is old
    assert csv_ledger.uses_s8_independent(name, sizing) is old
    assert caps.allows_price_add(name, sizing) is (
        sizing == "per_name" and name in FROZEN_PRICE_ADD_BOOKS
    )


def test_membership_and_registration():
    price = caps.PRICE_ADD_ELIGIBLE_BOOKS
    independent = caps.S8_INDEPENDENT_BOOKS
    assert isinstance(price, frozenset)
    assert isinstance(independent, frozenset)
    assert price == FROZEN_PRICE_ADD_BOOKS
    assert len(price) == 51
    assert len(independent) == 53
    assert price < independent
    assert independent - price == {"version8_2", "version8_6"}
    assert price <= BOOKS.keys()
    assert independent <= BOOKS.keys()
    assert "version7" in MINUTE_ONLY_BOOKS
    assert "version7" not in independent


@pytest.mark.parametrize("name", ["version6_999", "version6_future", "version8_7"])
def test_new_books_require_explicit_admission(name):
    assert not caps.allows_price_add(name, "per_name")
    assert not csv_ledger.uses_s8_independent(name, "per_name")


def test_no_prefix_inheritance_in_production_helpers():
    assert "startswith" not in inspect.getsource(caps)
    assert "startswith" not in inspect.getsource(csv_ledger.uses_s8_independent)
