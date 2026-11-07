"""Read-only CNINFO economic-date targets and offline evidence checks.

The export binds frozen inputs. It does not authorize a lake merge, a source
switch, or economic approval. ``owner_signature`` stays empty.

Suggestions distinguish an explicit announcement date from a compatibility
listing=ex policy date and from a backtest-adopted value. This slice never
emits listing=ex as an explicit source date.

Do not import the deleted processing modules (``hithink_incremental``,
``pull_corp_actions_incremental``, ``hithink_artifact``, ``corp_actions_econ_gate``).
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping

from oskh_data.symbol_format import is_canonical_symbol

FORMAT_VERSION = 1
TARGETS_KIND = "cninfo_economic_date_targets"
EVIDENCE_KIND = "cninfo_economic_date_evidence"
COMMIT_KIND = "cninfo_economic_date_evidence_commit"
SUGGESTION_KIND = "cninfo_economic_date_suggestions"
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DATE_FIELDS = (
    "record_date",
    "pay_date",
    "bonus_list_date",
    "transfer_list_date",
)
_AMOUNT_FIELDS = ("cash_div_per_share", "bonus_ratio", "transfer_ratio")
_EVENT_DATES = ("ex_date", *_DATE_FIELDS)
_VERDICTS = {
    "machine_matched",
    "basis_review",
    "amount_mismatch",
    "share_distribution_mismatch",
    "multiple_announcements",
    "revision_ambiguity",
    "after_as_of",
    "incomplete_parse",
    "unsupported",
    "unresolved",
}


class TargetPackageError(ValueError):
    """Fail-closed export or validation error."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _dumps(document: Mapping[str, Any]) -> str:
    return json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _write_new(path: Path, text: str) -> None:
    if path.exists():
        raise TargetPackageError(f"refuse overwrite: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    tmp.replace(path)


def _date_text(value: Any, *, required: bool) -> str | None:
    if value is None or value == "":
        if required:
            raise TargetPackageError("ISO date required")
        return None
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str) and _ISO_DATE.fullmatch(value):
        date.fromisoformat(value)
        return value
    raise TargetPackageError("ISO date required")


def _amount_text(value: Any) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise TargetPackageError("amount must not be bool")
    if isinstance(value, str):
        try:
            number = Decimal(value)
        except InvalidOperation as exc:
            raise TargetPackageError("amount must be decimal") from exc
        if not number.is_finite():
            raise TargetPackageError("amount must be finite")
        return value
    if isinstance(value, (int, Decimal)):
        number = Decimal(value)
        if not number.is_finite():
            raise TargetPackageError("amount must be finite")
        return format(number, "f")
    if isinstance(value, float):
        number = Decimal(str(value))
        if not number.is_finite():
            raise TargetPackageError("amount must be finite")
        return format(number, "f")
    raise TargetPackageError("amount must be numeric or a decimal string")


def _codes_from_json(data: Any) -> list[str]:
    if isinstance(data, dict):
        data = data.get("codes", data.get("universe"))
    if not isinstance(data, list):
        raise TargetPackageError("code list must be JSON list or {codes: [...]}")
    return [str(item) for item in data]


def read_codes(path: Path) -> list[str]:
    """Read a frozen code list from text, JSON, or a parquet ``code`` column."""
    suffix = path.suffix.lower()
    if suffix == ".parquet":
        import pyarrow.parquet as pq

        table = pq.ParquetFile(path).read(columns=["code"])
        values = [str(item) for item in table.column("code").to_pylist() if item]
    elif suffix == ".json":
        values = _codes_from_json(json.loads(path.read_text(encoding="utf-8")))
    else:
        values = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]
        values = [item for item in values if item and not item.startswith("#")]
    codes = []
    for item in values:
        if not is_canonical_symbol(item):
            raise TargetPackageError(f"canonical code required: {item}")
        codes.append(item)
    if len(codes) != len(set(codes)):
        raise TargetPackageError("duplicate code")
    return codes


def _rows_from_parquet(path: Path) -> list[dict[str, Any]]:
    import pyarrow.parquet as pq

    return pq.ParquetFile(path).read().to_pylist()


def read_events(path: Path) -> list[dict[str, Any]]:
    """Read frozen assembled events. JSON object/list or parquet. Never written back."""
    suffix = path.suffix.lower()
    if suffix == ".parquet":
        rows = _rows_from_parquet(path)
    else:
        data = json.loads(path.read_text(encoding="utf-8"))
        rows = data["events"] if isinstance(data, dict) else data
    if not isinstance(rows, list):
        raise TargetPackageError("assembled events must be a list")
    return [dict(row) for row in rows]


