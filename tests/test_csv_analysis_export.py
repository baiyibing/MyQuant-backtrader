"""CSV-engine analysis pack: FIFO trips, sidecar, scores; no resimulate."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from backtest.research.csv_analysis_export import (
    BUNDLE_CSV,
    FIELDS_NOTE_NAME,
    HUMAN_ANALYSIS_NAME,
    parse_account_from_summary,
    write_bundle,
)


def _run_dir(tmp_path: Path) -> Path:
    run = tmp_path / "run"
    run.mkdir()
    (run / "daily_equity.csv").write_text(
        "date,equity\n20260106,99.0\n20260107,110.0\n20260108,108.0\n",
        encoding="utf-8",
        newline="\n",
    )
    (run / "summary.txt").write_text(
        "csv_daily_test 20260106..20260108\n  期末净值: 108.00 / 100\n",
        encoding="utf-8",
        newline="\n",
    )
    (run / "trades.csv").write_text(
        "date,code,side,price,shares,notional,commission,reason\n"
        "20260106,600000.SH,BUY,10.0,10,100.0,1.0,pool\n"
        "20260107,600000.SH,SELL,12.0,10,120.0,2.0,stop_loss:close\n"
        "20260107,000001.SZ,BUY,8.0,5,40.0,0.5,pool\n"
        "20260108,000001.SZ,EOD_MARK,9.0,5,45.0,0.0,\n",
        encoding="utf-8",
        newline="\n",
    )
    return run


def test_parse_account_from_summary():
    text = "  期末净值: 104,572,769.55 / 100,000,000\n"
    assert parse_account_from_summary(text) == 100_000_000.0


def test_round_trip_pnl_and_open_eod(tmp_path: Path):
    run = _run_dir(tmp_path)
    out = tmp_path / "analysis"
    product = write_bundle(run, out, account=100.0, topk=50)
    trips = pd.read_csv(out / "round_trips.csv")
    assert len(trips) == 2
    closed = trips[trips["status"] == "closed"].iloc[0]
    assert closed["code"] == "600000.SH"
    # debit 101, credit 118
    assert abs(float(closed["realized_pnl"]) - 17.0) < 1e-9
    opened = trips[trips["status"] == "open_eod"].iloc[0]
    assert opened["code"] == "000001.SZ"
    assert abs(float(opened["mtm_pnl"]) - 4.5) < 1e-9
    summary = product["summary"]
    assert summary["buys"] == 2
    assert summary["sells"] == 1
    assert abs(summary["pnl_total"] - 21.5) < 1e-9
    for name in BUNDLE_CSV:
        assert (out / name).is_file()
    note = out / FIELDS_NOTE_NAME
    raw_note = note.read_bytes()
    assert raw_note.count(0) == 0
    text = raw_note.decode("utf-8")
    assert "run_dir:" in text
    assert "round_trips.csv" in text
    assert str(run) in text
    analysis = (out / HUMAN_ANALYSIS_NAME).read_text(encoding="utf-8")
    assert "最大回撤" in analysis
    assert "2026-01-08" in analysis
    assert "已平仓胜率: 100.00%（1 胜 / 1 笔）" in analysis
    assert abs(summary["max_drawdown"] - (108.0 / 110.0 - 1.0)) < 1e-12
    assert summary["win_rate_closed"] == 1.0
    assert summary["by_sell_reason"][0]["sell_reason"] == "stop_loss:close"
    raw = (out / "round_trips.csv").read_bytes()
    assert raw.count(0) == 0


def test_minute_symbol_schema(tmp_path: Path):
    run = tmp_path / "run"
    run.mkdir()
    (run / "daily_equity.csv").write_text(
        "date,equity\n20260106,100\n20260107,100\n", encoding="utf-8", newline="\n"
    )
    (run / "trades.csv").write_text(
        "date,symbol,hm,side,shares,price,reason\n"
        "20260106,600000.SH,1455,BUY,100,10.0,pool\n"
        "20260107,600000.SH,0930,SELL,100,11.0,ma_signal\n",
        encoding="utf-8",
        newline="\n",
    )
    out = tmp_path / "analysis"
    write_bundle(run, out, account=100.0)
    trips = pd.read_csv(out / "round_trips.csv")
    assert list(trips["code"]) == ["600000.SH"]
    assert trips.iloc[0]["sell_reason"] == "ma_signal"


def test_sidecar_and_scores_picks(tmp_path: Path):
    run = _run_dir(tmp_path)
    sidecar = tmp_path / "state.csv"
    sidecar.write_text(
        "trade_date,code,close,ma20,ma60,winratio\n"
        "2026-01-06,600000.SH,10.0,11.0,12.0,0.05\n"
        "2026-01-07,000001.SZ,8.0,7.0,7.5,0.80\n",
        encoding="utf-8",
        newline="\n",
    )
    scores = tmp_path / "scores"
    scores.mkdir()
    (scores / "20260106.csv").write_text(
        "code,score\n600000,0.9\n000002,0.8\n", encoding="utf-8", newline="\n"
    )
    (scores / "20260107.csv").write_text(
        "code,score\n000001,0.7\n600000,0.1\n", encoding="utf-8", newline="\n"
    )
    from backtest.research.topk_dropout_eligibility import load_buy_state_sidecar
    from backtest.research.topk_dropout_scores import load_scores_dir

    out = tmp_path / "analysis"
    write_bundle(
        run,
        out,
        scores_by_day=load_scores_dir(scores),
        state_map=load_buy_state_sidecar(sidecar),
        topk=2,
        account=100.0,
    )
    trips = pd.read_csv(out / "round_trips.csv")
    buy0 = trips[trips["code"] == "600000.SH"].iloc[0]
    assert bool(buy0["buy_cond1_below_ma_wr"]) is True
    assert buy0["buy_state_label"] == "cond1_below_ma_and_wr_lt_0.10"
    assert int(buy0["buy_rank"]) == 1
    picks = pd.read_csv(out / "daily_picks.csv")
    day6 = picks[picks["trade_date"] == "2026-01-06"]
    assert "new_buy" in set(day6["action"])
    missed = day6[day6["action"] == "missed"]
    assert list(missed["code"]) == ["000002.SZ"]


def test_missing_trades_fail_closed(tmp_path: Path):
    run = tmp_path / "empty"
    run.mkdir()
    (run / "daily_equity.csv").write_text("date,equity\n20260106,1\n", encoding="utf-8")
    try:
        write_bundle(run, tmp_path / "out")
    except FileNotFoundError as exc:
        assert "trades.csv" in str(exc)
    else:
        raise AssertionError("expected FileNotFoundError")


def test_summary_json_utf8(tmp_path: Path):
    run = _run_dir(tmp_path)
    out = tmp_path / "analysis"
    write_bundle(run, out, account=100.0)
    blob = (out / "summary.json").read_bytes()
    assert blob.count(0) == 0
    data = json.loads(blob.decode("utf-8"))
    assert data["round_trips"] == 1
    assert data["open_lots"] == 1
