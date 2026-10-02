"""TC3 named consumer closed loop: CLI HELP + freeze→run handcalc + optional S4."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from backtest.research.minute_orders_backend.types import (
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
from backtest.research.minute_orders_intent_x1 import (
    ADAPTER_ID,
    LimitIntent,
    freeze_command_batch,
    run_x1_frozen_batch,
    run_x1_frozen_batch_with_artifacts,
)

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "research" / "run_x1_frozen_batch.py"
FIXTURE = ROOT / "tests" / "fixtures" / "minute_orders_intent_x1" / "sketch_a_meta.json"
SHA = "c0ffee00c0ffee00c0ffee00c0ffee00c0ffee00"

D = Decimal
TZ = ZoneInfo("Asia/Shanghai")
PREV, D0, D1 = date(2026, 9, 25), date(2026, 9, 28), date(2026, 9, 29)
ZERO_FEES = FeeModelParams(D("0"), D("0.00"), ROUND_HALF_UP)


def at(value, day=D0):
    return datetime.fromisoformat(f"{day}T{value}").replace(tzinfo=TZ)


def bucket(start="09:30:00", *, close="10.00", volume=1000):
    begin = at(start)
    return CompletedBucket(
        "X", begin.isoformat(), begin, begin + timedelta(minutes=1),
        D(close), volume, False, False,
    )


def sketch_a_intents_and_facts():
    intents = (
        LimitIntent(
            "O1", "X", Side.BUY, 300, D("10.00"),
            at("09:29:00"), at("09:29:00"), at("09:30:00"), at("09:33:00"), 1,
        ),
        LimitIntent(
            "O2", "X", Side.BUY, 200, D("10.00"),
            at("09:29:01"), at("09:29:01"), at("09:30:00"), at("09:33:00"), 2,
        ),
    )
    buckets = (bucket(), bucket("09:31:00"), bucket("09:32:00"))
    sessions = tuple(
        SessionBucket(b.bucket_id, b.start, b.end, "continuous") for b in buckets
    )
    marks = tuple(
        MarkEvent(
            f"mark:{t}", at(t), at(t), (MarkPrice("X", D("10.00")),),
            "raw", "synthetic tc3",
        )
        for t in ("09:29:01", "09:31:00", "09:32:00", "09:33:00")
    )
    facts = dict(
        start_at=at("09:28:00"),
        end_at=at("09:35:00"),
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
    return intents, facts


def launch(cwd, argv=None, *, timeout=30):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *(argv or [])],
        cwd=cwd, capture_output=True, text=True, check=False, timeout=timeout,
    )


def test_cli_help_documents_adapter_contract_backend_and_bans(tmp_path):
    process = launch(tmp_path, ["--help"])
    assert process.returncode == 0, process.stderr
    help_text = process.stdout
    assert "minute_orders_intent_x1" in help_text
    assert "research contract v0 (L2-S0)" in help_text
    assert "minute_orders_research_v1" in help_text
    assert "no new economic contract" in help_text
    assert "no second price model" in help_text
    assert "no MatchCore" in help_text
    assert "no lake write" in help_text
    assert "≠δ5" in help_text or "delta5" in help_text.lower() or "δ5" in help_text
    assert "forever opt-in" in help_text
    assert "BOOKS" in help_text
    assert "--preset" in help_text
    assert "--write-artifacts" in help_text
    assert list(tmp_path.iterdir()) == []


def test_cli_closed_loop_sketch_a_with_fixture_meta(tmp_path):
    process = launch(tmp_path, ["--preset", "sketch_a", "--fixture", str(FIXTURE)])
    assert process.returncode == 0, process.stderr
    report = json.loads(process.stdout)
    assert report["adapter_id"] == ADAPTER_ID
    assert report["backend_id"] == "minute_orders_research_v1"
    assert report["contract"] == "research contract v0 (L2-S0)"
    assert report["command_ids"] == ["submit:O1", "submit:O2"]
    assert report["fixture_preset"] == "sketch_a"
    by_id = {o["order_id"]: o for o in report["orders"]}
    assert by_id["O1"] == {
        "order_id": "O1", "status": "Filled", "filled_qty": 300, "remaining_qty": 0,
    }
    assert by_id["O2"] == {
        "order_id": "O2", "status": "Expired", "filled_qty": 100, "remaining_qty": 100,
    }
    assert report["fill_count"] == 3
    assert D(report["fees_paid"]) == D("0")
    assert list(tmp_path.iterdir()) == []


def test_api_closed_loop_freeze_then_run_handcalc():
    """freeze intents → run_x1_frozen_batch → handcalc sketch A (reuse X1 semantics)."""
    intents, facts = sketch_a_intents_and_facts()
    frozen = freeze_command_batch(intents)
    assert [c.command_id for c in frozen] == ["submit:O1", "submit:O2"]

    outcome = run_x1_frozen_batch(intents, **facts)
    assert outcome.adapter_id == ADAPTER_ID
    assert outcome.commands == frozen
    assert outcome.run_input.commands is outcome.commands

    fills = [
        (f.proposal.order_id, f.proposal.qty, f.proposal.price, f.proposal.fee_delta)
        for f in outcome.result.fills
    ]
    assert fills == [
        ("O1", 200, D("10"), D("0")),
        ("O1", 100, D("10"), D("0")),
        ("O2", 100, D("10"), D("0")),
    ]
    states = {
        s.order.order_id: (s.status, s.filled_qty, s.remaining_qty)
        for s in outcome.result.orders
    }
    assert states == {
        "O1": (OrderStatus.FILLED, 300, 0),
        "O2": (OrderStatus.EXPIRED, 100, 100),
    }
    assert outcome.result.ledger.fees_paid == D("0")
    assert sum(l.qty for l in outcome.result.ledger.lots) == 400


def test_api_closed_loop_with_artifacts_unique_run_id_and_overwrite_refusal(tmp_path):
    intents, facts = sketch_a_intents_and_facts()
    run_id = "tc3-sketch-a-unique"
    first = run_x1_frozen_batch_with_artifacts(
        intents,
        parent=tmp_path,
        run_id=run_id,
        evidence_level="synthetic",
        code_sha=SHA,
        **facts,
    )
    assert first.adapter_id == ADAPTER_ID
    assert first.artifacts.status == "success"
    root = Path(first.artifacts.root)
    assert root.is_dir()
    summary = json.loads((root / "summary.json").read_text(encoding="utf-8"))
    assert summary["backend_id"] == "minute_orders_research_v1"
    assert summary["fill_count"] == 3
    by_id = {o["order_id"]: o for o in summary["orders"]}
    assert by_id["O1"]["status"] == "Filled" and by_id["O1"]["filled_qty"] == 300
    assert by_id["O2"]["status"] == "Expired" and by_id["O2"]["filled_qty"] == 100

    # S4 existing-root refusal still enforced by the writer (not bypassed by X1).
    with pytest.raises(FileExistsError):
        run_x1_frozen_batch_with_artifacts(
            intents,
            parent=tmp_path,
            run_id=run_id,
            evidence_level="synthetic",
            code_sha=SHA,
            **facts,
        )


def test_fixture_meta_identity_matches_adapter_constants():
    meta = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert meta["adapter_id"] == ADAPTER_ID
    assert meta["contract"] == "research contract v0 (L2-S0)"
    assert meta["backend_id"] == "minute_orders_research_v1"
    assert meta["evidence_level"] == "synthetic"
    assert meta["preset"] == "sketch_a"
    assert "no_new_backend_id" in meta["bans"]
    assert "forever_opt_in" in meta["bans"]
    assert meta["expected_orders"]["O1"]["filled_qty"] == 300
    assert meta["expected_orders"]["O2"]["status"] == "Expired"


def test_cli_write_artifacts_then_refuse_overwrite(tmp_path):
    run_id = "tc3-cli-art"
    argv = [
        "--preset", "sketch_a",
        "--fixture", str(FIXTURE),
        "--write-artifacts",
        "--parent", str(tmp_path),
        "--run-id", run_id,
        "--evidence-level", "synthetic",
        "--code-sha", SHA,
    ]
    first = launch(tmp_path, argv)
    assert first.returncode == 0, first.stderr
    report = json.loads(first.stdout)
    assert report["adapter_id"] == ADAPTER_ID
    assert report["status"] == "success"
    assert Path(report["root"]).is_dir()

    second = launch(tmp_path, argv)
    assert second.returncode == 4, second.stdout + second.stderr
    err = json.loads(second.stderr)
    assert err["status"] == "output_error"
    assert err["error_type"] == "FileExistsError"
