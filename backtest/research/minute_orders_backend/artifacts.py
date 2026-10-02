"""Independent S4 artifacts. No execution, market loading, or legacy writers.

See note-l2-s4-artifacts-isolation-2026-09-29.md for encoding and completion rules.
"""

from dataclasses import dataclass, fields, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

from .fees import from_cents, money_cents
from .types import (
    ClockEvent, LedgerSnapshot, MarkObservation, OrderStatus, OrderTransition, Phase,
    RunInput, RunResult, SubmitOrder,
)

BACKEND_ID = "minute_orders_research_v1"
SCHEMA_VERSION = "minute_orders_artifacts_v1"
COMPARISON_STATUS = "no_ssot_compare_authorization"
HYBRID_SCHEMA_VERSION = "minute_orders_artifacts_v2"


def _validate_evidence_request(run, evidence_level, source_provenance):
    if evidence_level == "synthetic":
        marks = getattr(run, "marks", ())
        if source_provenance is not None or any(
            isinstance(getattr(mark, "source", None), str) and mark.source.startswith("B-L2-01/")
            for mark in (marks if isinstance(marks, (list, tuple)) else ())
        ):
            raise ValueError("source-loaded input requires hybrid evidence; cannot label it synthetic")
        return
    if evidence_level != "hybrid" or source_provenance is None:
        raise ValueError("S4 requires synthetic or explicit hybrid evidence with source provenance")


@dataclass(frozen=True)
class FailedRun:
    """Available committed evidence only; never a successful RunResult."""

    error: Exception
    transitions: tuple[OrderTransition, ...] = ()
    marks: tuple[MarkObservation, ...] = ()
    ledger: LedgerSnapshot | None = None


@dataclass(frozen=True)
class ArtifactWriteResult:
    root: Path
    status: str
    contract_hash: str | None
    input_hash: str | None


class ArtifactWriteError(OSError):
    """A new run root failed to publish; root retains available evidence."""

    def __init__(self, root, stage, error, evidence_error=None):
        super().__init__(f"artifact write failed at {stage}: {error}")
        self.root = root
        self.stage = stage
        self.evidence_error = evidence_error


def _value(value):
    if is_dataclass(value) and not isinstance(value, type):
        return _value({field.name: getattr(value, field.name) for field in fields(value)})
    if isinstance(value, Enum):
        return _value(value.value)
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError("nonfinite Decimal cannot be an artifact value")
        return str(value)
    if isinstance(value, datetime):
        if value.utcoffset() is None:
            raise ValueError("artifact timestamps must be timezone-aware")
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        if any(type(key) is not str for key in value):
            raise TypeError("artifact object keys must be strings")
        return {key: _value(item) for key, item in value.items() if item is not None}
    if isinstance(value, (tuple, list)):
        return [_value(item) for item in value]
    if isinstance(value, frozenset):
        return sorted((_value(item) for item in value), key=_canonical)
    if value is None or type(value) in (str, int, bool):
        return value
    raise TypeError(f"unsupported artifact value: {type(value).__name__}")


def _canonical(value):
    return json.dumps(_value(value), sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _hash(data):
    return hashlib.sha256(data).hexdigest()


def _json(value):
    return _canonical(value) + b"\n"


def _jsonl(rows):
    return b"".join(_json(row) for row in rows)


def _code_identity(override):
    if override is not None:
        if not isinstance(override, str) or not re.fullmatch(r"[0-9a-f]{40}", override):
            raise ValueError("code_sha override must be a full lowercase git SHA")
        return {"code_sha": override, "code_sha_source": "caller_override"}
    repo = Path(__file__).resolve().parents[3]
    try:
        sha = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True, timeout=10,
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "-C", str(repo), "status", "--porcelain", "--untracked-files=all",
             "--", "backtest/research/minute_orders_backend"],
            check=True, capture_output=True, text=True, timeout=10,
        ).stdout != ""
    except (OSError, subprocess.SubprocessError):
        return {"code_sha_source": "unavailable"}
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        return {"code_sha_source": "unavailable"}
    return {"code_sha": sha, "code_sha_source": "git_head", "code_dirty": dirty}


