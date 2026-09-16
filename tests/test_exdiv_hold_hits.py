# -*- coding: utf-8 -*-
"""NP2 ex-div hold-hit probe (tmp_path synthetic fixture; data-free)."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from backtest.research.exdiv_hold_hits import (
    format_report_json,
    main,
    report_exdiv_hold_hits,
)


def _write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8", newline="\n")


def _ex_index_csv(path: Path) -> Path:
    _write(
        path,
        "stock_code,ex_date,dr\n"
        "000001.SZ,20251104,1.0\n"
        "000001.SZ,20251103,1.0\n"
        "000001.SZ,20251111,1.0\n"
        "600000.SH,20251105,1.0\n"
        "600001.SH,20251106,1.0\n"
        "600002.SH,20251107,1.0\n"
        "000002.SZ,20251111,1.0\n"
        "300001.SZ,20251020,1.0\n",
    )
    return path


def _ex_index_parquet(path: Path) -> Path:
    frame = pd.DataFrame(
        {
            "stock_code": ["000001.SZ", "000001.SZ", "600000.SH"],
            "ex_date": ["2025-11-04", "2025-11-03", "2025-11-05"],
            "dr": [1.0, 1.0, 1.0],
        }
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path, index=False)
    return path


def _trades(path: Path) -> Path:
    _write(
        path,
        "date,code,side,price,shares,notional,commission,reason,lot\n"
        "20251103,000001.SZ,BUY,10.0,100,1000.0,1.0,pool,0\n"
        "20251108,000001.SZ,SELL,9.5,100,950.0,0.95,trail:peak_dd,0\n"
        "20251109,000001.SZ,BUY,10.0,100,1000.0,1.0,pool,0\n"
        "20251109,000002.SZ,BUY,10.0,100,1000.0,1.0,pool,0\n"
        "20251112,000001.SZ,SELL,10.2,100,1020.0,1.02,trail:peak_dd,0\n"
        "20251112,000002.SZ,SELL,10.1,100,1010.0,1.01,trail:peak_dd,0\n"
        "20251104,600000.SH,BUY,20.0,100,2000.0,2.0,pool,0\n"
        "20251106,600000.SH,SELL,14.0,100,1400.0,1.4,stop_loss:gap_open,0\n"
        "20251105,600001.SH,BUY,30.0,100,3000.0,3.0,pool,0\n"
        "20251108,600001.SH,SELL,31.0,100,3100.0,3.1,trail:band:2,0\n"
        "20251105,600003.SH,BUY,8.0,100,800.0,0.8,pool,0\n"
        "20251105,600003.SH,SELL,7.5,100,750.0,0.75,defer_sell_limit_down,0\n"
        "20251108,600004.SH,BUY,5.0,100,500.0,0.5,pool,0\n",
    )
    return path


def test_t1_excludes_entry_day_and_counts_d1(tmp_path: Path):
    trades = _trades(tmp_path / "trades.csv")
    ex = _ex_index_csv(tmp_path / "ex_date_index.csv")
    report = report_exdiv_hold_hits(
        trades, ex, start="20251023", end="20260909", sample_limit=50
    )
    # Hits: 000001 life1 1104; life2 1111; 000002 1111; 600000 1105; 600001 1106
    assert report.hold_exdiv_hit_events == 5
    assert report.hold_exdiv_hit_lots == 5
    assert report.among_hits_sell_gap_open == 1
    assert report.among_hits_sell_band_trail == 1
    assert report.among_hits_sell_defer_limit_down == 0
    assert report.among_hits_sell_other == 3
    first = next(
        s for s in report.samples
        if s["code"] == "000001.SZ" and s["entry_date"] == "20251103"
    )
    assert first["ex_dates"] == ["20251104"]
    assert "20251103" not in first["ex_dates"]


def test_fifo_lot_reentry_same_lot_id(tmp_path: Path):
    trades = _trades(tmp_path / "trades.csv")
    ex = _ex_index_csv(tmp_path / "ex.csv")
    report = report_exdiv_hold_hits(trades, ex, start="20251023", end="20260909")
    lives = sorted(
        [s for s in report.samples if s["code"] == "000001.SZ"],
        key=lambda s: s["entry_date"],
    )
    assert len(lives) == 2
    assert lives[0]["entry_date"] == "20251103"
    assert lives[0]["ex_dates"] == ["20251104"]
    assert lives[1]["entry_date"] == "20251109"
    assert lives[1]["ex_dates"] == ["20251111"]
    assert any(
        s["code"] == "000002.SZ" and s["ex_dates"] == ["20251111"]
        for s in report.samples
    )


def test_defer_bucket_when_ex_hits(tmp_path: Path):
    trades = tmp_path / "t.csv"
    _write(
        trades,
        "date,code,side,price,shares,notional,commission,reason,lot\n"
        "20251104,600003.SH,BUY,8.0,100,800.0,0.8,pool,0\n"
        "20251108,600003.SH,SELL,7.5,100,750.0,0.75,defer_sell_limit_down,0\n",
    )
    ex = tmp_path / "ex.csv"
    _write(ex, "stock_code,ex_date\n600003.SH,20251106\n")
    report = report_exdiv_hold_hits(trades, ex, start="20251023", end="20260909")
    assert report.hold_exdiv_hit_lots == 1
    assert report.among_hits_sell_defer_limit_down == 1


def test_window_filter_drops_outside_ex(tmp_path: Path):
    trades = _trades(tmp_path / "trades.csv")
    ex = _ex_index_csv(tmp_path / "ex.csv")
    report = report_exdiv_hold_hits(trades, ex, start="20251105", end="20251106")
    assert report.n_ex_events_in_window == 2
    assert report.hold_exdiv_hit_events >= 1


def test_parquet_ex_index_and_parity(tmp_path: Path):
    trades = tmp_path / "trades.csv"
    _write(
        trades,
        "date,code,side,price,shares,notional,commission,reason,lot\n"
        "20251103,000001.SZ,BUY,10.0,100,1000.0,1.0,pool,0\n"
        "20251108,000001.SZ,SELL,9.0,100,900.0,0.9,stop_loss:gap_open,0\n",
    )
    ex = _ex_index_parquet(tmp_path / "ex_date_index.parquet")
    adj = tmp_path / "adj_factor.parquet"
    pd.DataFrame(
        {
            "date": ["20251103", "20251104", "20251105", "20251103", "20251104"],
            "stock_code": ["000001.SZ"] * 3 + ["999999.SH"] * 2,
            "cumulative_adj_factor": [1.0, 1.02, 1.02, float("nan"), float("nan")],
        }
    ).to_parquet(adj, index=False)
    report = report_exdiv_hold_hits(
        trades, ex, start="20251023", end="20260909", adj_factor=adj
    )
    assert report.hold_exdiv_hit_events == 1
    assert report.among_hits_sell_gap_open == 1
    assert report.parity is not None
    assert report.parity["eps"] == 5e-3
    assert report.parity["n_jumps_in_window"] >= 1
    assert report.parity["n_primary_hit_events_with_jump"] == 1
    assert report.parity["g4_adj_minus_ex"] >= 0


def test_json_format_and_cli_exit_zero(tmp_path: Path, capsys):
    trades = _trades(tmp_path / "trades.csv")
    ex = _ex_index_csv(tmp_path / "ex.csv")
    report = report_exdiv_hold_hits(trades, ex)
    payload = json.loads(format_report_json(report))
    assert payload["design_locks"].startswith("primary=ex_date_index")
    assert "HUMAN cut" in payload["adjudication_note"]
    assert payload["hold_exdiv_hit_events"] == 5

    assert main([
        "--trades", str(trades),
        "--ex-date-index", str(ex),
        "--format", "json",
        "--start", "20251023",
        "--end", "20260909",
    ]) == 0
    out = capsys.readouterr().out
    assert json.loads(out)["hold_exdiv_hit_lots"] == 5
