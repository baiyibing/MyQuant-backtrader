"""In-memory research API and a separately invoked S4 artifact wrapper."""

from dataclasses import replace

from .broker import BrokerCore
from .types import RunInput, RunResult


def run_minute_orders_research(run_input: RunInput) -> RunResult:
    """Replay explicit facts once; malformed inputs propagate, no success result.

    Empty marks are allowed only with requires_marks=False. Provided marks must
    be valid and cover held symbols at that event; S3 returns observations, not
    a NAV product. Active orders at end_at retain their remaining reservations.
    """
    return BrokerCore(run_input).run()


class _ObservedBroker(BrokerCore):
    """Observe committed snapshots without changing any broker handler."""

    def _record(self, event, state):
        super()._record(event, state)
        self._transitions[-1] = replace(
            self._transitions[-1], ledger=self.ledger.snapshot(),
        )


def run_minute_orders_research_with_artifacts(
    run_input: RunInput, parent, *, run_id: str, evidence_level: str, code_sha=None,
):
    """Explicit disk opt-in; return ArtifactWriteResult (including run failures).

    The writer creates a new parent/backtest_output/minute_orders_research_v1/
    run_id root. Writer errors raise; engine errors become failed evidence only.
    The ordinary in-memory API above retains its original exception semantics.
    """
    from .artifacts import FailedRun, write_minute_orders_artifacts

    broker = None
    try:
        broker = _ObservedBroker(run_input)
        outcome = broker.run()
    except Exception as error:
        outcome = FailedRun(
            error, tuple(broker._transitions) if broker else (),
            tuple(broker._marks) if broker else (),
            broker.ledger.snapshot() if broker else None,
        )
    return write_minute_orders_artifacts(
        run_input, outcome, parent, run_id=run_id,
        evidence_level=evidence_level, code_sha=code_sha,
    )