def _contract(run):
    return {
        "contract_version": "research contract v0 (L2-S0)", "backend_id": BACKEND_ID,
        "price_model": "completed_bucket_close",
        "clock": {"timezone": "Asia/Shanghai", "match_at": "bucket_end",
                  "eligibility": "available<=submitted<bucket_start; effective<=bucket_start; end<expiry",
                  "calendar": "explicit continuous minutes; missing/halt coverage required"},
        "phase": {"order": [phase.name for phase in Phase],
                  "key": ["event_time", "phase_rank", "sell_before_buy", "submitted_at",
                          "sequence", "order_id"]},
        "lifecycle": {"type": "LIMIT", "statuses": [s.value for s in OrderStatus],
                      "expiry": "right_open", "cancel": "remaining_only; terminal_noop"},
        "capacity": "lot*floor(participation_rate*volume_shares/lot); shared_both_sides_per_bucket",
        "lot": "integer lots; BUY sellable on next explicit trading date; SELL reserves sellable lots",
        "instrument": "main/raw; explicit tick/reference/daily limits; no buy at upper/no sell at lower",
        "reservation": "BUY limit*remaining+fee_upper; SELL available lots; insufficient rejects, no resize",
        "fee": "F(0)=0; F(N)=quantize(max(min_fee,N*rate),0.01,rounding); per_order_delta",
        "mark": "explicit raw events cover held symbols; no price fallback; no trade",
        "failure": "abort; committed evidence only; no success summary; existing root refused",
        "company_actions": "coverage required; nonempty events rejected",
        "parameters": {name: {"value": getattr(run, name), "source": f"inputs.json#/data/{name}"}
                       for name in ("buy_fees", "sell_fees", "participation_rate", "requires_marks")},
    }


def _commands(run):
    targets = {c.order_id: c for c in run.commands if isinstance(c, SubmitOrder)}
    rows = []
    for command in run.commands:
        row = _value(command)
        row["kind"] = "submit" if isinstance(command, SubmitOrder) else "cancel"
        target = targets.get(command.order_id)
        if target:
            row.update(symbol=target.symbol, side=target.side)
        rows.append(row)
    return rows


def _ledger_row(snapshot, **refs):
    row = _value(snapshot)
    row.pop("applied_fills")
    row["applied_fill_ids"] = sorted(snapshot.applied_fill_ids)
    row["lots"] = [dict(_value(lot), free_qty=lot.free_qty) for lot in snapshot.lots]
    row["buckets"] = [dict(_value(b), consumed=b.capacity - b.remaining) for b in snapshot.buckets]
    return dict(row, **refs)


def _reservation(snapshot, order_id):
    reservation = next((r for r in snapshot.reservations if r.order_id == order_id), None)
    # Absence in a known snapshot means zero resources, not unknown evidence.
    return {"cash": reservation.cash if reservation else Decimal("0.00"),
            "sellable_qty": sum(lot.qty for lot in reservation.lots) if reservation else 0}


