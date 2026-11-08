"""Offline B8 v1 goldens, forwarding, and public import/help surfaces."""

from __future__ import annotations

import copy
import hashlib
import importlib
import json
from pathlib import Path
import socket
import subprocess
import sys

import pytest

from bt_contract import canonical_json_bytes
from bt_contract import run_manifest as host_run
from bt_contract import signal_bundle as host_signal

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/b8_v1_contracts.json"
GOLDEN = json.loads(FIXTURE.read_bytes())


@pytest.fixture(autouse=True)
def forbid_network(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("B8 contract tests must stay offline")

    monkeypatch.setattr(socket, "create_connection", fail)
    monkeypatch.setattr(socket.socket, "connect", fail)
    monkeypatch.setattr(socket.socket, "connect_ex", fail)


def test_baseline_fixture_and_schema_are_frozen():
    assert GOLDEN["baseline_commit"] == "a13b0f2cf9142c36991e0de099ef238ebb382a56"
    assert hashlib.sha256(FIXTURE.read_bytes()).hexdigest() == (
        "f3487a57d395a69abfa92d05d4bb7895122b3bcfe323472342be18b2e6d30fea"
    )
    from importlib.resources import files

    schema = files("myquant_infra.contracts.signal_bundle").joinpath("schema/signal-bundle-1.schema.json")
    # This digest was computed from the former host schema's JSON value.
    # Infra owns the schema asset; formatting differs, the contract does not.
    canonical_schema = json.dumps(json.loads(schema.read_bytes()), sort_keys=True,
                                  separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    assert hashlib.sha256(canonical_schema).hexdigest() == (
        "3f1b188bd91e84818cd81cd59cc4c90e7acb7c3a0a78a306e08a9d9f41f60388"
    )


@pytest.mark.parametrize("case", GOLDEN["bundles"], ids=lambda case: case["name"])
def test_bundle_v1_golden_and_infra_parity(case, tmp_path):
    infra = pytest.importorskip("myquant_infra.contracts.signal_bundle")
    for filename, data in GOLDEN["pool_files"].items():
        (tmp_path / filename).write_bytes(data.encode())
    rows = copy.deepcopy(case["rows"])
    bundle = host_signal.build_signal_bundle(rows, **case["options"])
    assert host_signal.SCHEMA == infra.SCHEMA == "myquant.signal-bundle/1"
    assert bundle == infra.build_signal_bundle(rows, **case["options"]) == case["expected"]
    assert rows == case["rows"]
    assert bundle["rows"] is not rows
    before = canonical_json_bytes(bundle)
    assert before == infra.canonical_json_bytes(bundle)
    assert hashlib.sha256(before).hexdigest() == case["canonical_sha256"]
    assert host_signal.validate_signal_bundle(bundle, files_root=tmp_path) is None
    assert infra.validate_signal_bundle(bundle, files_root=tmp_path) is None
    assert canonical_json_bytes(bundle) == before


@pytest.mark.parametrize("case", GOLDEN["manifests"], ids=lambda case: case["name"])
def test_bt_manifest_v1_golden_and_infra_parity(case, tmp_path, monkeypatch):
    infra = pytest.importorskip("myquant_infra.artifacts.provenance")
    monkeypatch.chdir(tmp_path)
    Path("trades.csv").write_bytes(b"side,shares\nBUY,100\n")
    options = copy.deepcopy(case["options"])
    if case["name"] == "rich":
        # The old host normalized nested Paths and tuples before hashing.
        options["config"]["pool_dir"] = Path("pool/研究")
        options["config"]["nested"] = ({"root": Path("inputs")},)
        options["artifacts"] = (Path("trades.csv"),)
    before = copy.deepcopy(options)
    manifest = host_run.build_bt_run_manifest(**options)
    assert manifest == infra.build_bt_run_manifest(**options) == case["expected"]
    assert manifest["schema"] == "myquant.bt-run/1"
    assert infra.SCHEMA_ID == "myquant.run-manifest/1"  # MQ dialect stays separate.
    assert options == before
    payload = canonical_json_bytes(manifest)
    assert payload == infra.canonical_json_bytes(manifest)
    assert hashlib.sha256(payload).hexdigest() == case["canonical_sha256"]
    host_run.validate_bt_run_manifest(manifest)
    infra.validate_bt_run_manifest(manifest)
    write_options = dict(options, git_commit=manifest["git_commit"])
    assert host_run.write_bt_run_manifest("host.json", **write_options) == manifest
    assert infra.write_bt_run_manifest("infra.json", **write_options) == manifest
    host_run.write_run_identity_sidecar("identity.json", manifest)
    assert Path("host.json").read_bytes() == Path("infra.json").read_bytes() == payload
    assert Path("identity.json").read_bytes() == payload


def test_writer_captures_bt_repository_and_preserves_explicit_commit(tmp_path, monkeypatch):
    infra = pytest.importorskip("myquant_infra.artifacts.provenance")
    repos = []

    def capture(repo_root):
        repos.append(repo_root)
        return "a" * 40

    monkeypatch.setattr(infra, "git_commit", capture)
    options = dict(strategy="version6", dividend_type="none", config={})
    implicit = host_run.write_bt_run_manifest(tmp_path / "implicit.json", **options)
    explicit = host_run.write_bt_run_manifest(
        tmp_path / "explicit.json", **options, git_commit="b" * 40,
    )
    assert repos == [ROOT]
    assert implicit["git_commit"] == "a" * 40
    assert explicit["git_commit"] == "b" * 40


def test_delegates_resolve_the_shared_functions(monkeypatch):
    signal = pytest.importorskip("myquant_infra.contracts.signal_bundle")
    provenance = pytest.importorskip("myquant_infra.artifacts.provenance")
    sentinel = object()
    for module, name, args in [
        (signal, "canonical_json_bytes", ({"z": "研究"},)),
        (signal, "validate_signal_bundle", ({},)),
        (signal, "build_signal_bundle", ([],)),
        (provenance, "validate_bt_run_manifest", ({},)),
        (provenance, "write_run_identity_sidecar", ("unused.json", {})),
        (provenance, "_identity_mapping", ({}, "input_tokens")),
    ]:
        facade = host_signal if module is signal else host_run
        calls = []

        def delegated(*positional, **keywords):
            calls.append((positional, keywords))
            return sentinel

        with monkeypatch.context() as patch:
            patch.setattr(module, name, delegated)
            assert getattr(facade, name)(*args) is sentinel
        assert len(calls) == 1
        assert calls[0][0] == args


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_canonicalization_rejects_non_finite_values(value):
    pytest.importorskip("myquant_infra.contracts.signal_bundle")
    with pytest.raises(ValueError):
        canonical_json_bytes({"value": value})


@pytest.mark.parametrize("failure", ["absent", "submodule", "transitive", "symbol"])
def test_lazy_imports_and_missing_or_incomplete_infra(tmp_path, failure):
    # Separate interpreter: no module-cache contamination, installed package optional.
    code = '''
import importlib.abc
import pathlib
import socket
import sys

failure = sys.argv[1]
error = ModuleNotFoundError("private infra unavailable", name="myquant_infra")
if failure == "submodule":
    error = ModuleNotFoundError("missing signal submodule", name="myquant_infra.contracts.signal_bundle")
elif failure == "transitive":
    error = ModuleNotFoundError("missing transitive dependency", name="broken_dependency")
elif failure == "symbol":
    error = ImportError("cannot import shared API")

class BlockInfra(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "myquant_infra" or fullname.startswith("myquant_infra."):
            raise error

sys.meta_path.insert(0, BlockInfra())
def offline(*args, **kwargs):
    raise AssertionError("network forbidden")
socket.socket.connect = offline
socket.create_connection = offline

import bt_contract
from bt_contract import signal_bundle, run_manifest
assert not any(name.startswith("myquant_infra") for name in sys.modules)
if failure == "absent":
    import importlib
    for name in ("backtest.research.csv_daily_backtest", "backtest.research.csv_minute_backtest"):
        try:
            importlib.import_module(name)
        except ModuleNotFoundError as exc:
            assert exc is error
        else:
            raise AssertionError("research consumers must require infra")
for feature in (
    lambda: bt_contract.canonical_json_bytes({}),
    lambda: signal_bundle.validate_signal_bundle({}),
    lambda: signal_bundle.build_signal_bundle([]),
    lambda: run_manifest.build_bt_run_manifest(strategy="version6", dividend_type="none", config={}),
    lambda: run_manifest.validate_bt_run_manifest({}),
    lambda: run_manifest.write_bt_run_manifest(sys.argv[2]),
    lambda: run_manifest.write_run_identity_sidecar(sys.argv[2], {}),
    lambda: run_manifest._identity_mapping({}, "input_tokens"),
):
    try:
        feature()
    except ImportError as exc:
        if failure == "absent":
            assert "requirements-infra.txt" in str(exc)
            assert exc.__cause__ is error
        else:
            assert exc is error
    else:
        raise AssertionError("feature used a local fallback")
assert not pathlib.Path(sys.argv[2]).exists()
'''
    result = subprocess.run(
        [sys.executable, "-c", code, failure, str(tmp_path / "must-not-write.json")],
        cwd=ROOT, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr


def test_unknown_infra_module_does_not_become_an_install_hint(monkeypatch):
    loader = importlib.import_module("bt_contract._infra")
    error = ModuleNotFoundError("missing installed API", name="myquant_infra.contracts.missing")

    def broken(name):
        raise error

    monkeypatch.setattr(loader, "import_module", broken)
    with pytest.raises(ModuleNotFoundError) as caught:
        host_signal.build_signal_bundle([])
    assert caught.value is error


def _public_pool_facade(monkeypatch, error=None):
    import builtins
    import importlib.util

    original = builtins.__import__
    error = error or ModuleNotFoundError("private infra unavailable", name="myquant_infra")

    def absent(name, *args, **kwargs):
        if name == "myquant_infra" or name.startswith("myquant_infra."):
            raise error
        return original(name, *args, **kwargs)

    spec = importlib.util.spec_from_file_location(
        "b8_public_pool", ROOT / "common/infra/pool_csv.py",
    )
    module = importlib.util.module_from_spec(spec)
    with monkeypatch.context() as patch:
        patch.setattr(builtins, "__import__", absent)
        spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("error", [
    ModuleNotFoundError("private infra unavailable", name="myquant_infra"),
    ModuleNotFoundError("missing pool submodule", name="myquant_infra.reference_data.pool_csv"),
    ModuleNotFoundError("missing transitive dependency", name="broken_dependency"),
    ImportError("cannot import shared pool API"),
])
def test_pool_requires_infra_without_any_local_fallback(monkeypatch, error):
    with pytest.raises(type(error)) as caught:
        _public_pool_facade(monkeypatch, error)
    assert caught.value is error


def test_pool_facade_reexports_the_existing_infra_twin():
    infra = pytest.importorskip("myquant_infra.reference_data.pool_csv")
    host = importlib.import_module("common.infra.pool_csv")
    for name in ("PoolDuplicateCodeError", "check_pool_duplicate", "iter_pool_csv_rows", "pool_cell_to_bare"):
        assert getattr(host, name) is getattr(infra, name)


def test_pool_record_lines_and_duplicate_scope_stay_unchanged(tmp_path):
    pool = importlib.import_module("common.infra.pool_csv")
    path = tmp_path / "20260925.csv"
    path.write_text('\ufeffcode,name\n# comment,"\n000001,"first\nname"\n\nsz000001,second\n', encoding="utf-8", newline="\n")
    assert list(pool.iter_pool_csv_rows(path)) == [
        (3, ["000001", "first\nname"]), (6, ["sz000001", "second"]),
    ]
    for cell in ("SZ000001", "000001.SZ", '=\'000001\''):
        assert pool.pool_cell_to_bare(cell) == "000001"
    seen = {}
    pool.check_pool_duplicate(path, seen, "000001.SZ", 3, day="20260925")
    pool.check_pool_duplicate(path, seen, "000001.SZ", 4, day="20260928")
    with pytest.raises(pool.PoolDuplicateCodeError) as caught:
        pool.check_pool_duplicate(path, seen, "000001.SZ", 6, day="20260925")
    assert (caught.value.first_line, caught.value.second_line) == (3, 6)
    assert caught.value.code == "000001.SZ"
    assert caught.value.day == "20260925"