def _normalize_event(
    row: Mapping[str, Any], *, window_start: date, window_end: date
) -> dict[str, Any]:
    code = str(row.get("code") or "")
    if not is_canonical_symbol(code):
        raise TargetPackageError(f"canonical code required: {code}")
    event_id = str(row.get("event_id") or "")
    if not event_id:
        raise TargetPackageError("event_id required")
    ex_date = _date_text(row.get("ex_date"), required=True)
    assert ex_date is not None
    event = {
        "bonus_list_date": _date_text(row.get("bonus_list_date"), required=False),
        "bonus_ratio": _amount_text(row.get("bonus_ratio")),
        "cash_div_per_share": _amount_text(row.get("cash_div_per_share")),
        "code": code,
        "event_id": event_id,
        "ex_date": ex_date,
        "outside_window": not (window_start.isoformat() <= ex_date <= window_end.isoformat()),
        "pay_date": _date_text(row.get("pay_date"), required=False),
        "record_date": _date_text(row.get("record_date"), required=False),
        "transfer_list_date": _date_text(row.get("transfer_list_date"), required=False),
        "transfer_ratio": _amount_text(row.get("transfer_ratio")),
    }
    return event


def export_cninfo_economic_date_targets(
    *,
    assembled_events: Path,
    universe: Path,
    out: Path,
    window_start: date,
    window_end: date,
    d11_codes: Path | None = None,
    run_manifest: Path | None = None,
    run_hash: str | None = None,
) -> dict[str, Any]:
    """Export query targets. D11 codes are included without fabricated event rows."""
    if window_start > window_end:
        raise TargetPackageError("window start is after window end")
    if out.exists():
        raise TargetPackageError(f"refuse overwrite: {out}")
    assembled_events = Path(assembled_events)
    universe = Path(universe)
    assembled_hash = _sha256(assembled_events)
    universe_hash = _sha256(universe)
    universe_codes = set(read_codes(universe))
    events = [
        _normalize_event(row, window_start=window_start, window_end=window_end)
        for row in read_events(assembled_events)
    ]
    seen_ids: set[str] = set()
    for event in events:
        if event["event_id"] in seen_ids:
            raise TargetPackageError(f"duplicate event_id: {event['event_id']}")
        seen_ids.add(event["event_id"])
        if event["code"] not in universe_codes:
            raise TargetPackageError(f"event code is outside the universe: {event['code']}")
    d11 = read_codes(d11_codes) if d11_codes is not None else []
    event_codes = {event["code"] for event in events}
    for code in d11:
        if code not in universe_codes:
            raise TargetPackageError(f"D11 code is outside the universe: {code}")
        if code in event_codes:
            raise TargetPackageError(f"D11 code already has an event row: {code}")
    queries = [
        {"code": code, "has_event_row": True, "reason": "cash_event"}
        for code in sorted(event_codes)
    ]
    queries.extend({"code": code, "has_event_row": False, "reason": "D11"} for code in d11)
    queries.sort(key=lambda item: item["code"])
    if not queries:
        raise TargetPackageError("at least one query target is required")
    document = {
        "assembled_events_sha256": assembled_hash,
        "economic_approval": False,
        "events": sorted(
            events, key=lambda item: (item["code"], item["ex_date"], item["event_id"])
        ),
        "format_version": FORMAT_VERSION,
        "kind": TARGETS_KIND,
        "lake_write_authorized": False,
        "notes": [
            "This export is not lake-merge authorization.",
            "D11 codes are query targets and do not gain fabricated event rows.",
            "Empty share legs are preserved as null, not economic zero.",
        ],
        "owner_signature": "",
        "query_targets": queries,
        "run_hash": run_hash,
        "run_manifest_sha256": _sha256(run_manifest) if run_manifest is not None else None,
        "universe_sha256": universe_hash,
        "window": {"end": window_end.isoformat(), "start": window_start.isoformat()},
    }
    if _sha256(assembled_events) != assembled_hash or _sha256(universe) != universe_hash:
        raise TargetPackageError("frozen input changed while exporting")
    _write_new(out, _dumps(document))
    return document


