"""Offline B9 adapter checks; real source supplied by B9_TEST_INFRA_ROOT."""

from __future__ import annotations

import builtins
import hashlib
import importlib.util
import os
import re
import shutil
import socket
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.gates import run_infra_ci_hygiene as adopt

HOST_GATES = (
    "verify_data_path_ssot.py",
    "verify_no_hardcoded_machine_paths.py",
    "verify_tr_bridge_import_ssot.py",
    "verify_corp_actions_economics_fence.py",
)
# Frozen against current origin/master tip 3cb707e95948af66514df53f17227668df476135
# (post #576/#577). No OSkh trading fingerprints. Works in shallow public CI
# without git history. Intentional future host changes must review fingerprints.
# 2026-11-08 consumer policy updates path ownership, the corp-actions fence and
# the private dependency install workflow; other campaign fingerprints stay fixed.
HOST_FILE_HASHES = {
    "scripts/gates/verify_data_path_ssot.py": "ddc711924a66a117ab0219c88edd64cbd34a5127d691666018a87d2f18788651",
    "scripts/gates/verify_no_hardcoded_machine_paths.py": "02573756c2eb96467a20dd5b6f7b1eb994c6bc9e7605972f823d4d086f0347be",
    "scripts/gates/verify_tr_bridge_import_ssot.py": "fff0bf11b93bb4d750bb91815db5b859744c130cb45fd672d3b777c56f5aeddb",
    "scripts/gates/verify_corp_actions_economics_fence.py": "d42e160ac8fea2721e68856beebdad04ee1014a2e0a05b6fcdac3f720e9f6a4e",
    "scripts/install-git-hooks.sh": "4520f8fbda560daad157f4ebbbe8821784e75fb6cf57081da57fbdf4e3453e92",
    "scripts/install-git-hooks.ps1": "920921880b9868a478828c722f3a5c6a8923553eb3dcb08a16e2b1507c1635f6",
    ".github/workflows/python-tests.yml": "96872247e8a46bc6ac211e4c4b3a78d43c9701d0b6220fcab9811ca0a6ef33ec",
}


@pytest.fixture
def infra_root() -> Path:
    configured = os.environ.get("B9_TEST_INFRA_ROOT")
    if not configured:
        pytest.skip("optional pinned scripts unavailable; set B9_TEST_INFRA_ROOT")
    root = Path(configured).resolve()
    adopt.load_scripts(root)  # An explicitly supplied wrong source must fail.
    return root


@pytest.fixture
def target(tmp_path: Path) -> Path:
    root = tmp_path / "BT checkout"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    (root / "README.md").write_text("[guide](docs/guide.md)\n", encoding="utf-8")
    (root / "docs").mkdir()
    (root / "docs/guide.md").write_text("[root](../README.md)\n", encoding="utf-8")
    (root / "safe.py").write_text(
        "raise RuntimeError('scanned files must never execute')\n", encoding="utf-8"
    )
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    return root


@pytest.fixture
def trading_target(target: Path) -> Path:
    for parent in (target, target / "docs"):
        for name in ("live_trading", "trade_decision"):
            path = parent / name
            path.mkdir()
            (path / "README.md").write_bytes(b"\xff\xfe")
            (path / "fixture.py").write_text(repr("ghp_" + "C" * 36), encoding="utf-8")
    subprocess.run(["git", "-C", str(target), "add", "."], check=True)
    return target


@pytest.fixture
def offline(monkeypatch: pytest.MonkeyPatch) -> None:
    def reject_network(*args, **kwargs):
        pytest.fail("optional hygiene must not contact the network")

    monkeypatch.setattr(socket.socket, "connect", reject_network)
    monkeypatch.setattr(socket, "create_connection", reject_network)
    monkeypatch.setattr(socket, "getaddrinfo", reject_network)
    original_run = subprocess.run

    def only_local_git(command, *args, **kwargs):
        assert command[0] == "git", command
        assert command[1] == "-C" and command[3] == "ls-files", command
        return original_run(command, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", only_local_git)
    original_import = builtins.__import__

    def no_application_imports(name, *args, **kwargs):
        assert name.split(".")[0] not in {
            "myquant_infra", "live_trading", "trade_decision", "backtest", "oskh_data",
        }, name
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_application_imports)


def run(infra_root: Path, target: Path, *checks: str) -> int:
    args = ["--root", str(target), "--infra-root", str(infra_root)]
    for check in checks:
        args.extend(("--check", check))
    return adopt.main(args)


def test_missing_infra_is_actionable_without_network(target, offline, capsys):
    assert adopt.main(["--root", str(target)]) == 2
    error = capsys.readouterr().err
    assert "requirements-infra.txt" in error
    assert adopt.INFRA_PIN in error
    assert "--infra-root" in error and "git archive" in error
    assert "wheel alone" in error


