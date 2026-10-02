"""Staging dry-run planner for true-core write-lake residual (no lake write)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .policy import (
    BACKEND_ID,
    BANNED_REQUEST_KEYS,
    CONTRACT,
    FORBIDDEN_SUMMARY_NAME,
    MUST_HUMAN_CUTS,
    NOTICE,
    PLAN_FILENAME,
    REPORT_FILENAME,
    REPORT_SCHEMA,
    STAGING_ROOT_NAME,
    STAGING_STATUS,
    TOOL_ID,
    WriteLakeStagingError,
    assert_not_production_target,
    assert_staging_out_dir,
    must_human_cuts_payload,
)

_RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
REQUEST_SCHEMA = "minute_orders_write_lake_staging_request_v0"
ALLOWED_MODE = "staging_dry_run"


@dataclass(frozen=True)
class StagingRequest:
    schema: str
    mode: str
    proposed_symbols: tuple[str, ...]
    proposed_periods: tuple[str, ...]
    proposed_staging_layout: str
    notice: str
    raw: Mapping[str, Any]


@dataclass(frozen=True)
class StagingOutcome:
    tool_id: str
    staging_status: str
    report_path: Path
    cuts_path: Path
    report: Mapping[str, Any]


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise WriteLakeStagingError(msg)


def load_staging_request(path: Path) -> StagingRequest:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WriteLakeStagingError(f"cannot read staging request: {exc}") from exc
    return request_from_mapping(payload)


def request_from_mapping(payload: Mapping[str, Any]) -> StagingRequest:
    _require(isinstance(payload, dict), "staging request must be a JSON object")
    banned = sorted(BANNED_REQUEST_KEYS & set(payload))
    _require(not banned, f"banned top-level keys for write-lake staging: {banned}")

    schema = payload.get("schema")
    _require(
        schema == REQUEST_SCHEMA,
        f"unsupported schema {schema!r}; expected {REQUEST_SCHEMA}",
    )

    mode = payload.get("mode")
    _require(
        mode == ALLOWED_MODE,
        f"mode must be {ALLOWED_MODE!r} (got {mode!r}); "
        "production write is not available in this knife",
    )

    symbols = payload.get("proposed_symbols")
    _require(isinstance(symbols, list) and symbols, "proposed_symbols required")
    _require(all(isinstance(s, str) and s.strip() for s in symbols),
             "proposed_symbols must be non-empty strings")

    periods = payload.get("proposed_periods")
    _require(isinstance(periods, list) and periods, "proposed_periods required")
    allowed_periods = {"1m", "1d"}
    bad = [p for p in periods if p not in allowed_periods]
    _require(not bad, f"proposed_periods only allow {sorted(allowed_periods)}; got {bad}")

    layout = payload.get("proposed_staging_layout")
    _require(
        layout == "hive_underscore_end_lots_sparse_a",
        "proposed_staging_layout must be hive_underscore_end_lots_sparse_a "
        "(mirrors vendor Phase2 staging contract; not a production write)",
    )

    notice = payload.get("notice")
    _require(isinstance(notice, str) and "staging dry-run" in notice.lower(),
             "notice must mention staging dry-run")
    _require("production" in notice.lower() or "not production" in notice.lower()
             or "!=" in notice or "≠" in notice,
             "notice must disclaim production write")

    # Optional proposed_target_hint — if present, must not be a protected lake path.
    hint = payload.get("proposed_target_hint")
    if hint is not None:
        _require(isinstance(hint, str) and hint.strip(),
                 "proposed_target_hint must be a non-empty string when set")
        assert_not_production_target(Path(hint))

    return StagingRequest(
        schema=schema,
        mode=mode,
        proposed_symbols=tuple(symbols),
        proposed_periods=tuple(periods),
        proposed_staging_layout=layout,
        notice=notice,
        raw=dict(payload),
    )


def _validate_run_id(run_id: str) -> str:
    _require(isinstance(run_id, str) and bool(_RUN_ID_RE.match(run_id)),
             f"invalid run_id {run_id!r}")
    return run_id


def run_write_lake_staging_dry_run(
    *,
    request: StagingRequest,
    parent: Path,
    run_id: str,
) -> StagingOutcome:
    """Plan a staging dry-run under an independent tool root; never write the lake."""
    run_id = _validate_run_id(run_id)
    parent = Path(parent)
    _require(parent.is_absolute(), "parent must be an absolute path")

    root = parent / "backtest_output" / STAGING_ROOT_NAME / run_id
    assert_staging_out_dir(root)
    root.mkdir(parents=True, exist_ok=False)

    report = {
        "schema": REPORT_SCHEMA,
        "tool_id": TOOL_ID,
        "contract": CONTRACT,
        "backend_id_label_only": BACKEND_ID,
        "staging_status": STAGING_STATUS,
        "notice": NOTICE,
        "run_id": run_id,
        "parent": str(parent),
        "mode": request.mode,
        "proposed_symbols": list(request.proposed_symbols),
        "proposed_periods": list(request.proposed_periods),
        "proposed_staging_layout": request.proposed_staging_layout,
        "request_notice": request.notice,
        "must_human_cuts": [c["id"] for c in MUST_HUMAN_CUTS],
        "pointer_vendor_phase2_staging": (
            "docs/backtest/vendor-three-symbol-lake-ingest-2026-10-01/PLAN.md"
        ),
        "pointer_vendor_adapter": "scripts/research/vendor_to_lake_adapter.py",
        "bans": [
            "no_production_lake_write",
            "no_--write-lake_flag",
            "no_MatchCore_Fees_simulate_rewrite",
            "no_source_loader_rewrite",
            "no_4090_unless_separate_GO",
            "no_borrow_vendor_phase4_as_this_chain_authority",
            "no_summary.json",
            "no_green_r",
            "forever_opt_in",
            "never_BOOKS_default",
            "tool_id_not_backend_id",
            "not_delta5_certified",
            "not_R4",
        ],
    }

    report_path = root / REPORT_FILENAME
    cuts_path = root / PLAN_FILENAME
    if (root / FORBIDDEN_SUMMARY_NAME).exists():
        raise WriteLakeStagingError(
            f"refuses to co-exist with {FORBIDDEN_SUMMARY_NAME}"
        )

    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    cuts_path.write_text(
        json.dumps(must_human_cuts_payload(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    # Re-entry guard: same run_id must FileExistsError via mkdir(exist_ok=False)
    # already enforced; also refuse if caller tries again after success.
    return StagingOutcome(
        tool_id=TOOL_ID,
        staging_status=STAGING_STATUS,
        report_path=report_path,
        cuts_path=cuts_path,
        report=report,
    )


def write_report_only_guard(root: Path) -> None:
    """Helper for tests: ensure no success summary under the staging root."""
    summary = root / FORBIDDEN_SUMMARY_NAME
    if summary.exists():
        raise WriteLakeStagingError(
            f"staging root must not contain {FORBIDDEN_SUMMARY_NAME}"
        )