def _safe_rel(root: Path, rel: str) -> Path:
    if (
        not isinstance(rel, str)
        or rel == ""
        or rel.startswith(("/", "\\"))
        or "\\" in rel
        or ":" in rel
    ):
        raise TargetPackageError(f"path traversal: {rel}")
    parts = rel.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise TargetPackageError(f"path traversal: {rel}")
    resolved_root = root.resolve()
    candidate = resolved_root.joinpath(*parts).resolve(strict=False)
    if not candidate.is_relative_to(resolved_root):
        raise TargetPackageError(f"path traversal: {rel}")
    return candidate


def _check_field(evidence: Path, name: str, field: Mapping[str, Any]) -> None:
    if (
        field.get("inferred") is True
        or field.get("source_kind") == "compatibility_listing_equals_ex"
    ):
        raise TargetPackageError("inferred listing=ex is not an explicit source date")
    status = field.get("status")
    if status not in {"explicit", "missing", "explicit_absence"}:
        raise TargetPackageError(f"field status is invalid: {name}")
    if field.get("source_kind") not in {"explicit_announcement", "missing"}:
        raise TargetPackageError(f"field source_kind is invalid: {name}")
    value = field.get("value")
    if status == "explicit":
        if not isinstance(value, str) or value == "":
            raise TargetPackageError(f"explicit field needs a value: {name}")
        if name in _DATE_FIELDS or name == "ex_date":
            _date_text(value, required=True)
        elif name in _AMOUNT_FIELDS:
            _amount_text(value)
    elif value is not None:
        raise TargetPackageError("empty share or date must not become economic zero")
    for digest_key, rel_key in (("pdf_sha256", "pdf_relpath"), ("text_sha256", "text_relpath")):
        digest = field.get(digest_key)
        rel = field.get(rel_key)
        if digest is None and rel is None:
            continue
        if not isinstance(digest, str) or not isinstance(rel, str):
            raise TargetPackageError(f"tampered field source: {name}")
        path = _safe_rel(evidence, rel)
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise TargetPackageError(f"tampered field source: {name}")


def _date_slot(field: Mapping[str, Any] | None) -> dict[str, Any]:
    explicit = None
    if field and field.get("status") == "explicit":
        explicit = field.get("value")
    return {
        "backtest_adopted_value": None,
        "compatibility_policy_date": None,
        "explicit_announcement_date": explicit,
        "source": None
        if field is None
        else {
            "announcement_id": field.get("announcement_id"),
            "extracted_pages": field.get("extracted_pages"),
            "pdf_sha256": field.get("pdf_sha256"),
            "status": field.get("status"),
            "text_sha256": field.get("text_sha256"),
            "total_pages": field.get("total_pages"),
            "url": field.get("url"),
        },
    }


