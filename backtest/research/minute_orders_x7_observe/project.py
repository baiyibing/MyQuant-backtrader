"""A·X7 observation projector: already-obtained reports → red-label slice.

Does NOT recalculate NAV, does NOT invent fills, does NOT touch
backtest.research.run_protocol.views._FAMILIES.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .policy import (
    ALLOWED_SOURCE_KINDS,
    BACKEND_ID,
    BANNED_SOURCE_KEYS,
    CONTRACT,
    FORBIDDEN_SUMMARY_NAME,
    NOTICE,
    OBSERVATION_ID,
    OBSERVATION_ROOT_NAME,
    OBSERVATION_STATUS,
    REPORT_FILENAME,
    REPORT_SCHEMA,
    X7_PROJECTION_FAMILY,
    ObserveError,
    assert_not_views_families_registration,
)

_RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
REQUEST_SCHEMA = "minute_orders_x7_observe_request_v0"


def _iter_mapping_nodes(node: Any, path: str = "") -> list[tuple[str, Mapping[str, Any]]]:
    """Yield (path, mapping) for node and every nested dict (incl. list items)."""
    out: list[tuple[str, Mapping[str, Any]]] = []
    if isinstance(node, Mapping):
        out.append((path or "$", node))
        for key, value in node.items():
            child = f"{path}.{key}" if path else str(key)
            out.extend(_iter_mapping_nodes(value, child))
    elif isinstance(node, list):
        for idx, value in enumerate(node):
            child = f"{path}[{idx}]" if path else f"[{idx}]"
            out.extend(_iter_mapping_nodes(value, child))
    return out


def _refuse_banned_keys_recursive(payload: Mapping[str, Any], *, where: str) -> None:
    """Refuse BANNED_SOURCE_KEYS, nav/equity substrings, and views_family anywhere."""
    for path, mapping in _iter_mapping_nodes(payload):
        banned = sorted(BANNED_SOURCE_KEYS & set(mapping))
        _require(
            not banned,
            f"banned keys under {where} at {path}: {banned}",
        )
        for key in mapping:
            lowered = str(key).lower()
            _require(
                "nav" not in lowered and "equity" not in lowered,
                f"X7 refuses NAV/equity rewrite field {key!r} under {where} at {path}",
            )
            _require(
                lowered != "views_family",
                f"views_family is forbidden under {where} at {path}; "
                "X7 uses a new projection entry, never views._FAMILIES",
            )



@dataclass(frozen=True)
class ObserveRequest:
    schema: str
    source_kind: str
    source_label: str
    evidence_fields: Mapping[str, Any]
    notice: str
    raw: Mapping[str, Any]


@dataclass(frozen=True)
class ObservationOutcome:
    observation_id: str
    observation_status: str
    report_path: Path | None
    report: Mapping[str, Any]
    root: Path | None


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise ObserveError(msg)


def load_observe_request(path: Path) -> ObserveRequest:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ObserveError(f"cannot read observation request: {exc}") from exc
    return request_from_mapping(payload)


def request_from_mapping(payload: Mapping[str, Any]) -> ObserveRequest:
    _require(isinstance(payload, dict), "observation request must be a JSON object")
    # Recursive refuse: top-level + nested dicts/lists (incl. evidence_fields blobs).
    _refuse_banned_keys_recursive(payload, where="observation request")

    schema = payload.get("schema")
    _require(
        schema == REQUEST_SCHEMA,
        f"unsupported schema {schema!r}; expected {REQUEST_SCHEMA}",
    )

    source_kind = payload.get("source_kind")
    _require(
        source_kind in ALLOWED_SOURCE_KINDS,
        f"source_kind {source_kind!r} not in allowed already-obtained kinds "
        f"{sorted(ALLOWED_SOURCE_KINDS)}",
    )

    source_label = payload.get("source_label")
    _require(
        isinstance(source_label, str) and source_label.strip(),
        "source_label must be a non-empty string",
    )

    # Optional nested evidence: pass-through only; never invent.
    evidence = payload.get("evidence_fields")
    if evidence is None:
        evidence = {}
    _require(isinstance(evidence, dict), "evidence_fields must be an object when set")

    notice = payload.get("notice")
    _require(isinstance(notice, str) and notice.strip(), "notice required")
    lowered_notice = notice.lower()
    _require(
        "observation" in lowered_notice or "观察" in notice,
        "notice must mention observation",
    )
    _require(
        "green" in lowered_notice or "绿" in notice or "≠" in notice or "!=" in notice,
        "notice must disclaim green R / NAV upgrade",
    )

    return ObserveRequest(
        schema=schema,
        source_kind=source_kind,
        source_label=source_label,
        evidence_fields=dict(evidence),
        notice=notice,
        raw=dict(payload),
    )


def _validate_run_id(run_id: str) -> str:
    _require(
        isinstance(run_id, str) and bool(_RUN_ID_RE.match(run_id)),
        f"invalid run_id {run_id!r}",
    )
    return run_id


def project_observation_slice(request: ObserveRequest) -> dict[str, Any]:
    """Build an in-memory observation slice (pass-through; no NAV rewrite)."""
    return {
        "projection_family": X7_PROJECTION_FAMILY,
        "source_kind": request.source_kind,
        "source_label": request.source_label,
        "evidence_fields": dict(request.evidence_fields),
        "views_families_registration": assert_not_views_families_registration(),
        "nav_rewrite": "forbidden",
        "green_r": "forbidden",
    }


def run_x7_observe(
    *,
    request: ObserveRequest,
    parent: Path | None = None,
    run_id: str | None = None,
    memory_only: bool = False,
) -> ObservationOutcome:
    """Project already-obtained evidence into a red-label observation report."""
    slice_ = project_observation_slice(request)
    report: dict[str, Any] = {
        "schema": REPORT_SCHEMA,
        "observation_id": OBSERVATION_ID,
        "contract": CONTRACT,
        "backend_id_label_only": BACKEND_ID,
        "observation_status": OBSERVATION_STATUS,
        "notice": NOTICE,
        "request_notice": request.notice,
        "slice": slice_,
        "bans": [
            "no_views_FAMILIES_registration",
            "no_NAV_rewrite",
            "no_green_r",
            "no_summary.json",
            "no_production_lake_write",
            "no_4090_unless_separate_GO",
            "no_MatchCore_Fees_simulate_rewrite",
            "no_new_contract_mint",
            "no_new_backend_id_mint",
            "forever_opt_in",
            "never_BOOKS_default",
            "observation_id_not_backend_id",
            "not_delta5_certified",
            "not_R4",
            "observation_neq_green_r",
        ],
    }

    if memory_only:
        _require(parent is None and run_id is None,
                 "memory_only forbids parent/run_id")
        return ObservationOutcome(
            observation_id=OBSERVATION_ID,
            observation_status=OBSERVATION_STATUS,
            report_path=None,
            report=report,
            root=None,
        )

    _require(parent is not None and run_id is not None,
             "parent and run_id required unless memory_only")
    run_id = _validate_run_id(run_id)  # type: ignore[arg-type]
    parent_path = Path(parent)  # type: ignore[arg-type]
    _require(parent_path.is_absolute(), "parent must be an absolute path")

    root = parent_path / "backtest_output" / OBSERVATION_ROOT_NAME / run_id
    try:
        root.mkdir(parents=True, exist_ok=False)
    except FileExistsError as exc:
        raise ObserveError(
            f"observation root already exists for run_id={run_id!r}: {root}"
        ) from exc
    report["run_id"] = run_id
    report["parent"] = str(parent_path)

    if (root / FORBIDDEN_SUMMARY_NAME).exists():
        raise ObserveError(f"refuses to co-exist with {FORBIDDEN_SUMMARY_NAME}")

    report_path = root / REPORT_FILENAME
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return ObservationOutcome(
        observation_id=OBSERVATION_ID,
        observation_status=OBSERVATION_STATUS,
        report_path=report_path,
        report=report,
        root=root,
    )
