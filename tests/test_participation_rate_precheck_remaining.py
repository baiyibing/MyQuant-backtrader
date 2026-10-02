"""P2-B remaining-minute shell wires: v7/APP/L2/SENS; ≠δ5 certified ≠R4.

Data-free. Does not change simulate / MatchCore / VolumeCap.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backtest.research.ashare_volume_cap import BucketVolume
from backtest.research.csv_minute_volume import UNIT
from backtest.research.participation_rate_precheck import (
    precheck_cli_participation_rate,
    precheck_completed_bucket_samples,
)


def test_v7_cli_parser_exposes_participation_rate():
    from backtest.research.csv_minute_backtest_v7 import build_parser

    parser = build_parser()
    args = parser.parse_args(["--start", "20251024", "--end", "20251024", "--pool-dir", "x"])
    assert args.participation_rate is None
    args = parser.parse_args(
        ["--start", "20251024", "--end", "20251024", "--pool-dir", "x",
         "--participation-rate", "0.1"]
    )
    assert args.participation_rate == 0.1


def test_v7_cli_precheck_catches_qlib_before_load():
    from backtest.research import csv_minute_backtest_v7 as v7

    with pytest.raises(ValueError, match="raw lake minute volume in shares"):
        v7.main([
            "--start", "20251024", "--end", "20251024",
            "--pool-dir", "/tmp/no_such_pool",
            "--minute-source", "qlib_1min",
            "--participation-rate", "0.1",
        ])


def test_app_cli_parser_exposes_participation_rate():
    from backtest.research.csv_minute_backtest_topk_app_dropout import build_parser

    parser = build_parser()
    args = parser.parse_args(["--start", "20251024", "--end", "20251024", "--pool-dir", "x"])
    assert args.participation_rate is None


def test_rp_v7_adapter_shell_precheck(monkeypatch):
    from backtest.research.run_protocol.adapters import v7 as adapter
    from backtest.research.run_protocol.types import NativeApiRequest

    calls = []

    def fake_simulate(*args, **kwargs):
        calls.append(kwargs)
        return "ok"

    monkeypatch.setattr(
        "backtest.research.csv_minute_backtest_v7.simulate_v7", fake_simulate,
    )
    samples = {("600000.SH", "20251024", 571): BucketVolume(1000, 571, UNIT)}
    req = NativeApiRequest(
        family="v7",
        native_entry="csv_minute_backtest_v7.simulate_v7",
        args=(),
        kwargs={"participation_rate": 0.1, "volume_for_bucket": samples},
    )
    assert adapter.simulate_v7(req).native_value == "ok"
    assert calls and calls[0]["participation_rate"] == 0.1

    with pytest.raises(ValueError, match="finite and in"):
        adapter.simulate_v7(
            NativeApiRequest(
                family="v7",
                native_entry="csv_minute_backtest_v7.simulate_v7",
                kwargs={"participation_rate": 1.5},
            )
        )


def test_fullstrat_xor_still_rejects_cap_after_precheck():
    from backtest.research import fullstrat_research_v7 as fr
    from backtest.research.fullstrat_research_hooks import ResearchFillConfig

    cfg = ResearchFillConfig()
    with pytest.raises(ValueError, match="clock XOR slip"):
        fr.simulate({}, {}, {}, config=cfg, participation_rate=0.1)
    with pytest.raises(ValueError, match="finite and in"):
        fr.simulate({}, {}, {}, config=cfg, participation_rate=1.5)


def test_sens_helper_surface_and_semantics():
    src = Path("scripts/research/run_minute_sensitivity_b.py").read_text(encoding="utf-8")
    assert "def _shell_precheck_cap" in src
    assert "precheck_cli_participation_rate" in src
    assert "precheck_completed_bucket_samples" in src

    # Same shell semantics as the harness helper (data-free).
    def _shell_precheck_cap(rate, samples):
        precheck_cli_participation_rate(rate)
        if rate is None:
            return
        clean = {k: v for k, v in samples.items() if isinstance(v, BucketVolume)}
        if clean:
            precheck_completed_bucket_samples(clean)

    samples = {("600000.SH", "20251024", 571): BucketVolume(1000, 571, UNIT)}
    _shell_precheck_cap(None, {})
    _shell_precheck_cap(0.1, samples)
    with pytest.raises(ValueError, match="auction/open"):
        _shell_precheck_cap(
            0.1, {("600000.SH", "20251024", 570): BucketVolume(1000, 570, UNIT)}
        )


def test_l2_cli_precheck_surface():
    from backtest.research.minute_orders_backend import cli

    src = Path(cli.__file__).read_text(encoding="utf-8")
    assert "precheck_cli_participation_rate" in src
    assert "participation_rate_precheck" in src


def test_l2_source_loader_precheck_surface():
    from backtest.research.minute_orders_backend import source_loader

    src = Path(source_loader.__file__).read_text(encoding="utf-8")
    assert "precheck_cli_participation_rate" in src