def validate_cninfo_economic_date_evidence(
    *,
    evidence_dir: Path,
    targets: Path,
    assembled_events: Path,
    universe: Path,
    out: Path,
    run_manifest: Path | None = None,
) -> dict[str, Any]:
    """Check a 1.3 evidence directory and write suggestions. Frozen inputs are not modified."""
    if out.exists():
        raise TargetPackageError(f"refuse overwrite: {out}")
    evidence_dir = Path(evidence_dir)
    targets = Path(targets)
    assembled_events = Path(assembled_events)
    universe = Path(universe)
    assembled_before = assembled_events.read_bytes()
    universe_before = universe.read_bytes()
    commit_path = evidence_dir / "COMMITTED.json"
    manifest_path = evidence_dir / "manifest.json"
    if not commit_path.is_file():
        raise TargetPackageError("missing COMMITTED")
    if not manifest_path.is_file():
        raise TargetPackageError("missing manifest")
    committed = json.loads(commit_path.read_text(encoding="utf-8"))
    if committed.get("kind") != COMMIT_KIND:
        raise TargetPackageError("unexpected COMMITTED kind")
    if (
        committed.get("owner_signature") not in ("", None)
        or committed.get("lake_write_authorized") is not False
    ):
        raise TargetPackageError("evidence commit must stay unsigned and off-lake")
    if hashlib.sha256(manifest_path.read_bytes()).hexdigest() != committed.get("manifest_sha256"):
        raise TargetPackageError("hash mismatch: manifest")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("kind") != EVIDENCE_KIND or manifest.get("format_version") != FORMAT_VERSION:
        raise TargetPackageError("unexpected evidence manifest")
    if manifest.get("owner_signature") not in ("", None):
        raise TargetPackageError("evidence manifest must stay unsigned")
    target_doc = json.loads(targets.read_text(encoding="utf-8"))
    if target_doc.get("kind") != TARGETS_KIND:
        raise TargetPackageError("unexpected targets kind")
    target_hash = _sha256(targets)
    if (
        manifest.get("target_sha256") != target_hash
        or committed.get("target_sha256") != target_hash
    ):
        raise TargetPackageError("hash mismatch: targets")
    if target_doc.get("assembled_events_sha256") != hashlib.sha256(assembled_before).hexdigest():
        raise TargetPackageError("hash mismatch: assembled events")
    if target_doc.get("universe_sha256") != hashlib.sha256(universe_before).hexdigest():
        raise TargetPackageError("hash mismatch: universe")
    if run_manifest is not None and target_doc.get("run_manifest_sha256") != _sha256(run_manifest):
        raise TargetPackageError("hash mismatch: run manifest")
    listed = manifest.get("files")
    if not isinstance(listed, list):
        raise TargetPackageError("manifest files are missing")
    seen: set[str] = set()
    for item in listed:
        if not isinstance(item, dict):
            raise TargetPackageError("manifest file entry is invalid")
        rel = str(item.get("relpath") or "")
        path = _safe_rel(evidence_dir, rel)
        digest = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else ""
        if digest != item.get("sha256"):
            raise TargetPackageError(f"hash mismatch: {rel}")
        seen.add(rel)
    for file in evidence_dir.rglob("*"):
        if not file.is_file():
            continue
        rel = file.relative_to(evidence_dir).as_posix()
        if rel.startswith(".") or rel in {"manifest.json", "COMMITTED.json"}:
            continue
        if rel not in seen:
            raise TargetPackageError(f"hash mismatch: unlisted {rel}")
    known_ids = {str(event["event_id"]) for event in target_doc.get("events") or []}
    suggestions = []
    unresolved = []
    field_sources = []
    for match in manifest.get("matches") or []:
        if not isinstance(match, dict) or match.get("verdict") not in _VERDICTS:
            raise TargetPackageError("match verdict is invalid")
        if str(match.get("event_id")) not in known_ids:
            raise TargetPackageError("match event is not in the frozen targets")
        fields = match.get("fields") or {}
        if not isinstance(fields, dict):
            raise TargetPackageError("match fields are invalid")
        for name, field in fields.items():
            if not isinstance(field, dict):
                raise TargetPackageError("tampered field source")
            _check_field(evidence_dir, str(name), field)
            field_sources.append(
                {
                    "code": match.get("code"),
                    "event_id": match.get("event_id"),
                    "field": name,
                    "status": field.get("status"),
                    "value": field.get("value"),
                    "announcement_id": field.get("announcement_id"),
                    "url": field.get("url"),
                    "pdf_sha256": field.get("pdf_sha256"),
                    "text_sha256": field.get("text_sha256"),
                }
            )
        dates = {name: _date_slot(fields.get(name)) for name in _DATE_FIELDS}
        suggestion = {
            "code": match.get("code"),
            "dates": dates,
            "event_id": match.get("event_id"),
            "ex_date": match.get("ex_date"),
            "hithink_amounts": match.get("hithink_amounts"),
            "reasons": match.get("reasons") or [],
            "verdict": match.get("verdict"),
        }
        suggestions.append(suggestion)
        if match.get("verdict") != "machine_matched":
            unresolved.append(
                {
                    "code": match.get("code"),
                    "event_id": match.get("event_id"),
                    "reason": match.get("verdict"),
                }
            )
    for item in target_doc.get("query_targets") or []:
        if item.get("has_event_row") is False:
            unresolved.append(
                {"code": item.get("code"), "event_id": None, "reason": "D11_no_event_row"}
            )
    report = {
        "assembled_events_sha256": target_doc.get("assembled_events_sha256"),
        "committed_status": committed.get("status"),
        "disclaimer": (
            "Suggestions are not economic approval. "
            "compatibility_policy_date and backtest_adopted_value stay empty in this slice. "
            "A missing listing date is not filled from ex_date."
        ),
        "economic_approval": False,
        "field_sources": field_sources,
        "format_version": FORMAT_VERSION,
        "kind": SUGGESTION_KIND,
        "lake_write_authorized": False,
        "owner_signature": "",
        "suggestions": suggestions,
        "target_sha256": target_hash,
        "universe_sha256": target_doc.get("universe_sha256"),
        "unresolved": unresolved,
    }
    if (
        assembled_events.read_bytes() != assembled_before
        or universe.read_bytes() != universe_before
    ):
        raise TargetPackageError("frozen input changed during validation")
    _write_new(out, _dumps(report))
    return report