def _rows(run, outcome):
    transitions, marks, snapshot = outcome.transitions, outcome.marks, outcome.ledger
    fills = outcome.fills if isinstance(outcome, RunResult) else (
        snapshot.applied_fills if snapshot else ())
    fill_by_event = {(f.proposal.order_id, f.proposal.bucket_id): f for f in fills}
    orders, ledgers, fill_rows, mark_rows = [], [], [], []
    previous_reservations = {}
    match_events = {}
    for index, transition in enumerate(transitions):
        event, state, ledger = transition.event, transition.state, transition.ledger
        row = {"order_id": state.order.order_id, "status": state.status,
               "event_key": event.key, "event_time": event.event_time, "phase": event.phase.name,
               "original_qty": state.order.qty, "filled_qty": state.filled_qty,
               "remaining_qty": state.remaining_qty,
               "reason": state.rejection.reason if state.rejection else state.status.value,
               "command_id": getattr(event.payload, "command_id", None)}
        if state.rejection:
            row["rejection"] = state.rejection
        if event.phase is Phase.MATCH:
            fill = fill_by_event[(state.order.order_id, event.payload.bucket_id)]
            row["fill_id"] = fill.proposal.fill_id
            match_events[fill.proposal.fill_id] = transition
        if ledger is not None:
            after = _reservation(ledger, state.order.order_id)
            before = previous_reservations.get(state.order.order_id)
            # Submitted is observed before reservation; no prior state is invented.
            if state.status is OrderStatus.SUBMITTED:
                before = after
            row.update(reservation_before=before, reservation_after=after,
                       ledger_version=ledger.ledger_version)
            previous_reservations[state.order.order_id] = after
            ledgers.append(_ledger_row(ledger, event_key=event.key,
                                       order_ref=f"orders.jsonl#row={index + 1}"))
        orders.append(row)
    totals = {}
    # Capacities are registered once and never replenished: derive per-fill usage
    # from the committed final capacities and chronological applied-fill sequence.
    capacities = {(b.symbol, b.bucket_id): b.capacity for b in snapshot.buckets} if snapshot else {}
    for fill in fills:
        proposal = fill.proposal
        transition = match_events[proposal.fill_id]
        bucket = transition.event.payload
        notional = money_cents(proposal.price, "price") * proposal.qty
        prior_notional, prior_fee = totals.get(proposal.order_id, (0, 0))
        cumulative = prior_notional + notional, prior_fee + money_cents(proposal.fee_delta, "fee_delta")
        totals[proposal.order_id] = cumulative
        key = proposal.symbol, proposal.bucket_id
        before = capacities[key]
        capacities[key] -= proposal.capacity_consumed
        fill_rows.append(dict(
            _value(proposal), ledger_version=fill.ledger_version,
            notional=from_cents(notional), cumulative_notional=from_cents(cumulative[0]),
            cumulative_fee=from_cents(cumulative[1]), bucket_start=bucket.start, bucket_end=bucket.end,
            available_at=bucket.end, matched_at=transition.event.event_time,
            booked_at=transition.event.event_time, event_key=transition.event.key,
            capacity_before=before, capacity_after=capacities[key],
        ))
    if snapshot is not None:
        if any(capacities[b.symbol, b.bucket_id] != b.remaining for b in snapshot.buckets):
            raise ValueError("fill capacity projection differs from committed ledger")
        for total in snapshot.order_totals:
            if totals.get(total.order_id, (0, 0)) != (
                money_cents(total.notional, "notional"), money_cents(total.fees_paid, "fees_paid"),
            ):
                raise ValueError("fill totals projection differs from committed ledger")
    for index, observation in enumerate(marks):
        event, ledger = observation.event, observation.ledger
        prices = {p.symbol: p.price for p in event.prices}
        positions = [{"lot_id": lot.lot_id, "symbol": lot.symbol, "qty": lot.qty,
                      "price": prices[lot.symbol],
                      "market_value": from_cents(money_cents(prices[lot.symbol], "mark") * lot.qty)}
                     for lot in ledger.lots]
        key = ClockEvent(event.event_time, Phase.MARK, 0, event.event_time,
                         0, event.mark_id, event).key
        mark_rows.append(dict(_value(event), event_key=key, ledger_version=ledger.ledger_version,
                              positions=positions, valuation_valid=True))
        ledgers.append(_ledger_row(ledger, event_key=key, mark_ref=f"marks.jsonl#row={index + 1}"))
    ledgers.sort(key=lambda row: row["event_key"])
    if snapshot is not None:
        ledgers.append(_ledger_row(snapshot, observation="final" if isinstance(outcome, RunResult)
                                   else "last_committed", event_time=run.end_at
                                   if isinstance(outcome, RunResult) else None))
    return {"orders.jsonl": orders, "fills.jsonl": fill_rows,
            "ledger.jsonl": ledgers, "marks.jsonl": mark_rows}


def _validate_result(run, result):
    expected = {c.order_id: c for c in run.commands if isinstance(c, SubmitOrder)}
    if len(result.orders) != len(expected) or {s.order.order_id: s.order for s in result.orders} != expected:
        raise ValueError("result orders do not match supplied inputs")
    if result.fills != result.ledger.applied_fills:
        raise ValueError("result fills differ from committed ledger")
    if tuple(m.event for m in result.marks) != tuple(sorted(run.marks, key=lambda m: (m.event_time, m.mark_id))):
        raise ValueError("result marks do not match supplied inputs")


