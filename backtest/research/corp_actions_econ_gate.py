"""Explicit economics eligibility; the only registered corp-actions lake loader.

No current backtest consumer is connected here. Acquisition success is not an
entitlement assertion. Blocked rows and reasons must accompany research results.

OP06 defensive gate: stock-conversion / stock-merger arrangements (share-identity
swaps) can never be expressed through the cash/bonus ten-column schema. Rows whose
code is a pinned conversion source, or that smuggle a pinned conversion ratio into
bonus_ratio/transfer_ratio alongside conversion markers, are hard-blocked with the
stable reason key `unsupported_stock_conversion_in_cash_bonus_schema`.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re

import pyarrow.parquet as pq

from oskh_data.hithink_artifact import SOURCE, code, day, digest, number, read_json

FIELDS = ("code", "event_id", "ex_date", "record_date", "pay_date", "cash_div_per_share",
          "bonus_ratio", "transfer_ratio", "bonus_list_date", "source")
DATE_FIELDS = ("ex_date", "record_date", "pay_date", "bonus_list_date")
AMOUNTS = ("cash_div_per_share", "bonus_ratio", "transfer_ratio")


def fields_sha256(row):
    value = {k: (str(row[k].normalize()) if isinstance(row[k], Decimal) else str(row[k])
                 if isinstance(row[k], date) else row[k]) for k in FIELDS}
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class _VerifiedEvidence:
    revision: str
    events_sha256: str
    entries: dict


UNSUPPORTED_STOCK_CONVERSION_REASON = "unsupported_stock_conversion_in_cash_bonus_schema"


@dataclass(frozen=True)
class PinnedStockConversion:
    """A frozen share-identity swap that must never enter via cash/bonus columns."""

    source_code: str
    target_code: str
    target_shares_per_source_share: Decimal
    conversion_record_date: date
    delist_date: date


# OP06 frozen identity facts, pinned from
# docs/operations/evidence/hithink-artifact-2026-10-30/coverage-identity-facts.json
# (东兴证券 601198.SH absorbed by 中金公司 601995.SH). Deliberately not loaded from
# the evidence JSON at runtime; tests assert the pin matches those values.
PINNED_STOCK_CONVERSIONS = (
    PinnedStockConversion(
        source_code="601198.SH",
        target_code="601995.SH",
        target_shares_per_source_share=Decimal("0.4376"),
        conversion_record_date=date(2026, 10, 16),
        delist_date=date(2026, 10, 19),
    ),
)
_PINNED_CONVERSION_SOURCES = frozenset(p.source_code for p in PINNED_STOCK_CONVERSIONS)
_PINNED_CONVERSION_RATIOS = frozenset(
    p.target_shares_per_source_share for p in PINNED_STOCK_CONVERSIONS
)
_PINNED_CONVERSION_MARKER_TOKENS = frozenset(
    token
    for pinned in PINNED_STOCK_CONVERSIONS
    for token in (
        pinned.source_code,
        pinned.target_code,
        pinned.source_code.split(".")[0],
        pinned.target_code.split(".")[0],
        "换股",
        "conversion",
        "stock_merger",
        "stock-merger",
        "stock merger",
    )
)


def _stock_conversion_reasons(row):
    # Primary: a pinned conversion source code always blocks, even with amounts
    # shaped like an ordinary cash/bonus event — the identity swap and delist
    # conversion cannot be expressed in this schema.
    if row["code"] in _PINNED_CONVERSION_SOURCES:
        return [UNSUPPORTED_STOCK_CONVERSION_REASON]
    # Secondary (defense-in-depth): a pinned conversion ratio stuffed into
    # bonus/transfer columns blocks only when conversion markers name the
    # arrangement, so an unrelated code with a coincidentally equal bonus ratio
    # stays eligible.
    ratios = (row["bonus_ratio"], row["transfer_ratio"])
    if not any(ratio in _PINNED_CONVERSION_RATIOS for ratio in ratios):
        return []
    markers = " ".join((row["event_id"], row["source"])).lower()
    if any(token in markers for token in _PINNED_CONVERSION_MARKER_TOKENS):
        return [UNSUPPORTED_STOCK_CONVERSION_REASON]
    return []


def _validate_rows(rows):
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != set(FIELDS):
            raise ValueError("invalid corp-actions event structure")
        code(row["code"])
        if not isinstance(row["source"], str) or not (row["source"].startswith("wind:") or row["source"] == SOURCE):
            raise ValueError("unknown corporate-action source")
        if not isinstance(row["event_id"], str) or not row["event_id"] or row["event_id"] in seen:
            raise ValueError("missing/duplicate event identity")
        seen.add(row["event_id"])
        for key in DATE_FIELDS:
            if row[key] is not None and type(row[key]) is not date:
                raise ValueError("event date must be a date object or NULL")
        if row["ex_date"] is None:
            raise ValueError("event requires an ex_date")
        if row["record_date"] is not None and row["record_date"] > row["ex_date"]:
            raise ValueError("record date follows ex_date")
        for key in ("pay_date", "bonus_list_date"):
            if row[key] is not None and row[key] < row["ex_date"]:
                raise ValueError("economic date precedes ex_date")
        for key in AMOUNTS:
            if row[key] is not None:
                number(row[key])


def _review_reasons(entry, row):
    if not isinstance(entry, dict) or entry.get("fields_sha256") != fields_sha256(row):
        return ["missing_or_stale_economic_basis"]
    required_text = ("reviewed_by", "shareholder_class", "economic_basis", "policy_id", "event_identity")
    if any(not isinstance(entry.get(k), str) or not entry[k].strip() for k in required_text):
        return ["incomplete_economic_review"]
    from oskh_data.hithink_artifact import SHANGHAI
    if day(entry["reviewed_at"]) > datetime.now(SHANGHAI).date():
        return ["future_economic_review"]
    chain = entry.get("announcement_chain")
    if not isinstance(chain, list) or not chain:
        return ["missing_announcement_revision_chain"]
    identities = set()
    previous = None
    for notice in chain:
        if not isinstance(notice, dict) or not isinstance(notice.get("document_id"), str) or not notice["document_id"]:
            return ["invalid_announcement_revision_chain"]
        if not isinstance(notice.get("sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", notice["sha256"]):
            return ["invalid_announcement_revision_chain"]
        if notice["document_id"] in identities or notice.get("supersedes") != previous:
            return ["invalid_announcement_revision_chain"]
        identities.add(notice["document_id"])
        previous = notice["document_id"]
    if entry.get("applicable_document_id") != chain[-1]["document_id"]:
        return ["unresolved_announcement_revision"]
    return []


def gate_rows_for_economics(rows, *, evidence=None):
    """Return (accepted, blocked, reasons). Never fill NULL dates or sum events.

    Only loader-verified evidence can establish economic eligibility. A plain
    caller-supplied dictionary cannot assert its own revision as trustworthy.
    """
    rows = list(rows)
    _validate_rows(rows)
    counts = Counter((r["code"], r["ex_date"]) for r in rows)
    accepted, blocked, reasons = [], [], []
    verified = isinstance(evidence, _VerifiedEvidence)
    for row in rows:
        why = _stock_conversion_reasons(row)
        for key in ("record_date", "pay_date", "cash_div_per_share"):
            if row[key] is None:
                why.append("missing_" + key)
        bonus = (row["bonus_ratio"] or Decimal(0)) + (row["transfer_ratio"] or Decimal(0))
        if bonus > 0 and row["bonus_list_date"] is None:
            why.append("missing_bonus_list_date")
        entry = evidence.entries.get(row["event_id"]) if verified else None
        needs_review = row["source"] == SOURCE or counts[(row["code"], row["ex_date"])] > 1
        review_why = _review_reasons(entry, row) if verified and needs_review else ["unverified_economic_basis"]
        if needs_review:
            why.extend(review_why)
        if counts[(row["code"], row["ex_date"])] > 1:
            # Without a chosen holder class and disjoint event identities, even
            # two reviewed rows can double-pay. Keep both explicitly blocked.
            why.append("multiple_events_require_explicit_selection")
        if why:
            blocked.append(row)
            reasons.append({"event_id": row["event_id"], "code": row["code"], "ex_date": str(row["ex_date"]),
                            "source": row["source"], "reasons": why})
        else:
            accepted.append(row)
    return accepted, blocked, reasons


def load_corp_actions_for_economics(lake_dir=None, *, evidence_path=None):
    """Read, bind revision/file/fields, then gate. No network, publication or fallback."""
    if lake_dir is None:
        from common.infra.data_root import resolve_source_parquet
        lake_dir = resolve_source_parquet("corp_actions")
    lake = Path(lake_dir)
    manifest_hash = digest(lake / "manifest.json")
    manifest = read_json(lake / "manifest.json")
    revision = manifest.get("revision")
    if manifest.get("schema_version") != 1 or not isinstance(revision, str) or not revision:
        raise ValueError("invalid corporate-action manifest revision")
    expected = manifest["files"]["events.parquet"]["sha256"]
    actual = digest(lake / "events.parquet")
    if expected != actual:
        raise ValueError("events hash does not match lake manifest")
    rows = pq.ParquetFile(lake / "events.parquet").read().to_pylist()
    _validate_rows(rows)
    context = None
    if evidence_path is not None:
        evidence_hash = digest(evidence_path)
        proof = read_json(evidence_path)
        if proof.get("format_version") != 1 or proof.get("revision") != revision or proof.get("events_sha256") != actual:
            raise ValueError("economic evidence revision/file mismatch")
        entries = {}
        by_id = {r["event_id"]: r for r in rows}
        for entry in proof["entries"]:
            eid = entry["event_id"]
            if eid in entries or eid not in by_id or entry.get("fields_sha256") != fields_sha256(by_id[eid]):
                raise ValueError("economic evidence event/fields mismatch")
            entries[eid] = entry
        if digest(evidence_path) != evidence_hash:
            raise ValueError("economic evidence changed during read")
        context = _VerifiedEvidence(revision, actual, entries)
    result = gate_rows_for_economics(rows, evidence=context)
    if digest(lake / "manifest.json") != manifest_hash or digest(lake / "events.parquet") != actual:
        raise ValueError("corporate-action revision changed during read")
    return result
