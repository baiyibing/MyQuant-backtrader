"""Thin synthetic demo for TC2 narrow X1 frozen LIMIT batch consumer.

Builds a handcalc-style a-priori LIMIT batch, freezes it, then calls the
existing minute_orders_research_v1 in-memory runner. No lake loader.
≠δ5≠R4; adapter identity only — does not mint a new backend_id.
"""

from __future__ import annotations

import json
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
)

TZ = ZoneInfo("Asia/Shanghai")
D = Decimal
PREV, D0, D1 = date(2026, 9, 25), date(2026, 9, 28), date(2026, 9, 29)
ZERO_FEES = FeeModelParams(D("0"), D("0.00"), ROUND_HALF_UP)


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


def main(argv=None):
    del argv  # thin demo; no CLI flags
    intents, facts = _synthetic_sketch_a()
    outcome = run_x1_frozen_batch(intents, **facts)
    report = {
        "adapter_id": outcome.adapter_id,
        "backend_id": "minute_orders_research_v1",
        "contract": "research contract v0 (L2-S0)",
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
        "note": "adapter identity only; ≠δ5≠R4; no new economic contract/backend_id",
    }
    print(json.dumps(report, ensure_ascii=True, sort_keys=True, indent=2))
    # Sanity: sketch A expected terminal states
    by_id = {s.order.order_id: s for s in outcome.result.orders}
    ok = (
        outcome.adapter_id == ADAPTER_ID
        and by_id["O1"].status is OrderStatus.FILLED
        and by_id["O1"].filled_qty == 300
        and by_id["O2"].status is OrderStatus.EXPIRED
        and by_id["O2"].filled_qty == 100
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
