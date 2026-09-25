"""Audit uses actual invocation clocks and is observational only."""

import json
from dataclasses import asdict

import pytest
from backtest.research.csv_minute_backtest import simulate

from tests.minute_cash_fixtures import chronological_case, money


@pytest.mark.parametrize("enabled", [False, True])
def test_sidecar_preserves_state_and_records_real_clock_cash(enabled):
    trace = []
    plain = simulate(**chronological_case(), fix_minute_cash_order=enabled)
    observed = simulate(**chronological_case(), fix_minute_cash_order=enabled, audit_sink=trace)
    assert asdict(observed) == asdict(plain)
    assert "fix_minute_cash_order" not in observed.stats
    assert len(trace) == 3
    assert [(row["decision_hm"], row["side"]) for row in trace] == (
        [(895, "BUY"), (895, "SKIP"), (899, "SELL")] if enabled
        else [(895, "BUY"), (899, "SELL"), (895, "BUY")]
    )
    for row in trace:
        amount = row["notional"]
        expected = (row["cash_before"] - amount - row["commission"] if row["side"] == "BUY"
                    else row["cash_before"] + amount - row["commission"])
        assert money(row["cash_after"]) == money(expected)
        assert money(row["cash_after"]) >= 0
        assert row["hm"] == row["decision_hm"] == row["quote_hm"]
        assert row["phase"] == "close"


def test_target_decision_clock_retains_earlier_quote_clock():
    trace = []
    # Capacity callback contract is tested in the chronology suite; this audit
    # control intentionally leaves capacity disabled while retaining quote_hm.
    state = simulate(**chronological_case(sell_hm=893, buy_hm=890),
                     fix_minute_cash_order=True, audit_sink=trace)
    assert money(state.cash) == money(338.46)
    assert trace[-1]["decision_hm"] == 895
    assert trace[-1]["quote_hm"] == 890
    assert trace[-1]["phase"] == "close"


@pytest.mark.parametrize("enabled", [False, True])
def test_shared_cli_audit_sidecar_preserves_csv_surface(tmp_path, monkeypatch, enabled):
    from backtest.research import csv_minute_backtest as minute
    def frozen_run(*args, **kwargs):
        return simulate(**chronological_case(), fix_minute_cash_order=kwargs["fix_minute_cash_order"],
                        audit_sink=kwargs["audit_sink"])
    monkeypatch.setattr(minute, "run", frozen_run)
    monkeypatch.setattr(minute, "maybe_compare_daily", lambda *a, **kw: None)
    output, audit = tmp_path / "out", tmp_path / "audit.json"
    args = ["--strategy", "version8", "--start", "20251104", "--end", "20251105",
            "--pool-dir", str(tmp_path), "--out-dir", str(output), "--execution-audit-file", str(audit)]
    assert minute.main(args + (["--fix-minute-cash-order"] if enabled else [])) == 0
    payload = json.loads(audit.read_text())
    assert payload["fix_minute_cash_order"] is enabled
    assert payload["order"] == "actual_invocation_order"
    assert len(payload["events"]) == 3
    assert "decision_hm" not in (output / "trades.csv").read_text().splitlines()[0]


@pytest.mark.parametrize("enabled", [False, True])
def test_v7_cli_audit_and_run_config(tmp_path, monkeypatch, enabled):
    from backtest.research import csv_minute_backtest_v7 as v7

    from tests.test_v7_cash_chronology import chronological_case as v7_case
    case = v7_case()
    monkeypatch.setattr(v7, "load_pool_days", lambda *a: case["pool_days"])
    monkeypatch.setattr(v7, "_load_cli_bars", lambda *a, **kw: (case["minute_bars"], case["daily_bars"]))
    monkeypatch.setattr(v7, "load_limit_context", lambda *a: ({}, {}))
    monkeypatch.setattr(v7, "load_index_daily", lambda *a: case["index_days"])
    output, audit = tmp_path / "out", tmp_path / "audit.json"
    args = ["--start", "20260901", "--end", "20260902", "--cash-total", "421000",
            "--pool-dir", str(tmp_path), "--output-dir", str(output), "--execution-audit-file", str(audit)]
    assert v7.main(args + (["--fix-minute-cash-order"] if enabled else [])) == 0
    payload = json.loads(audit.read_text())
    assert payload["fix_minute_cash_order"] is enabled
    assert len(payload["events"]) == 4
    config = json.loads((output / "run-config.json").read_text())
    assert config["fix_minute_cash_order"] is enabled
    assert "cash_before" not in (output / "trades.csv").read_text().splitlines()[0]
