"""A·X7 observation surface: new projection entry; refuse _FAMILIES / NAV / fills."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from backtest.research.minute_orders_x7_observe import (
    BACKEND_ID,
    CONTRACT,
    FORBIDDEN_SUMMARY_NAME,
    OBSERVATION_ID,
    OBSERVATION_ROOT_NAME,
    OBSERVATION_STATUS,
    REPORT_FILENAME,
    X7_PROJECTION_FAMILY,
    ObserveError,
    assert_not_views_families_registration,
    load_observe_request,
    run_x7_observe,
)
from backtest.research.run_protocol import views as l1_views

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "research" / "run_x7_observe.py"
FIX = ROOT / "tests" / "fixtures" / "minute_orders_x7_observe"
OK = FIX / "request_ok.json"
NAV = FIX / "request_nav_rejected.json"
FAM = FIX / "request_families_rejected.json"
FILLS = FIX / "request_fills_rejected.json"
CORE = {
    ROOT / "backtest" / "research" / "minute_orders_backend" / "match.py",
    ROOT / "backtest" / "research" / "minute_orders_backend" / "fees.py",
    ROOT / "backtest" / "research" / "csv_minute_backtest.py",
    ROOT / "backtest" / "research" / "minute_orders_backend" / "source_loader.py",
    ROOT / "backtest" / "research" / "minute_orders_backend" / "cli.py",
    ROOT / "backtest" / "research" / "run_protocol" / "views.py",
}


def launch(cwd, argv=None, *, timeout=30):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *(argv or [])],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )


def test_cli_help_documents_identity_and_bans(tmp_path):
    process = launch(tmp_path, ["--help"])
    assert process.returncode == 0, process.stderr
    help_text = process.stdout
    assert OBSERVATION_ID in help_text
    assert "NOT a backend_id" in help_text
    assert X7_PROJECTION_FAMILY in help_text
    assert "_FAMILIES" in help_text or "views._FAMILIES" in help_text
    assert CONTRACT in help_text or "contract v0 (L2-S0)" in help_text
    assert BACKEND_ID in help_text
    assert OBSERVATION_STATUS in help_text
    assert "NAV" in help_text or "nav" in help_text
    assert "green R" in help_text or "green r" in help_text.lower()
    assert "MatchCore" in help_text
    assert "forever opt-in" in help_text
    assert "BOOKS" in help_text
    assert "≠δ5" in help_text or "delta5" in help_text.lower() or "δ5" in help_text
    assert list(tmp_path.iterdir()) == []


def test_request_ok_memory_and_write(tmp_path):
    request = load_observe_request(OK)
    assert request.source_kind == "synthetic_observation_sketch"
    mem = run_x7_observe(request=request, memory_only=True)
    assert mem.observation_id == OBSERVATION_ID
    assert mem.observation_status == OBSERVATION_STATUS
    assert mem.report_path is None
    assert mem.report["slice"]["projection_family"] == X7_PROJECTION_FAMILY
    assert mem.report["slice"]["nav_rewrite"] == "forbidden"

    outcome = run_x7_observe(
        request=request, parent=tmp_path, run_id="x7-ok-01"
    )
    assert outcome.report_path is not None
    assert outcome.report_path.name == REPORT_FILENAME
    assert outcome.report_path.is_file()
    report = json.loads(outcome.report_path.read_text(encoding="utf-8"))
    assert report["observation_status"] == OBSERVATION_STATUS
    assert report["observation_id"] == OBSERVATION_ID
    assert FORBIDDEN_SUMMARY_NAME not in {
        p.name for p in outcome.report_path.parent.iterdir()
    }
    assert (tmp_path / "backtest_output" / OBSERVATION_ROOT_NAME / "x7-ok-01").is_dir()


def test_same_run_id_refuses_overwrite(tmp_path):
    request = load_observe_request(OK)
    run_x7_observe(request=request, parent=tmp_path, run_id="dup-01")
    with pytest.raises((ObserveError, FileExistsError)):
        run_x7_observe(request=request, parent=tmp_path, run_id="dup-01")


def test_refuse_nav_field():
    with pytest.raises(ObserveError, match="NAV|nav|equity"):
        load_observe_request(NAV)


def test_refuse_views_family_stuffing():
    with pytest.raises(ObserveError, match="views_family|_FAMILIES"):
        load_observe_request(FAM)


def test_refuse_fills_key():
    with pytest.raises(ObserveError, match="banned"):
        load_observe_request(FILLS)


def test_x7_family_not_in_l1_views_families():
    """Hard lock: X7 projection family must NOT appear in L1 views._FAMILIES."""
    families = getattr(l1_views, "_FAMILIES")
    assert X7_PROJECTION_FAMILY not in families
    assert "minute_orders" not in families
    guard = assert_not_views_families_registration()
    assert guard["views_families_touch"] == "forbidden"


def test_cli_memory_only_roundtrip(tmp_path):
    process = launch(
        tmp_path,
        ["--request", str(OK.resolve()), "--memory-only"],
    )
    assert process.returncode == 0, process.stderr
    payload = json.loads(process.stdout)
    assert payload["observation_id"] == OBSERVATION_ID
    assert payload["observation_status"] == OBSERVATION_STATUS
    assert payload["memory_only"] is True
    assert list(tmp_path.iterdir()) == []


def test_cli_write_roundtrip(tmp_path):
    process = launch(
        tmp_path,
        [
            "--request", str(OK.resolve()),
            "--parent", str(tmp_path.resolve()),
            "--run-id", "cli-write-01",
        ],
    )
    assert process.returncode == 0, process.stderr
    payload = json.loads(process.stdout)
    report_path = Path(payload["report"])
    assert report_path.is_file()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["observation_status"] == OBSERVATION_STATUS
    assert FORBIDDEN_SUMMARY_NAME not in {
        p.name for p in report_path.parent.iterdir()
    }


def test_core_files_untouched_by_this_package():
    """Sanity: listed core paths exist (empty-diff discipline checked at review)."""
    for path in CORE:
        assert path.is_file(), path
