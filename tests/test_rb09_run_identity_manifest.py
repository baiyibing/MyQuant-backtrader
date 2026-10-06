"""RB-09 caller-supplied identity is opt-in audit provenance."""

import hashlib
import json
from pathlib import Path

import pytest

from bt_contract import canonical_json_bytes
from bt_contract.run_manifest import build_bt_run_manifest, write_run_identity_sidecar


def _build(**kwargs):
    return build_bt_run_manifest(
        strategy="version6", dividend_type="none", config={"flag": True}, **kwargs
    )


def test_default_manifest_matches_prior_shape_and_config_hash():
    expected = {
        "schema": "myquant.bt-run/1", "git_commit": "UNKNOWN",
        "strategy": "version6", "dividend_type": "none",
        "fee_schedule": "BILATERAL_10BP", "liquidity_cap": "off",
        "participation_rate": None, "signal_bundle_sha256": None,
        "config_sha256": hashlib.sha256(canonical_json_bytes({"flag": True})).hexdigest(),
        "artifacts": [],
    }
    assert _build() == expected
    assert _build(book_rule_revision=None, pool_identity=None, price_domain=None,
                  input_tokens=None, environment=None) == expected


def test_identity_hash_is_canonical_and_sensitive_to_tokens():
    fields = dict(
        book_rule_revision="version6:rules-v1", pool_identity="pool/sha256:abc",
        price_domain="raw", input_tokens={"source_snapshot": "snapshot:abc", "cache": "v1"},
        environment={"python": "3.12", "pandas": "2.2"},
    )
    manifest = _build(**fields)
    assert manifest["run_identity"] == fields
    assert manifest["run_identity_sha256"] == hashlib.sha256(
        canonical_json_bytes(fields)
    ).hexdigest()
    reordered = dict(fields, input_tokens=dict(reversed(list(fields["input_tokens"].items()))),
                     environment=dict(reversed(list(fields["environment"].items()))))
    assert canonical_json_bytes(_build(**reordered)) == canonical_json_bytes(manifest)
    changed = _build(**dict(fields, input_tokens={"source_snapshot": "snapshot:def"}))
    assert changed["run_identity_sha256"] != manifest["run_identity_sha256"]
    assert changed["config_sha256"] == _build()["config_sha256"]


@pytest.mark.parametrize("value", [Path("pool/input"), 42, None])
def test_tokens_require_strings(value):
    with pytest.raises(TypeError, match="input_tokens"):
        _build(input_tokens={"source_snapshot": value})


@pytest.mark.parametrize("value", ["", "  "])
def test_tokens_reject_empty_strings(value):
    with pytest.raises(ValueError, match="non-empty"):
        _build(input_tokens={"source_snapshot": value})


@pytest.mark.parametrize("value", ["/host/private/lake", "C:/private/lake", "\\\\host\\lake"])
def test_identity_rejects_absolute_host_paths(value):
    with pytest.raises(ValueError, match="absolute host path"):
        _build(input_tokens={"source_snapshot": value})


def test_partial_identity_omits_absent_fields_and_copies_mapping():
    tokens = {"source_snapshot": "resolver:stock/period=1m"}
    manifest = _build(input_tokens=tokens)
    tokens["source_snapshot"] = "changed"
    assert manifest["run_identity"] == {
        "input_tokens": {"source_snapshot": "resolver:stock/period=1m"}
    }
    assert _build(environment={})["run_identity"] == {"environment": {}}


def test_sidecar_is_explicit_canonical_write_without_mutation(tmp_path):
    output = tmp_path / "trades.csv"
    output.write_bytes(b"side,shares\nBUY,100\n")
    manifest = _build(price_domain="raw")
    path = tmp_path / "run-identity.json"
    assert list(tmp_path.iterdir()) == [output]
    before = canonical_json_bytes(manifest)
    write_run_identity_sidecar(path, manifest)
    assert path.read_bytes() == before
    assert json.loads(path.read_bytes()) == manifest
    assert canonical_json_bytes(manifest) == before
    assert output.read_bytes() == b"side,shares\nBUY,100\n"
