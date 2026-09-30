"""Hybrid evidence schema and refusal paths, exclusively synthetic fixtures."""

import json
from dataclasses import replace
from pathlib import Path

import pytest
from backtest.research.minute_orders_backend import artifacts, runner
from backtest.research.minute_orders_backend.input_codec import dumps_run_input, loads_run_input
from backtest.research.minute_orders_backend.source_provenance import (
    FIXTURE_NOTICE,
    SourceContractError,
    SourceProvenance,
    canonical,
    input_binding,
    sha256,
)

from tests.test_minute_orders_source_loader import SyntheticCase


@pytest.fixture
def source_case(tmp_path, monkeypatch):
    return SyntheticCase(tmp_path, monkeypatch)


def write(case, loaded=None, **changes):
    loaded = loaded or case.load()
    options = {"run_id": case.recipe["run_id"], "evidence_level": "hybrid", "source_provenance": loaded.provenance}
    options.update(changes)
    return runner.run_minute_orders_research_with_artifacts(loaded.run_input, case.recipe["parent"], **options)


def read(root, name):
    return json.loads((root / name).read_bytes())


def check_refs(root):
    manifest = read(root, "manifest.json")
    assert manifest["comparison_status"] == "no_ssot_compare_authorization"
    for ref in manifest["artifacts"]:
        assert sha256((root / ref["path"]).read_bytes()) == ref["sha256"]
    assert {r["path"] for r in manifest["artifacts"]} == {
        p.name for p in root.iterdir() if not p.name.startswith(".") and p.name != "manifest.json"
    }
    return manifest


def test_hybrid_writer_binds_sources_input_and_artifacts_with_truthful_fixture_identity(source_case, monkeypatch):
    loaded = source_case.load()
    published = []
    original = artifacts._publish

    def publish(root, name, data):
        published.append(name)
        if name == "summary.json":
            assert (root / "source_postflight.json").exists()
        original(root, name, data)

    monkeypatch.setattr(artifacts, "_publish", publish)
    result = write(source_case, loaded)
    assert result.status == "success" and published[-1] == "summary.json"
    manifest = check_refs(result.root)
    assert manifest["schema_version"] == "minute_orders_artifacts_v2"
    assert manifest["evidence_schema_version"] == "minute_orders_hybrid_evidence_v1"
    assert manifest["source_kind"] == "synthetic_fixture"
    assert manifest["source_components"] == {"market": "synthetic_fixture", "commands": "synthetic", "account": "synthetic"}
    assert manifest["evidence_notice"] == FIXTURE_NOTICE
    assert manifest["source_provenance_hash"] == loaded.provenance.sha256
    assert read(result.root, "source_provenance.json")["binding"] == input_binding(loaded.run_input)
    assert manifest["input_hash"] == loaded.provenance.document()["binding"]["input_hash"]
    assert manifest["contract_hash"] == loaded.provenance.document()["binding"]["contract_hash"]
    assert manifest["held_mark_coverage"] == "covered"
    assert manifest["live_acceptance_status"] == "not_assessed"
    assert manifest["host_attestation_status"] == "not_certified_by_writer"
    assert all(row["unchanged"] for row in read(result.root, "source_postflight.json"))
    # Independent hand calculation: 200 + 100 shares, one 5.00 minimum fee.
    summary = read(result.root, "summary.json")
    assert summary["filled_qty"] == 300 and summary["fees_paid"] == "5.00"
    with pytest.raises(FileExistsError):
        write(source_case, loaded)


@pytest.mark.parametrize("roundtrip", [False, True])
def test_loaded_input_cannot_be_labeled_synthetic_even_after_v1_codec(source_case, roundtrip):
    loaded = source_case.load()
    run = loads_run_input(dumps_run_input(loaded.run_input)) if roundtrip else loaded.run_input
    with pytest.raises(ValueError, match="cannot label it synthetic"):
        runner.run_minute_orders_research_with_artifacts(run, source_case.recipe["parent"],
                                                       run_id="wrong", evidence_level="synthetic")
    assert not Path(source_case.recipe["parent"]).exists()


@pytest.mark.parametrize("level", ["lake", "real", "hybrid"])
def test_no_new_evidence_level_passes_without_provenance(source_case, level):
    run = source_case.load().run_input
    with pytest.raises(ValueError, match="provenance"):
        runner.run_minute_orders_research_with_artifacts(run, source_case.recipe["parent"], run_id="wrong", evidence_level=level)


@pytest.mark.parametrize("case", ["hash", "binding", "forged_mapping", "notice", "schema", "run_id", "override"])
def test_evidence_rejects_tampering_and_archives_failure_before_execution(source_case, monkeypatch, case):
    loaded = source_case.load()
    provenance, run = loaded.provenance, loaded.run_input
    doc = provenance.document()
    options = {}
    if case == "hash":
        provenance = replace(provenance, sha256="0" * 64)
    elif case in ("binding", "forged_mapping"):
        run = replace(run, initial_cash=run.initial_cash + 1)
        if case == "forged_mapping":
            doc["binding"] = input_binding(run)
    elif case == "notice":
        doc["notice"] = "lake PASS"
    elif case == "schema":
        doc["schema_version"] = "invented"
    elif case == "run_id":
        options["run_id"] = "other"
    else:
        options["code_sha"] = "a" * 40
    if case not in ("hash", "binding"):
        provenance = SourceProvenance(canonical(doc), sha256(canonical(doc)))
    loaded = replace(loaded, run_input=run, provenance=provenance)

    def no_engine(*args, **kwargs):
        pytest.fail("invalid provenance must stop before engine execution")

    monkeypatch.setattr(runner._ObservedBroker, "run", no_engine)
    with pytest.raises(artifacts.ArtifactWriteError) as failed:
        write(source_case, loaded, **options)
    root = failed.value.root
    assert not (root / "summary.json").exists()
    assert read(root, "failure.json")["stage"] == "source_provenance"
    assert check_refs(root)["status"] == "failed"


