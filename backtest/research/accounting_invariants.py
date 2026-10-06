"""Pure, opt-in accounting checks over existing research output frames.

The checker does not read files, mutate frames, raise for detected violations,
or participate in a simulate path.  Share quantities are exact integers.
Float comparisons are limited to exported cash/notional/equity values and use
the explicit :class:`AccountingTolerances` absolute tolerances below.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from math import isfinite
from typing import Any

import pandas as pd

CHECK_ERRORS = (KeyError, OverflowError, TypeError, ValueError)


@dataclass(frozen=True)
class AccountingTolerances:
    """Absolute tolerances for float values; share accounting remains exact."""

    cash: float = 1e-6
    fee: float = 1e-12
    notional: float = 1e-8
    valuation: float = 1e-6


DEFAULT_TOLERANCES = AccountingTolerances()


@dataclass(frozen=True)
class InvariantViolation:
    invariant: str
    component: str
    date: str | None
    detail: str
    actual: Any = None
    expected: Any = None
    name: str | None = None
    row: int | None = None


def _records(frame: Any) -> list[dict[str, Any]]:
    if frame is None:
        return []
    if isinstance(frame, pd.DataFrame):
        return frame.to_dict("records")
    if isinstance(frame, Mapping):
        return [dict(frame)]
    return [dict(row) for row in frame]


def _date(value: Any) -> str:
    if value is None or pd.isna(value):
        raise ValueError("date is required")
    text = str(value).strip()
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:]}"
    timestamp = pd.Timestamp(value)
    if pd.isna(timestamp):
        raise ValueError("date is required")
    return timestamp.date().isoformat()


def _number(value: Any) -> float:
    result = float(value)
    if not isfinite(result):
        raise ValueError("value must be finite")
    return result


def _optional_number(row: Mapping[str, Any], *names: str) -> tuple[float | None, bool]:
    for name in names:
        if name in row and not pd.isna(row[name]):
            return _number(row[name]), True
    return None, False


def _shares(row: Mapping[str, Any]) -> int:
    value = next(row[name] for name in ("shares", "executed_quantity", "qty") if name in row)
    number = _number(value)
    if not number.is_integer():
        raise ValueError("shares must be an integer")
    return int(number)


def _name(row: Mapping[str, Any]) -> tuple[str, str]:
    raw_code = row.get("code", row.get("symbol", ""))
    raw_position_id = row.get("position_id", "")
    code = "" if pd.isna(raw_code) else str(raw_code).strip()
    position_id = "" if pd.isna(raw_position_id) else str(raw_position_id).strip()
    key = f"{code}|{position_id}" if position_id else code
    return key, code


def _add(
    violations: list[InvariantViolation],
    invariant: str,
    component: str,
    *,
    date: str | None,
    detail: str,
    actual: Any = None,
    expected: Any = None,
    name: str | None = None,
    row: int | None = None,
) -> None:
    violations.append(
        InvariantViolation(invariant, component, date, detail, actual, expected, name, row)
    )


def check_accounting_invariants(
    daily_equity: Any,
    trades_or_fills: Any,
    *,
    initial_cash: float | None = None,
    tolerances: AccountingTolerances = DEFAULT_TOLERANCES,
) -> list[InvariantViolation]:
    """Return all observable accounting violations without raising by default.

    Supported event aliases are ``code``/``symbol``, ``shares``/``qty``/
    ``executed_quantity``, and ``commission``/``fee``/``fee_delta``.
    Cash conservation is checked per fill when ``cash_before`` and
    ``cash_after`` are exported.  It is also checked against daily cash when
    every fill exports a fee and daily equity exports ``cash``.  An optional
    ``receivable_settlement`` column is included in that daily cash equation.

    Lots reconstructed from BUY/SELL events enforce exact per-name shares and
    T+1 (sell date must be later than acquisition date).  ``position_id``, when
    present, keeps S8 signal positions independent.  Final ``EOD_MARK`` rows
    are compared with reconstructed open shares.

    Equity rows with explicit ``cash``, ``holdings`` and ``receivable`` must
    satisfy the full equation.  If ``receivable`` is absent, a non-negative
    ``equity - cash - holdings`` is accepted as an unexported receivable.
    """

    violations: list[InvariantViolation] = []
    try:
        events = _records(trades_or_fills)
        equities = _records(daily_equity)
    except CHECK_ERRORS as exc:
        return [
            InvariantViolation(
                "schema",
                "input",
                None,
                f"frames could not be converted to records: {exc}",
            )
        ]

    lots: dict[str, list[list[Any]]] = defaultdict(list)
    marks: dict[tuple[str, str], int] = defaultdict(int)
    daily_flows: dict[str, float] = defaultdict(float)
    daily_fees_complete: dict[str, bool] = defaultdict(lambda: True)
    event_dates: set[str] = set()

    for index, row in enumerate(events):
        try:
            day = _date(row.get("date"))
            side = str(row.get("side", "")).strip().upper()
        except CHECK_ERRORS as exc:
            _add(
                violations,
                "schema",
                "event",
                date=None,
                detail=f"invalid event date/side: {exc}",
                row=index,
            )
            continue
        event_dates.add(day)
        if side not in {"BUY", "SELL", "EOD_MARK"}:
            continue

        try:
            quantity = _shares(row)
            name, code = _name(row)
        except CHECK_ERRORS as exc:
            _add(
                violations,
                "schema",
                "shares",
                date=day,
                detail=str(exc),
                row=index,
            )
            continue
        if not code:
            _add(
                violations,
                "schema",
                "shares",
                date=day,
                detail="event has no code/symbol",
                row=index,
            )
            continue
        if quantity < 0:
            _add(
                violations,
                "non_negative_shares",
                "per_name_shares",
                date=day,
                detail="event shares are negative",
                actual=quantity,
                expected=0,
                name=name,
                row=index,
            )
            continue
        if side == "EOD_MARK":
            marks[(day, name)] += quantity
            continue

        fee = None
        fee_present = False
        try:
            fee, fee_present = _optional_number(row, "commission", "fee", "fee_delta")
        except CHECK_ERRORS as exc:
            _add(
                violations,
                "schema",
                "fees",
                date=day,
                detail=f"invalid fee: {exc}",
                name=name,
                row=index,
            )
        if fee_present and fee is not None and fee < -tolerances.fee:
            _add(
                violations,
                "non_negative_fees",
                "fees",
                date=day,
                detail="fee is negative",
                actual=fee,
                expected=0.0,
                name=name,
                row=index,
            )

        try:
            notional, notional_present = _optional_number(row, "notional")
            price, price_present = _optional_number(row, "price")
        except CHECK_ERRORS as exc:
            _add(
                violations,
                "schema",
                "cash",
                date=day,
                detail=f"invalid notional/price: {exc}",
                name=name,
                row=index,
            )
            notional = None
            notional_present = price_present = False
            price = None
        if not notional_present and price_present:
            notional = quantity * price
            notional_present = True
        if notional_present and notional is not None:
            if notional < -tolerances.notional:
                _add(
                    violations,
                    "non_negative_notional",
                    "cash",
                    date=day,
                    detail="notional is negative",
                    actual=notional,
                    expected=0.0,
                    name=name,
                    row=index,
                )
            if price_present:
                expected_notional = quantity * price
                if abs(notional - expected_notional) > tolerances.notional:
                    _add(
                        violations,
                        "fill_notional",
                        "cash",
                        date=day,
                        detail="notional differs from shares times price",
                        actual=notional,
                        expected=expected_notional,
                        name=name,
                        row=index,
                    )

        cash_before = cash_after = None
        before_present = after_present = False
        try:
            cash_before, before_present = _optional_number(row, "cash_before")
            cash_after, after_present = _optional_number(row, "cash_after")
        except CHECK_ERRORS as exc:
            _add(
                violations,
                "schema",
                "cash",
                date=day,
                detail=f"invalid cash snapshot: {exc}",
                name=name,
                row=index,
            )
        for label, value, present in (
            ("cash_before", cash_before, before_present),
            ("cash_after", cash_after, after_present),
        ):
            if present and value is not None and value < -tolerances.cash:
                _add(
                    violations,
                    "non_negative_cash",
                    "cash",
                    date=day,
                    detail=f"{label} is negative",
                    actual=value,
                    expected=0.0,
                    name=name,
                    row=index,
                )
        if (
            before_present
            and after_present
            and fee_present
            and notional_present
            and None not in (cash_before, cash_after, fee, notional)
        ):
            expected_cash = (
                cash_before - notional - fee if side == "BUY" else cash_before + notional - fee
            )
            if abs(cash_after - expected_cash) > tolerances.cash:
                _add(
                    violations,
                    "cash_conservation",
                    "cash",
                    date=day,
                    detail="fill cash transition does not conserve cash",
                    actual=cash_after,
                    expected=expected_cash,
                    name=name,
                    row=index,
                )

        if not (fee_present and notional_present and fee is not None and notional is not None):
            daily_fees_complete[day] = False
        else:
            daily_flows[day] += -notional - fee if side == "BUY" else notional - fee

        if side == "BUY":
            lots[name].append([day, quantity])
            continue

        held = sum(item[1] for item in lots[name])
        sellable = sum(item[1] for item in lots[name] if item[0] < day)
        if quantity > held:
            _add(
                violations,
                "share_conservation",
                "per_name_shares",
                date=day,
                detail="sell exceeds reconstructed held shares",
                actual=quantity,
                expected=held,
                name=name,
                row=index,
            )
        if quantity > sellable:
            _add(
                violations,
                "t1_sellable",
                "per_name_shares",
                date=day,
                detail="sell exceeds shares acquired before this date",
                actual=quantity,
                expected=sellable,
                name=name,
                row=index,
            )
        remaining = quantity
        for lot in sorted(lots[name], key=lambda item: item[0] >= day):
            take = min(lot[1], remaining)
            lot[1] -= take
            remaining -= take
            if not remaining:
                break
        lots[name] = [item for item in lots[name] if item[1] > 0]

    for (day, name), marked in sorted(marks.items()):
        held = sum(item[1] for item in lots[name])
        if marked != held:
            _add(
                violations,
                "share_conservation",
                "per_name_shares",
                date=day,
                detail="EOD_MARK shares differ from reconstructed held shares",
                actual=marked,
                expected=held,
                name=name,
            )

    equity_by_date: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(equities):
        try:
            day = _date(row.get("date"))
        except CHECK_ERRORS as exc:
            _add(
                violations,
                "schema",
                "valuation",
                date=None,
                detail=f"invalid equity date: {exc}",
                row=index,
            )
            continue
        equity_by_date[day] = row
        values: dict[str, tuple[float | None, bool]] = {}
        for field in ("cash", "holdings", "receivable", "equity"):
            try:
                values[field] = _optional_number(row, field)
            except CHECK_ERRORS as exc:
                _add(
                    violations,
                    "schema",
                    "valuation",
                    date=day,
                    detail=f"invalid {field}: {exc}",
                    row=index,
                )
                values[field] = (None, False)
        cash, has_cash = values["cash"]
        holdings, has_holdings = values["holdings"]
        receivable, has_receivable = values["receivable"]
        equity, has_equity = values["equity"]
        for field, value, present, tolerance in (
            ("cash", cash, has_cash, tolerances.cash),
            ("holdings", holdings, has_holdings, tolerances.valuation),
            ("receivable", receivable, has_receivable, tolerances.cash),
        ):
            if present and value is not None and value < -tolerance:
                _add(
                    violations,
                    f"non_negative_{field}",
                    "valuation" if field == "holdings" else field,
                    date=day,
                    detail=f"{field} is negative",
                    actual=value,
                    expected=0.0,
                    row=index,
                )
        if has_cash and has_holdings and has_equity:
            base = cash + holdings
            if has_receivable:
                expected_equity = base + receivable
                if abs(equity - expected_equity) > tolerances.valuation:
                    _add(
                        violations,
                        "equity_identity",
                        "valuation",
                        date=day,
                        detail="equity differs from cash + holdings + receivable",
                        actual=equity,
                        expected=expected_equity,
                        row=index,
                    )
            elif equity < base - tolerances.valuation:
                _add(
                    violations,
                    "equity_identity",
                    "valuation",
                    date=day,
                    detail="equity is below cash + holdings; implied receivable is negative",
                    actual=equity,
                    expected=base,
                    row=index,
                )

    cash_rows = [
        (day, row)
        for day, row in sorted(equity_by_date.items())
        if "cash" in row and not pd.isna(row["cash"])
    ]
    if cash_rows and all(daily_fees_complete[day] for day in event_dates):
        try:
            running = _number(initial_cash) if initial_cash is not None else None
        except CHECK_ERRORS as exc:
            _add(
                violations,
                "schema",
                "cash",
                date=None,
                detail=f"invalid initial_cash: {exc}",
            )
            running = None
        for day, row in cash_rows:
            try:
                reported = _number(row["cash"])
                settlement, has_settlement = _optional_number(row, "receivable_settlement")
            except CHECK_ERRORS as exc:
                _add(
                    violations,
                    "schema",
                    "cash",
                    date=day,
                    detail=f"invalid daily cash/settlement: {exc}",
                )
                continue
            movement = daily_flows.get(day, 0.0) + (settlement if has_settlement else 0.0)
            if running is None:
                running = reported
            else:
                running += movement
                if abs(reported - running) > tolerances.cash:
                    _add(
                        violations,
                        "cash_conservation",
                        "cash",
                        date=day,
                        detail="daily cash differs from prior cash plus fills and settlement",
                        actual=reported,
                        expected=running,
                    )
                running = reported

    return violations


__all__ = [
    "DEFAULT_TOLERANCES",
    "AccountingTolerances",
    "InvariantViolation",
    "check_accounting_invariants",
]
