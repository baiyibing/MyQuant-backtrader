"""RB-16 opt-in accounting checks and semantic localization (data-free)."""

from __future__ import annotations

import ast
import json
from datetime import date
from pathlib import Path

import pandas as pd
import pytest
from backtest.research.accounting_invariants import check_accounting_invariants
from backtest.research.ashare_fees import QLIB_CLOSE_COST, QLIB_MIN_COST, QLIB_OPEN_COST
from backtest.research.csv_ledger import SimState, _sell, execute_buy
from backtest.research.minute_audit import audit_scope
from scripts.research.rb16_semantic_diff import (
    first_semantic_difference,
)
from scripts.research.rb16_semantic_diff import (
    main as semantic_diff_main,
)

ROOT = Path(__file__).resolve().parents[1]
CODE = "600000.SH"


def test_real_shared_ledger_min_fee_t1_partial_sell_has_no_violations():
    events: list[dict] = []
    state = SimState(
        cash=2_000.0,
        buy_cost_rate=QLIB_OPEN_COST,
        sell_cost_rate=QLIB_CLOSE_COST,
        min_cost=QLIB_MIN_COST,
    )
    with audit_scope(events, decision_hm=895, phase="close"):
        assert execute_buy(
            state,
            CODE,
            10.0,
            1_000.0,
            0,
            pd.Timestamp("2025-11-03"),
            shares_override=100,
        )
    day1_cash = state.cash
    with audit_scope(events, decision_hm=570, phase="open"):
        sold = _sell(
            state,
            CODE,
            state.positions[CODE][0],
            10.0,
            pd.Timestamp("2025-11-04"),
            "ma_signal:partial",
            wanted_shares=40,
            day_i=1,
        )
    assert sold == 40
    assert [event["commission"] for event in events] == [5.0, 5.0]
    assert state.positions[CODE][0].shares == 60
    equity = pd.DataFrame(
        [
            {
                "date": "2025-11-03",
                "cash": day1_cash,
                "holdings": 1_000.0,
                "receivable": 0.0,
                "equity": day1_cash + 1_000.0,
            },
            {
                "date": "2025-11-04",
                "cash": state.cash,
                "holdings": 600.0,
                "receivable": 0.0,
                "equity": state.cash + 600.0,
            },
        ]
    )
    assert check_accounting_invariants(equity, pd.DataFrame(events), initial_cash=2_000.0) == []


def test_real_daily_s8_independent_positions_have_no_violations():
    from backtest.research.csv_daily_backtest import simulate

    days = pd.bdate_range("2025-11-03", periods=3)
    index = pd.DatetimeIndex([days[0] - pd.Timedelta(days=3), *days])
    bars = {
        CODE: pd.DataFrame(
            {
                "open": [10.0, 10.0, 10.1, 10.2],
                "high": [10.0, 10.0, 10.1, 10.2],
                "low": [10.0, 10.0, 10.1, 10.2],
                "close": [10.0, 10.0, 10.1, 10.2],
            },
            index=index,
        )
    }
    pool = {
        days[0].strftime("%Y%m%d"): [CODE],
        days[1].strftime("%Y%m%d"): [CODE],
    }
    state = simulate(
        bars,
        pool,
        days[0].strftime("%Y%m%d"),
        days[-1].strftime("%Y%m%d"),
        strategy="version8",
        take_profit=lambda *_args: None,
    )
    buys = [row for row in state.trades if row["side"] == "BUY"]
    assert len(buys) == 2
    assert len({row["position_id"] for row in buys}) == 2
    assert (
        check_accounting_invariants(
            pd.DataFrame(state.equity_curve, columns=["date", "equity"]),
            pd.DataFrame(state.trades),
        )
        == []
    )


def test_real_v7_t1_output_has_no_violations():
    from backtest.research.csv_minute_backtest_v7 import simulate_v7

    d1, d2 = date(2026, 9, 1), date(2026, 9, 2)
    minute = {
        CODE: [
            {
                "date": d1,
                "hm": 895,
                "open": 100.0,
                "high": 100.0,
                "low": 100.0,
                "close": 100.0,
            },
            {
                "date": d2,
                "hm": 570,
                "open": 89.0,
                "high": 89.0,
                "low": 89.0,
                "close": 89.0,
            },
        ]
    }
    daily = {CODE: {date(2026, 8, 31): 100.0, d1: 98.0}}
    state = simulate_v7(minute, daily, {d1: [CODE]}, [d1, d2])
    fills = [row for row in state.trades if row["side"] in {"buy", "sell"}]
    assert [row["date"] for row in fills] == [d1.isoformat(), d2.isoformat()]
    assert (
        check_accounting_invariants(pd.DataFrame(state.equity_curve), pd.DataFrame(state.trades))
        == []
    )


