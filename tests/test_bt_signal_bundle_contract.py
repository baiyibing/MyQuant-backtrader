"""Data-free fixtures for the MQ signal file contract (no MQ checkout needed)."""

import ast
import hashlib
from pathlib import Path

import pytest

from bt_contract import canonical_json_bytes, validate_signal_bundle


def _digest(value):
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _sign(bundle):
    bundle["bundle_sha256"] = _digest(
        {key: value for key, value in bundle.items() if key != "bundle_sha256"}
    )
    return bundle


@pytest.fixture
def bundle(tmp_path):
    data = b"300190\n"
    (tmp_path / "20260925.csv").write_bytes(data)
    return _sign({
        "schema": "myquant.signal-bundle/1",
        "signal_asof_policy": "pred_minus_one",
        "availability": "unproven",
        "available_at": None,
        "calendar_id": _digest(["2026-09-25"]),
        "price_domain": "unspecified",
        "rows": [{
            "signal_asof": "2026-09-24", "target_session": "2026-09-25",
            "pool_file": "20260925.csv", "pool_md5": hashlib.md5(data).hexdigest(),
            "pool_sha256": hashlib.sha256(data).hexdigest(),
        }],
    })


def test_accepts_unproven_bundle_with_matching_file_hashes(bundle, tmp_path):
    before = canonical_json_bytes(bundle)
    assert validate_signal_bundle(bundle, files_root=tmp_path) is None
    assert canonical_json_bytes(bundle) == before


@pytest.mark.parametrize("algorithm,length", [("md5", 32), ("sha256", 64)])
def test_rejects_hash_mismatch(bundle, tmp_path, algorithm, length):
    bundle["rows"][0][f"pool_{algorithm}"] = "0" * length
    with pytest.raises(ValueError, match=f"pool_{algorithm} mismatch"):
        validate_signal_bundle(_sign(bundle), files_root=tmp_path)


def test_rejects_available_at_after_target_session(bundle):
    bundle.update(availability="declared", available_at="2026-09-26T09:00:00+08:00")
    with pytest.raises(ValueError, match="available_at is after"):
        validate_signal_bundle(_sign(bundle))


def test_rejects_unknown_schema(bundle):
    bundle["schema"] = "myquant.signal-bundle/2"
    with pytest.raises(ValueError, match="unknown schema"):
        validate_signal_bundle(_sign(bundle))


def test_pred_minus_one_equal_dates_rejected(bundle):
    bundle["rows"][0]["signal_asof"] = "2026-09-25"
    with pytest.raises(ValueError, match="pred_minus_one requires"):
        validate_signal_bundle(_sign(bundle))


def test_identity_requires_equal_dates(bundle):
    bundle["signal_asof_policy"] = "identity"
    with pytest.raises(ValueError, match="identity requires"):
        validate_signal_bundle(_sign(bundle))
    bundle["rows"][0]["signal_asof"] = "2026-09-25"
    validate_signal_bundle(_sign(bundle))


@pytest.mark.parametrize("field", ["calendar_id", "bundle_sha256"])
def test_rejects_internal_hash_mismatch(bundle, field):
    bundle[field] = "0" * 64
    with pytest.raises(ValueError, match=f"{field} mismatch"):
        validate_signal_bundle(bundle)


def test_rejects_duplicate_or_unsafe_pool_file(bundle, tmp_path):
    bundle["rows"].append(dict(bundle["rows"][0]))
    with pytest.raises(ValueError, match="duplicate pool_file"):
        validate_signal_bundle(_sign(bundle))
    bundle["rows"].pop()
    bundle["rows"][0]["pool_file"] = "../20260925.csv"
    with pytest.raises(ValueError, match="pool_file must be"):
        validate_signal_bundle(_sign(bundle), files_root=tmp_path)


def test_unproven_requires_null_available_at(bundle):
    bundle["available_at"] = "2026-09-24T18:00:00+08:00"
    with pytest.raises(ValueError, match="unproven availability"):
        validate_signal_bundle(_sign(bundle))


@pytest.mark.parametrize("timestamp", [
    "2026-09-24T18:00:00Z", "2026-09-24T18:00:00.1+08:00",
    "2026-09-24T24:00:00+08:00",
])
def test_rejects_malformed_declared_timestamp(bundle, timestamp):
    bundle.update(availability="declared", available_at=timestamp)
    with pytest.raises(ValueError, match="available_at"):
        validate_signal_bundle(_sign(bundle))


def test_declared_timestamp_and_empty_bundle_follow_mq_semantics(bundle):
    bundle.update(availability="declared", available_at="2026-09-23T18:00:00+08:00")
    validate_signal_bundle(_sign(bundle))
    bundle.update(rows=[], calendar_id=_digest([]))
    validate_signal_bundle(_sign(bundle))


def test_validator_does_not_import_research_or_fee_policy():
    package = Path(__file__).resolve().parents[1] / "bt_contract"
    forbidden = {"backtest", "oskh_data", "trade_fee_policy", "myquant_contract"}
    for path in package.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(not (set(alias.name.split(".")) & forbidden) for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                assert not (set((node.module or "").split(".")) & forbidden)
            elif isinstance(node, ast.Attribute):
                assert ast.unparse(node) != "sys.path"


def test_schema_file_sha256_pinned():
    path = Path(__file__).resolve().parents[1] / "bt_contract/schema/signal-bundle-1.schema.json"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == (
        "5464b038ac827969647f71d68041a732581e74859597f03d4b8b128cb1240f38"
    )


def test_canonical_json_is_utf8_without_bom():
    assert canonical_json_bytes({"z": "研究", "a": 1}) == '{"a":1,"z":"研究"}\n'.encode()
