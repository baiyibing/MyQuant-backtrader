"""Dedicated minute_orders_research_v1 CLI; one S4 wrapper call.

Synthetic path: explicit RunInput JSON → evidence_level=synthetic.
Lake path (forever opt-in): pinned lake+END recipe → load_minute_orders_source
→ S4 hybrid (CLI ``lake`` ≠ host PASS / item-4 live / green R; never BOOKS default).
"""

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

from . import runner
from .artifacts import (
    BACKEND_ID,
    COMPARISON_STATUS,
    HYBRID_SCHEMA_VERSION,
    SCHEMA_VERSION,
)
from .input_codec import load_run_input
from .types import OrderStatus

INPUT_ERROR = 2
ENGINE_FAILED = 3
OUTPUT_ERROR = 4

# Phase5 lake research path only (same gate as X6 e2e; CLI-local, no loader edit).
_LAKE_SOURCE_KIND = "lake"
_LAKE_BAR_TIME_LABEL = "END"
_LAKE_AVAILABILITY = "bucket_end"
_BANNED_RECIPE_TOP_LEVEL = frozenset({
    "lake_write", "lake_write_path", "write_lake", "write_path",
    "host_attestation", "green_r", "nav_rank",
})
_HYBRID_EVIDENCE_SCHEMA = "minute_orders_hybrid_evidence_v1"


def _run_id(value):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", value):
        raise argparse.ArgumentTypeError("run_id must be a single safe ASCII path component")
    return value


def _code_sha(value):
    if not re.fullmatch(r"[0-9a-f]{40}", value):
        raise argparse.ArgumentTypeError("code_sha must be a full lowercase git SHA")
    return value


def _sha256_hex(value):
    if not re.fullmatch(r"[0-9a-f]{64}", value):
        raise argparse.ArgumentTypeError("expected_sha256 must be a full lowercase SHA-256")
    return value


def _nonempty(value):
    if not value.strip():
        raise argparse.ArgumentTypeError("an explicit nonempty path is required")
    return value


def _parser():
    parser = argparse.ArgumentParser(
        prog="run_minute_orders_research.py", allow_abbrev=False,
        description=(
            f"{BACKEND_ID}: forever opt-in research replay. "
            "synthetic = explicit RunInput JSON (default historical path); "
            "lake = pinned lake+END recipe → existing loader → S4 hybrid "
            "(CLI lake is source selection, not host PASS / certified / green R; "
            "never BOOKS default; tool_id≠backend_id)."
        ),
    )
    parser.add_argument(
        "--input", type=_nonempty,
        help="versioned RunInput JSON file (required for --evidence-level=synthetic)",
    )
    parser.add_argument(
        "--recipe", type=_nonempty,
        help="absolute pinned lake+END recipe JSON (required for --evidence-level=lake)",
    )
    parser.add_argument(
        "--expected-sha256", type=_sha256_hex,
        help="full lowercase SHA-256 of the recipe file (required for lake)",
    )
    parser.add_argument("--parent", required=True, type=_nonempty, help="explicit artifact parent directory")
    parser.add_argument("--run-id", required=True, type=_run_id, help="new isolated run identity; never overwrite")
    parser.add_argument(
        "--evidence-level", required=True, choices=("synthetic", "lake"),
        help="synthetic = RunInput JSON; lake = recipe→loader→S4 hybrid (≠ host PASS)",
    )
    parser.add_argument(
        "--code-sha", type=_code_sha,
        help="synthetic-only provenance override; lake rejects overrides (S4 uses git HEAD)",
    )
    return parser


def _report(status, *, stream, **details):
    print(json.dumps(dict(backend_id=BACKEND_ID, status=status, **details),
                     ensure_ascii=True, sort_keys=True), file=stream)


def _preflight_lake_recipe(recipe, *, parent, run_id):
    """Refuse non-lake / START / write-lake masquerades before hybrid run."""
    if type(recipe) is not dict:
        raise ValueError("recipe must be a JSON object")
    banned = sorted(_BANNED_RECIPE_TOP_LEVEL & set(recipe))
    if banned:
        raise ValueError(f"banned top-level recipe keys for CLI lake: {banned}")
    source_kind = recipe.get("source_kind")
    if source_kind != _LAKE_SOURCE_KIND:
        raise ValueError(
            f"CLI --evidence-level=lake refuses source_kind={source_kind!r}; "
            f"only {_LAKE_SOURCE_KIND!r} "
            "(synthetic_fixture / RunInput JSON cannot masquerade as lake)"
        )
    bars = recipe.get("bars")
    if type(bars) is not list or not bars:
        raise ValueError("recipe.bars required for CLI lake")
    for index, bar in enumerate(bars):
        if type(bar) is not dict:
            raise ValueError(f"recipe.bars[{index}] must be object")
        time_spec = bar.get("time")
        if type(time_spec) is not dict:
            raise ValueError(f"recipe.bars[{index}].time required")
        label = time_spec.get("label")
        if label != _LAKE_BAR_TIME_LABEL:
            raise ValueError(
                f"CLI lake requires bar_time_label={_LAKE_BAR_TIME_LABEL!r} (Phase5); "
                f"got bars[{index}].time.label={label!r}"
            )
        availability = bar.get("availability")
        if availability != _LAKE_AVAILABILITY:
            raise ValueError(
                f"CLI lake requires availability={_LAKE_AVAILABILITY!r}; "
                f"got bars[{index}].availability={availability!r}"
            )
    recipe_run_id = recipe.get("run_id")
    if recipe_run_id != run_id:
        raise ValueError(
            f"CLI --run-id {run_id!r} must match recipe.run_id {recipe_run_id!r}"
        )
    recipe_parent = recipe.get("parent")
    if type(recipe_parent) is not str or not recipe_parent.strip():
        raise ValueError("recipe.parent must be an absolute path string")
    if str(Path(recipe_parent).resolve()) != str(Path(parent).resolve()):
        raise ValueError(
            "CLI --parent must resolve to the same absolute path as recipe.parent"
        )


