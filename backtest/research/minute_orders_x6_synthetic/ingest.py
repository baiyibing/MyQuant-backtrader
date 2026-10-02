"""Ingest synthetic_fixture boundary meta; refuse lake / promotion claims."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

BOUNDARY_META_SCHEMA = "minute_orders_x6_synthetic_boundary_meta_v0"
ALLOWED_SOURCE_KIND = "synthetic_fixture"
ALLOWED_EVIDENCE_LEVEL = "synthetic"
ALLOWED_ACCOUNT_ORIGIN = "synthetic_account"
ALLOWED_COMMANDS_ORIGIN = "designed_limit_batch"
REQUIRED_NOTICE_TOKEN = "Fixture PASS != lake PASS"

# Tip source_loader accepts lake | synthetic_fixture; this X6 tool hardens the
# synthetic-only surface and refuses lake packages (true lake = separate knife).
BANNED_SOURCE_KINDS = frozenset({"lake", "lake_bar", "hybrid", "certified_real"})
BANNED_EVIDENCE_LEVELS = frozenset({"lake", "hybrid", "certified", "host"})
BANNED_TOP_LEVEL_KEYS = frozenset({
    "lake_path", "lake_root", "host_attestation", "green_r", "nav_rank",
    "fills", "trades", "summary",
})


class DifferentialIngestError(ValueError):
    """Boundary meta refused (lake / promotion / schema)."""


@dataclass(frozen=True)
class SyntheticBoundaryMeta:
    """Attestation-level description of tip X6 synthetic_fixture boundary."""

    schema: str
    source_kind: str
    evidence_level: str
    account_origin: str
    commands_origin: str
    notice: str
    tip_gaps: tuple[str, ...]
    bans: tuple[str, ...]
    contract: str
    backend_id: str
    raw: Mapping[str, Any]


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise DifferentialIngestError(msg)


def meta_from_mapping(payload: Mapping[str, Any]) -> SyntheticBoundaryMeta:
    """Validate and load an X6 synthetic boundary meta mapping."""
    _require(isinstance(payload, dict), "boundary meta must be a JSON object")
    banned_present = sorted(BANNED_TOP_LEVEL_KEYS & set(payload))
    _require(
        not banned_present,
        f"banned top-level keys for X6 synthetic differential: {banned_present}",
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
        raise DifferentialIngestError(
            f"X6 synthetic differential refuses source_kind={source_kind!r}; "
            f"only {ALLOWED_SOURCE_KIND!r} (true lake = separate knife)"
        )

    evidence_level = payload.get("evidence_level")
    _require(isinstance(evidence_level, str) and bool(evidence_level.strip()),
             "evidence_level required")
    if (evidence_level in BANNED_EVIDENCE_LEVELS
            or evidence_level != ALLOWED_EVIDENCE_LEVEL):
        raise DifferentialIngestError(
            f"X6 synthetic differential refuses evidence_level={evidence_level!r}; "
            f"only {ALLOWED_EVIDENCE_LEVEL!r} (CLI tip surface; no lake loader)"
        )

    account_origin = payload.get("account_origin")
    _require(account_origin == ALLOWED_ACCOUNT_ORIGIN,
             f"account_origin must be {ALLOWED_ACCOUNT_ORIGIN!r} "
             f"(got {account_origin!r})")

    commands_origin = payload.get("commands_origin")
    _require(commands_origin == ALLOWED_COMMANDS_ORIGIN,
             f"commands_origin must be {ALLOWED_COMMANDS_ORIGIN!r} "
             f"(got {commands_origin!r})")

    notice = payload.get("notice")
    _require(isinstance(notice, str) and bool(notice.strip()), "notice required")
    _require(
        REQUIRED_NOTICE_TOKEN in notice,
        f"notice must contain {REQUIRED_NOTICE_TOKEN!r} "
        "(Fixture PASS != lake PASS / host attestation)",
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

    # Refuse silent promotion claims inside the meta.
    claims = payload.get("claims")
    if claims is not None:
        _require(isinstance(claims, dict), "claims must be an object when present")
        for key in ("lake_pass", "host_attestation", "green_r", "comparison_authorization"):
            if claims.get(key) is True:
                raise DifferentialIngestError(
                    f"refusing promotion claim claims.{key}=true "
                    "(Fixture PASS != lake PASS / host / green R)"
                )

    return SyntheticBoundaryMeta(
        schema=schema,
        source_kind=source_kind,
        evidence_level=evidence_level,
        account_origin=account_origin,
        commands_origin=commands_origin,
        notice=notice,
        tip_gaps=tuple(tip_gaps),
        bans=tuple(bans),
        contract=contract,
        backend_id=backend_id,
        raw=dict(payload),
    )


def load_synthetic_boundary_meta(path: str | Path) -> SyntheticBoundaryMeta:
    """Load and validate a synthetic boundary meta JSON file."""
    p = Path(path)
    _require(p.is_file(), f"boundary meta file not found: {p}")
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DifferentialIngestError(f"invalid JSON in {p}: {exc}") from exc
    return meta_from_mapping(payload)


__all__ = [
    "ALLOWED_ACCOUNT_ORIGIN",
    "ALLOWED_COMMANDS_ORIGIN",
    "ALLOWED_EVIDENCE_LEVEL",
    "ALLOWED_SOURCE_KIND",
    "BOUNDARY_META_SCHEMA",
    "DifferentialIngestError",
    "REQUIRED_NOTICE_TOKEN",
    "SyntheticBoundaryMeta",
    "load_synthetic_boundary_meta",
    "meta_from_mapping",
]
