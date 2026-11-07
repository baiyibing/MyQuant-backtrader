"""Synthetic export/validate coverage for CNINFO economic-date targets. No network."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from oskh_data.cninfo_economic_date_targets import (
    TargetPackageError,
    export_cninfo_economic_date_targets,
    validate_cninfo_economic_date_evidence,
)

PDF = b"%PDF-1.4\n%fixture\n"
TEXT = "股权登记日明确。\n".encode("utf-8")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _inputs(tmp: Path) -> dict[str, Path]:
    assembled = {
        "events": [
            {
                "bonus_list_date": None,
                "bonus_ratio": None,
                "cash_div_per_share": "0.5",
                "code": "600519.SH",
                "event_id": "e1",
                "ex_date": "2026-10-15",
                "pay_date": None,
                "record_date": None,
                "transfer_list_date": None,
                "transfer_ratio": None,
            },
            {
                "bonus_ratio": None,
                "cash_div_per_share": "0.2",
                "code": "600000.SH",
                "event_id": "outside",
                "ex_date": "2026-09-01",
            },
        ]
    }
    assembled_path = tmp / "assembled.json"
    _write(assembled_path, json.dumps(assembled, ensure_ascii=False) + "\n")
    universe = tmp / "universe.txt"
    _write(universe, "600519.SH\n600000.SH\n000001.SZ\n")
    d11 = tmp / "d11.txt"
    _write(d11, "000001.SZ\n")
    return {"assembled": assembled_path, "universe": universe, "d11": d11}


def _export(tmp: Path) -> tuple[dict[str, Path], bytes]:
    paths = _inputs(tmp)
    before = paths["assembled"].read_bytes()
    out = tmp / "targets.json"
    export_cninfo_economic_date_targets(
        assembled_events=paths["assembled"],
        universe=paths["universe"],
        d11_codes=paths["d11"],
        window_start=date(2026, 10, 7),
        window_end=date(2026, 10, 28),
        out=out,
        run_hash="run-frozen",
    )
    paths["targets"] = out
    return paths, before


def _field(pdf_sha: str, text_sha: str, *, value: str | None, status: str) -> dict:
    return {
        "announcement_id": "1225",
        "extracted_pages": 1,
        "inferred": False,
        "pdf_relpath": "codes/600519.SH/pdf/1225.pdf",
        "pdf_sha256": pdf_sha,
        "source_kind": "explicit_announcement",
        "status": status,
        "text_relpath": "codes/600519.SH/text/1225.txt",
        "text_sha256": text_sha,
        "total_pages": 1,
        "url": "https://static.cninfo.com.cn/finalpage/2026-10-15/1225.PDF",
        "value": value,
    }


def _evidence(tmp: Path, targets: Path) -> Path:
    root = tmp / "evidence"
    pdf = root / "codes" / "600519.SH" / "pdf" / "1225.pdf"
    text = root / "codes" / "600519.SH" / "text" / "1225.txt"
    pdf.parent.mkdir(parents=True)
    text.parent.mkdir(parents=True)
    pdf.write_bytes(PDF)
    text.write_bytes(TEXT)
    pdf_sha, text_sha = _sha(pdf), _sha(text)
    fields = {
        "pay_date": _field(pdf_sha, text_sha, value="2026-10-16", status="explicit"),
        "record_date": _field(pdf_sha, text_sha, value="2026-10-14", status="explicit"),
        "bonus_list_date": _field(pdf_sha, text_sha, value=None, status="missing"),
        "transfer_list_date": _field(pdf_sha, text_sha, value=None, status="missing"),
        "bonus_ratio": _field(pdf_sha, text_sha, value=None, status="explicit_absence"),
        "cash_div_per_share": _field(pdf_sha, text_sha, value="0.5", status="explicit"),
        "transfer_ratio": _field(pdf_sha, text_sha, value=None, status="missing"),
    }
    files = []
    for path in (pdf, text):
        rel = path.relative_to(root).as_posix()
        files.append({"relpath": rel, "sha256": _sha(path)})
    manifest = {
        "files": sorted(files, key=lambda item: item["relpath"]),
        "format_version": 1,
        "kind": "cninfo_economic_date_evidence",
        "lake_write_authorized": False,
        "matches": [
            {
                "code": "600519.SH",
                "event_id": "e1",
                "ex_date": "2026-10-15",
                "fields": fields,
                "hithink_amounts": {
                    "bonus_ratio": None,
                    "cash_div_per_share": "0.5",
                    "transfer_ratio": None,
                },
                "reasons": [],
                "verdict": "machine_matched",
            }
        ],
        "owner_signature": "",
        "target_sha256": _sha(targets),
    }
    manifest_path = root / "manifest.json"
    _write(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    committed = {
        "format_version": 1,
        "kind": "cninfo_economic_date_evidence_commit",
        "lake_write_authorized": False,
        "manifest_sha256": _sha(manifest_path),
        "owner_signature": "",
        "status": "complete",
        "target_sha256": _sha(targets),
    }
    _write(
        root / "COMMITTED.json",
        json.dumps(committed, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    return root


def test_export_binds_hashes_and_keeps_d11_without_event_rows(tmp_path: Path):
    paths, before = _export(tmp_path)
    document = json.loads(paths["targets"].read_text(encoding="utf-8"))
    assert document["owner_signature"] == ""
    assert document["lake_write_authorized"] is False
    assert document["assembled_events_sha256"] == _sha(paths["assembled"])
    assert document["universe_sha256"] == _sha(paths["universe"])
    assert document["run_hash"] == "run-frozen"
    codes = {event["code"] for event in document["events"]}
    assert "000001.SZ" not in codes
    d11 = next(item for item in document["query_targets"] if item["code"] == "000001.SZ")
    assert d11 == {"code": "000001.SZ", "has_event_row": False, "reason": "D11"}
    outside = next(event for event in document["events"] if event["event_id"] == "outside")
    assert outside["outside_window"] is True
    assert outside["bonus_ratio"] is None
    assert paths["assembled"].read_bytes() == before
    with pytest.raises(TargetPackageError, match="refuse overwrite"):
        export_cninfo_economic_date_targets(
            assembled_events=paths["assembled"],
            universe=paths["universe"],
            window_start=date(2026, 10, 7),
            window_end=date(2026, 10, 28),
            out=paths["targets"],
        )


def test_export_reads_parquet_events(tmp_path: Path):
    table = pa.table(
        {
            "bonus_list_date": pa.array([None], type=pa.string()),
            "bonus_ratio": pa.array([None], type=pa.string()),
            "cash_div_per_share": ["1.25"],
            "code": ["600519.SH"],
            "event_id": ["pq1"],
            "ex_date": ["2026-10-15"],
            "pay_date": pa.array([None], type=pa.string()),
            "record_date": pa.array([None], type=pa.string()),
            "transfer_list_date": pa.array([None], type=pa.string()),
            "transfer_ratio": pa.array([None], type=pa.string()),
        }
    )
    events = tmp_path / "events.parquet"
    pq.write_table(table, events)
    universe = tmp_path / "universe.txt"
    _write(universe, "600519.SH\n")
    out = tmp_path / "targets.json"
    document = export_cninfo_economic_date_targets(
        assembled_events=events,
        universe=universe,
        window_start=date(2026, 10, 1),
        window_end=date(2026, 10, 31),
        out=out,
    )
    assert document["events"][0]["cash_div_per_share"] == "1.25"
    assert document["events"][0]["record_date"] is None
    assert document["assembled_events_sha256"] == _sha(events)


def test_validate_writes_suggestions_without_touching_events(tmp_path: Path):
    paths, before = _export(tmp_path)
    evidence = _evidence(tmp_path, paths["targets"])
    out = tmp_path / "suggestions.json"
    report = validate_cninfo_economic_date_evidence(
        evidence_dir=evidence,
        targets=paths["targets"],
        assembled_events=paths["assembled"],
        universe=paths["universe"],
        out=out,
    )
    assert report["owner_signature"] == ""
    assert report["economic_approval"] is False
    assert report["lake_write_authorized"] is False
    suggestion = report["suggestions"][0]
    record = suggestion["dates"]["record_date"]
    assert record["explicit_announcement_date"] == "2026-10-14"
    assert record["compatibility_policy_date"] is None
    assert record["backtest_adopted_value"] is None
    listing = suggestion["dates"]["bonus_list_date"]
    assert listing["explicit_announcement_date"] is None
    assert listing["compatibility_policy_date"] is None
    assert any(
        item["reason"] == "D11_no_event_row" and item["code"] == "000001.SZ"
        for item in report["unresolved"]
    )
    assert paths["assembled"].read_bytes() == before
    assert report["field_sources"]
    with pytest.raises(TargetPackageError, match="refuse overwrite"):
        validate_cninfo_economic_date_evidence(
            evidence_dir=evidence,
            targets=paths["targets"],
            assembled_events=paths["assembled"],
            universe=paths["universe"],
            out=out,
        )


def test_validate_rejects_traversal_hash_commit_and_tamper(tmp_path: Path):
    paths, before = _export(tmp_path)
    evidence = _evidence(tmp_path, paths["targets"])
    manifest_path = evidence / "manifest.json"
    committed_path = evidence / "COMMITTED.json"

    def _retarget(mutate) -> None:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        mutate(manifest)
        _write(
            manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        )
        committed = json.loads(committed_path.read_text(encoding="utf-8"))
        committed["manifest_sha256"] = _sha(manifest_path)
        _write(
            committed_path,
            json.dumps(committed, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        )

    _retarget(
        lambda manifest: manifest["files"].__setitem__(
            0, {"relpath": "../outside.txt", "sha256": "abc"}
        )
    )
    with pytest.raises(TargetPackageError, match="path traversal"):
        validate_cninfo_economic_date_evidence(
            evidence_dir=evidence,
            targets=paths["targets"],
            assembled_events=paths["assembled"],
            universe=paths["universe"],
            out=tmp_path / "bad-path.json",
        )

    evidence = _evidence(tmp_path / "hash", paths["targets"])
    pdf = next(evidence.rglob("*.pdf"))
    pdf.write_bytes(pdf.read_bytes() + b"x")
    with pytest.raises(TargetPackageError, match="hash mismatch"):
        validate_cninfo_economic_date_evidence(
            evidence_dir=evidence,
            targets=paths["targets"],
            assembled_events=paths["assembled"],
            universe=paths["universe"],
            out=tmp_path / "bad-hash.json",
        )

    evidence = _evidence(tmp_path / "commit", paths["targets"])
    (evidence / "COMMITTED.json").unlink()
    with pytest.raises(TargetPackageError, match="missing COMMITTED"):
        validate_cninfo_economic_date_evidence(
            evidence_dir=evidence,
            targets=paths["targets"],
            assembled_events=paths["assembled"],
            universe=paths["universe"],
            out=tmp_path / "bad-commit.json",
        )

    evidence = _evidence(tmp_path / "tamper", paths["targets"])
    manifest_path = evidence / "manifest.json"
    committed_path = evidence / "COMMITTED.json"

    def _tamper(manifest: dict) -> None:
        manifest["matches"][0]["fields"]["record_date"]["pdf_sha256"] = "0" * 64

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    _tamper(manifest)
    _write(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    committed = json.loads(committed_path.read_text(encoding="utf-8"))
    committed["manifest_sha256"] = _sha(manifest_path)
    _write(
        committed_path, json.dumps(committed, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )
    with pytest.raises(TargetPackageError, match="tampered field source"):
        validate_cninfo_economic_date_evidence(
            evidence_dir=evidence,
            targets=paths["targets"],
            assembled_events=paths["assembled"],
            universe=paths["universe"],
            out=tmp_path / "bad-field.json",
        )
    assert paths["assembled"].read_bytes() == before


def test_validate_rejects_inferred_listing_equals_ex(tmp_path: Path):
    paths, _before = _export(tmp_path)
    evidence = _evidence(tmp_path, paths["targets"])
    manifest_path = evidence / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    listing = manifest["matches"][0]["fields"]["bonus_list_date"]
    listing["status"] = "explicit"
    listing["value"] = "2026-10-15"
    listing["inferred"] = True
    listing["source_kind"] = "compatibility_listing_equals_ex"
    _write(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    committed = json.loads((evidence / "COMMITTED.json").read_text(encoding="utf-8"))
    committed["manifest_sha256"] = _sha(manifest_path)
    _write(
        evidence / "COMMITTED.json",
        json.dumps(committed, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    with pytest.raises(TargetPackageError, match="inferred listing=ex"):
        validate_cninfo_economic_date_evidence(
            evidence_dir=evidence,
            targets=paths["targets"],
            assembled_events=paths["assembled"],
            universe=paths["universe"],
            out=tmp_path / "bad-infer.json",
        )
