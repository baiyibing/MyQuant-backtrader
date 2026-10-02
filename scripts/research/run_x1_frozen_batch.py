"""Named TC3 CLI for the minute_orders_intent_x1 frozen-batch consumer.

Human-invokable surface for the TC2 X1 adapter: freeze a-priori LIMIT intents,
then call the existing minute_orders_research_v1 in-memory runner (optional S4
write under the same backend root). Does not mint a new economic contract or
backend_id. ≠δ5≠R4; forever opt-in; never BOOKS default.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backtest.research.minute_orders_backend.types import (  # noqa: E402
    CalendarFacts,
    CompletedBucket,
    FeeModelParams,
    InstrumentFacts,
    MarkEvent,
    MarkPrice,
    OrderStatus,
    SessionBucket,
    Side,
)
from backtest.research.minute_orders_intent_x1 import (  # noqa: E402
    ADAPTER_ID,
    LimitIntent,
    run_x1_frozen_batch,
    run_x1_frozen_batch_with_artifacts,
)

TZ = ZoneInfo("Asia/Shanghai")
D = Decimal
PREV, D0, D1 = date(2026, 9, 25), date(2026, 9, 28), date(2026, 9, 29)
ZERO_FEES = FeeModelParams(D("0"), D("0.00"), ROUND_HALF_UP)
CONTRACT = "research contract v0 (L2-S0)"
BACKEND_ID = "minute_orders_research_v1"

HELP_DESCRIPTION = (
    "Named consumer for adapter_id=minute_orders_intent_x1: freeze a-priori "
    "LIMIT intents, then call existing minute_orders_research_v1. "
    f"Contract remains {CONTRACT}; backend_id remains {BACKEND_ID}. "
    "Synthetic / attestation-level only; no lake loader."
)

HELP_EPILOG = """\
Identity (unchanged from TC2 X1 / L2-S0):
  adapter_id   minute_orders_intent_x1   (adapter layer only; not a backend_id)
  contract     research contract v0 (L2-S0)
  backend_id   minute_orders_research_v1

Bans / out of scope:
  - no new economic contract or backend_id
  - no second price model (H-TC3=否)
  - no MatchCore / Fees / simulate / VolumeCap edits
  - no lake write; --evidence-level synthetic only
  - ≠δ5 certified ≠R4; no green-R / NAV mix-compare
  - forever opt-in; never BOOKS default
  - no X2–X8 / P3 / fills→intent / Compat main path