def test_missing_script_archive_is_actionable(target, tmp_path, offline, capsys):
    assert run(tmp_path / "absent", target) == 2
    assert "Optional infra CI scripts are missing" in capsys.readouterr().err


def test_real_pin_runs_all_checks_on_bt_not_archive(infra_root, target, offline, capsys):
    before = {p.relative_to(target): p.read_bytes() for p in target.rglob("*") if p.is_file()}
    archive_before = sorted(infra_root.rglob("__pycache__"))
    assert run(infra_root, target) == 0
    output = capsys.readouterr().out
    assert str(target) in output
    assert "Infra encoding:" in output
    assert "no secrets in 3 tracked file(s)" in output
    assert "relative links in 2 markdown files" in output
    after = {p.relative_to(target): p.read_bytes() for p in target.rglob("*") if p.is_file()}
    assert before == after
    assert not list(target.rglob("__pycache__"))
    assert sorted(infra_root.rglob("__pycache__")) == archive_before


def test_default_root_is_bt_checkout_and_independent_of_cwd(
    infra_root, target, offline, monkeypatch, capsys,
):
    monkeypatch.chdir(infra_root)
    monkeypatch.setattr(adopt, "REPO_ROOT", target)
    assert adopt.main(["--infra-root", str(infra_root), "--check", "links"]) == 0
    assert f"target: {target}" in capsys.readouterr().out


@pytest.mark.parametrize(("raw", "rule"), [
    (b"\xef\xbb\xbfhello", "utf8-bom"),
    (b"\xff\xfea\x00", "utf16-bom"),
    (b"a\x00b", "nul-byte"),
    (b"\x81", "not-utf8"),
])
def test_encoding_adopts_real_infra_classifier(infra_root, target, offline, capsys, raw, rule):
    (target / "untracked.txt").write_bytes(raw)
    assert run(infra_root, target, "encoding") == 1
    assert f"untracked.txt:0: {rule}" in capsys.readouterr().err


def test_encoding_keeps_bt_import_policy_and_has_no_oskh_vendor_exemption(
    infra_root, target, offline, capsys,
):
    (target / "scripts").mkdir()
    (target / "scripts/host.py").write_text("from common.infra import data_root\n", encoding="utf-8")
    assert run(infra_root, target, "encoding") == 0
    assert not (target / "scripts/ci/hygiene_allowlist.json").exists()
    (target / "vendor").mkdir()
    (target / "vendor/sample.py").write_bytes(b"\x81")
    assert run(infra_root, target, "encoding") == 1
    assert "vendor/sample.py:0: not-utf8" in capsys.readouterr().err


def test_secret_finding_is_from_bt_and_value_is_not_printed(infra_root, target, offline, capsys):
    sample = "ghp_" + "A" * 36  # synthetic token shape only
    (target / "safe.py").write_text(repr(sample), encoding="utf-8")
    assert run(infra_root, target, "secrets") == 1
    output = capsys.readouterr()
    assert "safe.py:1: github-token" in output.err
    assert sample not in output.out + output.err


def test_secrets_use_bt_allowlist_and_tracked_scope(infra_root, target, offline, capsys):
    (target / "scripts/ci").mkdir(parents=True)
    (target / "scripts/ci/scan_secrets_allow.txt").write_text(
        r"^safe\.py:" + "\n", encoding="utf-8"
    )
    sample = "ghp_" + "B" * 36
    (target / "safe.py").write_text(repr(sample), encoding="utf-8")
    (target / "untracked.py").write_text(repr(sample), encoding="utf-8")
    assert run(infra_root, target, "secrets") == 0
    assert sample not in capsys.readouterr().out


def test_links_find_bt_failure_and_do_not_fetch_external_urls(infra_root, target, offline, capsys):
    (target / "docs/guide.md").write_text(
        "[bad](absent.md)\n[external](https://unreachable.invalid/no-network)\n", encoding="utf-8"
    )
    assert run(infra_root, target, "links") == 1
    assert "docs/guide.md: missing absent.md" in capsys.readouterr().out.replace("\\", "/")


def test_trading_trees_are_never_read_by_any_check(
    infra_root, trading_target, offline, monkeypatch, capsys,
):
    original_read_bytes = Path.read_bytes
    original_read_text = Path.read_text

    def guarded_read_bytes(path, *args, **kwargs):
        assert not {"live_trading", "trade_decision"}.intersection(path.parts), path
        return original_read_bytes(path, *args, **kwargs)

    def guarded_read_text(path, *args, **kwargs):
        assert not {"live_trading", "trade_decision"}.intersection(path.parts), path
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_bytes", guarded_read_bytes)
    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    assert run(infra_root, trading_target) == 0
    output = capsys.readouterr()
    assert "Infra encoding: 0 finding(s) in 3 file(s)" in output.out
    assert "no secrets in 3 tracked file(s)" in output.out
    assert "relative links in 2 markdown files" in output.out


