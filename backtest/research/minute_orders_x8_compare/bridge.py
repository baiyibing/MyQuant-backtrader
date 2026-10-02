"""X8 comparison bridge: pre-match snapshot ↔ X1 frozen-batch, red-label only.

Writes under an independent comparison root (NOT minute_orders_research_v1).
Emits comparison_report.json with comparison_status always
no_ssot_compare_authorization. Never writes success summary.json.
Does not mint a new economic contract or backend_id for the runner.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any, Mapping, Sequence
from zoneinfo import ZoneInfo

from backtest.research.minute_orders_backend.types import (
    CalendarFacts,
    CompletedBucket,
    FeeModelParams,
    InstrumentFacts,
    MarkEvent,
    MarkPrice,
    SessionBucket,
    Side,
)
from backtest.research.minute_orders_intent_x1 import (
    ADAPTER_ID,
    CancelIntent,
    LimitIntent,
    freeze_command_batch,
    run_x1_frozen_batch,
)

from .ingest import PrematchSnapshot

COMPARISON_ID = "minute_orders_x8_compare"
# comparison_id is tooling identity only — NOT a backend_id / economic contract.
COMPARISON_ROOT_NAME = "minute_orders_x8_compare"
COMPARISON_STATUS = "no_ssot_compare_authorization"
REPORT_SCHEMA = "minute_orders_x8_comparison_report_v0"
REPORT_FILENAME = "comparison_report.json"
# Hard ban: never publish a research-looking success summary under the comparison root.
FORBIDDEN_SUMMARY_NAME = "summary.json"

CONTRACT = "research contract v0 (L2-S0)"
BACKEND_ID = "minute_orders_research_v1"

TZ = ZoneInfo("Asia/Shanghai")
D = Decimal
PREV, D0, D1 = date(2026, 9, 25), date(2026, 9, 28), date(2026, 9, 29)
ZERO_FEES = FeeModelParams(D("0"), D("0.00"), ROUND_HALF_UP)

_RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class CompareBridgeError(ValueError):
    """Bridge refused before or during write (not a green research failure)."""


@dataclass(frozen=True)
class ComparisonOutcome:
    """In-memory + on-disk red-label comparison result."""

    comparison_id: str
    comparison_status: str
    report: Mapping[str, Any]
    root: Path | None
    report_path: Path | None


def _at(value: str, day=D0) -> datetime:
    return datetime.fromisoformat(f"{day}T{value}").replace(tzinfo=TZ)


def _bucket(start: str, *, close="10.00", volume=1000) -> CompletedBucket:
    begin = _at(start)
    return CompletedBucket(
        "X", begin.isoformat(), begin, begin + timedelta(minutes=1),
        D(close), volume, False, False,
    )


def synthetic_sketch_a_facts() -> dict:
    """Same S0 handcalc sketch A market facts as X1/TC3 (attestation-level)."""
    buckets = (_bucket("09:30:00"), _bucket("09:31:00"), _bucket("09:32:00"))
    sessions = tuple(
        SessionBucket(b.bucket_id, b.start, b.end, "continuous") for b in buckets
    )
    marks = tuple(
        MarkEvent(
            f"mark:{t}", _at(t), _at(t), (MarkPrice("X", D("10.00")),),
            "raw", "synthetic x8 compare",
        )
        for t in ("09:29:01", "09:31:00", "09:32:00", "09:33:00")
    )
    return dict(
        start_at=_at("09:28:00"),
        end_at=_at("09:35:00"),
        buckets=buckets,
        calendar=CalendarFacts((PREV, D0, D1), sessions, True, ()),
        instruments=(InstrumentFacts(
            "X", D0, "main", "raw", D("0.01"), 100,
            D("10.00"), D("9.00"), D("11.00"),
        ),),
        initial_cash=D("10000.00"),
        initial_lots=(),
        buy_fees=ZERO_FEES,
        sell_fees=ZERO_FEES,
        participation_rate=D("0.20"),
        marks=marks,
        requires_marks=False,
    )


def _intent_fingerprint(intent: LimitIntent | CancelIntent) -> dict[str, Any]:
    if isinstance(intent, LimitIntent):
        return {
            "kind": "limit",
            "order_id": intent.order_id,
            "symbol": intent.symbol,
            "side": intent.side.value,
            "qty": intent.qty,
            "limit": str(intent.limit),
            "sequence": intent.sequence,
            "command_id": intent.command_id,
            "available_at": intent.available_at.isoformat(),
            "submitted_at": intent.submitted_at.isoformat(),
            "effective_at": intent.effective_at.isoformat(),
            "expires_at": intent.expires_at.isoformat(),
        }
    return {
        "kind": "cancel",
        "order_id": intent.order_id,
        "sequence": intent.sequence,
        "command_id": intent.command_id,
        "available_at": intent.available_at.isoformat(),
        "submitted_at": intent.submitted_at.isoformat(),
        "effective_at": intent.effective_at.isoformat(),
    }


def _require_run_id(run_id: str) -> str:
    if type(run_id) is not str or not _RUN_ID_RE.fullmatch(run_id):
        raise CompareBridgeError(
            "run_id must be a single safe ASCII path component "
            "[A-Za-z0-9][A-Za-z0-9._-]{0,127}"
        )
    return run_id


def comparison_root(parent: str | Path, run_id: str) -> Path:
    """Independent comparison root — never under minute_orders_research_v1."""
    parent = Path(parent)
    run_id = _require_run_id(run_id)
    return parent / COMPARISON_ROOT_NAME / run_id


def build_comparison_report(
    snapshot: PrematchSnapshot,
    *,
    commands,
    outcome,
    facts_preset: str,
) -> dict[str, Any]:
    """Build the red-label diagnostic report dict (no disk I/O)."""
    frozen_ids = [c.command_id for c in commands]
    # Expected command ids from LimitIntent defaults (submit:{order_id}).
    expected_ids = []
    for intent in snapshot.intents:
        if isinstance(intent, LimitIntent):
            expected_ids.append(
                intent.command_id if intent.command_id is not None
                else f"submit:{intent.order_id}"
            )
        else:
            expected_ids.append(
                intent.command_id if intent.command_id is not None
                else f"cancel:{intent.order_id}"
            )
    intent_vs_frozen = {
        "match": frozen_ids == expected_ids,
        "snapshot_expected_command_ids": expected_ids,
        "frozen_command_ids": frozen_ids,
        "diffs": (
            []
            if frozen_ids == expected_ids
            else [{"expected": expected_ids, "frozen": frozen_ids}]
        ),
    }
    orders = [
        {
            "order_id": s.order.order_id,
            "status": s.status.value,
            "filled_qty": s.filled_qty,
            "remaining_qty": s.remaining_qty,
        }
        for s in outcome.result.orders
    ]
    return {
        "schema": REPORT_SCHEMA,
        "comparison_id": COMPARISON_ID,
        "comparison_status": COMPARISON_STATUS,
        "red_label": True,
        "diagnostic_only": True,
        "label": (
            "RED · diagnostic · pre-match intent ↔ X1 frozen-batch; "
            "not fill-policy; not NAV rank; ≠δ5≠R4"
        ),
        "adapter_id_used": ADAPTER_ID,
        "contract": CONTRACT,
        "backend_id_reused": BACKEND_ID,
        "facts_preset": facts_preset,
        "note": (
            "comparison_id is NOT a backend_id; runner reuses v0/X1 unchanged; "
            "independent comparison root; no success summary.json; "
            "forever opt-in; never BOOKS default"
        ),
        "snapshot": {
            "schema": snapshot.schema,
            "snapshot_kind": snapshot.snapshot_kind,
            "intent_count": len(snapshot.intents),
            "intent_fingerprints": [
                _intent_fingerprint(i) for i in snapshot.intents
            ],
            "adapter_id": snapshot.adapter_id,
            "contract": snapshot.contract,
            "backend_id": snapshot.backend_id,
        },
        "frozen_batch": {
            "command_count": len(commands),
            "command_ids": frozen_ids,
        },
        "intent_vs_frozen": intent_vs_frozen,
        "x1_run": {
            "adapter_id": outcome.adapter_id,
            "orders": orders,
            "fill_count": len(outcome.result.fills),
            "fees_paid": str(outcome.result.ledger.fees_paid),
        },
        "bans": [
            "no_fills_to_intent",
            "no_success_summary_json",
            "no_new_contract",
            "no_new_backend_id",
            "no_matchcore_fees_simulate_edit",
            "no_nav_rank",
            "not_fill_policy",
            "not_delta5_certified",
            "not_r4",
            "not_books_default",
            "forever_opt_in",
            "independent_comparison_root",
        ],
    }


def write_comparison_report(
    report: Mapping[str, Any],
    *,
    parent: str | Path,
    run_id: str,
) -> tuple[Path, Path]:
    """Write comparison_report.json under the independent comparison root.

    Refuses existing roots. Never writes summary.json.
    """
    root = comparison_root(parent, run_id)
    if root.exists():
        raise FileExistsError(
            f"comparison root already exists (refuse overwrite): {root}"
        )
    # Guard: path must not land under the research success artifact root name.
    parts = {p.lower() for p in root.parts}
    if "minute_orders_research_v1" in parts:
        raise CompareBridgeError(
            "comparison root must NOT be under minute_orders_research_v1"
        )
    root.mkdir(parents=True, exist_ok=False)
    report_path = root / REPORT_FILENAME
    # Explicitly do not create summary.json — diagnostic only.
    forbidden = root / FORBIDDEN_SUMMARY_NAME
    if forbidden.exists():
        raise CompareBridgeError(
            f"refusing to publish beside existing {FORBIDDEN_SUMMARY_NAME}"
        )
    payload = json.dumps(report, ensure_ascii=True, sort_keys=True, indent=2) + "\n"
    report_path.write_text(payload, encoding="utf-8")
    if (root / FORBIDDEN_SUMMARY_NAME).exists():
        raise CompareBridgeError("internal error: summary.json must not be written")
    return root, report_path


def run_x8_compare(
    snapshot: PrematchSnapshot,
    *,
    facts: Mapping[str, Any] | None = None,
    facts_preset: str | None = None,
    parent: str | Path | None = None,
    run_id: str | None = None,
) -> ComparisonOutcome:
    """Freeze snapshot intents → X1 run → red-label comparison report.

    When parent+run_id are given, writes under
    ``{parent}/minute_orders_x8_compare/{run_id}/comparison_report.json``.
    """
    preset = facts_preset or snapshot.facts_preset or "sketch_a"
    if facts is None:
        if preset != "sketch_a":
            raise CompareBridgeError(
                f"unsupported facts_preset {preset!r}; only sketch_a synthetic facts"
            )
        facts = synthetic_sketch_a_facts()
    else:
        facts = dict(facts)

    commands = freeze_command_batch(snapshot.intents)
    outcome = run_x1_frozen_batch(snapshot.intents, **facts)
    # Identity: run must use the same frozen batch.
    if [c.command_id for c in outcome.commands] != [c.command_id for c in commands]:
        raise CompareBridgeError("X1 run commands diverged from frozen batch")

    report = build_comparison_report(
        snapshot, commands=commands, outcome=outcome, facts_preset=preset,
    )
    if report["comparison_status"] != COMPARISON_STATUS:
        raise CompareBridgeError("comparison_status must stay no_ssot_compare_authorization")

    root = report_path = None
    if parent is not None or run_id is not None:
        if parent is None or run_id is None:
            raise CompareBridgeError("parent and run_id must be supplied together")
        root, report_path = write_comparison_report(
            report, parent=parent, run_id=run_id,
        )
    return ComparisonOutcome(
        comparison_id=COMPARISON_ID,
        comparison_status=COMPARISON_STATUS,
        report=report,
        root=root,
        report_path=report_path,
    )


# Re-export Side for tests that build intents inline via this module.
__all__ = [
    "BACKEND_ID",
    "COMPARISON_ID",
    "COMPARISON_ROOT_NAME",
    "COMPARISON_STATUS",
    "CONTRACT",
    "CompareBridgeError",
    "ComparisonOutcome",
    "REPORT_FILENAME",
    "REPORT_SCHEMA",
    "Side",
    "build_comparison_report",
    "comparison_root",
    "run_x8_compare",
    "synthetic_sketch_a_facts",
    "write_comparison_report",
]
