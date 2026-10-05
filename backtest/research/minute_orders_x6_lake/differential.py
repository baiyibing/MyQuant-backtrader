"""X6 lake END / loader boundary differential (read-only; NOT host PASS).

Independent tool root; never writes success summary.json; never elevates to
lake PASS / host attestation / green R; never writes the lake. tool_id is NOT
a backend_id. Does not call load_minute_orders_source / MatchCore / Fees.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .ingest import (
    ALLOWED_ACCOUNT_ORIGIN,
    ALLOWED_AVAILABILITY,
    ALLOWED_BAR_TIME_LABEL,
    ALLOWED_COMMANDS_ORIGIN,
    ALLOWED_EVIDENCE_LEVEL,
    ALLOWED_SOURCE_KIND,
    REQUIRED_NOTICE_TOKEN,
    LakeBoundaryMeta,
)

TOOL_ID = "minute_orders_x6_lake"
# tool_id is tooling identity only — NOT a backend_id / economic contract.
DIFFERENTIAL_ROOT_NAME = "minute_orders_x6_lake"
DIFFERENTIAL_STATUS = "lake_boundary_attested_not_host_pass"
REPORT_SCHEMA = "minute_orders_x6_lake_differential_report_v0"
REPORT_FILENAME = "differential_report.json"
FORBIDDEN_SUMMARY_NAME = "summary.json"

CONTRACT = "research contract v0 (L2-S0)"
BACKEND_ID = "minute_orders_research_v1"
LAKE_BOUNDARY_NOTICE = (
    "真实行情驱动的合成订单研究; lake boundary attestation != host PASS "
    "or item-4 live PASS or green R; source validation is not host certification."
)

_RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")

# Tip source_loader / CLI / Phase5 gaps this knife documents/hardens (TC1 §5 X6).
TIP_GAP_CHECKS = (
    {
        "id": "source_kind_lake_only",
        "tip": "source_loader accepts source_kind in {lake, synthetic_fixture}",
        "harden": (
            "X6 lake tool accepts only lake; refuses synthetic_fixture "
            "masquerading as lake pass (symmetric to #307)"
        ),
    },
    {
        "id": "cli_evidence_still_synthetic_only",
        "tip": (
            "#309/#310 X6 tools themselves do not unlock backend CLI lake; "
            "CLI lake is a separate residual (see note-true-core-cli-lake)"
        ),
        "harden": (
            "boundary evidence_level=lake_boundary only; this tool does NOT "
            "unlock CLI --evidence-level=lake (backend CLI lake is separate)"
        ),
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
        "id": "bar_end_phase5_research_path",
        "tip": (
            "source_loader bars require availability=bucket_end and "
            "time.label in {START, END}"
        ),
        "harden": (
            "X6 lake research path requires bar_time_label=END + "
            "availability=bucket_end (Phase5); read-only; no lake write"
        ),
    },
    {
        "id": "lake_boundary_not_host_pass",
        "tip": (
            "lake source_kind notice = 真实行情驱动的合成订单研究; "
            "source validation is not host certification"
        ),
        "harden": (
            "notice must contain lake boundary attestation != host PASS; "
            "no lake_pass / host / green R / item4 promotion claims"
        ),
    },
)


class LakeDifferentialError(ValueError):
    """Differential refused before or during write."""


@dataclass(frozen=True)
class LakeDifferentialOutcome:
    """In-memory + optional on-disk differential result."""

    tool_id: str
    differential_status: str
    report: Mapping[str, Any]
    root: Path | None
    report_path: Path | None


def differential_root(parent: str | Path, run_id: str) -> Path:
    if not _RUN_ID_RE.fullmatch(run_id):
        raise LakeDifferentialError(
            "run_id must be a single safe ASCII path component"
        )
    return Path(parent).resolve() / DIFFERENTIAL_ROOT_NAME / run_id


def build_differential_report(meta: LakeBoundaryMeta) -> dict[str, Any]:
    """Build red-label lake boundary differential report."""
    if REQUIRED_NOTICE_TOKEN not in meta.notice:
        raise LakeDifferentialError(
            "meta notice missing lake boundary attestation != host PASS token"
        )

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
        "read_only": True,
        "label": (
            "X6 lake END / loader boundary differential · "
            "lake boundary attestation != host PASS · ≠δ5≠R4 · no lake write"
        ),
        "contract": CONTRACT,
        "backend_id_documented": BACKEND_ID,
        "note": (
            "tool_id is NOT a backend_id; no new economic contract; "
            "does not call load_minute_orders_source / MatchCore / Fees / simulate; "
            "independent tool root; no success summary.json; forever opt-in; "
            "never BOOKS default; read-only lake END boundary; "
            "this tool does NOT unlock CLI --evidence-level=lake "
            "(backend CLI lake is a separate residual); "
            "does NOT claim lake PASS / host attestation / item-4 live / green R"
        ),
        "lake_boundary_notice": LAKE_BOUNDARY_NOTICE,
        "boundary": {
            "schema": meta.schema,
            "source_kind": meta.source_kind,
            "evidence_level": meta.evidence_level,
            "account_origin": meta.account_origin,
            "commands_origin": meta.commands_origin,
            "bar_time_label": meta.bar_time_label,
            "availability": meta.availability,
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
            "bar_time_label": ALLOWED_BAR_TIME_LABEL,
            "availability": ALLOWED_AVAILABILITY,
            "notice_token": REQUIRED_NOTICE_TOKEN,
            "lake_boundary_is_not_host_pass": True,
            "fixture_pass_is_not_lake_pass": True,
            "cli_evidence_level_unlocked": False,
            "host_attestation": False,
            "comparison_authorization": False,
            "green_r": False,
            "lake_write": False,
            "read_only": True,
        },
        "bans": [
            "no_lake_write",
            "no_synthetic_fixture_masquerade",
            "no_cli_evidence_level_lake_unlock",
            "no_host_attestation_claim",
            "no_lake_pass_claim",
            "no_green_r",
            "no_success_summary_json",
            "no_new_contract",
            "no_new_backend_id",
            "no_matchcore_fees_simulate_edit",
            "no_load_minute_orders_source_call",
            "not_delta5_certified",
            "not_r4",
            "not_books_default",
            "forever_opt_in",
            "independent_tool_root",
            "read_only_lake_end_boundary",
        ],
    }


def write_differential_report(
    report: Mapping[str, Any],
    *,
    parent: str | Path,
    run_id: str,
) -> tuple[Path, Path]:
    """Write differential_report.json under the independent tool root.

    Refuses existing roots. Never writes summary.json. Never writes lake.
    """
    root = differential_root(parent, run_id)
    if root.exists():
        raise FileExistsError(
            f"differential root already exists (refuse overwrite): {root}"
        )
    parts = {p.lower() for p in root.parts}
    if "minute_orders_research_v1" in parts:
        raise LakeDifferentialError(
            "differential root must NOT be under minute_orders_research_v1"
        )
    root.mkdir(parents=True, exist_ok=False)
    report_path = root / REPORT_FILENAME
    forbidden = root / FORBIDDEN_SUMMARY_NAME
    if forbidden.exists():
        raise LakeDifferentialError(
            f"refusing to publish beside existing {FORBIDDEN_SUMMARY_NAME}"
        )
    payload = json.dumps(report, ensure_ascii=True, sort_keys=True, indent=2) + "\n"
    report_path.write_text(payload, encoding="utf-8")
    if (root / FORBIDDEN_SUMMARY_NAME).exists():
        raise LakeDifferentialError("internal error: summary.json must not be written")
    return root, report_path


def run_x6_lake_differential(
    meta: LakeBoundaryMeta,
    *,
    parent: str | Path | None = None,
    run_id: str | None = None,
) -> LakeDifferentialOutcome:
    """Validate lake boundary meta → differential report; optional root write."""
    report = build_differential_report(meta)
    if report["differential_status"] != DIFFERENTIAL_STATUS:
        raise LakeDifferentialError(
            "differential_status must stay lake_boundary_attested_not_host_pass"
        )
    if report["boundary"]["source_kind"] != ALLOWED_SOURCE_KIND:
        raise LakeDifferentialError("report source_kind drifted from lake")
    if report["boundary"]["bar_time_label"] != ALLOWED_BAR_TIME_LABEL:
        raise LakeDifferentialError("report bar_time_label drifted from END")
    if report["invariants"]["lake_write"] is not False:
        raise LakeDifferentialError("lake_write invariant must stay False")

    root = report_path = None
    if parent is not None or run_id is not None:
        if parent is None or run_id is None:
            raise LakeDifferentialError("parent and run_id must be supplied together")
        root, report_path = write_differential_report(
            report, parent=parent, run_id=run_id,
        )
    return LakeDifferentialOutcome(
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
    "FORBIDDEN_SUMMARY_NAME",
    "LAKE_BOUNDARY_NOTICE",
    "REPORT_FILENAME",
    "REPORT_SCHEMA",
    "TIP_GAP_CHECKS",
    "TOOL_ID",
    "LakeDifferentialError",
    "LakeDifferentialOutcome",
    "build_differential_report",
    "differential_root",
    "run_x6_lake_differential",
    "write_differential_report",
]
