from __future__ import annotations

import pandas as pd

from backtest.research import csv_daily_backtest as daily
from backtest.research.csv_artifacts import summarize, write_run_artifacts
from backtest.research.csv_ledger import SimState
from backtest.research.csv_sim_profile import (
    SimPhaseClock,
    attach_host_profile,
    format_profile_lines,
    profile_sim_enabled,
    resolve_sim_clock,
    write_profile_sim,
)


def test_phase_share_excludes_wrapper_day_loop():
    clock = SimPhaseClock()
    clock.seconds["day_loop"] = 100.0
    clock.seconds["held_scan"] = 80.0
    clock.seconds["pool_buy"] = 20.0
    report = clock.report()
    assert report["phases_s"]["day_loop"] == 100.0
    assert "day_loop" not in report["phase_share"]
    assert report["phase_share"]["held_scan"] == 0.8
    assert report["phase_share"]["pool_buy"] == 0.2
    text = "\n".join(format_profile_lines(report))
    assert "日循环合计 100.0s" in text
    assert "日循环合计 100.0s (" not in text
    assert "持仓扫描 80.0s (80%)" in text


def test_phase_clock_accumulates_and_counts():
    clock = SimPhaseClock()
    clock.begin("held_scan")
    clock.count("held_codes", 3)
    clock.end("held_scan")
    with clock.phase("parking"):
        clock.count("calendar_days")
    report = clock.report(strategy="version6_53", rule_profile="industry")
    assert report["wall_s"] >= 0.0
    assert "held_scan" in report["phases_s"]
    assert "parking" in report["phases_s"]
    assert report["counts"]["held_codes"] == 3
    assert report["counts"]["calendar_days"] == 1
    assert report["strategy"] == "version6_53"
    assert report["started_at"]
    assert report["finished_at"]
    lines = format_profile_lines(report)
    assert any(line.startswith("  开始:") for line in lines)
    assert any("持仓扫描" in line for line in lines)


def test_summarize_and_artifact_write_profile(tmp_path):
    st = SimState(cash=21_000_000.0)
    st.sim_profile = {
        "started_at": "2026-10-09T11:00:00+08:00",
        "finished_at": "2026-10-09T11:10:00+08:00",
        "wall_s": 600.0,
        "phases_s": {"held_scan": 400.0, "pool_buy": 50.0},
        "phase_share": {"held_scan": 0.8889, "pool_buy": 0.1111},
        "counts": {"calendar_days": 215, "held_codes": 1000},
    }
    text = summarize(st, 21_000_000.0, "20251023", "20260909", engine="csv_minute_v6_53")
    assert "开始: 2026-10-09T11:00:00+08:00" in text
    assert "墙钟: 600.0s" in text
    assert "持仓扫描 400.0s" in text
    out = tmp_path / "run"
    write_run_artifacts(out, st, text, "LOCK")
    profile_path = out / "profile_sim.json"
    assert profile_path.is_file()
    raw = profile_path.read_bytes()
    assert raw.count(0) == 0
    assert b"held_scan" in raw


def test_write_profile_sim_utf8(tmp_path):
    path = write_profile_sim(tmp_path, {"started_at": "t0", "wall_s": 1.5, "phases_s": {}})
    data = path.read_bytes()
    assert data.count(0) == 0
    assert data.startswith(b"{")


def test_profile_sim_default_on_env_can_disable(monkeypatch):
    monkeypatch.delenv("OSKH_PROFILE_SIM", raising=False)
    assert profile_sim_enabled() is True
    assert profile_sim_enabled(None) is True
    assert profile_sim_enabled(True) is True
    assert profile_sim_enabled(False) is False
    monkeypatch.setenv("OSKH_PROFILE_SIM", "0")
    assert profile_sim_enabled() is False
    assert profile_sim_enabled(True) is False
    monkeypatch.setenv("OSKH_PROFILE_SIM", "1")
    assert profile_sim_enabled(False) is False
    monkeypatch.delenv("OSKH_PROFILE_SIM", raising=False)
    assert not isinstance(resolve_sim_clock(False), SimPhaseClock)
    assert isinstance(resolve_sim_clock(True), SimPhaseClock)


def test_daily_simulate_records_phases_without_changing_fills():
    symbol = "600000.SH"
    index = pd.to_datetime(["2025-10-31", "2025-11-03", "2025-11-04"])
    bars = {
        symbol: pd.DataFrame(
            {
                "open": [10.0, 10.0, 9.4],
                "high": [10.0, 10.1, 9.5],
                "low": [10.0, 9.9, 9.3],
                "close": [10.0, 10.0, 9.4],
            },
            index=index,
        )
    }
    kwargs = {
        "bars": bars,
        "pool_days": {"20251103": [symbol]},
        "start": "20251103",
        "end": "20251104",
        "strategy": "version6",
        "stop_pct": 0.02,
    }
    plain = daily.simulate(**kwargs)
    clock = SimPhaseClock()
    profiled = daily.simulate(**kwargs, sim_profile=clock)
    assert [t["side"] for t in plain.trades] == [t["side"] for t in profiled.trades]
    assert not hasattr(plain, "sim_profile")
    for name in (
        "day_loop",
        "parking",
        "index_cut",
        "held_scan",
        "chase",
        "pool_buy",
        "eod",
        "finish",
    ):
        assert name in clock.seconds
    assert clock.counts["calendar_days"] == 2
    attach_host_profile(
        profiled,
        clock,
        strategy="version6",
        rule_profile="industry",
        load_s={"t_pool_s": 0.1, "t_daily_s": 0.2, "t_sim_s": 0.5},
    )
    assert profiled.sim_profile["strategy"] == "version6"
    assert "开始:" in "\n".join(format_profile_lines(profiled.sim_profile))
