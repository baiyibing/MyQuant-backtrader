"""X6 synthetic_fixture / attestation differential report (NOT true lake).

Independent tool root; never writes success summary.json; never elevates to
lake PASS / host attestation / green R. tool_id is NOT a backend_id.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from backtest.research.minute_orders_backend.source_provenance import (
    FIXTURE_NOTICE as TIP_FIXTURE_NOTICE,
)

from .ingest import (
    ALLOWED_ACCOUNT_ORIGIN,
    ALLOWED_COMMANDS_ORIGIN,
    ALLOWED_EVIDENCE_LEVEL,
    ALLOWED_SOURCE_KIND,
    REQUIRED_NOTICE_TOKEN,
    SyntheticBoundaryMeta,
)

TOOL_ID = "minute_orders_x6_synthetic"
# tool_id is tooling identity only — NOT a backend_id / economic contract.
DIFFERENTIAL_ROOT_NAME = "minute_orders_x6_synthetic"
DIFFERENTIAL_STATUS = "fixture_pass_not_lake_pass"
REPORT_SCHEMA = "minute_orders_x6_synthetic_differential_report_v0"
REPORT_FILENAME = "differential_report.json"
FORBIDDEN_SUMMARY_NAME = "summary.json"

CONTRACT = "research contract v0 (L2-S0)"
BACKEND_ID = "minute_orders_research_v1"
FIXTURE_NOTICE = TIP_FIXTURE_NOTICE

_RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")

# Tip source_loader gaps this knife documents/hardens (TC1 §5 X6).
TIP_GAP_CHECKS = (
    {
        "id": "source_kind_synthetic_only",
        "tip": "source_loader accepts source_kind in {lake, synthetic_fixture}",
        "harden": "X6 synthetic tool accepts only synthetic_fixture; lake refused",
    },
    {
        "id": "cli_evidence_synthetic_only",
        "tip": "CLI --evidence-level choices=('synthetic',) only; no lake loader",
        "harden": "boundary meta evidence_level must be synthetic",
    },
    {
        "id": "account_origin_synthetic",
        "tip": "account origin still synthetic_account",
        "harden": "boundary meta account_origin must be synthetic_account",
    },
    {
        "id": "commands_origin_designed_limit",
        "tip": "commands origin still designed_limit_batch",
        "harden": "boundary meta commands_origin must be designed_limit_batch",
    },
    {
        "id": "fixture_notice_not_lake_pass",
        "tip": "synthetic_fixture notice = Fixture PASS != lake PASS …",
        "harden": "notice must contain Fixture PASS != lake PASS; no promotion claims",
    },
)


class DifferentialError(ValueError):
    """Differential refused before or during write."""


@dataclass(frozen=True)
class DifferentialOutcome:
    """In-memory + optional on-disk differential result."""

    tool_id: str
    differential_status: str
    report: Mapping[str, Any]
    root: Path | None
    report_path: Path | None


def differential_root(parent: str | Path, run_id: str) -> Path:
    if not _RUN_ID_RE.fullmatch(run_id):
        raise DifferentialError("run_id must be a single safe ASCII path component")
    return Path(parent).resolve() / DIFFERENTIAL_ROOT_NAME / run_id


def build_differential_report(meta: SyntheticBoundaryMeta) -> dict[str, Any]:
    """Build red-label differential report from validated boundary meta."""
    # Re-assert tip FIXTURE_NOTICE constant alignment.
    if REQUIRED_NOTICE_TOKEN not in FIXTURE_NOTICE:
        raise DifferentialError("tip FIXTURE_NOTICE lost Fixture PASS != lake PASS token")
    if REQUIRED_NOTICE_TOKEN not in meta.notice:
        raise DifferentialError("meta notice missing Fixture PASS != lake PASS token")

    gap_results = []
    for check in TIP_GAP_CHECKS:
        gap_results.append({
            "id": check["id"],
            "tip": check["tip"],
            "harden": check["harden"],
            "status": "enforced",
        })

    return {
        "schema": REPORT_SCHEMA,
        "tool_id": TOOL_ID,
        "differential_status": DIFFERENTIAL_STATUS,
        "red_label": True,
        "diagnostic_only": True,
        "label": (
            "X6 synthetic_fixture / attestation differential · "
            "Fixture PASS != lake PASS · NOT host attestation · ≠δ5≠R4"
        ),
        "contract": CONTRACT,
        "backend_id_documented": BACKEND_ID,
        "note": (
            "tool_id is NOT a backend_id; no new economic contract; "
            "does not call MatchCore/Fees/simulate; independent tool root; "
            "no success summary.json; forever opt-in; never BOOKS default; "
            "true lake ingress remains a separate knife"
        ),
        "fixture_notice": FIXTURE_NOTICE,
        "boundary": {
            "schema": meta.schema,
            "source_kind": meta.source_kind,
            "evidence_level": meta.evidence_level,
            "account_origin": meta.account_origin,
            "commands_origin": meta.commands_origin,
            "notice": meta.notice,
            "tip_gaps": list(meta.tip_gaps),
            "bans": list(meta.bans),
            "contract": meta.contract,
            "backend_id": meta.backend_id,
        },
        "tip_gap_checks": gap_results,
        "invariants": {
            "source_kind": ALLOWED_SOURCE_KIND,
            "evidence_level": ALLOWED_EVIDENCE_LEVEL,
            "account_origin": ALLOWED_ACCOUNT_ORIGIN,
            "commands_origin": ALLOWED_COMMANDS_ORIGIN,
            "notice_token": REQUIRED_NOTICE_TOKEN,
            "fixture_pass_is_not_lake_pass": True,
            "host_attestation": False,
            "comparison_authorization": False,
            "green_r": False,
        },
        "bans": [
            "no_lake_write",
            "no_lake_source_kind",
            "no_evidence_level_lake",
            "no_host_attestation_claim",
            "no_green_r",
            "no_success_summary_json",
            "no_new_contract",
            "no_new_backend_id",
            "no_matchcore_fees_simulate_edit",
            "not_delta5_certified",
            "not_r4",
            "not_books_default",
            "forever_opt_in",
            "independent_tool_root",
            "true_lake_separate_knife",
        ],
    }


def write_differential_report(
    report: Mapping[str, Any],
    *,
    parent: str | Path,
    run_id: str,
) -> tuple[Path, Path]:
    """Write differential_report.json under the independent tool root.

    Refuses existing roots. Never writes summary.json.
    """
    root = differential_root(parent, run_id)
    if root.exists():
        raise FileExistsError(
            f"differential root already exists (refuse overwrite): {root}"
        )
    parts = {p.lower() for p in root.parts}
    if "minute_orders_research_v1" in parts:
        raise DifferentialError(
            "differential root must NOT be under minute_orders_research_v1"
        )
    root.mkdir(parents=True, exist_ok=False)
    report_path = root / REPORT_FILENAME
    forbidden = root / FORBIDDEN_SUMMARY_NAME
    if forbidden.exists():
        raise DifferentialError(
            f"refusing to publish beside existing {FORBIDDEN_SUMMARY_NAME}"
        )
    payload = json.dumps(report, ensure_ascii=True, sort_keys=True, indent=2) + "\n"
    report_path.write_text(payload, encoding="utf-8")
    if (root / FORBIDDEN_SUMMARY_NAME).exists():
        raise DifferentialError("internal error: summary.json must not be written")
    return root, report_path


def run_x6_synthetic_differential(
    meta: SyntheticBoundaryMeta,
    *,
    parent: str | Path | None = None,
    run_id: str | None = None,
) -> DifferentialOutcome:
    """Validate boundary meta → differential report; optional independent root write."""
    report = build_differential_report(meta)
    if report["differential_status"] != DIFFERENTIAL_STATUS:
        raise DifferentialError("differential_status must stay fixture_pass_not_lake_pass")
    if report["boundary"]["source_kind"] != ALLOWED_SOURCE_KIND:
        raise DifferentialError("report source_kind drifted from synthetic_fixture")

    root = report_path = None
    if parent is not None or run_id is not None:
        if parent is None or run_id is None:
            raise DifferentialError("parent and run_id must be supplied together")
        root, report_path = write_differential_report(
            report, parent=parent, run_id=run_id,
        )
    return DifferentialOutcome(
        tool_id=TOOL_ID,
        differential_status=DIFFERENTIAL_STATUS,
        report=report,
        root=root,
        report_path=report_path,
    )


__all__ = [
    "BACKEND_ID",
    "CONTRACT",
    "DIFFERENTIAL_ROOT_NAME",
    "DIFFERENTIAL_STATUS",
    "FIXTURE_NOTICE",
    "FORBIDDEN_SUMMARY_NAME",
    "REPORT_FILENAME",
    "REPORT_SCHEMA",
    "TIP_GAP_CHECKS",
    "TOOL_ID",
    "DifferentialError",
    "DifferentialOutcome",
    "build_differential_report",
    "differential_root",
    "run_x6_synthetic_differential",
    "write_differential_report",
]
