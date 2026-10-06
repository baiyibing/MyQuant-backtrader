"""Explicit per-purpose capabilities frozen from tip 9dd59b0.

Price-add eligibility controls daily adds and minute split group scans.
S8 independent binding controls position groups and the short-cash default.
These purposes differ: version8_2 and version8_6 are independent-only.
Both require per_name sizing. New books require explicit admission to each
relevant frozenset; names never confer inherited capabilities.
"""

from __future__ import annotations

from collections.abc import Iterable

PRICE_ADD_ELIGIBLE_BOOKS: frozenset[str] = frozenset({
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

S8_INDEPENDENT_BOOKS: frozenset[str] = frozenset({
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
    "version8_2",
    "version8_3",
    "version8_4",
    "version8_5",
    "version8_6",
})


PREFIX_FAMILY_OPT_OUT: dict[str, str] = {
    "version8_1": (
        "Band/float book intentionally outside S8 independent and price-add; "
        "matches the pre-#412 startswith exception."
    ),
}


def in_prefix_family(name: str) -> bool:
    """Frozen legacy family for admission scans only, never inheritance."""
    return (name.startswith("version6_") or name == "version8"
            or name.startswith("version8_"))


def unclassified_prefix_family_books(registered_names: Iterable[str]) -> list[str]:
    """Return sorted, unique family names without an explicit classification."""
    classified = (PRICE_ADD_ELIGIBLE_BOOKS | S8_INDEPENDENT_BOOKS
                  | PREFIX_FAMILY_OPT_OUT.keys())
    return sorted({name for name in registered_names
                   if in_prefix_family(name) and name not in classified})


def assert_prefix_family_classified(registered_names: Iterable[str]) -> None:
    """Fail admission when a registered legacy-family book lacks a decision."""
    missing = unclassified_prefix_family_books(registered_names)
    if missing:
        raise AssertionError("\n".join([
            "Unclassified registered prefix-family books:",
            *(f"  - {name}" for name in missing),
            "Edit backtest/research/book_capabilities.py:",
            "  Add each book to PRICE_ADD_ELIGIBLE_BOOKS and/or S8_INDEPENDENT_BOOKS.",
            "  Keep MC-5 purposes distinct: price-add eligibility != S8 independent binding.",
            "  OR add it to PREFIX_FAMILY_OPT_OUT with a reason.",
        ]))


def allows_price_add(name: str | None, sizing: str | None) -> bool:
    """Whether this per-name book permits price adds and split group scans."""
    return sizing == "per_name" and name in PRICE_ADD_ELIGIBLE_BOOKS


def uses_s8_independent(name: str | None, sizing: str | None) -> bool:
    """Whether this book binds S8 and defaults on_short_cash to raise."""
    return sizing == "per_name" and name in S8_INDEPENDENT_BOOKS