See docs/backtest/note-true-core-tc3-named-consumer-2026-10-02.md
"""


def _at(value: str, day=D0) -> datetime:
    return datetime.fromisoformat(f"{day}T{value}").replace(tzinfo=TZ)


def _bucket(start: str, *, close="10.00", volume=1000) -> CompletedBucket:
    begin = _at(start)
    return CompletedBucket(
        "X", begin.isoformat(), begin, begin + timedelta(minutes=1),
        D(close), volume, False, False,
    )


def _synthetic_sketch_a():
    """S0 handcalc sketch A: two BUY LIMITs sharing capacity, then expiry."""
    intents = (
        LimitIntent(
            "O1", "X", Side.BUY, 300, D("10.00"),
            _at("09:29:00"), _at("09:29:00"), _at("09:30:00"), _at("09:33:00"), 1,
        ),
        LimitIntent(
            "O2", "X", Side.BUY, 200, D("10.00"),
            _at("09:29:01"), _at("09:29:01"), _at("09:30:00"), _at("09:33:00"), 2,
        ),
    )
    buckets = (_bucket("09:30:00"), _bucket("09:31:00"), _bucket("09:32:00"))
    sessions = tuple(
        SessionBucket(b.bucket_id, b.start, b.end, "continuous") for b in buckets
    )
    marks = tuple(
        MarkEvent(
            f"mark:{t}", _at(t), _at(t), (MarkPrice("X", D("10.00")),),
            "raw", "synthetic x1 demo",
        )
        for t in ("09:29:01", "09:31:00", "09:32:00", "09:33:00")
    )
    return intents, dict(
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


def _run_id(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", value):
        raise argparse.ArgumentTypeError("run_id must be a single safe ASCII path component")
    return value


def _nonempty(value: str) -> str:
    if not value.strip():
        raise argparse.ArgumentTypeError("an explicit nonempty path is required")
    return value


def _code_sha(value: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{40}", value):
        raise argparse.ArgumentTypeError("code_sha must be a full lowercase git SHA")
    return value


def _load_fixture_meta(path: Path) -> dict:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if type(raw) is not dict:
        raise ValueError("fixture meta must be a JSON object")
    if raw.get("adapter_id") != ADAPTER_ID:
        raise ValueError(f"fixture adapter_id must be {ADAPTER_ID}")
    if raw.get("contract") != CONTRACT:
        raise ValueError(f"fixture contract must remain {CONTRACT}")
    if raw.get("backend_id") != BACKEND_ID:
        raise ValueError(f"fixture backend_id must remain {BACKEND_ID}")
    if raw.get("evidence_level") != "synthetic":
        raise ValueError("fixture evidence_level must be synthetic (no lake)")
    preset = raw.get("preset")
    if preset not in ("sketch_a",):
        raise ValueError(f"unsupported fixture preset: {preset!r}")
    return raw


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run_x1_frozen_batch.py",
        allow_abbrev=False,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=HELP_DESCRIPTION,
        epilog=HELP_EPILOG,
    )
    parser.add_argument(
        "--preset",
        choices=("sketch_a",),
        default="sketch_a",
        help="built-in synthetic sketch (default: sketch_a S0 handcalc)",
    )
    parser.add_argument(
        "--fixture",
        type=_nonempty,
        help=(
            "optional path to attestation-level fixture meta JSON; loaded only when "
            "passed; verifies adapter_id / contract / backend_id / evidence_level / "
            "preset and expected_* terminal states; does NOT supply market data "
            "(example: tests/fixtures/minute_orders_intent_x1/sketch_a_meta.json)"
        ),
    )
    parser.add_argument(
        "--write-artifacts",
        action="store_true",
        help="also write via existing S4 wrapper under minute_orders_research_v1",
    )
    parser.add_argument(
        "--parent",
        type=_nonempty,
        help="artifact parent directory (required with --write-artifacts)",
    )
    parser.add_argument(
        "--run-id",
        type=_run_id,
        help="new isolated run identity; never overwrite (required with --write-artifacts)",
    )
    parser.add_argument(
        "--evidence-level",
        choices=("synthetic",),
        default="synthetic",
        help="artifact evidence level (synthetic only; no lake loader)",
    )
    parser.add_argument(
        "--code-sha",
        type=_code_sha,
        help="explicit provenance override for S4; otherwise S4 reads git HEAD",
    )
    return parser


def _sketch_a_ok(outcome) -> bool:
    by_id = {s.order.order_id: s for s in outcome.result.orders}
    return (
        outcome.adapter_id == ADAPTER_ID
        and by_id["O1"].status is OrderStatus.FILLED
        and by_id["O1"].filled_qty == 300
        and by_id["O2"].status is OrderStatus.EXPIRED
        and by_id["O2"].filled_qty == 100
    )


def _sketch_a_orders_ok(orders) -> bool:
    """Dict-form sketch A terminal gate (memory report or summary.json orders)."""
    by_id = {o["order_id"]: o for o in orders}
    o1, o2 = by_id.get("O1"), by_id.get("O2")
    if o1 is None or o2 is None:
        return False
    return (
        o1.get("status") == OrderStatus.FILLED.value
        and o1.get("filled_qty") == 300
        and o2.get("status") == OrderStatus.EXPIRED.value
        and o2.get("filled_qty") == 100
    )


def _normalize_order_rows(orders) -> list:
    return [
        {
            "order_id": o["order_id"],
            "status": o["status"] if isinstance(o["status"], str) else str(o["status"]),
            "filled_qty": o["filled_qty"],
            "remaining_qty": o["remaining_qty"],
        }
        for o in orders
    ]


def _fixture_expected_ok(orders, fill_count, fees_paid, fixture_meta) -> bool:
    """Compare report terminal state against fixture expected_* (attestation gate)."""
    expected_orders = fixture_meta.get("expected_orders")
    if type(expected_orders) is not dict:
        return False
    by_id = {o["order_id"]: o for o in orders}
    for order_id, expected in expected_orders.items():
        got = by_id.get(order_id)
        if got is None:
            return False
        if got.get("status") != expected.get("status"):
            return False
        if got.get("filled_qty") != expected.get("filled_qty"):
            return False
        if got.get("remaining_qty") != expected.get("remaining_qty"):
            return False
    if fill_count != fixture_meta.get("expected_fill_count"):
        return False
    try:
        if D(str(fees_paid)) != D(str(fixture_meta.get("expected_fees_paid"))):
            return False
    except Exception:
        return False
    return True


def _terminal_ok(orders, fill_count, fees_paid, *, adapter_id, fixture_meta) -> bool:
    ok = adapter_id == ADAPTER_ID and _sketch_a_orders_ok(orders)
    if fixture_meta is not None:
        ok = ok and _fixture_expected_ok(orders, fill_count, fees_paid, fixture_meta)
    return ok


def _memory_report(outcome) -> dict:
    return {
        "adapter_id": outcome.adapter_id,
        "backend_id": BACKEND_ID,
        "contract": CONTRACT,
        "command_count": len(outcome.commands),
        "command_ids": [c.command_id for c in outcome.commands],
        "orders": [
            {
                "order_id": s.order.order_id,
                "status": s.status.value,
                "filled_qty": s.filled_qty,
                "remaining_qty": s.remaining_qty,
            }
            for s in outcome.result.orders
        ],
        "fill_count": len(outcome.result.fills),
        "fees_paid": str(outcome.result.ledger.fees_paid),
        "note": (
            "adapter identity only; ≠δ5≠R4; no new economic contract/backend_id; "
            "forever opt-in; never BOOKS default"
        ),
    }


def main(argv=None):
    args = _parser().parse_args(argv)
    fixture_meta = None
    if args.fixture is not None:
        try:
            fixture_meta = _load_fixture_meta(Path(args.fixture))
        except (OSError, ValueError, json.JSONDecodeError) as error:
            print(
                json.dumps(
                    {
                        "status": "input_error",
                        "reason": str(error),
                        "error_type": type(error).__name__,
                    },
                    ensure_ascii=True,
                    sort_keys=True,
                ),
                file=sys.stderr,
            )
            return 2
        if fixture_meta["preset"] != args.preset:
            print(
                json.dumps(
                    {
                        "status": "input_error",
                        "reason": (
                            f"fixture preset {fixture_meta['preset']!r} "
                            f"!= --preset {args.preset!r}"
                        ),
                    },
                    ensure_ascii=True,
                    sort_keys=True,
                ),
                file=sys.stderr,
            )
            return 2

    if args.preset != "sketch_a":
        print(
            json.dumps(
                {"status": "input_error", "reason": f"unsupported preset {args.preset!r}"},
                ensure_ascii=True,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2

    if args.write_artifacts and (args.parent is None or args.run_id is None):
        print(
            json.dumps(
                {
                    "status": "input_error",
                    "reason": "--write-artifacts requires --parent and --run-id",
                },
                ensure_ascii=True,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2

    intents, facts = _synthetic_sketch_a()
    if args.write_artifacts:
        try:
            artifacts_outcome = run_x1_frozen_batch_with_artifacts(
                intents,
                parent=args.parent,
                run_id=args.run_id,
                evidence_level=args.evidence_level,
                code_sha=args.code_sha,
                **facts,
            )
        except FileExistsError as error:
            print(
                json.dumps(
                    {
                        "status": "output_error",
                        "error_type": "FileExistsError",
                        "reason": str(error),
                        "adapter_id": ADAPTER_ID,
                        "backend_id": BACKEND_ID,
                        "note": "S4 existing-root refusal unchanged",
                    },
                    ensure_ascii=True,
                    sort_keys=True,
                ),
                file=sys.stderr,
            )
            return 4
        except Exception as error:
            print(
                json.dumps(
                    {
                        "status": "output_error",
                        "error_type": type(error).__name__,
                        "reason": str(error),
                        "adapter_id": ADAPTER_ID,
                        "backend_id": BACKEND_ID,
                    },
                    ensure_ascii=True,
                    sort_keys=True,
                ),
                file=sys.stderr,
            )
            return 4
        art = artifacts_outcome.artifacts
        root = Path(getattr(art, "root", ""))
        summary = json.loads((root / "summary.json").read_text(encoding="utf-8"))
        orders = _normalize_order_rows(summary["orders"])
        fill_count = summary["fill_count"]
        fees_paid = str(summary.get("fees_paid", "0"))
        report = {
            "adapter_id": artifacts_outcome.adapter_id,
            "backend_id": BACKEND_ID,
            "contract": CONTRACT,
            "command_count": len(artifacts_outcome.commands),
            "command_ids": [c.command_id for c in artifacts_outcome.commands],
            "status": getattr(art, "status", None),
            "root": str(root),
            "orders": orders,
            "fill_count": fill_count,
            "fees_paid": fees_paid,
            "fixture_preset": None if fixture_meta is None else fixture_meta["preset"],
            "note": (
                "adapter identity only; ≠δ5≠R4; S4 write under existing backend root; "
                "forever opt-in; never BOOKS default"
            ),
        }
        if fixture_meta is not None:
            report["fixture_adapter_id"] = fixture_meta["adapter_id"]
        print(json.dumps(report, ensure_ascii=True, sort_keys=True, indent=2))
        ok = (
            getattr(art, "status", None) == "success"
            and _terminal_ok(
                orders,
                fill_count,
                fees_paid,
                adapter_id=artifacts_outcome.adapter_id,
                fixture_meta=fixture_meta,
            )
        )
        return 0 if ok else 1

    outcome = run_x1_frozen_batch(intents, **facts)
    report = _memory_report(outcome)
    if fixture_meta is not None:
        report["fixture_preset"] = fixture_meta["preset"]
        report["fixture_adapter_id"] = fixture_meta["adapter_id"]
    print(json.dumps(report, ensure_ascii=True, sort_keys=True, indent=2))
    ok = _sketch_a_ok(outcome)
    if fixture_meta is not None:
        ok = ok and _fixture_expected_ok(
            report["orders"],
            report["fill_count"],
            report["fees_paid"],
            fixture_meta,
        )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
