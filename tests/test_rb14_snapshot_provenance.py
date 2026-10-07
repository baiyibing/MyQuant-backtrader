"""Synthetic-only RB-14 provenance and opt-in fences."""

import ast
import json
from pathlib import Path

import pytest
from backtest.research.snapshot_provenance import snapshot_provenance_tokens
from bt_contract.run_manifest import build_bt_run_manifest

from tests.test_ashare_simulate_import_fence import SIMULATE_HOT_PATH


@pytest.mark.parametrize("token", ["upstream:release-17", "shallow-v1:" + "a" * 64])
def test_sidecar_and_identity_compose_without_mutation(tmp_path, token):
    identity = {"source_snapshot": token, "resolver_identity": "/unread/lake", "identity_version": 1}
    path = tmp_path / "synthetic.json"
    path.write_text(json.dumps(identity), encoding="utf-8")
    before = path.read_bytes()
    tokens = snapshot_provenance_tokens(path)
    assert tokens == snapshot_provenance_tokens(identity) == {"source_snapshot": token}
    manifest = build_bt_run_manifest(strategy="version6", dividend_type="none", config={}, input_tokens=tokens)
    assert manifest["run_identity"]["input_tokens"] == tokens
    assert manifest["run_identity_sha256"]
    assert path.read_bytes() == before
    assert list(tmp_path.iterdir()) == [path]
    assert identity["source_snapshot"] == token


@pytest.mark.parametrize("identity", [{}, {"source_snapshot": None}, {"source_snapshot": ""}, {"source_snapshot": "  "}])
def test_unavailable(tmp_path, identity):
    path = tmp_path / "missing-token.json"
    path.write_text(json.dumps(identity), encoding="utf-8")
    assert snapshot_provenance_tokens(path) == snapshot_provenance_tokens(identity) == {}


@pytest.mark.parametrize("token,error", [(42, TypeError), ("/host/lake", ValueError)])
def test_reuses_rb09_validation(token, error):
    with pytest.raises(error):
        snapshot_provenance_tokens({"source_snapshot": token})


def test_invalid_sidecars_are_explicit_errors(tmp_path):
    path = tmp_path / "bad.json"
    with pytest.raises(FileNotFoundError):
        snapshot_provenance_tokens(path)
    path.write_text("{", encoding="utf-8")
    with pytest.raises(ValueError):
        snapshot_provenance_tokens(path)
    path.write_text("[]", encoding="utf-8")
    with pytest.raises(TypeError):
        snapshot_provenance_tokens(path)


def test_opt_in_hot_path_and_no_directory_walking():
    root = Path(__file__).resolve().parents[1] / "backtest/research"
    for name in SIMULATE_HOT_PATH:
        tree = ast.parse((root / f"{name}.py").read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                assert "snapshot_provenance" not in ast.unparse(node)
    tree = ast.parse((root / "snapshot_provenance.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            assert ast.unparse(node.func) not in {"os.walk", "walk", "rglob"}
            if isinstance(node.func, ast.Attribute):
                assert node.func.attr not in {"walk", "rglob", "glob", "iterdir", "stat"}


def test_string_argument_is_path(tmp_path):
    path = tmp_path / "identity.json"
    path.write_text('{"source_snapshot": "upstream:release-17"}', encoding="utf-8")
    assert snapshot_provenance_tokens(str(path)) == snapshot_provenance_tokens(path)
    with pytest.raises(FileNotFoundError):
        snapshot_provenance_tokens('{"source_snapshot": "inline"}')


def test_documented_empty_token_composition_preserves_default_manifest():
    tokens = snapshot_provenance_tokens({})
    options = dict(strategy="version6", dividend_type="none", config={})
    assert build_bt_run_manifest(**options, input_tokens=tokens or None) == build_bt_run_manifest(**options)