@pytest.mark.parametrize("when", ["before", "during", "writer"])
def test_snapshot_changes_retain_before_after_hashes_and_never_publish_summary(source_case, monkeypatch, when):
    loaded = source_case.load()
    original = source_case.bar_path.read_bytes()

    def mutate():
        source_case.bar_path.write_bytes(original + b"fixture mutation")

    if when == "before":
        mutate()
    elif when == "during":
        run = runner._ObservedBroker.run

        def changed(self):
            result = run(self)
            mutate()
            return result

        monkeypatch.setattr(runner._ObservedBroker, "run", changed)
    else:
        original_write = artifacts._write_file

        def changed(root, name, data):
            original_write(root, name, data)
            if name == "marks.jsonl":
                mutate()

        monkeypatch.setattr(artifacts, "_write_file", changed)
    with pytest.raises(artifacts.ArtifactWriteError) as failed:
        write(source_case, loaded)
    root = failed.value.root
    assert not (root / "summary.json").exists()
    name = "source_postflight.json" if when == "writer" else "source_checks.json"
    changed = [r for r in read(root, name) if not r["unchanged"]]
    assert len(changed) == 1
    assert changed[0]["before_sha256"] == sha256(original)
    assert changed[0]["after_sha256"] == sha256(original + b"fixture mutation")
    assert check_refs(root)["status"] == "failed"


def test_engine_failure_preserves_hybrid_provenance_and_partial_trace(source_case, monkeypatch):
    original = runner._ObservedBroker._mark

    def failure(self, event):
        if event.payload.mark_id == "final":
            raise RuntimeError("synthetic engine failure after earlier mark")
        original(self, event)

    monkeypatch.setattr(runner._ObservedBroker, "_mark", failure)
    result = write(source_case)
    assert result.status == "failed"
    manifest = check_refs(result.root)
    assert manifest["evidence_level"] == "hybrid"
    assert (result.root / "source_provenance.json").exists()
    assert not (result.root / "summary.json").exists()
    assert "synthetic engine failure" in read(result.root, "failure.json")["reason"]


def test_empty_positions_report_uncovered_mark_acceptance(source_case):
    source_case.sidecars["account"]["initial_cash"] = "0.00"
    source_case.freeze()
    result = write(source_case)
    assert result.status == "success"  # Valid business rejection, not a lake acceptance result.
    assert check_refs(result.root)["held_mark_coverage"] == "not_covered"


def test_lake_claim_requires_clean_code_and_matching_attestation(source_case, monkeypatch):
    # Still only fabricated files. Exercise the refusal, never emit lake evidence.
    source_case.recipe["source_kind"] = "lake"
    source_case.freeze()
    with pytest.raises(SourceContractError, match="source kind mismatch"):
        source_case.load()
    source_case.sidecars["attestation"]["source_kind"] = "lake"
    source_case.freeze()
    from backtest.research.minute_orders_backend import source_loader
    original = source_loader.execution_identity

    def dirty():
        return dict(original(), code_dirty=True)

    monkeypatch.setattr(source_loader, "execution_identity", dirty)
    with pytest.raises(SourceContractError, match="clean pinned implementation"):
        source_case.load()


def test_legacy_synthetic_bytes_match_pinned_pre_loader_writer(tmp_path):
    # Obtained by executing S4 artifacts.py from the requested 58b6355 base,
    # with that same unchanged test request and observed trace. Never re-record
    # from the new writer to make a failure disappear.
    from tests.test_minute_orders_artifacts import request

    baseline = {
        "commands.jsonl": "1100207767d7a79cdde600fd25a9d93d3b9ea6f8f76eb20d2b4760d9ff3b4d09",
        "contract.json": "dada9c08e2e8c0280329e5503109124e3c3c9bc385c251e0c7f3faa85dfa1c2c",
        "fills.jsonl": "f5292750ad0d0df846e3cdc1b9965cb89c164fc811f07ca1729423b1233d07c6",
        "inputs.json": "e2788ad30773e6d37e4a31720e2e6fea5051e91d07c26b08b894fe0db2f08dcd",
        "ledger.jsonl": "632dfc5c0f6bc9303de7652b333d7dc53d190280a0d24183bc37fc3979593c62",
        "manifest.json": "8e88269a09f5dd176db9ae18e4ddad43854c8dcb64128a7e88873c8ad8590b31",
        "marks.jsonl": "7f32f3563c3801f7dd573e613960862c78fb00138c09e2228761d8707305d354",
        "orders.jsonl": "8f514598e86c11dd15516a3bc7038cc5c05f0c056c3ee32f339da5f172bad053",
        "summary.json": "c17782b694eb72a634b32a114029d8cee24264d2b3bbd179e3e413150674e91a",
    }
    result = runner.run_minute_orders_research_with_artifacts(
        request(), tmp_path, run_id="synthetic-byte-compat", evidence_level="synthetic",
        code_sha="58b63554efeafcd4bcd53c8ed2ecb00141fbaca9",
    )
    assert {p.name: sha256(p.read_bytes()) for p in result.root.iterdir()} == baseline
