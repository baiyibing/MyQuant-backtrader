# -*- coding: utf-8 -*-
"""Data-free unit tests for exdiv_map (slice A)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from backtest.research import exdiv_map as em


def _write_adj(path: Path, rows: list[tuple[str, str, float]]) -> Path:
    pd.DataFrame(
        {
            "date": [r[0] for r in rows],
            "stock_code": [r[1] for r in rows],
            "cumulative_adj_factor": [r[2] for r in rows],
        }
    ).to_parquet(path, index=False)
    return path


def _write_ex(path: Path, rows: list[tuple[str, str]]) -> Path:
    pd.DataFrame(
        {"stock_code": [r[0] for r in rows], "ex_date": [r[1] for r in rows]}
    ).to_parquet(path, index=False)
    return path


def test_ex_event_primary_builds_k(tmp_path: Path):
    adj = _write_adj(
        tmp_path / "adj_factor.parquet",
        [
            ("20251103", "600000.SH", 1.0),
            ("20251104", "600000.SH", 1.0),
            ("20251105", "600000.SH", 2.0),  # ex day, k=0.5
            ("20251106", "600000.SH", 2.0),
        ],
    )
    ex = _write_ex(tmp_path / "ex_date_index.parquet", [("600000.SH", "20251105")])
    skipped: dict = {}
    ratios = em.load_exdiv_ratios(
        ["600000.SH"],
        "20251103",
        "20251107",
        adj_factor_path=adj,
        ex_date_index_path=ex,
        skipped_out=skipped,
    )
    assert ratios["600000.SH"]["20251105"] == pytest.approx(0.5)
    assert skipped.get("exdiv_skipped_no_factor", 0) == 0


def test_fallback_jump_without_ex_row(tmp_path: Path):
    adj = _write_adj(
        tmp_path / "adj_factor.parquet",
        [
            ("20251103", "600000.SH", 1.0),
            ("20251104", "600000.SH", 1.0),
            ("20251105", "600000.SH", 1.02),  # 2% jump, no ex → fallback
        ],
    )
    ex = _write_ex(tmp_path / "ex_date_index.parquet", [])  # empty
    ratios = em.load_exdiv_ratios(
        ["600000.SH"],
        "20251103",
        "20251107",
        adj_factor_path=adj,
        ex_date_index_path=ex,
    )
    assert "20251105" in ratios["600000.SH"]
    assert ratios["600000.SH"]["20251105"] == pytest.approx(1.0 / 1.02)


def test_noise_band_ex_event_not_adjusted(tmp_path: Path):
    adj = _write_adj(
        tmp_path / "adj_factor.parquet",
        [
            ("20251103", "600000.SH", 1.0),
            ("20251104", "600000.SH", 1.0),
            ("20251105", "600000.SH", 1.003),  # 0.3% < 0.5%
        ],
    )
    ex = _write_ex(tmp_path / "ex_date_index.parquet", [("600000.SH", "20251105")])
    ratios = em.load_exdiv_ratios(
        ["600000.SH"],
        "20251103",
        "20251107",
        adj_factor_path=adj,
        ex_date_index_path=ex,
    )
    assert ratios.get("600000.SH", {}).get("20251105") is None


def test_t14_gate_small_jump_no_ex_no_adjust(tmp_path: Path):
    """0.8% jump without ex_index → not fallback (need >1e-2)."""
    adj = _write_adj(
        tmp_path / "adj_factor.parquet",
        [
            ("20251103", "600000.SH", 1.0),
            ("20251105", "600000.SH", 1.008),
        ],
    )
    ex = _write_ex(tmp_path / "ex_date_index.parquet", [])
    ratios = em.load_exdiv_ratios(
        ["600000.SH"],
        "20251103",
        "20251107",
        adj_factor_path=adj,
        ex_date_index_path=ex,
    )
    assert ratios.get("600000.SH", {}) == {}


def test_nan_factor_on_ex_day_skipped(tmp_path: Path):
    adj = _write_adj(
        tmp_path / "adj_factor.parquet",
        [
            ("20251103", "600000.SH", 1.0),
            ("20251104", "600000.SH", 1.0),
            ("20251105", "600000.SH", float("nan")),
        ],
    )
    ex = _write_ex(tmp_path / "ex_date_index.parquet", [("600000.SH", "20251105")])
    skipped: dict = {}
    ratios = em.load_exdiv_ratios(
        ["600000.SH"],
        "20251103",
        "20251107",
        adj_factor_path=adj,
        ex_date_index_path=ex,
        skipped_out=skipped,
    )
    assert ratios.get("600000.SH", {}) == {}
    assert skipped["exdiv_skipped_no_factor"] >= 1


def test_missing_adj_file_empty_map_stderr(tmp_path: Path, capsys):
    em.reset_missing_warn_flag_for_tests()
    missing = tmp_path / "no_adj.parquet"
    ex = _write_ex(tmp_path / "ex_date_index.parquet", [("600000.SH", "20251105")])
    ratios = em.load_exdiv_ratios(
        ["600000.SH"],
        "20251103",
        "20251107",
        adj_factor_path=missing,
        ex_date_index_path=ex,
    )
    assert ratios == {}
    err = capsys.readouterr().err
    assert "adj_factor missing" in err


def test_datetime_date_column_normalized(tmp_path: Path):
    adj = tmp_path / "adj_factor.parquet"
    pd.DataFrame(
        {
            "date": pd.to_datetime(["2025-11-03", "2025-11-04", "2025-11-05"]),
            "stock_code": ["600000.SH"] * 3,
            "cumulative_adj_factor": [1.0, 1.0, 2.0],
        }
    ).to_parquet(adj, index=False)
    ex = tmp_path / "ex_date_index.parquet"
    pd.DataFrame(
        {
            "stock_code": ["600000.SH"],
            "ex_date": pd.to_datetime(["2025-11-05"]),
        }
    ).to_parquet(ex, index=False)
    ratios = em.load_exdiv_ratios(
        ["600000.SH"],
        "20251103",
        "20251107",
        adj_factor_path=adj,
        ex_date_index_path=ex,
    )
    assert ratios["600000.SH"]["20251105"] == pytest.approx(0.5)


def test_warmup_boundary_keeps_first_event_k(tmp_path: Path):
    """Predecessor just before start must still supply LAG k for start-day event."""
    adj = _write_adj(
        tmp_path / "adj_factor.parquet",
        [
            ("20251028", "600000.SH", 1.0),  # warmup pred
            ("20251103", "600000.SH", 2.0),  # start = ex day
            ("20251104", "600000.SH", 2.0),
        ],
    )
    ex = _write_ex(tmp_path / "ex_date_index.parquet", [("600000.SH", "20251103")])
    ratios = em.load_exdiv_ratios(
        ["600000.SH"],
        "20251103",
        "20251107",
        adj_factor_path=adj,
        ex_date_index_path=ex,
    )
    assert ratios["600000.SH"]["20251103"] == pytest.approx(0.5)


def test_mapped_prev_close_helper():
    raw, mapped = em.mapped_prev_close({"600000.SH": {"20251105": 0.5}}, "600000.SH", "20251105", 10.0)
    assert mapped is True
    assert raw == pytest.approx(5.0)
    raw2, mapped2 = em.mapped_prev_close(None, "600000.SH", "20251105", 10.0)
    assert mapped2 is False
    assert raw2 == pytest.approx(10.0)
