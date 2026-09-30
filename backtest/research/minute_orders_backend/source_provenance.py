"""B-L2-01 source identities, independently bound to the unchanged S4 input.

This is evidence validation, not host certification. Fixture PASS != lake PASS.
Nothing is resolved or read until an explicit source/evidence API is called.
"""

import hashlib
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from importlib.metadata import version
from pathlib import Path

PROVENANCE_VERSION = "minute_orders_source_provenance_v1"
EVIDENCE_VERSION = "minute_orders_hybrid_evidence_v1"
TRANSFORM_VERSION = "bl2_source_transform_v1"
SOURCE_MARK_PREFIX = "B-L2-01/"
FIXTURE_NOTICE = "Fixture PASS != lake PASS; no host attestation or live PASS is established."


class SourceContractError(ValueError):
    """Source preflight failed; do not invent bars, coverage or evidence."""


def require(condition, message):
    if not condition:
        raise SourceContractError(message)


def object_fields(value, names, where):
    require(type(value) is dict and set(value) == set(names),
            f"{where}: schema fields must be {sorted(names)}")


def nonempty(value, where):
    require(type(value) is str and bool(value.strip()), f"{where}: nonempty text required")
    return value


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def attestation_scope(recipe):
    """Bind the exact recipe/mappings and all material except the attestation.

    Excluding that one descriptor avoids a circular file hash. Its own bytes
    remain pinned by the recipe. Thus a different START/END label, unit/factor,
    source, mark grid or command batch requires a newly scoped attestation.
    """
    return sha256(canonical({**recipe, "sources": [
        source for source in recipe["sources"]
        if source["id"] != recipe["roles"]["attestation"]
    ]}))


def strict_json(data, ref):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, f"{ref}: duplicate JSON key {key}")
            result[key] = value
        return result

    def bad_number(value):
        raise SourceContractError(f"{ref}: use Decimal strings, not {value}")

    try:
        return json.loads(data.decode("utf-8"), object_pairs_hook=pairs,
                          parse_float=bad_number, parse_constant=bad_number)
    except (UnicodeError, ValueError) as error:
        raise SourceContractError(f"{ref}: invalid UTF-8/JSON: {error}") from error


def read_pinned(path, expected):
    require(type(expected) is str and re.fullmatch(r"[0-9a-f]{64}", expected),
            f"{path}: full lowercase SHA-256 required")
    path = Path(path)
    require(path.is_absolute(), f"{path}: an absolute resolved source ref is required")
    try:
        data = path.read_bytes()
    except OSError as error:
        raise SourceContractError(f"source unreadable: {path}: {error}") from error
    actual = sha256(data)
    require(actual == expected, f"source hash mismatch: {path}: expected={expected} actual={actual}")
    return data


def execution_identity():
    """Actual checkout and conversion runtime, never a caller code_sha override."""
    repo = Path(__file__).resolve().parents[3]
    try:
        sha = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                             check=True, capture_output=True, text=True, timeout=10).stdout.strip()
        dirty = bool(subprocess.run(
            ["git", "-C", str(repo), "status", "--porcelain", "--untracked-files=all"],
            check=True, capture_output=True, text=True, timeout=10,
        ).stdout)
    except (OSError, subprocess.SubprocessError) as error:
        raise SourceContractError(f"cannot pin loader implementation: {error}") from error
    require(re.fullmatch(r"[0-9a-f]{40}", sha), "loader code SHA is unknown")
    paths = [Path(__file__).parent / (name + ".py") for name in (
        "source_loader", "source_provenance", "input_codec", "artifacts", "runner",
        "types", "clock", "broker", "match", "ledger", "fees",
    )]
    paths += [repo / "common/infra/data_root.py", repo / "oskh_data/symbol_format.py"]
    return {"code_sha": sha, "code_dirty": dirty, "code_sha_source": "git_head",
            "python_executable": sys.executable, "python_version": sys.version,
            "pyarrow_version": version("pyarrow"),
            "code_files": {str(p.relative_to(repo)): sha256(p.read_bytes()) for p in paths}}


@dataclass(frozen=True)
class SourceProvenance:
    """Immutable canonical document; its hash alone is never accepted as proof."""

    payload: bytes
    sha256: str

    def document(self):
        require(type(self.payload) is bytes and sha256(self.payload) == self.sha256,
                "provenance hash mismatch")
        result = strict_json(self.payload, "source provenance")
        object_fields(result, (
            "schema_version", "evidence_version", "unit", "source_kind", "notice",
            "recipe", "resolver", "snapshots", "attestation", "transform",
            "execution", "binding", "source_checks_at_load",
        ), "source provenance")
        require(result["schema_version"] == PROVENANCE_VERSION
                and result["evidence_version"] == EVIDENCE_VERSION
                and result["unit"] == "B-L2-01", "unsupported source provenance version/unit")
        require(result["source_kind"] in ("lake", "synthetic_fixture"), "unknown source kind")
        require(canonical(result) == self.payload, "provenance must have canonical encoding")
        return result


def input_binding(run):
    # Use exactly S4's canonicalization, including its historical null omission.
    from .artifacts import _canonical, _contract, _hash, _value

    data = _value(run)
    return {"input_hash": _hash(_canonical(data)),
            "contract_hash": _hash(_canonical(_contract(run))),
            "components": {k: _hash(_canonical(v)) for k, v in data.items()}}


def source_checks(provenance):
    """Observe every source even after a mismatch; retain both identities."""
    doc = provenance.document()
    observations = []
    for source in [doc["recipe"], *doc["snapshots"]]:
        row = {"ref": source["ref"], "before_sha256": source["sha256"]}
        try:
            row["after_sha256"] = sha256(Path(source["ref"]).read_bytes())
            row["unchanged"] = row["after_sha256"] == row["before_sha256"]
        except OSError as error:
            row.update(unchanged=False, error=str(error))
        observations.append(row)
    return observations


def require_unchanged(checks):
    require(all(row["unchanged"] for row in checks),
            "source snapshot changed or disappeared: " + json.dumps(
                [row for row in checks if not row["unchanged"]], ensure_ascii=False))


def validate_source_provenance(run, provenance, *, parent, run_id, code_sha=None):
    """Re-map pinned sources to reject forged/edited provenance and stale input.

    Called only for explicit hybrid evidence, before execution and by S4 after
    execution. Re-reading is intentional: there is no unverified derived cache.
    """
    require(type(provenance) is SourceProvenance, "hybrid requires loader SourceProvenance")
    require(code_sha is None, "hybrid rejects caller code_sha overrides")
    doc = provenance.document()
    require(doc["binding"] == input_binding(run), "provenance/input binding mismatch")
    require(doc["recipe"]["run_id"] == run_id
            and doc["recipe"]["parent"] == str(Path(parent).resolve()),
            "provenance run_id/parent mismatch")
    require_unchanged(source_checks(provenance))
    from .source_loader import load_minute_orders_source

    rebuilt = load_minute_orders_source(doc["recipe"]["ref"],
                                        expected_sha256=doc["recipe"]["sha256"])
    require(rebuilt.provenance == provenance,
            "provenance replay mismatch: source mapping/resolver/implementation changed")
    require(input_binding(rebuilt.run_input) == input_binding(run), "source replay/input mismatch")
    return doc
