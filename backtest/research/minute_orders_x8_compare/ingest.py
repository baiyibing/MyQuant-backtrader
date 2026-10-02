"""Ingest pre-match intent snapshots only. Refuse fills→intent reconstruction.

TC1 §5 X8 / PLAN TC4: only 撮合前 intent snapshots (commands / LimitIntent
freeze). Reconstructing intents from fills/trades is a hard ban.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping
from zoneinfo import ZoneInfo

from backtest.research.minute_orders_backend.types import Side
from backtest.research.minute_orders_intent_x1 import CancelIntent, LimitIntent

PREMATCH_SNAPSHOT_SCHEMA = "minute_orders_x8_prematch_intent_snapshot_v0"
SNAPSHOT_KIND = "pre_match_intent"

# Keys that signal post-match / fills-derived material — refuse the whole payload.
_BANNED_PAYLOAD_KEYS = frozenset(
    {
        "fills",
        "fill",
        "trades",
        "trade",
        "fill_events",
        "fill_proposals",
        "ledger",
        "nav",
        "pnl",
        "reconstructed_from_fills",
        "derived_from_fills",
        "from_fills",
        "from_trades",
    }
)

_BANNED_KIND_TOKENS = frozenset(
    {
        "fills",
        "fill",
        "trades",
        "trade",
        "post_match",
        "post-match",
        "reconstructed",
        "fills_to_intent",
        "fills→intent",
    }
)


class CompareIngestError(ValueError):
    """Snapshot rejected before any X1 run (malformed or fills→intent ban)."""


@dataclass(frozen=True)
class PrematchSnapshot:
    """Validated a-priori intent snapshot (no market / fill material)."""

    schema: str
    snapshot_kind: str
    intents: tuple[LimitIntent | CancelIntent, ...]
    adapter_id: str | None
    contract: str | None
    backend_id: str | None
    facts_preset: str | None
    raw_meta: Mapping[str, Any]


def _reject_banned_keys(payload: Mapping[str, Any], *, where: str) -> None:
    banned = sorted(k for k in payload if k in _BANNED_PAYLOAD_KEYS)
    if banned:
        raise CompareIngestError(
            f"{where}: fills→intent / post-match keys banned by X8: {banned}; "
            "only pre-match intent snapshots are accepted"
        )


def _reject_banned_kind(kind: str, *, where: str) -> None:
    lowered = kind.strip().lower().replace(" ", "_")
    if lowered != SNAPSHOT_KIND:
        # Explicit fills/trades kinds get a sharper message.
        tokens = set(lowered.replace("-", "_").split("_"))
        if tokens & _BANNED_KIND_TOKENS or "fill" in lowered or "trade" in lowered:
            raise CompareIngestError(
                f"{where}: snapshot_kind={kind!r} looks like fills/trades path; "
                f"X8 bans fills→intent; require snapshot_kind={SNAPSHOT_KIND!r}"
            )
        raise CompareIngestError(
            f"{where}: snapshot_kind must be {SNAPSHOT_KIND!r}, got {kind!r}"
        )


def _parse_aware(value: Any, name: str) -> datetime:
    """Parse ISO datetime and normalize to named Asia/Shanghai (Clock contract)."""
    shanghai = ZoneInfo("Asia/Shanghai")

    def _to_shanghai(dt: datetime) -> datetime:
        if dt.utcoffset() is None:
            raise CompareIngestError(f"{name} must be timezone-aware")
        # Clock.require_shanghai demands tzinfo.key == Asia/Shanghai.
        converted = dt.astimezone(shanghai)
        return converted.replace(tzinfo=shanghai)

    if isinstance(value, datetime):
        return _to_shanghai(value)
    if type(value) is not str or not value.strip():
        raise CompareIngestError(f"{name} must be an ISO-8601 timezone-aware string")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise CompareIngestError(f"{name}: invalid datetime {value!r}") from error
    return _to_shanghai(parsed)


def _parse_side(value: Any) -> Side:
    if isinstance(value, Side):
        return value
    if type(value) is not str:
        raise CompareIngestError("side must be BUY or SELL")
    try:
        return Side(value)
    except ValueError as error:
        raise CompareIngestError(f"side must be BUY or SELL, got {value!r}") from error


def _parse_limit_intent(row: Mapping[str, Any], index: int) -> LimitIntent:
    _reject_banned_keys(row, where=f"intents[{index}]")
    kind = row.get("kind", "limit")
    if kind not in ("limit", "LIMIT", "LimitIntent"):
        raise CompareIngestError(
            f"intents[{index}]: kind must be limit/LimitIntent, got {kind!r}"
        )
    try:
        qty = row["qty"]
        sequence = row["sequence"]
        limit_raw = row["limit"]
    except KeyError as error:
        raise CompareIngestError(f"intents[{index}]: missing field {error.args[0]}") from error
    if type(qty) is not int:
        raise CompareIngestError(f"intents[{index}]: qty must be int")
    if type(sequence) is not int:
        raise CompareIngestError(f"intents[{index}]: sequence must be int")
    return LimitIntent(
        order_id=str(row["order_id"]),
        symbol=str(row["symbol"]),
        side=_parse_side(row["side"]),
        qty=qty,
        limit=Decimal(str(limit_raw)),
        available_at=_parse_aware(row["available_at"], f"intents[{index}].available_at"),
        submitted_at=_parse_aware(row["submitted_at"], f"intents[{index}].submitted_at"),
        effective_at=_parse_aware(row["effective_at"], f"intents[{index}].effective_at"),
        expires_at=_parse_aware(row["expires_at"], f"intents[{index}].expires_at"),
        sequence=sequence,
        command_id=None if row.get("command_id") is None else str(row["command_id"]),
        order_type="LIMIT",
    )


def _parse_cancel_intent(row: Mapping[str, Any], index: int) -> CancelIntent:
    _reject_banned_keys(row, where=f"intents[{index}]")
    kind = row.get("kind", "cancel")
    if kind not in ("cancel", "CANCEL", "CancelIntent"):
        raise CompareIngestError(
            f"intents[{index}]: kind must be cancel/CancelIntent, got {kind!r}"
        )
    try:
        sequence = row["sequence"]
    except KeyError as error:
        raise CompareIngestError(f"intents[{index}]: missing field {error.args[0]}") from error
    if type(sequence) is not int:
        raise CompareIngestError(f"intents[{index}]: sequence must be int")
    return CancelIntent(
        order_id=str(row["order_id"]),
        available_at=_parse_aware(row["available_at"], f"intents[{index}].available_at"),
        submitted_at=_parse_aware(row["submitted_at"], f"intents[{index}].submitted_at"),
        effective_at=_parse_aware(row["effective_at"], f"intents[{index}].effective_at"),
        sequence=sequence,
        command_id=None if row.get("command_id") is None else str(row["command_id"]),
    )


def _parse_intent_row(row: Any, index: int) -> LimitIntent | CancelIntent:
    if not isinstance(row, Mapping):
        raise CompareIngestError(f"intents[{index}] must be an object")
    kind = str(row.get("kind", "limit")).lower()
    if kind in ("cancel", "cancelintent"):
        return _parse_cancel_intent(row, index)
    if kind in ("limit", "limitintent"):
        return _parse_limit_intent(row, index)
    # Unknown kind — if it smells like fills, ban; else reject.
    if "fill" in kind or "trade" in kind:
        raise CompareIngestError(
            f"intents[{index}]: kind={kind!r} banned (fills→intent); "
            "only limit/cancel pre-match intents accepted"
        )
    raise CompareIngestError(
        f"intents[{index}]: unsupported kind {kind!r}; use limit or cancel"
    )


def snapshot_from_mapping(payload: Mapping[str, Any]) -> PrematchSnapshot:
    """Validate a pre-match intent snapshot mapping. No runner side effects."""
    if not isinstance(payload, Mapping):
        raise CompareIngestError("snapshot must be a JSON object")
    _reject_banned_keys(payload, where="snapshot")

    schema = payload.get("schema")
    if schema != PREMATCH_SNAPSHOT_SCHEMA:
        raise CompareIngestError(
            f"snapshot.schema must be {PREMATCH_SNAPSHOT_SCHEMA!r}, got {schema!r}"
        )

    kind = payload.get("snapshot_kind")
    if type(kind) is not str:
        raise CompareIngestError("snapshot_kind must be a string")
    _reject_banned_kind(kind, where="snapshot")

    intents_raw = payload.get("intents")
    if not isinstance(intents_raw, list) or not intents_raw:
        raise CompareIngestError("snapshot.intents must be a nonempty list")

    # Nested ban: refuse a sibling "commands_from_fills" style bag even if top-level clean.
    for nested_key in ("source", "origin", "provenance", "meta"):
        nested = payload.get(nested_key)
        if isinstance(nested, Mapping):
            _reject_banned_keys(nested, where=f"snapshot.{nested_key}")

    intents = tuple(_parse_intent_row(row, i) for i, row in enumerate(intents_raw))

    facts_preset = payload.get("facts_preset")
    if facts_preset is not None and type(facts_preset) is not str:
        raise CompareIngestError("facts_preset must be a string when present")

    return PrematchSnapshot(
        schema=PREMATCH_SNAPSHOT_SCHEMA,
        snapshot_kind=SNAPSHOT_KIND,
        intents=intents,
        adapter_id=None if payload.get("adapter_id") is None else str(payload["adapter_id"]),
        contract=None if payload.get("contract") is None else str(payload["contract"]),
        backend_id=None if payload.get("backend_id") is None else str(payload["backend_id"]),
        facts_preset=facts_preset,
        raw_meta={
            k: payload[k]
            for k in ("note", "bans", "label")
            if k in payload
        },
    )


def load_prematch_intent_snapshot(path: str | Path) -> PrematchSnapshot:
    """Load + validate a pre-match intent snapshot JSON file."""
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise CompareIngestError(f"cannot read snapshot {path}: {error}") from error
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as error:
        raise CompareIngestError(f"snapshot JSON decode failed: {error}") from error
    if type(payload) is not dict:
        raise CompareIngestError("snapshot root must be a JSON object")
    return snapshot_from_mapping(payload)
