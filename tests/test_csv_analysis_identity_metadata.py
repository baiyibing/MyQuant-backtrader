"""Identified analysis metadata keeps integer lots and legacy bundle bytes."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from backtest.research.csv_analysis_export import (
    FIELDS_NOTE_NAME,
    FIELDS_NOTE_SRC,
    load_trades,
    write_bundle,
)


def _run(tmp_path: Path, *, identity: str = "identified") -> Path:
    run = tmp_path / "run"
    run.mkdir()
    (run / "daily_equity.csv").write_text(
        "date,equity\n20260106,10000\n20260107,10200\n20260108,10400\n",
        encoding="utf-8",
    )
    header = ["date", "code", "side", "price", "shares", "commission", "reason", "lot"]
    rows = [
        ["20260106", "600000.SH", "BUY", "10", "100", "0", "pool", "0.0"],
        ["20260106", "600000.SH", "BUY", "11", "200", "0", "add", "1"],
        ["20260106", "000001.SZ", "BUY", "8", "100", "0", "pool", ""],
        ["20260106", "000002.SZ", "SKIP", "8", "0", "0", "skip_cash", ""],
        ["20260107", "600000.SH", "SELL", "12", "200", "0", "exit", "1.0"],
        ["20260108", "600000.SH", "EOD_MARK", "11", "100", "0", "", "0"],
        ["20260108", "000001.SZ", "EOD_MARK", "9", "100", "0", "", ""],
    ]
    if identity != "absent":
        header.append("position_id")
        for row in rows:
            if identity == "identified":
                row.append(f"{row[1]}@20260106" if row[2] != "SKIP" else "")
            else:
                row.append(" " if identity == "whitespace" else "")
    with (run / "trades.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)
    return run


def _csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def test_identified_lot_csv_tokens_are_integers_or_blank(tmp_path: Path):
    run = _run(tmp_path)
    out = tmp_path / "analysis"
    write_bundle(run, out, account=10000)

    for filename in ("trades_daily.csv", "round_trips.csv", "ledger_by_stock.csv"):
        rows = _csv_rows(out / filename)
        assert {row["lot"] for row in rows} == {"0", "1", ""}, filename
        assert all("position_id" in row for row in rows), filename
        for row in rows:
            if row["code"] == "000001.SZ":
                assert row["lot"] == ""
                assert row["position_id"] == "000001.SZ@20260106"
    skip = next(row for row in _csv_rows(out / "trades_daily.csv") if row["side"] == "SKIP")
    assert skip["lot"] == skip["position_id"] == ""
    positions = _csv_rows(out / "positions_daily.csv")
    assert positions
    assert all("position_id" in row and "lot" not in row for row in positions)


@pytest.mark.parametrize("identity", ["absent", "empty", "whitespace", "identified"])
def test_identity_field_note_is_appended_only_for_identified_runs(tmp_path: Path, identity: str):
    run = _run(tmp_path, identity=identity)
    out = tmp_path / "analysis"
    write_bundle(run, out, account=10000)
    legacy_note = (
        f"本次导出\nrun_dir: {run}\n窗口: 2026-01-06 .. 2026-01-08\n\n".encode("utf-8")
        + FIELDS_NOTE_SRC.read_bytes()
    )
    actual = (out / FIELDS_NOTE_NAME).read_bytes()
    if identity != "identified":
        assert actual == legacy_note
        assert "position_id" not in load_trades(run).columns
    else:
        assert actual.startswith(legacy_note)
        extra = actual[len(legacy_note):]
        source = FIELDS_NOTE_SRC.with_name("csv-analysis-identity-fields.txt").read_bytes()
        assert extra.endswith(source)
        assert b"position_id" in extra and b"lot" in extra
    assert b"\x00" not in actual


@pytest.mark.parametrize("fractional_lot", ["0.5", "1.25"])
def test_identified_fractional_lot_does_not_silently_truncate(tmp_path: Path, fractional_lot: str):
    run = _run(tmp_path)
    path = run / "trades.csv"
    text = path.read_text(encoding="utf-8")
    path.write_text(text.replace("pool,0.0,", f"pool,{fractional_lot},", 1), encoding="utf-8")
    with pytest.raises((TypeError, ValueError), match="lot|integer|int64"):
        load_trades(run)