def _load_lake_source(recipe_path, *, expected_sha256, parent, run_id):
    """Preflight lake+END recipe → existing loader (read-only)."""
    from .source_loader import load_minute_orders_source
    from .source_provenance import SourceContractError, sha256, strict_json

    path = Path(recipe_path)
    if not path.is_absolute():
        raise ValueError("recipe ref must be absolute")
    path = path.resolve()
    try:
        raw = path.read_bytes()
    except OSError as error:
        raise ValueError(f"recipe unreadable: {path}: {error}") from error
    actual = sha256(raw)
    if actual != expected_sha256:
        raise ValueError(
            f"recipe hash mismatch: expected={expected_sha256} actual={actual}"
        )
    try:
        recipe = strict_json(raw, str(path))
    except SourceContractError as error:
        raise ValueError(str(error)) from error
    _preflight_lake_recipe(recipe, parent=parent, run_id=run_id)
    try:
        return load_minute_orders_source(path, expected_sha256=expected_sha256)
    except SourceContractError as error:
        raise ValueError(str(error)) from error


def _validate_completion(result, run_id, *, cli_evidence_level):
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
    if cli_evidence_level == "synthetic":
        if (manifest.get("schema_version") != SCHEMA_VERSION
                or manifest.get("evidence_level") != "synthetic"
                or manifest.get("comparison_status") != COMPARISON_STATUS
                or (root / "failure.json").exists()):
            raise ValueError("invalid success manifest or conflicting failure evidence")
    elif cli_evidence_level == "lake":
        # CLI lake → S4 hybrid artifacts; source_kind remains lake.
        if (manifest.get("schema_version") != HYBRID_SCHEMA_VERSION
                or manifest.get("evidence_level") != "hybrid"
                or manifest.get("evidence_schema_version") != _HYBRID_EVIDENCE_SCHEMA
                or manifest.get("source_kind") != _LAKE_SOURCE_KIND
                or manifest.get("comparison_status") != COMPARISON_STATUS
                or manifest.get("host_attestation_status") != "not_certified_by_writer"
                or manifest.get("live_acceptance_status") != "not_assessed"
                or type(manifest.get("source_provenance_hash")) is not str
                or not re.fullmatch(r"[0-9a-f]{64}", manifest["source_provenance_hash"])
                or not (root / "source_provenance.json").is_file()
                or (root / "failure.json").exists()):
            raise ValueError("invalid hybrid lake success manifest or conflicting failure evidence")
        published = json.loads((root / "source_provenance.json").read_bytes())
        if type(published) is not dict or published.get("source_kind") != _LAKE_SOURCE_KIND:
            raise ValueError("source_provenance.json missing lake source_kind")
    else:
        raise ValueError(f"unknown cli evidence level: {cli_evidence_level!r}")
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


def _resolve_run_input(args):
    """Dispatch synthetic JSON vs lake recipe; never fall back across sources."""
    if args.evidence_level == "synthetic":
        if args.recipe is not None or args.expected_sha256 is not None:
            raise ValueError(
                "synthetic evidence refuses --recipe/--expected-sha256 "
                "(use --evidence-level=lake for pinned lake recipes)"
            )
        if args.input is None:
            raise ValueError("--input is required for --evidence-level=synthetic")
        return load_run_input(args.input), None, "synthetic"
    if args.evidence_level == "lake":
        if args.input is not None:
            raise ValueError(
                "lake evidence refuses --input RunInput JSON "
                "(pinned --recipe/--expected-sha256 only; no synthetic masquerade)"
            )
        if args.code_sha is not None:
            raise ValueError(
                "lake evidence rejects --code-sha overrides "
                "(hybrid pins git HEAD via loader provenance)"
            )
        if args.recipe is None or args.expected_sha256 is None:
            raise ValueError(
                "--recipe and --expected-sha256 are required for --evidence-level=lake"
            )
        loaded = _load_lake_source(
            args.recipe, expected_sha256=args.expected_sha256,
            parent=args.parent, run_id=args.run_id,
        )
        return loaded.run_input, loaded.provenance, "hybrid"
    raise ValueError(f"unsupported evidence level: {args.evidence_level!r}")


def main(argv=None):
    args = _parser().parse_args(argv)
    try:
        run_input, source_provenance, s4_evidence_level = _resolve_run_input(args)
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
            evidence_level=s4_evidence_level, code_sha=args.code_sha,
            source_provenance=source_provenance,
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
        _validate_completion(result, args.run_id, cli_evidence_level=args.evidence_level)
    except (OSError, ValueError, TypeError, RecursionError) as error:
        _report("output_error", stream=sys.stderr, root=str(result.root),
                error_type=type(error).__name__, reason=str(error))
        return OUTPUT_ERROR
    _report("success", stream=sys.stdout, root=str(result.root),
            summary=str(result.root / "summary.json"))
    return 0
