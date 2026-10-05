"""True-core X6 · lake recipe e2e (load_minute_orders_source; read-only)."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from backtest.research.minute_orders_backend import source_loader
from backtest.research.minute_orders_x6_lake import (
    BACKEND_ID,
    CONTRACT,
    DIFFERENTIAL_ROOT_NAME,
    E2E_REPORT_FILENAME,
    E2E_STATUS,
    TOOL_ID,
    LakeRecipeE2EError,
    run_x6_lake_recipe_e2e,
)
from tests.test_minute_orders_source_loader import SyntheticCase

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "research" / "run_x6_lake_recipe_e2e.py"
PKG = ROOT / "backtest" / "research" / "minute_orders_x6_lake"
# Knife base tip (#308 MERGED). Guard compares commits, not working-tree vs HEAD.
KNIFE_BASE = "5fe84f725a0290318fcbe6a8ab9a8d097bda3d9f"
CORE = {
    ROOT / "backtest" / "research" / "minute_orders_backend" / "match.py",
    ROOT / "backtest" / "research" / "minute_orders_backend" / "fees.py",
    ROOT / "backtest" / "research" / "csv_minute_backtest.py",
    ROOT / "backtest" / "research" / "minute_orders_backend" / "source_loader.py",
    # cli.py unlocked by residual R1 CLI lake knife (separate from #310 e2e).
    ROOT / "backtest" / "research" / "ashare_volume_cap.py",
    ROOT / "backtest" / "research" / "run_protocol" / "facade.py",
    ROOT / "backtest" / "research" / "run_protocol" / "views.py",
}


def launch(cwd, argv=None, *, timeout=60):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *(argv or [])],
        cwd=cwd, capture_output=True, text=True, check=False, timeout=timeout,
    )


def _prepare_lake_end_case(case: SyntheticCase, monkeypatch) -> SyntheticCase:
    """Fabricated tmp lake+END recipe; never reads a configured production lake."""
    original = source_loader.execution_identity
    if original()["code_dirty"]:
        monkeypatch.setattr(
            source_loader,
            "execution_identity",
            lambda: dict(original(), code_dirty=False),
        )
    # Refresh implementation pin after possible monkeypatch.
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


def test_cli_help_documents_identity_and_bans(tmp_path):
    process = launch(tmp_path, ["--help"])
    assert process.returncode == 0, process.stderr
    help_text = process.stdout
    assert TOOL_ID in help_text
    assert "NOT a backend_id" in help_text or "not a backend_id" in help_text.lower()
    assert CONTRACT in help_text
    assert BACKEND_ID in help_text
    assert E2E_STATUS in help_text
    assert "load_minute_orders_source" in help_text
    assert "END" in help_text
    assert "host PASS" in help_text or "host_pass" in help_text.lower()
    assert "MatchCore" in help_text
    assert "forever opt-in" in help_text
    assert "BOOKS" in help_text
    assert "no lake write" in help_text.lower() or "NO lake write" in help_text
    assert "--evidence-level=lake" in help_text or "evidence-level=lake" in help_text
    assert "--recipe" in help_text
    assert "--expected-sha256" in help_text
    assert list(tmp_path.iterdir()) == []


def test_e2e_loads_lake_end_recipe_memory_only(lake_end_case):
    outcome = run_x6_lake_recipe_e2e(
        lake_end_case.path,
        expected_sha256=lake_end_case.digest,
    )
    assert outcome.tool_id == TOOL_ID
    assert outcome.e2e_status == E2E_STATUS
    assert outcome.root is None
    report = outcome.report
    assert report["e2e_status"] == E2E_STATUS
    assert report["recipe"]["source_kind"] == "lake"
    assert report["recipe"]["bar_time_label"] == "END"
    assert report["loaded"]["source_kind"] == "lake"
    assert report["loaded"]["bucket_count"] >= 1
    assert report["invariants"]["load_minute_orders_source_called"] is True
    assert report["invariants"]["lake_write"] is False
    assert report["invariants"]["cli_evidence_level_unlocked"] is False
    assert report["invariants"]["matchcore_fills_run"] is False
    assert report["invariants"]["research_v1_success_summary_written"] is False
    assert report["invariants"]["lake_recipe_e2e_is_not_host_pass"] is True
    assert not Path(lake_end_case.recipe["parent"]).exists()


def test_e2e_writes_independent_tool_root(lake_end_case, tmp_path):
    # Must NOT reuse SyntheticCase recipe["parent"] (tmp_path/out) — that path is
    # documented for research artifacts and must stay uncreated by this knife.
    parent = tmp_path / "e2e-out"
    outcome = run_x6_lake_recipe_e2e(
        lake_end_case.path,
        expected_sha256=lake_end_case.digest,
        parent=parent,
        run_id="x6-lake-e2e-1",
    )
    assert outcome.root == parent / DIFFERENTIAL_ROOT_NAME / "x6-lake-e2e-1"
    assert outcome.report_path == outcome.root / E2E_REPORT_FILENAME
    assert outcome.report_path.is_file()
    disk = json.loads(outcome.report_path.read_text(encoding="utf-8"))
    assert disk["e2e_status"] == E2E_STATUS
    assert disk["tool_id"] == TOOL_ID
    assert not (outcome.root / "summary.json").exists()
    assert "minute_orders_research_v1" not in str(outcome.root)
    assert not Path(lake_end_case.recipe["parent"]).exists()

    with pytest.raises(FileExistsError):
        run_x6_lake_recipe_e2e(
            lake_end_case.path,
            expected_sha256=lake_end_case.digest,
            parent=parent,
            run_id="x6-lake-e2e-1",
        )


def test_e2e_refuses_synthetic_fixture(tmp_path, monkeypatch):
    case = SyntheticCase(tmp_path, monkeypatch)
    # Default SyntheticCase is synthetic_fixture + START; e2e must refuse.
    with pytest.raises(LakeRecipeE2EError, match="source_kind"):
        run_x6_lake_recipe_e2e(case.path, expected_sha256=case.digest)
    assert not Path(case.recipe["parent"]).exists()


def test_e2e_refuses_start_label_even_when_lake(tmp_path, monkeypatch):
    case = SyntheticCase(tmp_path, monkeypatch)
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
    # Keep START label — Phase5 e2e must refuse before load.
    assert case.recipe["bars"][0]["time"]["label"] == "START"
    case.freeze()
    with pytest.raises(LakeRecipeE2EError, match="bar_time_label|END"):
        run_x6_lake_recipe_e2e(case.path, expected_sha256=case.digest)


def test_e2e_refuses_sha_mismatch(lake_end_case):
    with pytest.raises(LakeRecipeE2EError, match="sha256 mismatch"):
        run_x6_lake_recipe_e2e(
            lake_end_case.path,
            expected_sha256="0" * 64,
        )


def test_e2e_refuses_dirty_code_for_lake(lake_end_case, monkeypatch):
    original = source_loader.execution_identity
    monkeypatch.setattr(
        source_loader,
        "execution_identity",
        lambda: dict(original(), code_dirty=True),
    )
    with pytest.raises(LakeRecipeE2EError, match="clean pinned implementation"):
        run_x6_lake_recipe_e2e(
            lake_end_case.path,
            expected_sha256=lake_end_case.digest,
        )


def test_e2e_refuses_write_lake_key(lake_end_case):
    payload = json.loads(lake_end_case.path.read_text(encoding="utf-8"))
    payload["write_lake"] = True
    bad = lake_end_case.root / "bad_recipe.json"
    text = json.dumps(payload, ensure_ascii=False)
    bad.write_text(text, encoding="utf-8")
    digest = __import__("hashlib").sha256(text.encode()).hexdigest()
    with pytest.raises(LakeRecipeE2EError, match="write_lake|banned"):
        run_x6_lake_recipe_e2e(bad, expected_sha256=digest)


def test_cli_memory_only_and_write(lake_end_case, tmp_path):
    # Subprocess cannot inherit monkeypatch; lake load requires clean git pin.
    # Check real git dirtiness (fixture may have monkeypatched execution_identity).
    import subprocess as _sp
    porcelain = _sp.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True)
    if porcelain.strip():
        pytest.skip("CLI lake e2e needs clean git pin (subprocess); library API covered above")

    mem = launch(
        tmp_path,
        [
            "--recipe", str(lake_end_case.path),
            "--expected-sha256", lake_end_case.digest,
            "--memory-only",
        ],
    )
    assert mem.returncode == 0, mem.stderr
    report = json.loads(mem.stdout)
    assert report["e2e_status"] == E2E_STATUS
    # memory-only must not create the independent tool root
    assert not (tmp_path / DIFFERENTIAL_ROOT_NAME).exists()

    parent = tmp_path / "cli-out"
    written = launch(
        tmp_path,
        [
            "--recipe", str(lake_end_case.path),
            "--expected-sha256", lake_end_case.digest,
            "--parent", str(parent),
            "--run-id", "cli-x6-lake-e2e-1",
        ],
    )
    assert written.returncode == 0, written.stderr
    report_path = parent / DIFFERENTIAL_ROOT_NAME / "cli-x6-lake-e2e-1" / E2E_REPORT_FILENAME
    assert report_path.is_file()
    assert "wrote:" in written.stderr

    again = launch(
        tmp_path,
        [
            "--recipe", str(lake_end_case.path),
            "--expected-sha256", lake_end_case.digest,
            "--parent", str(parent),
            "--run-id", "cli-x6-lake-e2e-1",
        ],
    )
    assert again.returncode == 2
    assert "exists" in again.stderr.lower() or "overwrite" in again.stderr.lower()


def test_cli_refuses_relative_recipe(tmp_path, lake_end_case):
    process = launch(
        tmp_path,
        [
            "--recipe", "relative/recipe.json",
            "--expected-sha256", lake_end_case.digest,
            "--memory-only",
        ],
    )
    assert process.returncode == 2
    assert "absolute" in process.stderr.lower()


def test_package_calls_load_but_core_untouched():
    e2e_text = (PKG / "e2e.py").read_text(encoding="utf-8")
    assert "load_minute_orders_source" in e2e_text
    assert "load_minute_orders_source(" in e2e_text
    # Boundary differential knife still must not call loader.
    diff_text = (PKG / "differential.py").read_text(encoding="utf-8")
    assert "load_minute_orders_source(" not in diff_text
    # #310 e2e did not unlock CLI lake; residual R1 may add lake choice later.
    # Keep asserting this e2e package still does not call the research runner.
    assert "run_minute_orders_research_with_artifacts" not in e2e_text


def test_core_files_byte_stable_vs_knife_base():
    """Guard: MatchCore/Fees/simulate/source_loader/VolumeCap/_ENTRIES/_FAMILIES empty this knife (cli.py is R1 CLI lake; guarded there)."""
    import subprocess
    probe = subprocess.run(
        ["git", "cat-file", "-e", f"{KNIFE_BASE}^{{commit}}"],
        cwd=ROOT, capture_output=True, text=True,
    )
    if probe.returncode:
        pytest.skip(f"pinned guard base {KNIFE_BASE} unavailable in this checkout")

    import subprocess as sp
    result = sp.run(
        [
            "git", "diff", "--name-only", f"{KNIFE_BASE}..HEAD", "--",
            *[str(p) for p in sorted(CORE)],
        ],
        cwd=ROOT, capture_output=True, text=True, check=True,
    )
    assert result.stdout.strip() == ""
