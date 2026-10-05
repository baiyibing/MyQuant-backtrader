"""Named X1 consumer: frozen LIMIT batch → existing v0 runner (in-memory first).

Assembles RunInput from explicit caller facts + a priori frozen commands, then
calls run_minute_orders_research. Optional artifact write reuses the existing
S4 wrapper (already refuses overwrite of existing roots). Does not import
broker / match / ledger internals.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Iterable, Sequence

from backtest.research.minute_orders_backend.runner import (
    run_minute_orders_research,
    run_minute_orders_research_with_artifacts,
)
from backtest.research.minute_orders_backend.types import (
    CalendarFacts,
    CancelOrder,
    CompletedBucket,
    FeeModelParams,
    InstrumentFacts,
    LotPosition,
    MarkEvent,
    RunInput,
    RunResult,
    SubmitOrder,
)

from .builders import (
    ADAPTER_ID,
    CancelIntent,
    IntentBuildError,
    LimitIntent,
    freeze_command_batch,
)


@dataclass(frozen=True)
class FrozenBatchRun:
    """Result of the named consumer, including the a-priori frozen commands."""

    adapter_id: str
    commands: tuple[SubmitOrder | CancelOrder, ...]
    run_input: RunInput
    result: RunResult


@dataclass(frozen=True)
class FrozenBatchArtifacts:
    """Optional S4 artifact outcome; root refusal semantics unchanged from v0."""

    adapter_id: str
    commands: tuple[SubmitOrder | CancelOrder, ...]
    run_input: RunInput
    artifacts: object  # ArtifactWriteResult from S4; typed loosely to avoid importing artifacts


def assemble_run_input(
    *,
    commands: tuple[SubmitOrder | CancelOrder, ...],
    start_at: datetime,
    end_at: datetime,
    buckets: Sequence[CompletedBucket],
    calendar: CalendarFacts,
    instruments: Sequence[InstrumentFacts],
    initial_cash: Decimal,
    initial_lots: Sequence[LotPosition],
    buy_fees: FeeModelParams,
    sell_fees: FeeModelParams,
    participation_rate: Decimal,
    marks: Sequence[MarkEvent] = (),
    requires_marks: bool = False,
) -> RunInput:
    """Assemble RunInput from an already-frozen command batch + explicit facts.

    No economic defaults: every field is caller-supplied (marks/requires_marks
    keep the same optional observation contract as the S3 runner).
    """
    if type(commands) is not tuple:
        raise IntentBuildError("commands must be a frozen tuple from freeze_command_batch")
    if any(type(c) not in (SubmitOrder, CancelOrder) for c in commands):
        raise IntentBuildError("commands must contain only SubmitOrder / CancelOrder")
    return RunInput(
        start_at,
        end_at,
        commands,
        tuple(buckets),
        calendar,
        tuple(instruments),
        initial_cash,
        tuple(initial_lots),
        buy_fees,
        sell_fees,
        participation_rate,
        tuple(marks),
        requires_marks,
    )


def run_x1_frozen_batch(
    intents: Sequence[LimitIntent | CancelIntent] | Iterable[LimitIntent | CancelIntent],
    *,
    start_at: datetime,
    end_at: datetime,
    buckets: Sequence[CompletedBucket],
    calendar: CalendarFacts,
    instruments: Sequence[InstrumentFacts],
    initial_cash: Decimal,
    initial_lots: Sequence[LotPosition] = (),
    buy_fees: FeeModelParams,
    sell_fees: FeeModelParams,
    participation_rate: Decimal,
    marks: Sequence[MarkEvent] = (),
    requires_marks: bool = False,
) -> FrozenBatchRun:
    """Freeze LIMIT intents a priori, assemble RunInput, call existing runner.

    Order of steps is intentional and test-observable:
    1. freeze_command_batch(intents) — batch fixed, no runner yet
    2. assemble_run_input(..., commands=that_batch)
    3. run_minute_orders_research(run_input) — v0 economic path unchanged
    """
    commands = freeze_command_batch(intents)
    run_input = assemble_run_input(
        commands=commands,
        start_at=start_at,
        end_at=end_at,
        buckets=buckets,
        calendar=calendar,
        instruments=instruments,
        initial_cash=initial_cash,
        initial_lots=initial_lots,
        buy_fees=buy_fees,
        sell_fees=sell_fees,
        participation_rate=participation_rate,
        marks=marks,
        requires_marks=requires_marks,
    )
    # Identity check: RunInput must carry the exact frozen tuple (no rebuild).
    if run_input.commands is not commands:
        raise IntentBuildError("RunInput commands must be the frozen batch identity")
    result = run_minute_orders_research(run_input)
    return FrozenBatchRun(ADAPTER_ID, commands, run_input, result)


def run_x1_frozen_batch_with_artifacts(
    intents: Sequence[LimitIntent | CancelIntent] | Iterable[LimitIntent | CancelIntent],
    *,
    start_at: datetime,
    end_at: datetime,
    buckets: Sequence[CompletedBucket],
    calendar: CalendarFacts,
    instruments: Sequence[InstrumentFacts],
    initial_cash: Decimal,
    initial_lots: Sequence[LotPosition] = (),
    buy_fees: FeeModelParams,
    sell_fees: FeeModelParams,
    participation_rate: Decimal,
    marks: Sequence[MarkEvent] = (),
    requires_marks: bool = False,
    parent,
    run_id: str,
    evidence_level: str = "synthetic",
    code_sha=None,
) -> FrozenBatchArtifacts:
    """Same freeze→assemble path; optional S4 write under existing backend root.

    Does not mint a new backend_id. Existing-root refusal is enforced by S4.
    """
    commands = freeze_command_batch(intents)
    run_input = assemble_run_input(
        commands=commands,
        start_at=start_at,
        end_at=end_at,
        buckets=buckets,
        calendar=calendar,
        instruments=instruments,
        initial_cash=initial_cash,
        initial_lots=initial_lots,
        buy_fees=buy_fees,
        sell_fees=sell_fees,
        participation_rate=participation_rate,
        marks=marks,
        requires_marks=requires_marks,
    )
    if run_input.commands is not commands:
        raise IntentBuildError("RunInput commands must be the frozen batch identity")
    artifacts = run_minute_orders_research_with_artifacts(
        run_input, parent, run_id=run_id, evidence_level=evidence_level, code_sha=code_sha,
    )
    return FrozenBatchArtifacts(ADAPTER_ID, commands, run_input, artifacts)
