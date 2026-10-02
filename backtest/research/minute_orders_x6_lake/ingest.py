"""Ingest lake boundary meta; refuse synthetic masquerade / promotion / write."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

BOUNDARY_META_SCHEMA = "minute_orders_x6_lake_boundary_meta_v0"
ALLOWED_SOURCE_KIND = "lake"
# Tool-local evidence token. Does NOT unlock backend CLI --evidence-level=lake
# (tip CLI remains synthetic-only). Not host / certified / green R.
ALLOWED_EVIDENCE_LEVEL = "lake_boundary"
ALLOWED_ACCOUNT_ORIGIN = "synthetic_account"
ALLOWED_COMMANDS_ORIGIN = "designed_limit_batch"
ALLOWED_BAR_TIME_LABEL = "END"
ALLOWED_AVAILABILITY = "bucket_end"
REQUIRED_NOTICE_TOKEN = "lake boundary attestation != host PASS"

# Symmetric to X6 synthetic: refuse synthetic_fixture packages masquerading as
# lake pass; refuse host/certified promotion; refuse write-lake keys.
BANNED_SOURCE_KINDS = frozenset({
    "synthetic_fixture", "hybrid", "certified_real", "lake_bar",
})
BANNED_EVIDENCE_LEVELS = frozenset({
    "synthetic", "hybrid", "certified", "host", "lake",
})
BANNED_TOP_LEVEL_KEYS = frozenset({
    "lake_write", "lake_write_path", "write_lake", "write_path",
    "host_attestation", "green_r", "nav_rank",
    "fills", "trades", "summary",
})


class LakeBoundaryIngestError(ValueError):
    """Lake boundary meta refused (synthetic masquerade / promotion / schema)."""


@dataclass(frozen=True)
class LakeBoundaryMeta:
    """Read-only lake END / loader boundary description (NOT host PASS)."""

    schema: str
    source_kind: str
    evidence_level: str
    account_origin: str
    commands_origin: str
    bar_time_label: str
    availability: str
    notice: str
    tip_gaps: tuple[str, ...]
    bans: tuple[str, ...]
    contract: str
    backend_id: str
    raw: Mapping[str, Any]


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise LakeBoundaryIngestError(msg)


def meta_from_mapping(payload: Mapping[str, Any]) -> LakeBoundaryMeta:
    """Validate and load an X6 lake boundary meta mapping."""
    _require(isinstance(payload, dict), "boundary meta must be a JSON object")
    banned_present = sorted(BANNED_TOP_LEVEL_KEYS & set(payload))
    _require(
        not banned_present,
        f"banned top-level keys for X6 lake boundary: {banned_present}",
    )

    schema = payload.get("schema")
    _require(
        schema == BOUNDARY_META_SCHEMA,
        f"unsupported schema {schema!r}; expected {BOUNDARY_META_SCHEMA}",
    )

    source_kind = payload.get("source_kind")
    _require(isinstance(source_kind, str) and bool(source_kind.strip()),
             "source_kind required")
    if source_kind in BANNED_SOURCE_KINDS or source_kind != ALLOWED_SOURCE_KIND:
        raise LakeBoundaryIngestError(
            f"X6 lake boundary refuses source_kind={source_kind!r}; "
            f"only {ALLOWED_SOURCE_KIND!r} "
            "(synthetic_fixture masquerade forbidden; use X6 synthetic knife)"
        )

    evidence_level = payload.get("evidence_level")
    _require(isinstance(evidence_level, str) and bool(evidence_level.strip()),
             "evidence_level required")
    if (evidence_level in BANNED_EVIDENCE_LEVELS
            or evidence_level != ALLOWED_EVIDENCE_LEVEL):
        raise LakeBoundaryIngestError(
            f"X6 lake boundary refuses evidence_level={evidence_level!r}; "
            f"only {ALLOWED_EVIDENCE_LEVEL!r} "
            "(does NOT unlock CLI --evidence-level=lake; not host/certified)"
        )

    account_origin = payload.get("account_origin")
    _require(account_origin == ALLOWED_ACCOUNT_ORIGIN,
             f"account_origin must be {ALLOWED_ACCOUNT_ORIGIN!r} "
             f"(got {account_origin!r})")

    commands_origin = payload.get("commands_origin")
    _require(commands_origin == ALLOWED_COMMANDS_ORIGIN,
             f"commands_origin must be {ALLOWED_COMMANDS_ORIGIN!r} "
             f"(got {commands_origin!r})")

    bar_time_label = payload.get("bar_time_label")
    _require(bar_time_label == ALLOWED_BAR_TIME_LABEL,
             f"bar_time_label must be {ALLOWED_BAR_TIME_LABEL!r} "
             f"(Phase5 research path; tip loader still accepts START|END generally; "
             f"got {bar_time_label!r})")

    availability = payload.get("availability")
    _require(availability == ALLOWED_AVAILABILITY,
             f"availability must be {ALLOWED_AVAILABILITY!r} "
             f"(got {availability!r})")

    notice = payload.get("notice")
    _require(isinstance(notice, str) and bool(notice.strip()), "notice required")
    _require(
        REQUIRED_NOTICE_TOKEN in notice,
        f"notice must contain {REQUIRED_NOTICE_TOKEN!r} "
        "(lake boundary attestation != host PASS / item-4 live / green R)",
    )

    tip_gaps = payload.get("tip_gaps")
    _require(isinstance(tip_gaps, list) and bool(tip_gaps),
             "tip_gaps must be a nonempty list")
    for item in tip_gaps:
        _require(isinstance(item, str) and bool(item.strip()),
                 "tip_gaps items must be nonempty strings")

    bans = payload.get("bans")
    _require(isinstance(bans, list) and bool(bans), "bans must be a nonempty list")
    for item in bans:
        _require(isinstance(item, str) and bool(item.strip()),
                 "bans items must be nonempty strings")

    contract = payload.get("contract")
    backend_id = payload.get("backend_id")
    _require(contract == "research contract v0 (L2-S0)",
             "contract must remain research contract v0 (L2-S0); no new contract")
    _require(backend_id == "minute_orders_research_v1",
             "backend_id must remain minute_orders_research_v1; no new backend_id")

    claims = payload.get("claims")
    if claims is not None:
        _require(isinstance(claims, dict), "claims must be an object when present")
        for key in ("lake_pass", "host_attestation", "green_r",
                    "comparison_authorization", "item4_live_pass"):
            if claims.get(key) is True:
                raise LakeBoundaryIngestError(
                    f"refusing promotion claim claims.{key}=true "
                    "(lake boundary attestation != host PASS / lake PASS / green R)"
                )

    # Refuse elevating fixture_pass to lake_pass via claims or aliases.
    if payload.get("fixture_promoted_to_lake_pass") is True:
        raise LakeBoundaryIngestError(
            "refusing fixture_promoted_to_lake_pass=true "
            "(Fixture PASS != lake PASS; synthetic knife stays separate)"
        )

    return LakeBoundaryMeta(
        schema=schema,
        source_kind=source_kind,
        evidence_level=evidence_level,
        account_origin=account_origin,
        commands_origin=commands_origin,
        bar_time_label=bar_time_label,
        availability=availability,
        notice=notice,
        tip_gaps=tuple(tip_gaps),
        bans=tuple(bans),
        contract=contract,
        backend_id=backend_id,
        raw=dict(payload),
    )


def load_lake_boundary_meta(path: str | Path) -> LakeBoundaryMeta:
    """Load and validate a lake boundary meta JSON file."""
    p = Path(path)
    _require(p.is_file(), f"boundary meta file not found: {p}")
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise LakeBoundaryIngestError(f"invalid JSON in {p}: {exc}") from exc
    return meta_from_mapping(payload)


__all__ = [
    "ALLOWED_ACCOUNT_ORIGIN",
    "ALLOWED_AVAILABILITY",
    "ALLOWED_BAR_TIME_LABEL",
    "ALLOWED_COMMANDS_ORIGIN",
    "ALLOWED_EVIDENCE_LEVEL",
    "ALLOWED_SOURCE_KIND",
    "BOUNDARY_META_SCHEMA",
    "LakeBoundaryIngestError",
    "LakeBoundaryMeta",
    "REQUIRED_NOTICE_TOKEN",
    "load_lake_boundary_meta",
    "meta_from_mapping",
]
