"""CSV-engine analysis pack: FIFO trips, sidecar, scores; no resimulate."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest
from backtest.research.csv_analysis_export import (
    BUNDLE_CSV,
    FIELDS_NOTE_NAME,
    HUMAN_ANALYSIS_NAME,
    load_nav,
    load_trades,
    pair_round_trips,
    parse_account_from_summary,
    positions_daily,
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


def _identity_run(tmp_path: Path, rows: str, *, lot: bool = True) -> Path:
    run = tmp_path / "run"
    run.mkdir()
    (run / "daily_equity.csv").write_text(
        "date,equity\n20260106,10000\n20260107,10000\n"
        "20260108,10000\n20260109,10000\n", encoding="utf-8",
    )
    header = "date,code,side,price,shares,commission,reason,position_id"
    if lot:
        header += ",lot"
    (run / "trades.csv").write_text(header + "\n" + rows, encoding="utf-8")
    return run


@pytest.mark.parametrize("lot", [False, True])
def test_position_round_trips_sell_newer_group_first(tmp_path: Path, lot: bool):
    rows = [
        "20260106,600000.SH,BUY,10,100,1,pool,600000.SH@20260106,0",
        "20260107,600000.SH,BUY,20,200,2,pool,600000.SH@20260107,0",
        "20260107,600000.SH,BUY,12,100,1,add,600000.SH@20260106,1",
        "20260108,600000.SH,BUY,22,100,1,add,600000.SH@20260107,1",
        "20260108,600000.SH,SELL,23,200,2,profit_take,600000.SH@20260107,0",
        "20260109,600000.SH,SELL,24,100,1,profit_take|t1_deferred,600000.SH@20260107,1",
        "20260109,600000.SH,SELL,11,100,1,stop_loss,600000.SH@20260106,0",
        "20260109,600000.SH,EOD_MARK,11,100,0,,600000.SH@20260106,1",
    ]
    if not lot:
        rows = [row.rsplit(",", 1)[0] for row in rows]
    run = _identity_run(tmp_path, "\n".join(rows) + "\n", lot=lot)
    trades = load_trades(run)
    nav = load_nav(run)
    fills, trips, ledger = pair_round_trips(trades, nav)
    assert fills["position_id"].tolist() == trades.loc[trades.side != "EOD_MARK", "position_id"].tolist()
    newer = trips[trips.position_id == "600000.SH@20260107"]
    assert newer.buy_price.tolist() == [20.0, 22.0]
    assert newer.sell_date.tolist() == ["2026-01-08", "2026-01-09"]
    assert newer.sell_reason.tolist() == ["profit_take", "profit_take|t1_deferred"]
    assert newer.realized_pnl.tolist() == [596.0, 198.0]
    older = trips[trips.position_id == "600000.SH@20260106"]
    assert older.buy_price.tolist() == [10.0, 12.0]
    assert older.status.tolist() == ["closed", "open_eod"]
    assert older.realized_pnl.iloc[0] == 98.0
    assert older.mtm_pnl.iloc[1] == -101.0
    assert ledger[ledger.event == "sell"].entry_price.tolist() == [20.0, 22.0, 10.0]
    positions = positions_daily(trades, nav)
    day7 = positions[positions.date == "2026-01-07"]
    assert dict(zip(day7.position_id, day7.shares)) == {
        "600000.SH@20260106": 200.0, "600000.SH@20260107": 200.0,
    }
    last = positions[positions.date == "2026-01-09"]
    assert last.position_id.tolist() == ["600000.SH@20260106"]
    assert last.shares.tolist() == [100.0]


def test_position_lot_numbers_override_fifo_and_merge_tail_children(tmp_path: Path):
    run = _identity_run(
        tmp_path,
        "20260106,600000.SH,BUY,10,100,1,tail,600000.SH@20260106,0\n"
        "20260106,600000.SH,BUY,12,100,2,tail,600000.SH@20260106,0\n"
        "20260107,600000.SH,BUY,20,100,1,add,600000.SH@20260106,1\n"
        "20260108,600000.SH,SELL,21,100,1,profit_take,600000.SH@20260106,1\n"
        "20260108,600000.SH,SELL,13,50,1,profit_take,600000.SH@20260106,0\n"
        "20260109,600000.SH,SELL,14,150,2,profit_take|t1_deferred,600000.SH@20260106,0\n"
    )
    trades = load_trades(run)
    nav = load_nav(run)
    _, trips, ledger = pair_round_trips(trades, nav)
    first_lot = trips[trips.lot == 0]
    assert first_lot.buy_price.tolist() == [11.0, 11.0]
    assert first_lot.shares.tolist() == [50.0, 150.0]
    assert first_lot.buy_notional.tolist() == [550.0, 1650.0]
    assert first_lot.buy_commission.tolist() == [0.75, 2.25]
    assert first_lot.realized_pnl.tolist() == [98.25, 445.75]
    assert trips[trips.lot == 1].realized_pnl.tolist() == [98.0]
    assert ledger[ledger.event == "sell"].entry_price.tolist() == [20.0, 11.0, 11.0]
    pos = positions_daily(trades, nav)
    assert pos[pos.date == "2026-01-08"].shares.tolist() == [150.0]
    assert pos[pos.date == "2026-01-08"].entry_price.tolist() == [11.0]
    assert pos[pos.date == "2026-01-09"].empty


def test_mixed_empty_id_sell_uses_code_fifo(tmp_path: Path):
    run = _identity_run(
        tmp_path,
        "20260106,600000.SH,BUY,10,100,1,pool,600000.SH@20260106,0\n"
        "20260107,600000.SH,BUY,20,100,1,pool,600000.SH@20260107,0\n"
        "20260107,600000.SH,BUY,30,100,1,pool, ,9\n"
        "20260108,600000.SH,SELL,11,100,1,legacy_exit,,9\n"
        "20260108,600000.SH,SELL,21,100,1,identified_exit,600000.SH@20260107,0\n"
        "20260109,600000.SH,SELL,31,100,1,legacy_exit, ,0\n"
    )
    trades = load_trades(run)
    assert trades.position_id.iloc[2] == ""
    assert trades.position_id.iloc[3] == ""
    _, trips, _ = pair_round_trips(trades, load_nav(run))
    assert trips.position_id.tolist() == ["600000.SH@20260106", "600000.SH@20260107", ""]
    assert trips.buy_price.tolist() == [10.0, 20.0, 30.0]
    assert trips.sell_price.tolist() == [11.0, 21.0, 31.0]
    assert trips.realized_pnl.tolist() == [98.0, 98.0, 98.0]
    pos = positions_daily(trades, load_nav(run))
    assert pos[pos.date == "2026-01-08"].position_id.tolist() == [""]
    assert pos[pos.date == "2026-01-09"].empty


def test_position_fifo_without_lot_splits_one_sell_across_buys(tmp_path: Path):
    run = _identity_run(
        tmp_path,
        "20260106,600000.SH,BUY,10,100,1,tail,600000.SH@20260106\n"
        "20260106,600000.SH,BUY,12,200,2,tail,600000.SH@20260106\n"
        "20260107,600000.SH,BUY,20,100,1,pool,600000.SH@20260107\n"
        "20260108,600000.SH,SELL,13,250,2.5,profit_take,600000.SH@20260106\n"
        "20260109,600000.SH,SELL,14,50,0.5,profit_take|t1_deferred,600000.SH@20260106\n"
        "20260109,600000.SH,EOD_MARK,14,100,0,,600000.SH@20260107\n",
        lot=False,
    )
    trades = load_trades(run)
    nav = load_nav(run)
    _, trips, ledger = pair_round_trips(trades, nav)
    older = trips[trips.position_id == "600000.SH@20260106"]
    assert older.shares.tolist() == [100.0, 150.0, 50.0]
    assert older.buy_notional.tolist() == [1000.0, 1800.0, 600.0]
    assert older.buy_commission.tolist() == [1.0, 1.5, 0.5]
    assert older.sell_notional.tolist() == [1300.0, 1950.0, 700.0]
    assert older.sell_commission.tolist() == [1.0, 1.5, 0.5]
    assert older.realized_pnl.tolist() == [298.0, 147.0, 99.0]
    assert ledger[ledger.event == "sell"].amount_after.tolist() == [300.0, 150.0, 100.0]
    assert trips[trips.position_id == "600000.SH@20260107"].status.tolist() == ["open_eod"]
    pos = positions_daily(trades, nav)
    day8 = pos[pos.date == "2026-01-08"]
    assert dict(zip(day8.position_id, day8.shares)) == {
        "600000.SH@20260106": 50.0, "600000.SH@20260107": 100.0,
    }


def test_identified_sell_never_consumes_other_position(tmp_path: Path):
    run = _identity_run(
        tmp_path,
        "20260106,600000.SH,BUY,10,100,1,pool,,0\n"
        "20260107,600000.SH,SELL,11,100,1,exit,600000.SH@20260107,0\n"
    )
    with pytest.raises(SystemExit, match="unmatched SELL.*position_id=600000.SH@20260107"):
        pair_round_trips(load_trades(run), load_nav(run))


def test_eod_marks_value_each_position_and_lot_once(tmp_path: Path):
    run = _identity_run(
        tmp_path,
        "20260106,600000.SH,BUY,10,100,1,pool,600000.SH@20260106,0\n"
        "20260107,600000.SH,BUY,20,200,2,pool,600000.SH@20260107,0\n"
        "20260107,600000.SH,BUY,12,50,1,add,600000.SH@20260106,1\n"
        "20260109,600000.SH,EOD_MARK,11,100,0,,600000.SH@20260106,0\n"
        "20260109,600000.SH,EOD_MARK,11,200,0,,600000.SH@20260107,0\n"
        "20260109,600000.SH,EOD_MARK,11,50,0,,600000.SH@20260106,1\n"
    )
    _, trips, _ = pair_round_trips(load_trades(run), load_nav(run))
    assert trips.sell_notional.tolist() == [1100.0, 2200.0, 550.0]
    assert trips.mtm_pnl.tolist() == [99.0, -1802.0, -51.0]


def _legacy_fifo_run(tmp_path: Path) -> Path:
    run = _run_dir(tmp_path)
    (run / "trades.csv").write_text(
        "date,code,side,price,shares,notional,commission,reason,lot\n"
        "20260106,600000.SH,BUY,10,100,1000,1,pool,0\n"
        "20260106,600000.SH,BUY,11,200,2200,2,add,1\n"
        "20260106,000001.SZ,SKIP,8,0,0,0,skip_cash,0\n"
        "20260107,600000.SH,SELL,12,100,1200,1,exit,1\n"
        "20260107,000001.SZ,BUY,8,5,40,0.5,pool,0\n"
        "20260108,600000.SH,SELL,13,200,2600,2,exit,0\n"
        "20260108,000001.SZ,EOD_MARK,9,5,45,0,,0\n",
        encoding="utf-8",
    )
    return run


def _bundle_byte_hashes(run: Path, out: Path) -> dict[str, str]:
    hashes = {}
    for path in sorted(out.iterdir()):
        blob = path.read_bytes()
        # Temporary directory names are not part of the output contract.
        blob = blob.replace(str(out).encode(), b"<OUT_DIR>")
        blob = blob.replace(str(run).encode(), b"<RUN_DIR>")
        hashes[path.name] = hashlib.sha256(blob).hexdigest()
    return hashes


@pytest.mark.parametrize("empty_identity", [False, True])
def test_legacy_bundle_bytes_match_before_position_pairing(tmp_path: Path, empty_identity: bool):
    run = _legacy_fifo_run(tmp_path)
    if empty_identity:
        raw = pd.read_csv(run / "trades.csv")
        raw["position_id"] = [None, "", " ", None, "", " ", None]
        raw.to_csv(run / "trades.csv", index=False)
    out = tmp_path / "analysis"
    write_bundle(run, out, account=100.0)
    expected = json.loads(
        (Path(__file__).parent / "fixtures" / "csv_analysis_legacy_bytes_followups_20260926.json")
        .read_text(encoding="utf-8")
    )
    assert _bundle_byte_hashes(run, out) == expected["sha256"]
    for name in ("trades_daily.csv", "round_trips.csv", "ledger_by_stock.csv", "positions_daily.csv"):
        assert "position_id" not in pd.read_csv(out / name).columns