def test_broken_frames_report_cash_t1_fee_and_valuation_components():
    cash = pd.DataFrame(
        [
            {
                "date": "2025-11-03",
                "code": CODE,
                "side": "BUY",
                "shares": 100,
                "price": 10.0,
                "notional": 1_000.0,
                "commission": 5.0,
                "cash_before": 2_000.0,
                "cash_after": 996.0,
            }
        ]
    )
    cash_violations = check_accounting_invariants(None, cash)
    assert any(
        item.invariant == "cash_conservation" and item.component == "cash"
        for item in cash_violations
    )

    t1_and_fee = pd.DataFrame(
        [
            {
                "date": "2025-11-03",
                "code": CODE,
                "side": "BUY",
                "shares": 100,
                "price": 10.0,
                "commission": 1.0,
            },
            {
                "date": "2025-11-03",
                "code": CODE,
                "side": "SELL",
                "shares": 100,
                "price": 10.0,
                "commission": -1.0,
            },
        ]
    )
    violations = check_accounting_invariants(None, t1_and_fee)
    assert any(item.invariant == "t1_sellable" for item in violations)
    assert any(item.invariant == "non_negative_fees" for item in violations)

    bad_equity = pd.DataFrame(
        [
            {
                "date": "2025-11-03",
                "cash": 100.0,
                "holdings": 50.0,
                "receivable": 10.0,
                "equity": 159.0,
            }
        ]
    )
    violations = check_accounting_invariants(bad_equity, None)
    assert [(item.invariant, item.component) for item in violations] == [
        ("equity_identity", "valuation")
    ]


def test_semantic_diff_localizes_first_fee_date_and_cli_writes_only_out(tmp_path):
    equity = pd.DataFrame(
        [
            {"date": "2025-11-03", "equity": 2_000.0},
            {"date": "2025-11-04", "equity": 2_010.0},
        ]
    )
    common = {
        "date": "2025-11-03",
        "code": CODE,
        "side": "BUY",
        "shares": 100,
        "price": 10.0,
        "notional": 1_000.0,
    }
    left_trades = pd.DataFrame([{**common, "commission": 1.0}])
    right_trades = pd.DataFrame([{**common, "commission": 5.0}])
    difference = first_semantic_difference(equity, left_trades, equity, right_trades)
    assert difference is not None
    assert difference.first_date == "2025-11-03"
    assert difference.component == "fees"
    assert "cash" in difference.components

    left = tmp_path / "left"
    right = tmp_path / "right"
    left.mkdir()
    right.mkdir()
    equity.to_csv(left / "daily_equity.csv", index=False)
    equity.to_csv(right / "daily_equity.csv", index=False)
    left_trades.to_csv(left / "trades.csv", index=False)
    right_trades.to_csv(right / "trades.csv", index=False)
    out = tmp_path / "report.json"
    assert semantic_diff_main([str(left), str(right), "--out", str(out)]) == 0
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["first_difference"]["first_date"] == "2025-11-03"
    assert report["first_difference"]["component"] == "fees"
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "left",
        "report.json",
        "right",
    ]


@pytest.mark.parametrize(
    "relative",
    [
        "backtest/research/csv_daily_backtest.py",
        "backtest/research/csv_minute_backtest.py",
        "backtest/research/csv_minute_backtest_v7.py",
        "backtest/research/csv_ledger.py",
        "backtest/research/csv_simulate_loop.py",
        "backtest/research/csv_artifacts.py",
        "scripts/research/generate_off_byte_baseline.py",
    ],
)
def test_default_simulate_export_and_baseline_paths_do_not_import_rb16(relative):
    path = ROOT / relative
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
    assert not any(
        "accounting_invariants" in name or "rb16_semantic_diff" in name for name in imports
    )