@pytest.mark.parametrize("check", ["encoding", "secrets", "links"])
def test_symlink_rejected_before_reading(infra_root, target, tmp_path, offline, capsys, check,
                                       require_directory_symlink):
    outside = tmp_path / "outside.md"
    outside.write_bytes(b"\xff\xfe")
    link = target / "docs/guide.md"  # already tracked; selected by all checks
    link.unlink()
    link.symlink_to(outside)
    assert run(infra_root, target, check) == 2
    assert "symlink-or-escape" in capsys.readouterr().err


def test_wrong_pin_fails_before_loading_any_code(
    infra_root, target, tmp_path, offline, monkeypatch, capsys,
):
    wrong = tmp_path / "wrong/scripts/ci"
    wrong.mkdir(parents=True)
    for name in adopt.SCRIPT_HASHES:
        shutil.copyfile(infra_root / "scripts/ci" / f"{name}.py", wrong / f"{name}.py")
    (wrong / "check_md_links.py").write_text(
        "raise AssertionError('must not execute')", encoding="utf-8"
    )

    def reject_loading(*args, **kwargs):
        pytest.fail("all scripts must be verified before any module is created")

    monkeypatch.setattr(adopt, "ModuleType", reject_loading)
    assert run(wrong.parents[1], target) == 2
    assert "does not match the pin" in capsys.readouterr().err


def test_invalid_target_does_not_fall_back_to_infra(infra_root, tmp_path, offline, capsys):
    assert run(infra_root, tmp_path / "not a checkout", "links") == 2
    assert "Git checkout root" in capsys.readouterr().err


def test_fresh_bindings_and_repeated_selections(infra_root, target, tmp_path, offline, capsys):
    (target / "safe.py").write_text(repr("ghp_" + "D" * 36), encoding="utf-8")
    assert run(infra_root, target, "secrets", "secrets") == 1
    clean = tmp_path / "another checkout"
    shutil.copytree(target, clean)
    (clean / "safe.py").write_text("# safe\n", encoding="utf-8")
    assert run(infra_root, clean, "secrets", "links", "links", "secrets") == 0
    assert f"target: {clean}" in capsys.readouterr().out


@pytest.mark.parametrize("name", HOST_GATES)
def test_host_gates_import_and_keep_public_entrypoints_without_infra(name, monkeypatch):
    def reject_infra(*args, **kwargs):
        pytest.fail("host gates must remain independent of optional infra")

    monkeypatch.setattr(adopt, "load_scripts", reject_infra)
    path = adopt.REPO_ROOT / "scripts/gates" / name
    spec = importlib.util.spec_from_file_location(f"_b9_host_{path.stem}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    if name in {"verify_data_path_ssot.py", "verify_no_hardcoded_machine_paths.py"}:
        with pytest.raises(SystemExit) as exited:
            module.main(["--help"])
        assert exited.value.code == 0
    else:
        assert module.main() == 0  # These host gates have no argparse/help API.


def test_reviewed_host_contract_fingerprints():
    for name, expected in HOST_FILE_HASHES.items():
        # Ignore checkout-only autocrlf conversion on Windows runners.
        source = (adopt.REPO_ROOT / name).read_bytes().replace(b"\r\n", b"\n")
        assert hashlib.sha256(source).hexdigest() == expected, name


def test_optional_entrypoint_help_runs_without_infra(tmp_path):
    result = subprocess.run(
        [sys.executable, str(Path(adopt.__file__)), "--help"],
        cwd=tmp_path, check=False, capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "--infra-root" in result.stdout
    assert "Optional, additive" in result.stdout


def test_public_import_does_not_load_optional_or_application_packages(offline):
    spec = importlib.util.spec_from_file_location("_b9_public_import", adopt.__file__)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.REPO_ROOT == adopt.REPO_ROOT


def test_required_pin_preserves_migration_provenance_and_optional_tool_pin():
    text = (adopt.REPO_ROOT / "requirements-infra.txt").read_text(encoding="utf-8")
    pins = re.findall(r"^myquant-infra(?:\[[^]]+\])? @ git\+(\S+)$", text, re.M)
    assert len(pins) == 1
    assert pins[0].endswith(f"MyQuant-infra.git@{adopt.INFRA_PIN}")
    for record in ("b2-bars-adj", "k18-duckdb", "b7-hithink-artifact"):
        assert f"docs/engineering/{record}-infra-switch-20261105.md" in text
