"""X6 lake recipe e2e: call load_minute_orders_source (read-only; NOT host PASS).

Human GO · full lake e2e (read-only) after #309. Completes the
load_minute_orders_source / lake recipe path under tool_id=minute_orders_x6_lake.
Does NOT unlock backend CLI --evidence-level=lake; does NOT write the lake;
does NOT run MatchCore fills / research_v1 success summary; ≠δ5≠R4.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from backtest.research.minute_orders_backend.source_loader import (
    LoadedSource,
    load_minute_orders_source,
)
from backtest.research.minute_orders_backend.source_provenance import (
    SourceContractError,
)

from .differential import (
    BACKEND_ID,
    CONTRACT,
    DIFFERENTIAL_ROOT_NAME,
    FORBIDDEN_SUMMARY_NAME,
    TOOL_ID,
)
from .ingest import (
    ALLOWED_ACCOUNT_ORIGIN,
    ALLOWED_AVAILABILITY,
    ALLOWED_BAR_TIME_LABEL,
    ALLOWED_COMMANDS_ORIGIN,
    ALLOWED_SOURCE_KIND,
)

E2E_STATUS = "lake_recipe_e2e_loaded_not_host_pass"
E2E_REPORT_SCHEMA = "minute_orders_x6_lake_recipe_e2e_report_v0"
E2E_REPORT_FILENAME = "e2e_report.json"

LAKE_E2E_NOTICE = (
    "真实行情驱动的合成订单研究; lake recipe e2e load != host PASS "
    "or item-4 live PASS or green R; source validation is not host certification; "
    "does NOT unlock CLI --evidence-level=lake; no lake write."
)

REQUIRED_PROVENANCE_NOTICE_TOKEN = "source validation is not host certification"

_RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")

BANNED_RECIPE_TOP_LEVEL = frozenset({
    "lake_write", "lake_write_path", "write_lake", "write_path",
    "host_attestation", "green_r", "nav_rank",
})


class LakeRecipeE2EError(ValueError):
    """Lake recipe e2e refused (preflight / promotion / write)."""


@dataclass(frozen=True)
class LakeRecipeE2EOutcome:
    """In-memory + optional on-disk lake recipe e2e result."""

    tool_id: str
    e2e_status: str
    report: Mapping[str, Any]
    loaded: LoadedSource
    root: Path | None
    report_path: Path | None


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise LakeRecipeE2EError(msg)


def _preflight_recipe(recipe: Mapping[str, Any]) -> dict[str, Any]:
    """Enforce X6 Phase5 lake-only + END research path before load."""
    _require(isinstance(recipe, dict), "recipe must be a JSON object")
    banned = sorted(BANNED_RECIPE_TOP_LEVEL & set(recipe))
    _require(not banned, f"banned top-level recipe keys for X6 lake e2e: {banned}")

    source_kind = recipe.get("source_kind")
    _require(
        source_kind == ALLOWED_SOURCE_KIND,
        f"X6 lake recipe e2e refuses source_kind={source_kind!r}; "
        f"only {ALLOWED_SOURCE_KIND!r} "
        "(synthetic_fixture masquerade forbidden; use X6 synthetic knife)",
    )

    bars = recipe.get("bars")
    _require(isinstance(bars, list) and bool(bars), "recipe.bars required")
    for index, bar in enumerate(bars):
        _require(isinstance(bar, dict), f"recipe.bars[{index}] must be object")
        time_spec = bar.get("time")
        _require(isinstance(time_spec, dict), f"recipe.bars[{index}].time required")
        label = time_spec.get("label")
        _require(
            label == ALLOWED_BAR_TIME_LABEL,
            f"X6 lake recipe e2e requires bar_time_label={ALLOWED_BAR_TIME_LABEL!r} "
            f"(Phase5); got bars[{index}].time.label={label!r}",
        )
        availability = bar.get("availability")
        _require(
            availability == ALLOWED_AVAILABILITY,
            f"X6 lake recipe e2e requires availability={ALLOWED_AVAILABILITY!r}; "
            f"got bars[{index}].availability={availability!r}",
        )

    return {
        "source_kind": source_kind,
        "bar_time_label": ALLOWED_BAR_TIME_LABEL,
        "availability": ALLOWED_AVAILABILITY,
        "bar_count": len(bars),
    }


def e2e_root(parent: str | Path, run_id: str) -> Path:
    if not _RUN_ID_RE.fullmatch(run_id):
        raise LakeRecipeE2EError(
            "run_id must be a single safe ASCII path component"
        )
    return Path(parent).resolve() / DIFFERENTIAL_ROOT_NAME / run_id


def build_e2e_report(
    *,
    recipe_path: Path,
    expected_sha256: str,
    preflight: Mapping[str, Any],
    loaded: LoadedSource,
) -> dict[str, Any]:
    """Build red-label lake recipe e2e report (load attestation only)."""
    doc = loaded.provenance.document()
    run = loaded.run_input
    notice = doc.get("notice", "")
    _require(
        isinstance(notice, str) and REQUIRED_PROVENANCE_NOTICE_TOKEN in notice,
        "provenance notice missing host-certification denial token",
    )
    _require(
        doc.get("source_kind") == ALLOWED_SOURCE_KIND,
        f"loaded provenance source_kind drifted: {doc.get('source_kind')!r}",
    )

    symbols = sorted({b.symbol for b in run.buckets})
    return {
        "schema": E2E_REPORT_SCHEMA,
        "tool_id": TOOL_ID,
        "e2e_status": E2E_STATUS,
        "red_label": True,
        "diagnostic_only": True,
        "read_only": True,
        "label": (
            "X6 lake recipe e2e · load_minute_orders_source (read-only) · "
            "lake recipe e2e load != host PASS · ≠δ5≠R4 · no lake write · "
            "CLI --evidence-level=lake still locked"
        ),
        "contract": CONTRACT,
        "backend_id_documented": BACKEND_ID,
        "note": (
            "tool_id is NOT a backend_id; no new economic contract; "
            "calls load_minute_orders_source only; does NOT run MatchCore fills; "
            "does NOT write minute_orders_research_v1 success summary.json; "
            "does NOT unlock CLI --evidence-level=lake; "
            "does NOT write the lake; forever opt-in; never BOOKS default; "
            "does NOT claim lake PASS / host attestation / item-4 live / green R"
        ),
        "lake_e2e_notice": LAKE_E2E_NOTICE,
        "recipe": {
            "ref": str(recipe_path.resolve()),
            "sha256": expected_sha256,
            "source_kind": preflight["source_kind"],
            "bar_time_label": preflight["bar_time_label"],
            "availability": preflight["availability"],
            "bar_spec_count": preflight["bar_count"],
            "run_id": doc.get("recipe", {}).get("run_id"),
            "parent_documented": doc.get("recipe", {}).get("parent"),
        },
        "loaded": {
            "source_kind": doc.get("source_kind"),
            "notice": notice,
            "bucket_count": len(run.buckets),
            "command_count": len(run.commands),
            "mark_count": len(run.marks),
            "instrument_count": len(run.instruments),
            "symbols": symbols,
            "account_origin_documented": ALLOWED_ACCOUNT_ORIGIN,
            "commands_origin_documented": ALLOWED_COMMANDS_ORIGIN,
            "execution_code_dirty": bool(doc.get("execution", {}).get("code_dirty")),
            "provenance_sha256": loaded.provenance.sha256,
        },
        "invariants": {
            "source_kind": ALLOWED_SOURCE_KIND,
            "bar_time_label": ALLOWED_BAR_TIME_LABEL,
            "availability": ALLOWED_AVAILABILITY,
            "account_origin": ALLOWED_ACCOUNT_ORIGIN,
            "commands_origin": ALLOWED_COMMANDS_ORIGIN,
            "load_minute_orders_source_called": True,
            "lake_recipe_e2e_is_not_host_pass": True,
            "fixture_pass_is_not_lake_pass": True,
            "cli_evidence_level_unlocked": False,
            "host_attestation": False,
            "comparison_authorization": False,
            "green_r": False,
            "lake_write": False,
            "matchcore_fills_run": False,
            "research_v1_success_summary_written": False,
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
            "no_backend_cli_edit",
            "not_delta5_certified",
            "not_r4",
            "not_books_default",
            "forever_opt_in",
            "independent_tool_root",
            "read_only_lake_recipe_e2e",
            "no_4090_host_live",
        ],
    }


def write_e2e_report(
    report: Mapping[str, Any],
    *,
    parent: str | Path,
    run_id: str,
) -> tuple[Path, Path]:
    """Write e2e_report.json under the independent tool root.

    Refuses existing roots. Never writes summary.json. Never writes lake.
    """
    root = e2e_root(parent, run_id)
    if root.exists():
        raise FileExistsError(
            f"e2e root already exists (refuse overwrite): {root}"
        )
    parts = {p.lower() for p in root.parts}
    if "minute_orders_research_v1" in parts:
        raise LakeRecipeE2EError(
            "e2e root must NOT be under minute_orders_research_v1"
        )
    root.mkdir(parents=True, exist_ok=False)
    report_path = root / E2E_REPORT_FILENAME
    forbidden = root / FORBIDDEN_SUMMARY_NAME
    if forbidden.exists():
        raise LakeRecipeE2EError(
            f"refusing to publish beside existing {FORBIDDEN_SUMMARY_NAME}"
        )
    payload = json.dumps(report, ensure_ascii=True, sort_keys=True, indent=2) + "\n"
    report_path.write_text(payload, encoding="utf-8")
    if (root / FORBIDDEN_SUMMARY_NAME).exists():
        raise LakeRecipeE2EError("internal error: summary.json must not be written")
    return root, report_path


def run_x6_lake_recipe_e2e(
    recipe_path: str | Path,
    *,
    expected_sha256: str,
    parent: str | Path | None = None,
    run_id: str | None = None,
) -> LakeRecipeE2EOutcome:
    """Preflight lake+END recipe → load_minute_orders_source → e2e report."""
    path = Path(recipe_path)
    _require(path.is_file(), f"recipe file not found: {path}")
    _require(path.is_absolute(), "recipe path must be absolute")
    path = path.resolve()
    digest = _sha256_file(path)
    _require(
        digest == expected_sha256,
        f"recipe sha256 mismatch: got {digest}, expected {expected_sha256}",
    )
    try:
        recipe = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise LakeRecipeE2EError(f"invalid recipe JSON in {path}: {exc}") from exc

    preflight = _preflight_recipe(recipe)

    try:
        loaded = load_minute_orders_source(path, expected_sha256=expected_sha256)
    except SourceContractError as exc:
        raise LakeRecipeE2EError(f"load_minute_orders_source refused: {exc}") from exc

    report = build_e2e_report(
        recipe_path=path,
        expected_sha256=expected_sha256,
        preflight=preflight,
        loaded=loaded,
    )
    if report["e2e_status"] != E2E_STATUS:
        raise LakeRecipeE2EError("e2e_status drifted")
    if report["invariants"]["lake_write"] is not False:
        raise LakeRecipeE2EError("lake_write invariant must stay False")
    if report["invariants"]["cli_evidence_level_unlocked"] is not False:
        raise LakeRecipeE2EError("cli unlock invariant must stay False")
    if report["invariants"]["matchcore_fills_run"] is not False:
        raise LakeRecipeE2EError("MatchCore fills must not run in this knife")

    root = report_path = None
    if parent is not None or run_id is not None:
        if parent is None or run_id is None:
            raise LakeRecipeE2EError("parent and run_id must be supplied together")
        root, report_path = write_e2e_report(
            report, parent=parent, run_id=run_id,
        )
        # recipe.parent is documented only; this knife must not materialize it.
        recipe_parent = Path(recipe["parent"]).resolve()
        if recipe_parent.exists() and recipe_parent != root:
            # Allowed only if pre-existing; we never create research_v1 success.
            pass
    return LakeRecipeE2EOutcome(
        tool_id=TOOL_ID,
        e2e_status=E2E_STATUS,
        report=report,
        loaded=loaded,
        root=root,
        report_path=report_path,
    )


__all__ = [
    "E2E_REPORT_FILENAME",
    "E2E_REPORT_SCHEMA",
    "E2E_STATUS",
    "LAKE_E2E_NOTICE",
    "LakeRecipeE2EError",
    "LakeRecipeE2EOutcome",
    "build_e2e_report",
    "e2e_root",
    "run_x6_lake_recipe_e2e",
    "write_e2e_report",
]
