"""Pure out-of-core builders: explicit LIMIT intent → frozen command batch.

No Broker/MatchCore/Ledger imports. Commands use the existing v0 schema only.
The batch is fixed before any runner call; this module never mutates prior results.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Iterable, Literal, Sequence

from backtest.research.minute_orders_backend.types import CancelOrder, Side, SubmitOrder

ADAPTER_ID = "minute_orders_intent_x1"
# Adapter identity only — does NOT mint a new economic contract or backend_id.
# Reuses research contract v0 (L2-S0) / minute_orders_research_v1 unchanged.


class IntentBuildError(ValueError):
    """Malformed intent facts; nothing has been run."""


@dataclass(frozen=True)
class LimitIntent:
    """A-priori LIMIT intent. Becomes SubmitOrder when frozen into a batch."""

    order_id: str
    symbol: str
    side: Side
    qty: int
    limit: Decimal
    available_at: datetime
    submitted_at: datetime
    effective_at: datetime
    expires_at: datetime
    sequence: int
    command_id: str | None = None
    order_type: Literal["LIMIT"] = "LIMIT"


@dataclass(frozen=True)
class CancelIntent:
    """A-priori cancel intent targeting an order_id already in the same batch."""

    order_id: str
    available_at: datetime
    submitted_at: datetime
    effective_at: datetime
    sequence: int
    command_id: str | None = None


def _require_id(value: str, name: str) -> str:
    if type(value) is not str or not value.strip():
        raise IntentBuildError(f"{name} must be a nonempty string")
    return value


def _require_int(value: int, name: str, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise IntentBuildError(f"{name} must be an integer >= {minimum}")
    return value


def _require_price(value: Decimal, name: str) -> Decimal:
    if not isinstance(value, Decimal) or not value.is_finite() or value <= 0:
        raise IntentBuildError(f"{name} must be a finite positive Decimal")
    _, denominator = value.as_integer_ratio()
    if 100 % denominator:
        raise IntentBuildError(f"{name} must be cent-aligned; no price rounding")
    return value


def _require_aware(value: datetime, name: str) -> datetime:
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise IntentBuildError(f"{name} must be a timezone-aware datetime")
    return value


def build_submit_order(intent: LimitIntent) -> SubmitOrder:
    """Map one LimitIntent to an immutable SubmitOrder (LIMIT only)."""
    if type(intent) is not LimitIntent:
        raise IntentBuildError("expected LimitIntent")
    if intent.order_type != "LIMIT":
        raise IntentBuildError("only LIMIT intents are supported (no stop/market/replace/GTC)")
    if not isinstance(intent.side, Side):
        raise IntentBuildError("side must be Side.BUY or Side.SELL")
    order_id = _require_id(intent.order_id, "order_id")
    command_id = intent.command_id if intent.command_id is not None else f"submit:{order_id}"
    return SubmitOrder(
        _require_id(command_id, "command_id"),
        order_id,
        _require_id(intent.symbol, "symbol"),
        intent.side,
        _require_int(intent.qty, "qty", minimum=1),
        _require_price(intent.limit, "limit"),
        _require_aware(intent.available_at, "available_at"),
        _require_aware(intent.submitted_at, "submitted_at"),
        _require_aware(intent.effective_at, "effective_at"),
        _require_aware(intent.expires_at, "expires_at"),
        _require_int(intent.sequence, "sequence"),
        "LIMIT",
    )


def build_cancel_order(intent: CancelIntent) -> CancelOrder:
    """Map one CancelIntent to an immutable CancelOrder."""
    if type(intent) is not CancelIntent:
        raise IntentBuildError("expected CancelIntent")
    order_id = _require_id(intent.order_id, "order_id")
    command_id = intent.command_id if intent.command_id is not None else f"cancel:{order_id}"
    return CancelOrder(
        _require_id(command_id, "command_id"),
        order_id,
        _require_aware(intent.available_at, "available_at"),
        _require_aware(intent.submitted_at, "submitted_at"),
        _require_aware(intent.effective_at, "effective_at"),
        _require_int(intent.sequence, "sequence"),
    )


def freeze_command_batch(
    intents: Sequence[LimitIntent | CancelIntent] | Iterable[LimitIntent | CancelIntent],
) -> tuple[SubmitOrder | CancelOrder, ...]:
    """Build a frozen LIMIT command batch a priori. No runner side effects.

    The returned tuple is the sole command input for the consumer. Callers must
    not regenerate commands from fills or cash after this point (X8-style
    fills→intent is banned by TC1 §5/§6).
    """
    if not isinstance(intents, (list, tuple)):
        intents = tuple(intents)
    commands: list[SubmitOrder | CancelOrder] = []
    seen_command_ids: set[str] = set()
    for index, intent in enumerate(intents):
        if isinstance(intent, LimitIntent):
            command = build_submit_order(intent)
        elif isinstance(intent, CancelIntent):
            command = build_cancel_order(intent)
        else:
            raise IntentBuildError(
                f"intents[{index}]: expected LimitIntent or CancelIntent, got {type(intent).__name__}"
            )
        if command.command_id in seen_command_ids:
            raise IntentBuildError(f"duplicate command_id in frozen batch: {command.command_id}")
        seen_command_ids.add(command.command_id)
        commands.append(command)
    return tuple(commands)