def _summary(result):
    active = {OrderStatus.ACCEPTED, OrderStatus.PARTIALLY_FILLED}
    return {"status": "success", "backend_id": BACKEND_ID,
            "order_count": len(result.orders),
            "status_counts": {s.value: sum(o.status is s for o in result.orders) for s in OrderStatus},
            "orders": [{"order_id": o.order.order_id, "status": o.status,
                        "filled_qty": o.filled_qty, "remaining_qty": o.remaining_qty,
                        "active": o.status in active} for o in result.orders],
            "fill_count": len(result.fills),
            "filled_qty": sum(f.proposal.qty for f in result.fills),
            "fees_paid": result.ledger.fees_paid,
            "mark_refs": [f"marks.jsonl#row={i + 1}" for i in range(len(result.marks))]}


def _new_root(parent, run_id):
    if not isinstance(run_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", run_id):
        raise ValueError("run_id must be a single safe ASCII path component")
    parent = Path(parent)
    parent.mkdir(parents=True, exist_ok=True)
    root = parent
    for name in ("backtest_output", BACKEND_ID):
        root = root / name
        try:
            root.mkdir()
        except FileExistsError:
            if root.is_symlink() or not root.is_dir():
                raise FileExistsError(f"artifact namespace is not a real directory: {root}")
    root = root / run_id
    root.mkdir()  # Exclusive ownership. No failure handler may touch a rejected root.
    return root


def _write_file(root, name, data):
    with (root / name).open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def _publish(root, name, data):
    pending = root / ("." + name + ".pending")
    _write_file(root, pending.name, data)
    if pending.read_bytes() != data:
        raise OSError(f"staged artifact verification failed: {name}")
    os.replace(pending, root / name)


def _refs(root):
    return [{"path": path.name, "sha256": _hash(path.read_bytes())}
            for path in sorted(root.iterdir())
            if path.is_file() and not path.name.startswith(".") and path.name != "manifest.json"]


def _failure(root, identity, *, stage, error, outcome):
    # Only called after this invocation exclusively created root.
    (root / "summary.json").unlink(missing_ok=True)
    failure = {"status": "failed", "stage": stage, "reason": str(error),
               "error_type": type(error).__name__,
               "input_ref": "inputs.json#/data" if (root / "inputs.json").is_file() else None,
               "artifacts": _refs(root)}
    if isinstance(outcome, (RunResult, FailedRun)) and outcome.ledger is not None:
        failure["last_committed_ledger_version"] = outcome.ledger.ledger_version
        if outcome.transitions:
            failure["last_recorded_event_key"] = outcome.transitions[-1].event.key
    if isinstance(outcome, FailedRun) and error is not outcome.error:
        failure["run_error"] = {"error_type": type(outcome.error).__name__, "reason": str(outcome.error)}
    _publish(root, "failure.json", _json(failure))
    _publish(root, "manifest.json", _json(dict(identity, status="failed", artifacts=_refs(root))))


def write_minute_orders_artifacts(
    run_input: RunInput, run_result_or_error: RunResult | FailedRun | Exception,
    parent, *, run_id: str, evidence_level: str, code_sha: str | None = None,
    source_provenance=None,
) -> ArtifactWriteResult:
    """Write one new isolated root; never replay an engine to recover evidence.

    A direct S3 result lacks historical reservation snapshots: omit unknowns.
    Use runner.run_minute_orders_research_with_artifacts for the complete trace.
    Engine failures return status=failed; disk/encoding failures raise with root.
    """
    _validate_evidence_request(run_input, evidence_level, source_provenance)
    if not isinstance(run_result_or_error, (RunResult, FailedRun, Exception)):
        raise TypeError("expected RunResult, FailedRun or an engine Exception")
    identity = dict(schema_version=SCHEMA_VERSION, run_id=run_id, backend_id=BACKEND_ID,
                    evidence_level=evidence_level, comparison_status=COMPARISON_STATUS,
                    **_code_identity(code_sha))
    if evidence_level == "hybrid":
        from .source_provenance import EVIDENCE_VERSION

        identity.update(schema_version=HYBRID_SCHEMA_VERSION, evidence_schema_version=EVIDENCE_VERSION)
    root = _new_root(parent, run_id)
    outcome = FailedRun(run_result_or_error) if isinstance(run_result_or_error, Exception) else run_result_or_error
    stage = "encode_inputs"
    try:
        contract = _contract(run_input)
        data = _value(run_input)
        identity.update(contract_hash=_hash(_canonical(contract)), input_hash=_hash(_canonical(data)))
        inputs = {"input_hash": identity["input_hash"], "data": data,
                  "components": {name: {"sha256": _hash(_canonical(value)),
                                         "ref": f"inputs.json#/data/{name}"}
                                 for name, value in data.items()}}
        documents = {"contract.json": _json(contract), "inputs.json": _json(inputs),
                     "commands.jsonl": _jsonl(_commands(run_input))}
        for name, body in documents.items():
            stage = name
            _write_file(root, name, body)
        if evidence_level == "hybrid":
            from .source_provenance import (
                SourceProvenance, require, require_unchanged, source_checks,
                validate_source_provenance,
            )

            stage = "source_provenance"
            require(type(source_provenance) is SourceProvenance, "hybrid requires loader SourceProvenance")
            documents["source_provenance.json"] = source_provenance.payload + b"\n"
            _write_file(root, "source_provenance.json", documents["source_provenance.json"])
            # Observe before validation so changed/missing sources retain both hashes.
            documents["source_checks.json"] = _json(source_checks(source_provenance))
            _write_file(root, "source_checks.json", documents["source_checks.json"])
            doc = validate_source_provenance(run_input, source_provenance, parent=parent,
                                             run_id=run_id, code_sha=code_sha)
            identity.update(source_provenance_hash=source_provenance.sha256,
                            source_kind=doc["source_kind"], evidence_notice=doc["notice"],
                            source_components={"market": doc["source_kind"],
                                               "commands": "synthetic", "account": "synthetic"},
                            host_attestation_status="not_certified_by_writer",
                            live_acceptance_status="not_assessed",
                            code_sha=doc["execution"]["code_sha"],
                            code_dirty=doc["execution"]["code_dirty"], code_sha_source="git_head")
        stage = "validate_result"
        if isinstance(outcome, RunResult):
            _validate_result(run_input, outcome)
            if evidence_level == "hybrid":
                identity["held_mark_coverage"] = (
                    "covered" if any(m.ledger.lots for m in outcome.marks) else "not_covered"
                )
        for name, rows in _rows(run_input, outcome).items():
            stage = name
            documents[name] = _jsonl(rows)
            _write_file(root, name, documents[name])
        if isinstance(outcome, FailedRun):
            stage = "run"
            _failure(root, identity, stage=stage, error=outcome.error, outcome=outcome)
            return ArtifactWriteResult(root, "failed", identity["contract_hash"], identity["input_hash"])
        stage = "validate_artifacts"
        if evidence_level == "hybrid":
            stage = "source_postflight"
            checks = source_checks(source_provenance)
            documents["source_postflight.json"] = _json(checks)
            _write_file(root, "source_postflight.json", documents["source_postflight.json"])
            require_unchanged(checks)
            stage = "validate_artifacts"
        summary = _json(dict(_summary(outcome), run_id=run_id,
                             contract_hash=identity["contract_hash"], input_hash=identity["input_hash"]))
        refs = [{"path": name, "sha256": _hash(body)} for name, body in documents.items()]
        refs.append({"path": "summary.json", "sha256": _hash(summary)})
        manifest = _json(dict(identity, status="success", artifacts=refs))
        documents["manifest.json"] = manifest
        _write_file(root, "manifest.json", manifest)
        for name, body in documents.items():
            if (root / name).read_bytes() != body:
                raise OSError(f"artifact verification failed: {name}")
            for line in body.splitlines():
                json.loads(line)
        stage = "summary.json"
        _publish(root, "summary.json", summary)  # Sole completion marker; final publication.
        return ArtifactWriteResult(root, "success", identity["contract_hash"], identity["input_hash"])
    except Exception as error:
        evidence_error = None
        try:
            _failure(root, identity, stage=stage, error=error, outcome=outcome)
        except Exception as failed_evidence:
            evidence_error = failed_evidence
        raise ArtifactWriteError(root, stage, error, evidence_error) from error
