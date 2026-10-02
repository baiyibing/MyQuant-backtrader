"""TC4 · X8 compare bridge: pre-match snapshot ↔ X1 run; refuse fills→intent."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from backtest.research.minute_orders_x8_compare import (
    COMPARISON_ID,
    COMPARISON_ROOT_NAME,
    COMPARISON_STATUS,
    CompareIngestError,
    load_prematch_intent_snapshot,
    run_x8_compare,
    snapshot_from_mapping,
)
from backtest.research.minute_orders_x8_compare.bridge import REPORT_FILENAME

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "research" / "run_x8_compare_bridge.py"
FIXTURE = (
    ROOT / "tests" / "fixtures" / "minute_orders_x8_compare"
    / "sketch_a_prematch_snapshot.json"
)
FILLS_FIXTURE = (
    ROOT / "tests" / "fixtures" / "minute_orders_x8_compare"
    / "fills_derived_rejected.json"
)
PKG = ROOT / "backtest" / "research" / "minute_orders_x8_compare"


def launch(cwd, argv=None, *, timeout=30):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *(argv or [])],
        cwd=cwd, capture_output=True, text=True, check=False, timeout=timeout,
    )


def test_cli_help_documents_identity_and_bans(tmp_path):
    process = launch(tmp_path, ["--help"])
    assert process.returncode == 0, process.stderr
    help_text = process.stdout
    assert COMPARISON_ID in help_text
    assert "NOT a backend_id" in help_text or "not a backend_id" in help_text.lower()
    assert "research contract v0 (L2-S0)" in help_text
    assert "minute_orders_research_v1" in help_text
    assert "minute_orders_intent_x1" in help_text
    assert COMPARISON_STATUS in help_text
    assert "fills" in help_text.lower() or "fills→intent" in help_text
    assert "summary.json" in help_text
    assert "no MatchCore" in help_text or "MatchCore" in help_text
    assert "forever opt-in" in help_text
    assert "BOOKS" in help_text
    assert "--snapshot" in help_text
    assert list(tmp_path.iterdir()) == []


def test_ingest_prematch_snapshot_happy_path():
    snapshot = load_prematch_intent_snapshot(FIXTURE)
    assert snapshot.schema.endswith("prematch_intent_snapshot_v0")
    assert snapshot.snapshot_kind == "pre_match_intent"
    assert len(snapshot.intents) == 2
    assert snapshot.intents[0].order_id == "O1"
    assert snapshot.intents[1].order_id == "O2"
    assert snapshot.facts_preset == "sketch_a"


def test_ingest_refuses_fills_derived_payload():
    with pytest.raises(CompareIngestError) as caught:
        load_prematch_intent_snapshot(FILLS_FIXTURE)
    msg = str(caught.value).lower()
    assert "fill" in msg
    # Top-level fills key or banned kind — either is enough.
    assert "banned" in msg or "fills" in msg


def test_ingest_refuses_inline_fills_key():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    payload["fills"] = [{"order_id": "O1", "qty": 1}]
    with pytest.raises(CompareIngestError) as caught:
        snapshot_from_mapping(payload)
    assert "fills" in str(caught.value).lower()


def test_ingest_refuses_from_trades_kind():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    payload["snapshot_kind"] = "from_trades"
    # Also strip any accidental fills to isolate kind check — still refuse.
    payload.pop("fills", None)
    with pytest.raises(CompareIngestError) as caught:
        snapshot_from_mapping(payload)
    assert "fill" in str(caught.value).lower() or "trade" in str(caught.value).lower()


def test_bridge_memory_and_write_no_summary_json(tmp_path):
    snapshot = load_prematch_intent_snapshot(FIXTURE)
    mem = run_x8_compare(snapshot, facts_preset="sketch_a")
    assert mem.comparison_id == COMPARISON_ID
    assert mem.comparison_status == COMPARISON_STATUS
    assert mem.root is None
    assert mem.report["red_label"] is True
    assert mem.report["diagnostic_only"] is True
    assert mem.report["intent_vs_frozen"]["match"] is True
    assert mem.report["frozen_batch"]["command_ids"] == ["submit:O1", "submit:O2"]
    by_id = {o["order_id"]: o for o in mem.report["x1_run"]["orders"]}
    assert by_id["O1"]["status"] == "Filled" and by_id["O1"]["filled_qty"] == 300
    assert by_id["O2"]["status"] == "Expired" and by_id["O2"]["filled_qty"] == 100
    assert mem.report["x1_run"]["fill_count"] == 3
    # Memory report must document the ban, but must not claim a written summary path.
    assert "no_success_summary_json" in mem.report["bans"]
    assert "summary_path" not in mem.report
    assert "root" not in mem.report

    run_id = "tc4-x8-sketch-a"
    written = run_x8_compare(
        snapshot, facts_preset="sketch_a", parent=tmp_path, run_id=run_id,
    )
    assert written.root is not None
    assert written.root == tmp_path / COMPARISON_ROOT_NAME / run_id
    assert written.report_path == written.root / REPORT_FILENAME
    assert written.report_path.is_file()
    assert not (written.root / "summary.json").exists()
    disk = json.loads(written.report_path.read_text(encoding="utf-8"))
    assert disk["comparison_status"] == COMPARISON_STATUS
    assert disk["comparison_id"] == COMPARISON_ID
    assert "minute_orders_research_v1" not in str(written.root)

    # Overwrite refusal.
    with pytest.raises(FileExistsError):
        run_x8_compare(
            snapshot, facts_preset="sketch_a", parent=tmp_path, run_id=run_id,
        )


def test_cli_closed_loop_write_and_refuse_fills(tmp_path):
    run_id = "tc4-cli-x8"
    first = launch(
        tmp_path,
        [
            "--snapshot", str(FIXTURE),
            "--preset", "sketch_a",
            "--parent", str(tmp_path),
            "--run-id", run_id,
        ],
    )
    assert first.returncode == 0, first.stderr
    report = json.loads(first.stdout)
    assert report["comparison_id"] == COMPARISON_ID
    assert report["comparison_status"] == COMPARISON_STATUS
    assert report["red_label"] is True
    assert report["summary_json_absent"] is True
    root = Path(report["root"])
    assert root.is_dir()
    assert (root / REPORT_FILENAME).is_file()
    assert not (root / "summary.json").exists()
    assert report["intent_vs_frozen"]["match"] is True
    assert report["x1_run"]["fill_count"] == 3

    second = launch(
        tmp_path,
        [
            "--snapshot", str(FIXTURE),
            "--parent", str(tmp_path),
            "--run-id", run_id,
        ],
    )
    assert second.returncode == 4, second.stdout + second.stderr
    err = json.loads(second.stderr)
    assert err["error_type"] == "FileExistsError"

    refused = launch(tmp_path, ["--snapshot", str(FILLS_FIXTURE), "--memory-only"])
    assert refused.returncode == 2, refused.stdout + refused.stderr
    err2 = json.loads(refused.stderr)
    assert err2["status"] == "input_error"
    assert err2["error_type"] == "CompareIngestError"
    assert "fill" in err2["reason"].lower()


def test_cli_memory_only(tmp_path):
    process = launch(
        tmp_path,
        ["--snapshot", str(FIXTURE), "--memory-only"],
    )
    assert process.returncode == 0, process.stderr
    report = json.loads(process.stdout)
    assert report["comparison_status"] == COMPARISON_STATUS
    assert "root" not in report
    assert list(tmp_path.iterdir()) == []


def test_package_source_bans_engine_imports():
    """X8 package must not import MatchCore/Fees/simulate/VolumeCap/broker/ledger."""
    banned_tokens = (
        "minute_orders_backend.match",
        "minute_orders_backend.fees",
        "minute_orders_backend.broker",
        "minute_orders_backend.ledger",
        "minute_orders_backend.clock",
        "csv_minute_backtest",
        "ashare_volume_cap",
        "simulate_v7",
    )
    sources = []
    for path in PKG.glob("*.py"):
        sources.append(path.read_text(encoding="utf-8"))
    blob = "\n".join(sources)
    for token in banned_tokens:
        assert token not in blob, f"banned import/token present: {token}"
