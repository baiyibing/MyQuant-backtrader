"""Locate the first accounting-component divergence between two CSV runs.

This is an opt-in, post-run reader.  It never invokes an engine and writes only
the path explicitly supplied with ``--out``.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backtest.research.accounting_invariants import (
    DEFAULT_TOLERANCES,
    AccountingTolerances,
)

COMPONENT_PRIORITY = (
    "fees",
    "per_name_shares",
    "receivable",
    "cash",
    "valuation",
)


@dataclass(frozen=True)
class SemanticDifference:
    first_date: str
    component: str
    components: tuple[str, ...]
    left: Any
    right: Any


def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return frame.to_dict("records")


def _date(value: Any) -> str:
    if value is None or pd.isna(value):
        raise ValueError("date is required")
    text = str(value).strip()
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:]}"
    return pd.Timestamp(value).date().isoformat()


def _number(row: dict[str, Any], *names: str) -> float | None:
    for name in names:
        if name in row and not pd.isna(row[name]):
            return float(row[name])
    return None


def _quantity(row: dict[str, Any]) -> int:
    for name in ("shares", "executed_quantity", "qty"):
        if name in row and not pd.isna(row[name]):
            return int(float(row[name]))
    return 0


def _name(row: dict[str, Any]) -> str:
    raw_code = row.get("code", row.get("symbol", ""))
    raw_position_id = row.get("position_id", "")
    code = "" if pd.isna(raw_code) else str(raw_code).strip()
    position_id = "" if pd.isna(raw_position_id) else str(raw_position_id).strip()
    return f"{code}|{position_id}" if position_id else code


def _timeline(equity: pd.DataFrame, trades: pd.DataFrame) -> dict[str, dict[str, Any]]:
    events: dict[str, list[dict[str, Any]]] = defaultdict(list)
    equity_rows: dict[str, dict[str, Any]] = {}
    for row in _records(trades):
        events[_date(row["date"])].append(row)
    for row in _records(equity):
        equity_rows[_date(row["date"])] = row

    dates = sorted(set(events) | set(equity_rows))
    shares: dict[str, int] = defaultdict(int)
    fees = 0.0
    cash_delta = 0.0
    last_equity: dict[str, Any] | None = None
    timeline: dict[str, dict[str, Any]] = {}
    for day in dates:
        for row in events.get(day, ()):
            side = str(row.get("side", "")).strip().upper()
            if side not in {"BUY", "SELL"}:
                continue
            quantity = _quantity(row)
            name = _name(row)
            shares[name] += quantity if side == "BUY" else -quantity
            fee = _number(row, "commission", "fee", "fee_delta") or 0.0
            fees += fee
            notional = _number(row, "notional")
            if notional is None:
                price = _number(row, "price") or 0.0
                notional = quantity * price
            cash_delta += -notional - fee if side == "BUY" else notional - fee

        if day in equity_rows:
            last_equity = equity_rows[day]
        row = last_equity or {}
        cash = _number(row, "cash")
        cash_component = cash_delta if cash is None else cash
        receivable = _number(row, "receivable")
        holdings = _number(row, "holdings")
        equity_value = _number(row, "equity")
        if receivable is None:
            if None not in (equity_value, cash, holdings):
                receivable = equity_value - cash - holdings
            else:
                receivable = 0.0
        if holdings is not None:
            valuation = holdings
        elif equity_value is not None:
            valuation = equity_value - cash_component - receivable
        else:
            valuation = None
        timeline[day] = {
            "cash": cash_component,
            "per_name_shares": {key: value for key, value in sorted(shares.items()) if value},
            "receivable": receivable,
            "fees": fees,
            "valuation": valuation,
        }
    return timeline


def _different(
    component: str,
    left: Any,
    right: Any,
    tolerances: AccountingTolerances,
) -> bool:
    if component == "per_name_shares":
        return left != right
    if left is None or right is None:
        return left is not right
    tolerance = {
        "fees": tolerances.fee,
        "receivable": tolerances.cash,
        "cash": tolerances.cash,
        "valuation": tolerances.valuation,
    }[component]
    return abs(float(left) - float(right)) > tolerance


def first_semantic_difference(
    left_equity: pd.DataFrame,
    left_trades: pd.DataFrame,
    right_equity: pd.DataFrame,
    right_trades: pd.DataFrame,
    *,
    tolerances: AccountingTolerances = DEFAULT_TOLERANCES,
) -> SemanticDifference | None:
    """Return the first date/component divergence, or ``None`` when equivalent.

    Multiple components can diverge on the same first date.  The complete set
    is returned in ``components``; ``component`` uses the causal localization
    priority fees, shares, receivable, cash, then valuation.
    """

    left = _timeline(left_equity, left_trades)
    right = _timeline(right_equity, right_trades)
    empty = {
        "cash": 0.0,
        "per_name_shares": {},
        "receivable": 0.0,
        "fees": 0.0,
        "valuation": None,
    }
    left_state = empty
    right_state = empty
    for day in sorted(set(left) | set(right)):
        left_state = left.get(day, left_state)
        right_state = right.get(day, right_state)
        components = tuple(
            component
            for component in COMPONENT_PRIORITY
            if _different(
                component,
                left_state[component],
                right_state[component],
                tolerances,
            )
        )
        if components:
            primary = components[0]
            return SemanticDifference(
                day,
                primary,
                components,
                left_state[primary],
                right_state[primary],
            )
    return None


def compare_run_dirs(
    left_dir: Path,
    right_dir: Path,
    *,
    tolerances: AccountingTolerances = DEFAULT_TOLERANCES,
) -> dict[str, Any]:
    left_dir = Path(left_dir)
    right_dir = Path(right_dir)
    difference = first_semantic_difference(
        pd.read_csv(left_dir / "daily_equity.csv"),
        pd.read_csv(left_dir / "trades.csv"),
        pd.read_csv(right_dir / "daily_equity.csv"),
        pd.read_csv(right_dir / "trades.csv"),
        tolerances=tolerances,
    )
    return {
        "equal": difference is None,
        "first_difference": None if difference is None else asdict(difference),
        "left": str(left_dir),
        "right": str(right_dir),
        "component_priority": list(COMPONENT_PRIORITY),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Locate the first accounting-component difference between two run dirs."
    )
    parser.add_argument("left", type=Path, help="first run output directory")
    parser.add_argument("right", type=Path, help="second run output directory")
    parser.add_argument("--out", type=Path, required=True, help="required JSON report path")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = compare_run_dirs(args.left, args.right)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
