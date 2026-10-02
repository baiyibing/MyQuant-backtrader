"""Dedicated synthetic minute_orders_research_v1 CLI; one S4 wrapper call."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

from . import runner
from .artifacts import BACKEND_ID, COMPARISON_STATUS, SCHEMA_VERSION
from .input_codec import load_run_input
from .types import OrderStatus

INPUT_ERROR = 2
ENGINE_FAILED = 3
OUTPUT_ERROR = 4


def _run_id(value):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", value):
        raise argparse.ArgumentTypeError("run_id must be a single safe ASCII path component")
    return value


def _code_sha(value):
    if not re.fullmatch(r"[0-9a-f]{40}", value):
        raise argparse.ArgumentTypeError("code_sha must be a full lowercase git SHA")
    return value


def _nonempty(value):
    if not value.strip():
        raise argparse.ArgumentTypeError("an explicit nonempty path is required")
    return value


def _parser():
    parser = argparse.ArgumentParser(
        prog="run_minute_orders_research.py", allow_abbrev=False,
        description=f"{BACKEND_ID}: explicit synthetic RunInput JSON research replay; no lake loader.",
    )
    parser.add_argument("--input", required=True, type=_nonempty, help="versioned RunInput JSON file")
    parser.add_argument("--parent", required=True, type=_nonempty, help="explicit artifact parent directory")
    parser.add_argument("--run-id", required=True, type=_run_id, help="new isolated run identity; never overwrite")
    parser.add_argument("--evidence-level", required=True, choices=("synthetic",))
    parser.add_argument("--code-sha", type=_code_sha, help="explicit provenance override; otherwise S4 reads git HEAD")
    return parser


def _report(status, *, stream, **details):
    print(json.dumps(dict(backend_id=BACKEND_ID, status=status, **details),
                     ensure_ascii=True, sort_keys=True), file=stream)


def _validate_completion(result, run_id):
    """Check native success plus S4's published, hash-linked completion marker."""
    root = Path(result.root)
    summary_bytes = (root / "summary.json").read_bytes()
    summary = json.loads(summary_bytes)
    manifest = json.loads((root / "manifest.json").read_bytes())
    identity = dict(status="success", backend_id=BACKEND_ID, run_id=run_id,
                    contract_hash=result.contract_hash, input_hash=result.input_hash)
    if any(not isinstance(identity[name], str) or not re.fullmatch(r"[0-9a-f]{64}", identity[name])
           for name in ("contract_hash", "input_hash")):
        raise ValueError("native success lacks contract/input hashes")
    if not all(type(doc) is dict and all(doc.get(k) == v for k, v in identity.items())
               for doc in (summary, manifest)):
        raise ValueError("success summary/manifest identity disagrees with native result")
    if (manifest.get("schema_version") != SCHEMA_VERSION
            or manifest.get("evidence_level") != "synthetic"
            or manifest.get("comparison_status") != COMPARISON_STATUS
            or (root / "failure.json").exists()):
        raise ValueError("invalid success manifest or conflicting failure evidence")
    refs = manifest.get("artifacts")
    if type(refs) is not list or any(type(ref) is not dict for ref in refs):
        raise ValueError("invalid artifact references")
    if [ref for ref in refs if ref.get("path") == "summary.json"] != [
        dict(path="summary.json", sha256=hashlib.sha256(summary_bytes).hexdigest()),
    ]:
        raise ValueError("success summary is not hash-linked in manifest")
    for name in ("order_count", "fill_count", "filled_qty"):
        if type(summary.get(name)) is not int or summary[name] < 0:
            raise ValueError(f"invalid summary {name}")
    if (type(summary.get("orders")) is not list
            or len(summary["orders"]) != summary["order_count"]
            or type(summary.get("status_counts")) is not dict
            or type(summary.get("mark_refs")) is not list
            or type(summary.get("fees_paid")) is not str
            or not re.fullmatch(r"[0-9]+\.[0-9]{2}", summary["fees_paid"])):
        raise ValueError("incomplete success summary")
    counts = dict.fromkeys((status.value for status in OrderStatus), 0)
    order_ids = set()
    for order in summary["orders"]:
        if (type(order) is not dict
                or type(order.get("order_id")) is not str or not order["order_id"].strip()
                or order["order_id"] in order_ids
                or type(order.get("status")) is not str or order["status"] not in counts
                or any(type(order.get(k)) is not int or order[k] < 0
                       for k in ("filled_qty", "remaining_qty"))
                or type(order.get("active")) is not bool
                or order["active"] != (order["status"] in ("Accepted", "PartiallyFilled"))):
            raise ValueError("invalid summary order")
        order_ids.add(order["order_id"])
        counts[order["status"]] += 1
    if (any(type(value) is not int for value in summary["status_counts"].values())
            or summary["status_counts"] != counts
            or sum(order["filled_qty"] for order in summary["orders"]) != summary["filled_qty"]
            or summary["mark_refs"] != [f"marks.jsonl#row={i + 1}" for i in range(len(summary["mark_refs"]))]):
        raise ValueError("inconsistent success summary")


def main(argv=None):
    args = _parser().parse_args(argv)
    try:
        run_input = load_run_input(args.input)
    except (OSError, ValueError, RecursionError) as error:
        _report("input_error", stream=sys.stderr, error_type=type(error).__name__, reason=str(error))
        return INPUT_ERROR
    try:
        # P2-B CLI shell: participation_rate unit/domain. ≠δ5≠R4. Not MatchCore.
        from backtest.research.participation_rate_precheck import (
            precheck_cli_participation_rate,
        )

        precheck_cli_participation_rate(float(run_input.participation_rate))
    except (TypeError, ValueError) as error:
        _report("input_error", stream=sys.stderr, error_type=type(error).__name__, reason=str(error))
        return INPUT_ERROR
    try:
        result = runner.run_minute_orders_research_with_artifacts(
            run_input, args.parent, run_id=args.run_id,
            evidence_level=args.evidence_level, code_sha=args.code_sha,
        )
    except Exception as error:
        details = dict(error_type=type(error).__name__, reason=str(error))
        if hasattr(error, "root"):
            details["root"] = str(error.root)
        _report("output_error", stream=sys.stderr, **details)
        return OUTPUT_ERROR
    if result.status == "failed":
        _report("engine_failed", stream=sys.stderr, root=str(result.root),
                failure=str(result.root / "failure.json"))
        return ENGINE_FAILED
    try:
        if result.status != "success":
            raise ValueError(f"unknown native status: {result.status!r}")
        _validate_completion(result, args.run_id)
    except (OSError, ValueError, TypeError, RecursionError) as error:
        _report("output_error", stream=sys.stderr, root=str(result.root),
                error_type=type(error).__name__, reason=str(error))
        return OUTPUT_ERROR
    _report("success", stream=sys.stdout, root=str(result.root),
            summary=str(result.root / "summary.json"))
    return 0
