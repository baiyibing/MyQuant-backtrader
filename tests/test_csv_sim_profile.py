from __future__ import annotations

from backtest.research.csv_artifacts import summarize, write_run_artifacts
from backtest.research.csv_ledger import SimState
from backtest.research.csv_sim_profile import (
    SimPhaseClock,
    format_profile_lines,
    profile_sim_enabled,
    resolve_sim_clock,
    write_profile_sim,
)


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
