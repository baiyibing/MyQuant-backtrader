# -*- coding: utf-8 -*-
"""CLI coverage for csv_daily --out-dir (M5-R4). Lake is not required."""

from __future__ import annotations

from pathlib import Path

import backtest.research.csv_daily_backtest as sim
from backtest.research.csv_ledger import SimState


def _stub_state() -> SimState:
    st = SimState(cash=21_000_000.0)
    st.equity_curve = [("20260303", 21_000_000.0)]
    st.stats["sell_book"] = "v6"
    st.stats["profit_base"] = 0.08
    st.stats["trail_t1"] = 0.03
    st.stats["trail_t2"] = 0.04
    st.stats["stop_pct"] = 0.06
    return st


def test_resolve_out_dir_explicit_wins_over_legacy_layout(tmp_path: Path):
    dest = tmp_path / "m5_pred"
    assert sim.resolve_csv_daily_out_dir(
        dest, book="v6", start="20260303", end="20260323"
    ) == dest
    assert sim.resolve_csv_daily_out_dir(
        None, book="v6", start="20260303", end="20260323"
    ) == Path(sim.REPO) / "backtest_output" / "csv_daily_v6_20260303_20260323"


def test_cli_out_dir_writes_artifacts_there(tmp_path: Path, monkeypatch):
    dest = tmp_path / "m5_hand"
    monkeypatch.setattr(sim, "run", lambda *a, **k: _stub_state())
    rc = sim.main(
        [
            "--strategy",
            "version6",
            "--start",
            "20260303",
            "--end",
            "20260323",
            "--out-dir",
            str(dest),
        ]
    )
    assert rc == 0
    assert (dest / "summary.txt").is_file()
    assert (dest / "daily_equity.csv").is_file()
    assert (dest / "trades.csv").is_file()
    summary = (dest / "summary.txt").read_text(encoding="utf-8")
    assert "csv_daily_v6 20260303..20260323" in summary
    legacy = Path(sim.REPO) / "backtest_output" / "csv_daily_v6_20260303_20260323"
    assert not legacy.exists()


def test_cli_omitted_out_dir_keeps_legacy_layout(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(sim, "REPO", str(tmp_path))
    monkeypatch.setattr(sim, "run", lambda *a, **k: _stub_state())
    rc = sim.main(
        ["--strategy", "version6", "--start", "20260303", "--end", "20260323"]
    )
    assert rc == 0
    out = tmp_path / "backtest_output" / "csv_daily_v6_20260303_20260323"
    assert (out / "summary.txt").is_file()
    assert (out / "daily_equity.csv").is_file()
    assert (out / "trades.csv").is_file()
