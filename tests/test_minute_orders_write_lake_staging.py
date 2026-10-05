"""True-core residual R2 · write-lake staging dry-run tests (no production write)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from backtest.research.minute_orders_write_lake_staging import (
    BACKEND_ID,
    CONTRACT,
    FORBIDDEN_SUMMARY_NAME,
    MUST_HUMAN_CUTS,
    REPORT_FILENAME,
    STAGING_ROOT_NAME,
    STAGING_STATUS,
    TOOL_ID,
    WriteLakeStagingError,
    assert_not_production_target,
    assert_staging_out_dir,
    load_staging_request,
    must_human_cuts_payload,
    run_write_lake_staging_dry_run,
)

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "research" / "run_write_lake_staging_dry_run.py"
FIX = ROOT / "tests" / "fixtures" / "minute_orders_write_lake_staging"
OK = FIX / "request_ok.json"
WRITE_KEY = FIX / "request_write_key_rejected.json"
PROD_MODE = FIX / "request_production_mode_rejected.json"
CORE = {
    ROOT / "backtest" / "research" / "minute_orders_backend" / "match.py",
    ROOT / "backtest" / "research" / "minute_orders_backend" / "fees.py",
    ROOT / "backtest" / "research" / "csv_minute_backtest.py",
    ROOT / "backtest" / "research" / "minute_orders_backend" / "source_loader.py",
    ROOT / "backtest" / "research" / "minute_orders_backend" / "cli.py",
}


@pytest.fixture(autouse=True)
def isolated_protected_roots(monkeypatch):
    # CI's workspace root contains pytest basetemp; it is not this fixture's lake.
    # Individual protection tests explicitly configure their own protected root.
    for key in ("OSKH_SOURCE_PARQUET_ROOT", "OSKH_PERIOD_1D_ROOT",
                "OSKH_PERIOD_1M_ROOT", "OSKH_AUTHORITY_HINT_ROOT", "OSKH_DATA_ROOT"):
        monkeypatch.delenv(key, raising=False)


def launch(cwd, argv=None, *, timeout=30, env=None):
    merged = os.environ.copy()
    if env:
        merged.update(env)
    return subprocess.run(
        [sys.executable, str(SCRIPT), *(argv or [])],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
        env=merged,
    )


def test_cli_help_documents_identity_and_bans(tmp_path):
    process = launch(tmp_path, ["--help"])
    assert process.returncode == 0, process.stderr
    help_text = process.stdout
    assert TOOL_ID in help_text
    assert "NOT a backend_id" in help_text
    assert "contract v0 (L2-S0)" in help_text or CONTRACT in help_text
    assert BACKEND_ID in help_text
    assert STAGING_STATUS in help_text
    assert "NO lake write" in help_text or "no lake write" in help_text.lower()
    assert "--write-lake" in help_text or "write-lake" in help_text
    assert "MatchCore" in help_text
    assert "forever opt-in" in help_text
    assert "BOOKS" in help_text
    assert "≠δ5" in help_text or "delta5" in help_text.lower() or "δ5" in help_text
    assert list(tmp_path.iterdir()) == []


def test_request_ok_and_dry_run(tmp_path):
    request = load_staging_request(OK)
    assert request.mode == "staging_dry_run"
    assert "002231.SZ" in request.proposed_symbols
    outcome = run_write_lake_staging_dry_run(
        request=request,
        parent=tmp_path,
        run_id="staging-ok-01",
    )
    assert outcome.tool_id == TOOL_ID
    assert outcome.staging_status == STAGING_STATUS
    assert outcome.report_path.name == REPORT_FILENAME
    assert outcome.report_path.is_file()
    assert outcome.cuts_path.is_file()
    report = json.loads(outcome.report_path.read_text(encoding="utf-8"))
    assert report["staging_status"] == STAGING_STATUS
    assert report["tool_id"] == TOOL_ID
    assert FORBIDDEN_SUMMARY_NAME not in {
        p.name for p in outcome.report_path.parent.iterdir()
    }
    cuts = json.loads(outcome.cuts_path.read_text(encoding="utf-8"))
    assert {c["id"] for c in cuts["cuts"]} == {c["id"] for c in MUST_HUMAN_CUTS}
    assert "owner" in {c["id"] for c in cuts["cuts"]}
    assert "no_borrow_receipt" in {c["id"] for c in cuts["cuts"]}


def test_same_run_id_refuses_overwrite(tmp_path):
    request = load_staging_request(OK)
    run_write_lake_staging_dry_run(
        request=request, parent=tmp_path, run_id="dup-01"
    )
    with pytest.raises((WriteLakeStagingError, FileExistsError)):
        run_write_lake_staging_dry_run(
            request=request, parent=tmp_path, run_id="dup-01"
        )


def test_refuse_write_lake_key():
    with pytest.raises(WriteLakeStagingError, match="banned"):
        load_staging_request(WRITE_KEY)


def test_refuse_production_mode():
    with pytest.raises(WriteLakeStagingError, match="staging_dry_run"):
        load_staging_request(PROD_MODE)


def test_refuse_stock_data_out_dir(tmp_path):
    bad = tmp_path / "stock_data" / "staging"
    bad.mkdir(parents=True)
    with pytest.raises(WriteLakeStagingError, match="stock_data"):
        assert_staging_out_dir(bad)


def test_refuse_configured_lake_root(tmp_path, monkeypatch):
    lake = tmp_path / "configured_lake"
    lake.mkdir()
    monkeypatch.setenv("OSKH_SOURCE_PARQUET_ROOT", str(lake))
    target = lake / "nested_staging"
    with pytest.raises(WriteLakeStagingError, match="OSKH_SOURCE_PARQUET_ROOT"):
        assert_staging_out_dir(target)


def test_refuse_production_target_hint(tmp_path):
    with pytest.raises(WriteLakeStagingError, match="stock_data"):
        assert_not_production_target(tmp_path / "stock_data" / "period=1m")


def test_cli_success_and_reject(tmp_path):
    parent = tmp_path / "parent"
    parent.mkdir()
    ok = launch(
        tmp_path,
        [
            "--request", str(OK.resolve()),
            "--parent", str(parent.resolve()),
            "--run-id", "cli-ok-01",
            "--print-must-cuts",
        ],
    )
    assert ok.returncode == 0, ok.stderr
    payload = json.loads(ok.stdout)
    assert payload["tool_id"] == TOOL_ID
    assert payload["staging_status"] == STAGING_STATUS
    assert "owner" in ok.stderr
    report_path = Path(payload["report"])
    assert report_path.is_file()
    assert not (report_path.parent / FORBIDDEN_SUMMARY_NAME).exists()

    bad = launch(
        tmp_path,
        [
            "--request", str(WRITE_KEY.resolve()),
            "--parent", str(parent.resolve()),
            "--run-id", "cli-bad-01",
        ],
    )
    assert bad.returncode == 2
    assert "banned" in bad.stderr.lower() or "ERROR" in bad.stderr


def test_cli_refuses_relative_paths(tmp_path):
    process = launch(
        tmp_path,
        ["--request", "relative.json", "--parent", str(tmp_path), "--run-id", "r1"],
    )
    assert process.returncode == 2


def test_must_human_cuts_payload_stable():
    payload = must_human_cuts_payload()
    assert payload["tool_id"] == TOOL_ID
    assert payload["staging_status"] == STAGING_STATUS
    assert len(payload["cuts"]) >= 7
    assert "not_production_lake_write" in payload["non_claims"]


def test_core_files_untouched_in_this_branch():
    """Guard: this residual must keep MatchCore/Fees/simulate/loader/cli empty."""
    import subprocess as sp

    diff = sp.run(
        ["git", "diff", "--name-only", "master...HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    # On uncommitted worktree, also check staged+unstaged relative to master tip files.
    changed = set(diff.stdout.split())
    status = sp.run(
        ["git", "status", "--porcelain"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    for line in status.stdout.splitlines():
        path = line[3:].strip().split(" -> ")[-1]
        changed.add(path)
    for core in CORE:
        rel = str(core.relative_to(ROOT))
        assert rel not in changed, f"core file unexpectedly changed: {rel}"


def test_root_name_constant():
    assert STAGING_ROOT_NAME == "minute_orders_write_lake_staging"
