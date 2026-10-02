"""True-core residual R2 · write-lake staging dry-run policy (NOT production write).

This fork is consume-only for market bars (AGENTS.md). Real Phase4 lake writes
live on host / OSkhQuant1.3 + vendor_to_lake_adapter ownership. This residual
knife only plans / audits an independent staging dry-run and lists MUST Human
cuts before any production write can be authorized.

tool_id is tooling identity only — NOT a backend_id.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

TOOL_ID = "minute_orders_write_lake_staging"
# tool_id ≠ backend_id / economic contract.
CONTRACT = "research contract v0 (L2-S0)"
BACKEND_ID = "minute_orders_research_v1"

STAGING_ROOT_NAME = "minute_orders_write_lake_staging"
STAGING_STATUS = "write_lake_staging_dry_run_not_production_write"
REPORT_SCHEMA = "minute_orders_write_lake_staging_report_v0"
REPORT_FILENAME = "staging_dry_run_report.json"
FORBIDDEN_SUMMARY_NAME = "summary.json"
PLAN_FILENAME = "MUST_HUMAN_CUTS.json"

NOTICE = (
    "write-lake residual staging dry-run != production lake write "
    "!= host PASS != item-4 live != green R; "
    "this fork remains consume-only; Phase4 production write needs separate "
    "named Human cuts + explicit host/1.3 owner."
)

# Reuse vendor Phase2 path-protection spelling (stock_data component + configured roots).
PROTECTED_PATH_TOKENS = ("stock_data",)
PROTECTED_ENV_ROOTS = (
    "OSKH_SOURCE_PARQUET_ROOT",
    "OSKH_PERIOD_1D_ROOT",
    "OSKH_PERIOD_1M_ROOT",
    "OSKH_AUTHORITY_HINT_ROOT",
    "OSKH_DATA_ROOT",
)

# Keys that would claim production write / promotion — banned in request payloads.
BANNED_REQUEST_KEYS = frozenset({
    "write_lake",
    "write_lake_path",
    "lake_write",
    "lake_write_path",
    "production_write",
    "overwrite_lake",
    "host_attestation",
    "green_r",
    "nav_rank",
    "summary",
    "fills",
    "trades",
})

# MUST Human cuts before any production write GO can be considered complete.
MUST_HUMAN_CUTS: tuple[dict[str, str], ...] = (
    {
        "id": "owner",
        "cut": (
            "Name the production write owner: host agent / OSkhQuant1.3 download "
            "transport / vendor merge — NOT this research fork as default writer "
            "(AGENTS.md consume-only)."
        ),
    },
    {
        "id": "target_pin",
        "cut": (
            "Pin exact lake root, underscore hive symbols, periods {1m,1d}, "
            "dividend_type, and expected sha256 of sources; no wildcards."
        ),
    },
    {
        "id": "no_borrow_receipt",
        "cut": (
            "Do not borrow vendor three-symbol Phase4/Phase5 PASS receipts as "
            "authority for this true-core residual chain write."
        ),
    },
    {
        "id": "rollback",
        "cut": (
            "Name rollback: never overwrite existing lake partitions in place; "
            "new write must be additive or explicitly Human-approved replace "
            "with backup path."
        ),
    },
    {
        "id": "no_write_flag_in_tip",
        "cut": (
            "This tip knife must NOT grow a --write-lake production flag; "
            "staging dry-run only until a separate named production-write GO."
        ),
    },
    {
        "id": "locks",
        "cut": (
            "Keep locks: empty MatchCore/Fees/simulate/source_loader; ≠δ5≠R4; "
            "never BOOKS; forever opt-in; no green R; no 4090 unless separately GO'd."
        ),
    },
    {
        "id": "budget",
        "cut": (
            "Re-estimate budget separately (H-TC8); C already-opened does not "
            "absorb write-lake into the original 1–2 person-week envelope."
        ),
    },
)


class WriteLakeStagingError(ValueError):
    """Staging dry-run refused (protected path / promotion / schema)."""


def _path_spellings(path: Path) -> tuple[str, str]:
    return (str(path), str(path.resolve()))


def _refuse_protected_components(path: Path) -> None:
    for spelling in _path_spellings(path):
        parts = re.split(r"[/\\]+", spelling.lower())
        for token in PROTECTED_PATH_TOKENS:
            if token in parts:
                raise WriteLakeStagingError(
                    f"protected {token} lake path; production write needs "
                    "separate named Human write-lake GO + host/1.3 owner"
                )
    resolved = path.resolve()
    for key in PROTECTED_ENV_ROOTS:
        raw = os.environ.get(key)
        if not raw:
            continue
        root = Path(raw).resolve()
        if resolved == root or root in resolved.parents:
            raise WriteLakeStagingError(
                f"protected configured lake root via {key}; staging only"
            )


def assert_staging_out_dir(path: Path) -> Path:
    """Refuse production lake roots; require new/empty independent staging dir."""
    _refuse_protected_components(path)
    out = path.resolve()
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        raise WriteLakeStagingError(
            "staging out-dir must be new or empty; never overwrite"
        )
    return out


def assert_not_production_target(path: Path) -> Path:
    """Refuse protected lake roots for any proposed target in a plan request.

    Unlike assert_staging_out_dir, does not require the path to be empty —
    used only to reject production targets named inside a dry-run request.
    """
    _refuse_protected_components(path)
    return path.resolve()


def must_human_cuts_payload() -> dict:
    return {
        "schema": "minute_orders_write_lake_must_human_cuts_v0",
        "tool_id": TOOL_ID,
        "staging_status": STAGING_STATUS,
        "notice": NOTICE,
        "cuts": list(MUST_HUMAN_CUTS),
        "non_claims": [
            "not_production_lake_write",
            "not_delta5_certified",
            "not_R4",
            "not_host_pass",
            "not_green_r",
            "not_borrow_vendor_phase4_receipt",
            "no_MatchCore_Fees_simulate_rewrite",
            "forever_opt_in",
            "never_BOOKS_default",
            "tool_id_not_backend_id",
        ],
    }
