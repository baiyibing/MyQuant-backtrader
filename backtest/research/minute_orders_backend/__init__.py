"""L2-S1/S2 public exports only.

Clock, BrokerCore and runner live in submodules and are imported explicitly;
see docs/backtest/note-l2-s3-clock-broker-runner-2026-09-29.md.
"""

from .fees import FeeModel
from .ledger import Ledger
from .match import compute_bucket_capacity, match_candidates
from .types import (
    BucketCapacity,
    BucketQuote,
    CandidateMatch,
    FeeContractError,
    FeeModelParams,
    FillApplied,
    FillProposal,
    LedgerError,
    LedgerSnapshot,
    LimitOrderMatchInput,
    LotAllocation,
    LotPosition,
    MatchContractError,
    MatchReason,
    NoMatch,
    OrderTotals,
    Reservation,
    ReservationRejected,
    ResourceRejectReason,
    Side,
)

__all__ = [
    "BucketCapacity",
    "BucketQuote",
    "CandidateMatch",
    "FeeContractError",
    "FeeModel",
    "FeeModelParams",
    "FillApplied",
    "FillProposal",
    "Ledger",
    "LedgerError",
    "LedgerSnapshot",
    "LimitOrderMatchInput",
    "LotAllocation",
    "LotPosition",
    "MatchContractError",
    "MatchReason",
    "NoMatch",
    "OrderTotals",
    "Reservation",
    "ReservationRejected",
    "ResourceRejectReason",
    "Side",
    "compute_bucket_capacity",
    "match_candidates",
]
