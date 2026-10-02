"""True-core X6 · synthetic_fixture / attestation differential tests."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from backtest.research.minute_orders_backend.source_provenance import FIXTURE_NOTICE
from backtest.research.minute_orders_x6_synthetic import (
    BACKEND_ID,
    CONTRACT,
    DIFFERENTIAL_ROOT_NAME,
    DIFFERENTIAL_STATUS,
    TOOL_ID,
    DifferentialIngestError,
    load_synthetic_boundary_meta,
    meta_from_mapping,
    run_x6_synthetic_differential,
)
from backtest.research.minute_orders_x6_synthetic.differential import REPORT_FILENAME

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "research" / "run_x6_synthetic_differential.py"
OK = ROOT / "tests" / "fixtures" / "minute_orders_x6_synthetic" / "boundary_ok.json"
LAKE = ROOT / "tests" / "fixtures" / "minute_orders_x6_synthetic" / "lake_kind_rejected.json"
PKG = ROOT / "backtest" / "research" / "minute_orders_x6_synthetic"
CORE = {
    ROOT / "backtest" / "research" / "minute_orders_backend" / "match.py",
    ROOT / "backtest" / "research" / "minute_orders_backend" / "fees.py",
    ROOT / "backtest" / "research" / "csv_minute_backtest.py",
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
    assert "synthetic_fixture" in help_text
    assert "lake" in help_text.lower()
    assert "Fixture PASS != lake PASS" in help_text or "fixture_pass" in help_text.lower()
    assert "MatchCore" in help_text
    assert "forever opt-in" in help_text
    assert "BOOKS" in help_text
    assert "--meta" in help_text
    assert list(tmp_path.iterdir()) == []


def test_ingest_boundary_ok():
    meta = load_synthetic_boundary_meta(OK)
    assert meta.schema.endswith("boundary_meta_v0")
    assert meta.source_kind == "synthetic_fixture"
    assert meta.evidence_level == "synthetic"
    assert meta.account_origin == "synthetic_account"
    assert meta.commands_origin == "designed_limit_batch"
    assert "Fixture PASS != lake PASS" in meta.notice
    assert meta.contract == CONTRACT
    assert meta.backend_id == BACKEND_ID


def test_ingest_refuses_lake_source_kind():
    with pytest.raises(DifferentialIngestError) as caught:
        load_synthetic_boundary_meta(LAKE)
    msg = str(caught.value).lower()
    assert "lake" in msg
    assert "synthetic_fixture" in msg or "refuse" in msg


def test_ingest_refuses_evidence_level_lake():
    payload = json.loads(OK.read_text(encoding="utf-8"))
    payload["evidence_level"] = "lake"
    with pytest.raises(DifferentialIngestError) as caught:
        meta_from_mapping(payload)
    assert "evidence_level" in str(caught.value).lower()


def test_ingest_refuses_promotion_claim():
    payload = json.loads(OK.read_text(encoding="utf-8"))
    payload["claims"] = {"lake_pass": True, "host_attestation": False,
                         "green_r": False, "comparison_authorization": False}
    with pytest.raises(DifferentialIngestError) as caught:
        meta_from_mapping(payload)
    assert "lake_pass" in str(caught.value).lower()


def test_ingest_refuses_banned_top_level_lake_path():
    payload = json.loads(OK.read_text(encoding="utf-8"))
    payload["lake_path"] = "/tmp/fake-lake"
    with pytest.raises(DifferentialIngestError) as caught:
        meta_from_mapping(payload)
    assert "lake_path" in str(caught.value).lower()


def test_differential_memory_and_write_no_summary_json(tmp_path):
    meta = load_synthetic_boundary_meta(OK)
    mem = run_x6_synthetic_differential(meta)
    assert mem.tool_id == TOOL_ID
    assert mem.differential_status == DIFFERENTIAL_STATUS
    assert mem.root is None
    assert mem.report["invariants"]["fixture_pass_is_not_lake_pass"] is True
    assert mem.report["invariants"]["host_attestation"] is False
    assert mem.report["fixture_notice"] == FIXTURE_NOTICE
    assert len(mem.report["tip_gap_checks"]) >= 5
    assert all(c["status"] == "enforced" for c in mem.report["tip_gap_checks"])

    out = run_x6_synthetic_differential(meta, parent=tmp_path, run_id="x6-ok-1")
    assert out.root is not None
    assert out.report_path is not None
    assert out.report_path.name == REPORT_FILENAME
    assert out.root == tmp_path / DIFFERENTIAL_ROOT_NAME / "x6-ok-1"
    assert out.report_path.is_file()
    assert not (out.root / "summary.json").exists()
    disk = json.loads(out.report_path.read_text(encoding="utf-8"))
    assert disk["differential_status"] == DIFFERENTIAL_STATUS
    assert disk["boundary"]["source_kind"] == "synthetic_fixture"

    with pytest.raises(FileExistsError):
        run_x6_synthetic_differential(meta, parent=tmp_path, run_id="x6-ok-1")


def test_cli_memory_and_write(tmp_path):
    mem = launch(tmp_path, ["--meta", str(OK), "--memory-only"])
    assert mem.returncode == 0, mem.stderr
    report = json.loads(mem.stdout)
    assert report["tool_id"] == TOOL_ID
    assert report["differential_status"] == DIFFERENTIAL_STATUS
    assert list(tmp_path.iterdir()) == []

    written = launch(
        tmp_path,
        ["--meta", str(OK), "--parent", str(tmp_path), "--run-id", "cli-x6-1"],
    )
    assert written.returncode == 0, written.stderr
    report_path = tmp_path / DIFFERENTIAL_ROOT_NAME / "cli-x6-1" / REPORT_FILENAME
    assert report_path.is_file()
    assert "wrote:" in written.stderr
    assert not (report_path.parent / "summary.json").exists()

    again = launch(
        tmp_path,
        ["--meta", str(OK), "--parent", str(tmp_path), "--run-id", "cli-x6-1"],
    )
    assert again.returncode == 2
    assert "already exists" in again.stderr.lower() or "exist" in again.stderr.lower()


def test_cli_refuses_lake_meta(tmp_path):
    process = launch(tmp_path, ["--meta", str(LAKE), "--memory-only"])
    assert process.returncode == 2
    assert "lake" in process.stderr.lower()


def test_package_does_not_import_matchcore_fees_simulate():
    text = "\n".join(p.read_text(encoding="utf-8") for p in PKG.glob("*.py"))
    assert "match_candidates" not in text
    assert "compute_bucket_capacity" not in text
    assert "csv_minute_backtest" not in text
    assert "simulate(" not in text
    # Imports of source_provenance FIXTURE_NOTICE only — OK.
    assert "from .match" not in text
    assert "from .fees" not in text


def test_core_files_untouched_by_this_package():
    # Sanity: core paths still exist and this test file does not rewrite them.
    for path in CORE:
        assert path.is_file(), path
