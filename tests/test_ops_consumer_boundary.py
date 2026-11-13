"""Host invocation contracts; shared runtime behavior is tested in ops."""
import json
import importlib.util
from pathlib import Path
import subprocess
import sys
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load_local(name: str, relative: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Explicit file loading avoids another checkout's "scripts" namespace in test
# execution environments; this is the actual host adapter under test.
host = load_local("bt_ops_host", "scripts/_ops_bootstrap.py")
gate = load_local("bt_ops_gate", "scripts/gates/verify_ops_consumer_boundary.py")
ENTRIES, RETIRED, violations = gate.ENTRIES, gate.RETIRED, gate.violations


@pytest.fixture
def ops(tmp_path):
    root = tmp_path / "explicit ops"
    (root / "scripts").mkdir(parents=True)
    (root / "scripts/runtime-api.json").write_text(
        json.dumps({"schema_version": 1, "entries": list(ENTRIES),
                    "entry_scopes": {entry: "repo" for entry in ENTRIES},
                    "capabilities": sorted(host.REVIEW_CAPABILITIES)}), encoding="utf-8")
    for entry in ENTRIES:
        path = root / entry
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# synthetic entry\n", encoding="utf-8")
    return root


def test_repository_has_no_local_ops_implementation():
    assert violations(ROOT) == []


def test_missing_or_incompatible_ops_fails_before_subprocess(monkeypatch, tmp_path):
    monkeypatch.delenv("MYQUANT_OPS_ROOT", raising=False)
    calls = []
    monkeypatch.setattr(host.subprocess, "call", lambda *a, **kw: calls.append((a, kw)))
    with pytest.raises(SystemExit) as exc:
        host.run_ops(ENTRIES[0], [])
    assert exc.value.code == 2
    for value in ("relative", str(tmp_path)):
        with pytest.raises(SystemExit):
            host.run_ops(ENTRIES[0], ["--ops-root", value])
    assert calls == []


@pytest.mark.parametrize("entry,profile", [
    (ENTRIES[0], "config/ops/bt-review.json"),
    (ENTRIES[1], "config/ops/bt-adversarial.json"), (ENTRIES[2], None),
])
def test_host_injects_root_and_profile_and_propagates_failure(ops, monkeypatch, entry, profile):
    calls = []
    monkeypatch.setenv("MYQUANT_OPS_ROOT", str(ops))
    monkeypatch.setattr(host.subprocess, "call", lambda *a, **kw: calls.append((a, kw)) or 17)
    assert host.run_ops(entry, ["--dry-run"], profile=profile) == 17
    args, kwargs = calls[0]
    command = args[0]
    assert command[:4] == [sys.executable, str(ops / entry), "--repo-root", str(ROOT)]
    assert command[-1] == "--dry-run" and kwargs["cwd"] == ROOT
    if profile:
        assert command[4:6] == ["--profile-file", str(ROOT / profile)]
    else:
        assert "--profile-file" not in command


@pytest.mark.parametrize("option", ["--repo-root", "--repo-root=other", "--profile-file", "--profile-file=other",
                                    "--repo-r", "--repo-r=other", "--profile-f", "--profile-f=other"])
def test_host_context_cannot_be_overridden(ops, option):
    with pytest.raises(SystemExit) as exc:
        host.run_ops(ENTRIES[0], ["--ops-root", str(ops), option])
    assert exc.value.code == 2


@pytest.mark.parametrize("entry", ENTRIES)
def test_legacy_cli_from_unrelated_cwd_uses_shared_entry_only(tmp_path, ops, entry):
    source = ops / entry
    source.write_text("import json,sys\nprint(json.dumps(sys.argv[1:]))\nraise SystemExit(19)\n", encoding="utf-8")
    result = subprocess.run([sys.executable, str(ROOT / entry), "--ops-root", str(ops), "--dry-run"],
                            cwd=tmp_path, text=True, capture_output=True)
    assert result.returncode == 19, result.stderr
    args = json.loads(result.stdout)
    assert args[:2] == ["--repo-root", str(ROOT)] and args[-1] == "--dry-run"


def test_profiles_preserve_host_policy_without_model_catalogs():
    review = json.loads((ROOT / "config/ops/bt-review.json").read_text(encoding="utf-8"))
    adversarial = json.loads((ROOT / "config/ops/bt-adversarial.json").read_text(encoding="utf-8"))
    assert "T+1" in review["domain_context"] and "向量化 CSV" in review["domain_context"]
    assert len(adversarial["lanes"]) == 3
    assert "T+1" in adversarial["lanes"][1][2]
    assert set(review) == {"schema_version", "domain_context", "ssot_paths", "role_suffix"}
    assert review["schema_version"] == 2 and all((ROOT / p).is_file() for p in review["ssot_paths"])
    assert set(adversarial) == {"schema_version", "lanes", "prompt_template"}


def test_gate_rejects_restored_model_catalog_and_runtime(tmp_path):
    profile = tmp_path / "config/ops/bt-review.json"
    profile.parent.mkdir(parents=True)
    profile.write_bytes((ROOT / "config/ops/bt-review.json").read_bytes())
    for name in ENTRIES:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((ROOT / name).read_bytes())
    assert violations(tmp_path) == []
    retired = tmp_path / RETIRED
    retired.write_text("# restored runtime\n", encoding="utf-8")
    assert any("retired ops" in error for error in violations(tmp_path))
    retired.unlink()
    path = tmp_path / ENTRIES[0]
    with path.open("a", encoding="utf-8") as stream:
        stream.write("CATALOG = ['local model copy']\n")
    assert any("local ops" in error for error in violations(tmp_path))


def test_gate_rejects_local_publisher_or_runner_inside_wrapper(tmp_path):
    for name in ENTRIES:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((ROOT / name).read_bytes())
    with (tmp_path / ENTRIES[2]).open("a", encoding="utf-8") as stream:
        stream.write("def publish():\n    return 0\n")
    assert any("local ops implementation" in error for error in violations(tmp_path))


def test_old_api_is_still_compatible_for_publisher_and_v1_adversarial_only(ops, monkeypatch):
    (ops / "scripts/runtime-api.json").write_text(json.dumps({"schema_version": 1, "entries": list(ENTRIES)}), encoding="utf-8")
    calls = []
    monkeypatch.setattr(host.subprocess, "call", lambda *a, **kw: calls.append(a) or 17)
    for entry in ENTRIES[1:]:
        assert host.run_ops(entry, ["--ops-root", str(ops)]) == 17
    with pytest.raises(SystemExit) as exc:
        host.run_ops(ENTRIES[0], ["--ops-root", str(ops)], profile="config/ops/bt-review.json")
    assert exc.value.code == 2 and len(calls) == 2


@pytest.mark.parametrize("extra", ['\nexec("def local_runtime(): pass")\n', '\nrun_ops("extra")\n'])
def test_gate_rejects_extra_top_level_execution(tmp_path, extra):
    for entry in ENTRIES:
        path = tmp_path / entry
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((ROOT / entry).read_bytes())
    profile = tmp_path / "config/ops/bt-review.json"
    profile.parent.mkdir(parents=True)
    profile.write_bytes((ROOT / "config/ops/bt-review.json").read_bytes())
    assert violations(tmp_path) == []
    with (tmp_path / ENTRIES[0]).open("a", encoding="utf-8") as stream:
        stream.write(extra)
    assert any("local ops implementation" in error for error in violations(tmp_path))
