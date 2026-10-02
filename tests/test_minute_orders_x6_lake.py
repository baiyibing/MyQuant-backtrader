"""True-core X6 · lake END / loader boundary differential tests."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from backtest.research.minute_orders_x6_lake import (
    BACKEND_ID,
    CONTRACT,
    DIFFERENTIAL_ROOT_NAME,
    DIFFERENTIAL_STATUS,
    TOOL_ID,
    LakeBoundaryIngestError,
    load_lake_boundary_meta,
    meta_from_mapping,
    run_x6_lake_differential,
)
from backtest.research.minute_orders_x6_lake.differential import REPORT_FILENAME

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "research" / "run_x6_lake_differential.py"
OK = ROOT / "tests" / "fixtures" / "minute_orders_x6_lake" / "boundary_ok.json"
SYN = ROOT / "tests" / "fixtures" / "minute_orders_x6_lake" / "synthetic_kind_rejected.json"
START = ROOT / "tests" / "fixtures" / "minute_orders_x6_lake" / "start_label_rejected.json"
PKG = ROOT / "backtest" / "research" / "minute_orders_x6_lake"
CORE = {
    ROOT / "backtest" / "research" / "minute_orders_backend" / "match.py",
    ROOT / "backtest" / "research" / "minute_orders_backend" / "fees.py",
    ROOT / "backtest" / "research" / "csv_minute_backtest.py",
    ROOT / "backtest" / "research" / "minute_orders_backend" / "source_loader.py",
    ROOT / "backtest" / "research" / "minute_orders_backend" / "cli.py",
}


def launch(cwd, argv=None, *, timeout=30):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *(argv or [])],
        cwd=cwd, capture_output=True, text=True, check=False, timeout=timeout,
    )


def test_cli_help_documents_identity_and_bans(tmp_path):
    process = launch(tmp_path, ["--help"])
    assert process.returncode == 0, process.stderr
    help_text = process.stdout
    assert TOOL_ID in help_text
    assert "NOT a backend_id" in help_text or "not a backend_id" in help_text.lower()
    assert CONTRACT in help_text
    assert BACKEND_ID in help_text
    assert DIFFERENTIAL_STATUS in help_text
    assert "lake" in help_text.lower()
    assert "END" in help_text
    assert "host PASS" in help_text or "host_pass" in help_text.lower()
    assert "MatchCore" in help_text
    assert "forever opt-in" in help_text
    assert "BOOKS" in help_text
    assert "no lake write" in help_text.lower() or "NO lake write" in help_text
    assert "--evidence-level=lake" in help_text or "evidence-level=lake" in help_text
    assert "--meta" in help_text
    assert list(tmp_path.iterdir()) == []


def test_ingest_boundary_ok():
    meta = load_lake_boundary_meta(OK)
    assert meta.schema.endswith("boundary_meta_v0")
    assert meta.source_kind == "lake"
    assert meta.evidence_level == "lake_boundary"
    assert meta.account_origin == "synthetic_account"
    assert meta.commands_origin == "designed_limit_batch"
    assert meta.bar_time_label == "END"
    assert meta.availability == "bucket_end"
    assert "lake boundary attestation != host PASS" in meta.notice
    assert meta.contract == CONTRACT
    assert meta.backend_id == BACKEND_ID


def test_ingest_refuses_synthetic_fixture_masquerade():
    with pytest.raises(LakeBoundaryIngestError) as caught:
        load_lake_boundary_meta(SYN)
    msg = str(caught.value).lower()
    assert "synthetic_fixture" in msg
    assert "lake" in msg or "refuse" in msg


def test_ingest_refuses_start_label():
    with pytest.raises(LakeBoundaryIngestError) as caught:
        load_lake_boundary_meta(START)
    msg = str(caught.value)
    assert "END" in msg
    assert "START" in msg or "bar_time_label" in msg.lower()


def test_ingest_refuses_evidence_level_lake_cli_unlock():
    payload = json.loads(OK.read_text(encoding="utf-8"))
    payload["evidence_level"] = "lake"
    with pytest.raises(LakeBoundaryIngestError) as caught:
        meta_from_mapping(payload)
    assert "evidence_level" in str(caught.value).lower()


def test_ingest_refuses_promotion_claim():
    payload = json.loads(OK.read_text(encoding="utf-8"))
    payload["claims"] = {
        "lake_pass": True,
        "host_attestation": False,
        "green_r": False,
        "comparison_authorization": False,
    }
    with pytest.raises(LakeBoundaryIngestError) as caught:
        meta_from_mapping(payload)
    assert "lake_pass" in str(caught.value).lower()


def test_ingest_refuses_write_lake_key():
    payload = json.loads(OK.read_text(encoding="utf-8"))
    payload["write_lake"] = True
    with pytest.raises(LakeBoundaryIngestError) as caught:
        meta_from_mapping(payload)
    assert "write_lake" in str(caught.value).lower()


def test_ingest_refuses_fixture_promotion_alias():
    payload = json.loads(OK.read_text(encoding="utf-8"))
    payload["fixture_promoted_to_lake_pass"] = True
    with pytest.raises(LakeBoundaryIngestError) as caught:
        meta_from_mapping(payload)
    assert "fixture" in str(caught.value).lower()


def test_differential_memory_and_write_no_summary_json(tmp_path):
    meta = load_lake_boundary_meta(OK)
    mem = run_x6_lake_differential(meta)
    assert mem.tool_id == TOOL_ID
    assert mem.differential_status == DIFFERENTIAL_STATUS
    assert mem.root is None
    assert mem.report["invariants"]["lake_boundary_is_not_host_pass"] is True
    assert mem.report["invariants"]["fixture_pass_is_not_lake_pass"] is True
    assert mem.report["invariants"]["cli_evidence_level_unlocked"] is False
    assert mem.report["invariants"]["lake_write"] is False
    assert mem.report["invariants"]["read_only"] is True
    assert mem.report["invariants"]["host_attestation"] is False
    assert mem.report["boundary"]["bar_time_label"] == "END"
    assert len(mem.report["tip_gap_checks"]) >= 6
    assert all(c["status"] == "enforced" for c in mem.report["tip_gap_checks"])

    out = run_x6_lake_differential(meta, parent=tmp_path, run_id="x6-lake-1")
    assert out.root is not None
    assert out.report_path is not None
    assert out.report_path.name == REPORT_FILENAME
    assert out.root == tmp_path / DIFFERENTIAL_ROOT_NAME / "x6-lake-1"
    assert out.report_path.is_file()
    assert not (out.root / "summary.json").exists()
    disk = json.loads(out.report_path.read_text(encoding="utf-8"))
    assert disk["differential_status"] == DIFFERENTIAL_STATUS
    assert disk["boundary"]["source_kind"] == "lake"
    assert disk["boundary"]["bar_time_label"] == "END"

    with pytest.raises(FileExistsError):
        run_x6_lake_differential(meta, parent=tmp_path, run_id="x6-lake-1")


def test_cli_memory_and_write(tmp_path):
    mem = launch(tmp_path, ["--meta", str(OK), "--memory-only"])
    assert mem.returncode == 0, mem.stderr
    report = json.loads(mem.stdout)
    assert report["tool_id"] == TOOL_ID
    assert report["differential_status"] == DIFFERENTIAL_STATUS
    assert list(tmp_path.iterdir()) == []

    written = launch(
        tmp_path,
        ["--meta", str(OK), "--parent", str(tmp_path), "--run-id", "cli-x6-lake-1"],
    )
    assert written.returncode == 0, written.stderr
    report_path = tmp_path / DIFFERENTIAL_ROOT_NAME / "cli-x6-lake-1" / REPORT_FILENAME
    assert report_path.is_file()
    assert "wrote:" in written.stderr
    assert not (report_path.parent / "summary.json").exists()

    again = launch(
        tmp_path,
        ["--meta", str(OK), "--parent", str(tmp_path), "--run-id", "cli-x6-lake-1"],
    )
    assert again.returncode == 2
    assert "already exists" in again.stderr.lower() or "exist" in again.stderr.lower()


def test_cli_refuses_synthetic_meta(tmp_path):
    process = launch(tmp_path, ["--meta", str(SYN), "--memory-only"])
    assert process.returncode == 2
    assert "synthetic" in process.stderr.lower()


def test_package_does_not_import_matchcore_fees_simulate_or_loader():
    text = "\n".join(p.read_text(encoding="utf-8") for p in PKG.glob("*.py"))
    assert "match_candidates" not in text
    assert "compute_bucket_capacity" not in text
    assert "csv_minute_backtest" not in text
    assert "simulate(" not in text
    assert "from .match" not in text
    assert "from .fees" not in text
    # May mention load_minute_orders_source in docs/bans; must not import/call it.
    assert "import load_minute_orders_source" not in text
    assert "source_loader import" not in text
    assert "load_minute_orders_source(" not in text


def test_core_files_untouched_by_this_package():
    for path in CORE:
        assert path.is_file(), path
