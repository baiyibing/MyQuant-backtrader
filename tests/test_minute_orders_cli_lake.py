"""CLI --evidence-level=lake → loader → S4 hybrid (forever opt-in; ≠ host PASS)."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from backtest.research.minute_orders_backend import cli, source_loader
from tests.test_minute_orders_artifacts import read
from tests.test_minute_orders_source_loader import SyntheticCase

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/research/run_minute_orders_research.py"
# Knife base tip (#310 MERGED). Empty-diff guard for MatchCore/Fees/simulate/loader.
KNIFE_BASE = "6c8178ad8f3f987da6075a4fa69250a2f7855744"
CORE = {
    ROOT / "backtest" / "research" / "minute_orders_backend" / "match.py",
    ROOT / "backtest" / "research" / "minute_orders_backend" / "fees.py",
    ROOT / "backtest" / "research" / "csv_minute_backtest.py",
    ROOT / "backtest" / "research" / "minute_orders_backend" / "source_loader.py",
    ROOT / "backtest" / "research" / "ashare_volume_cap.py",
    ROOT / "backtest" / "research" / "run_protocol" / "facade.py",
    ROOT / "backtest" / "research" / "run_protocol" / "views.py",
}


def _prepare_lake_end_case(case: SyntheticCase, monkeypatch) -> SyntheticCase:
    """Fabricated tmp lake+END recipe; never reads a configured production lake."""
    original = source_loader.execution_identity
    if original()["code_dirty"]:
        monkeypatch.setattr(
            source_loader,
            "execution_identity",
            lambda: dict(original(), code_dirty=False),
        )
    execution = source_loader.execution_identity()
    case.recipe["implementation"] = {
        "code_sha": execution["code_sha"],
        "python_version": execution["python_version"],
        "pyarrow_version": execution["pyarrow_version"],
        "transform_version": case.recipe["implementation"]["transform_version"],
    }
    case.recipe["source_kind"] = "lake"
    case.sidecars["attestation"]["source_kind"] = "lake"
    for row in case.rows:
        row["time"] = (
            datetime.fromisoformat(row["time"]) + timedelta(minutes=1)
        ).isoformat()
    case.recipe["bars"][0]["time"]["label"] = "END"
    for mark in case.recipe["mark_grid"]:
        mark["prices"][0]["time"]["label"] = "END"
    case.attest_fabricated_bindings()
    case.freeze()
    return case


@pytest.fixture
def lake_end_case(tmp_path, monkeypatch):
    case = SyntheticCase(tmp_path, monkeypatch)
    return _prepare_lake_end_case(case, monkeypatch)


def lake_argv(case, *, code_sha=None, evidence_level="lake", run_id=None, parent=None,
              recipe=None, expected_sha256=None, extra=()):
    argv = [
        "--evidence-level", evidence_level,
        "--parent", str(parent or case.recipe["parent"]),
        "--run-id", run_id or case.recipe["run_id"],
        "--recipe", str(recipe or case.path.resolve()),
        "--expected-sha256", expected_sha256 or case.digest,
    ]
    if code_sha is not None:
        argv.extend(["--code-sha", code_sha])
    argv.extend(list(extra))
    return argv


def test_cli_help_documents_lake_opt_in_and_bans(tmp_path):
    process = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        cwd=tmp_path, capture_output=True, text=True, check=False, timeout=30,
    )
    assert process.returncode == 0, process.stderr
    help_text = process.stdout
    assert "minute_orders_research_v1" in help_text
    assert "lake" in help_text
    assert "synthetic" in help_text
    assert "host PASS" in help_text or "host_pass" in help_text.lower()
    assert "forever opt-in" in help_text
    assert "BOOKS" in help_text
    assert "--recipe" in help_text
    assert "--expected-sha256" in help_text
    assert "hybrid" in help_text.lower() or "S4 hybrid" in help_text
    assert list(tmp_path.iterdir()) == []


def test_lake_cli_runs_hybrid_research_success(lake_end_case, capsys):
    code = cli.main(lake_argv(lake_end_case))
    captured = capsys.readouterr()
    assert code == 0, captured.err
    report = json.loads(captured.out)
    assert report["status"] == "success"
    assert report["backend_id"] == "minute_orders_research_v1"
    result_root = Path(report["root"])
    assert (result_root / "summary.json").is_file()
    assert not (result_root / "failure.json").exists()
    manifest = read(result_root, "manifest.json")
    assert manifest["status"] == "success"
    assert manifest["evidence_level"] == "hybrid"
    assert manifest["schema_version"] == "minute_orders_artifacts_v2"
    assert manifest["source_kind"] == "lake"
    assert manifest["host_attestation_status"] == "not_certified_by_writer"
    assert manifest["live_acceptance_status"] == "not_assessed"
    assert manifest["comparison_status"] == "no_ssot_compare_authorization"
    assert (result_root / "source_provenance.json").is_file()
    summary = read(result_root, "summary.json")
    # Same handcalc as hybrid fixture path: 300 filled, 5.00 fee.
    assert summary["filled_qty"] == 300 and summary["fees_paid"] == "5.00"


def test_lake_cli_rejects_code_sha_override(lake_end_case, capsys):
    code = cli.main(lake_argv(
        lake_end_case, code_sha="6cd29e6bf4fe06b4c2e5d27d5a93d0bc304745a6",
    ))
    captured = capsys.readouterr()
    assert code == 2
    err = json.loads(captured.err)
    assert err["status"] == "input_error"
    assert "code-sha" in err["reason"]
    assert not Path(lake_end_case.recipe["parent"]).exists()


def test_lake_cli_rejects_input_json_masquerade(lake_end_case, capsys):
    code = cli.main(lake_argv(lake_end_case) + [
        "--input", str(ROOT / "tests/fixtures/minute_orders/partial_cancel_expiry_v1.json"),
    ])
    captured = capsys.readouterr()
    assert code == 2
    err = json.loads(captured.err)
    assert err["status"] == "input_error"
    assert "--input" in err["reason"]
    assert not Path(lake_end_case.recipe["parent"]).exists()


def test_lake_cli_rejects_synthetic_fixture_recipe(tmp_path, monkeypatch, capsys):
    case = SyntheticCase(tmp_path, monkeypatch)
    code = cli.main(lake_argv(case))
    captured = capsys.readouterr()
    assert code == 2
    err = json.loads(captured.err)
    assert err["status"] == "input_error"
    assert "source_kind" in err["reason"]
    assert not Path(case.recipe["parent"]).exists()


def test_lake_cli_rejects_start_label(tmp_path, monkeypatch, capsys):
    case = SyntheticCase(tmp_path, monkeypatch)
    original = source_loader.execution_identity
    if original()["code_dirty"]:
        monkeypatch.setattr(
            source_loader, "execution_identity",
            lambda: dict(original(), code_dirty=False),
        )
    execution = source_loader.execution_identity()
    case.recipe["implementation"] = {
        "code_sha": execution["code_sha"],
        "python_version": execution["python_version"],
        "pyarrow_version": execution["pyarrow_version"],
        "transform_version": case.recipe["implementation"]["transform_version"],
    }
    case.recipe["source_kind"] = "lake"
    case.sidecars["attestation"]["source_kind"] = "lake"
    case.attest_fabricated_bindings()
    case.freeze()
    code = cli.main(lake_argv(case))
    captured = capsys.readouterr()
    assert code == 2
    err = json.loads(captured.err)
    assert err["status"] == "input_error"
    assert "bar_time_label" in err["reason"] or "END" in err["reason"]
    assert not Path(case.recipe["parent"]).exists()


def test_lake_cli_rejects_sha_mismatch(lake_end_case, capsys):
    code = cli.main(lake_argv(lake_end_case, expected_sha256="0" * 64))
    captured = capsys.readouterr()
    assert code == 2
    err = json.loads(captured.err)
    assert err["status"] == "input_error"
    assert "hash" in err["reason"]
    assert not Path(lake_end_case.recipe["parent"]).exists()


def test_lake_cli_rejects_run_id_mismatch(lake_end_case, capsys):
    code = cli.main(lake_argv(lake_end_case, run_id="other-run"))
    captured = capsys.readouterr()
    assert code == 2
    err = json.loads(captured.err)
    assert err["status"] == "input_error"
    assert "run-id" in err["reason"] or "run_id" in err["reason"]
    assert not Path(lake_end_case.recipe["parent"]).exists()


def test_synthetic_still_rejects_recipe_flags(tmp_path, lake_end_case, capsys):
    code = cli.main([
        "--evidence-level", "synthetic",
        "--input", str(ROOT / "tests/fixtures/minute_orders/partial_cancel_expiry_v1.json"),
        "--parent", str(tmp_path / "output"),
        "--run-id", "case",
        "--recipe", str(lake_end_case.path.resolve()),
        "--expected-sha256", lake_end_case.digest,
    ])
    captured = capsys.readouterr()
    assert code == 2
    err = json.loads(captured.err)
    assert err["status"] == "input_error"
    assert "recipe" in err["reason"]


def test_lake_missing_recipe_args_are_input_error(tmp_path, capsys):
    code = cli.main([
        "--evidence-level", "lake",
        "--parent", str(tmp_path / "out"),
        "--run-id", "case",
    ])
    captured = capsys.readouterr()
    assert code == 2
    err = json.loads(captured.err)
    assert err["status"] == "input_error"
    assert "recipe" in err["reason"]
    assert list(tmp_path.iterdir()) == []


def test_empty_diff_core_vs_knife_base():
    """CLI lake knife must not touch MatchCore / Fees / simulate / loader / views."""
    import subprocess as sp
    dirty = sp.run(
        ["git", "diff", "--name-only", KNIFE_BASE, "--", *[str(p.relative_to(ROOT)) for p in sorted(CORE)]],
        cwd=ROOT, capture_output=True, text=True, check=True,
    )
    assert dirty.stdout.strip() == "", f"core files changed:\n{dirty.stdout}"
