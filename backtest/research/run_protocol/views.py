"""Opt-in, in-memory projections of already obtained native evidence.

No execution, file reads/writes, account arithmetic or lifecycle reconstruction.
Pass a native result or preloaded records, not an ApiResult/Path. Field names,
numeric representations and record order remain native. See the L1 views note.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, fields, is_dataclass, replace
from datetime import date, datetime, time
from decimal import Decimal
from types import MappingProxyType
from typing import Generic, TypeVar

from .types import Family


__all__ = [
    "Provenance", "Evidence", "Projection", "OrderView", "FillView",
    "PortfolioView", "AccountPortfolioView", "GridInstancePortfolioView",
    "GridSpecPortfolioView", "TimeEvidence", "project_orders", "project_fills",
    "project_portfolio", "project_time_evidence",
]

_MISSING = object()
_FAMILIES = ("csv_minute", "v7", "joint_return", "grid_modeb")


@dataclass(frozen=True)
class Provenance:
    """Path uses native keys / zero-based record indices, not CSV line numbers.

    source_file is caller supplied, never discovered. None denotes unknown;
    unknown_reasons explains missing run/file metadata. A field's path includes
    its row and field, including nested positions, lots and transition records.
    """

    family: Family
    run_id: str | None
    source_file: str | None
    path: tuple[str | int, ...] = ()
    unknown_reasons: tuple[str, ...] = ()

    def at(self, *parts: str | int) -> Provenance:
        return replace(self, path=self.path + parts)


@dataclass(frozen=True)
class Evidence:
    value: object
    provenance: Provenance
    unknown_reason: str | None = None
    derived: bool = False


def _members(value):
    if isinstance(value, Mapping):
        return value
    if is_dataclass(value) and not isinstance(value, type):
        return {f.name: getattr(value, f.name) for f in fields(value)}
    raise TypeError("expected native mapping/dataclass or preloaded list/tuple records")


def _freeze(value):
    # Snapshot containers recursively; never retain writable native objects or
    # invoke native properties (e.g. v7 shares/sellable calculations).
    if isinstance(value, Mapping) or (is_dataclass(value) and not isinstance(value, type)):
        return MappingProxyType({k: _freeze(v) for k, v in _members(value).items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(v) for v in value)
    if value is None or isinstance(value, (str, bytes, bool, int, float, Decimal, date, datetime, time)):
        return value
    raise TypeError(f"unsupported native evidence value: {type(value).__name__}")


def _evidence(value, provenance):
    if value is _MISSING:
        return Evidence(None, provenance, "field_missing")
    return Evidence(value, provenance, "native_null" if value is None else None)


@dataclass(frozen=True)
class _RecordView:
    provenance: Provenance
    native_fields: Mapping[str, object]

    def field(self, *path: str | int) -> Evidence:
        """Read a native field, with reverse lookup even when it is absent."""
        value = self.native_fields
        for part in path:
            if isinstance(value, Mapping):
                value = value.get(part, _MISSING)
            elif isinstance(value, tuple) and isinstance(part, int) and 0 <= part < len(value):
                value = value[part]
            else:
                value = _MISSING
            if value is _MISSING:
                break
        return _evidence(value, self.provenance.at(*path))


@dataclass(frozen=True)
class OrderView(_RecordView):
    """Native order snapshot only; no synthesized events or observation ID."""

    @property
    def order_id(self) -> Evidence:
        return self.field("order_id")

    @property
    def status(self) -> Evidence:
        return self.field("status")


@dataclass(frozen=True)
class FillView(_RecordView):
    """One native incremental fill/trade row, retaining its original granularity."""

    @property
    def quantity(self) -> Evidence:
        return self.field("executed_quantity" if self.provenance.family == "joint_return" else "shares")

    @property
    def price(self) -> Evidence:
        return self.field("price")

    @property
    def fee(self) -> Evidence:
        # CSV records commission, not an assertion of complete taxes/fees.
        return self.field("commission" if self.provenance.family == "csv_minute" else "fee")


@dataclass(frozen=True)
class PortfolioView(_RecordView):
    """Base for disjoint native account / grid experiment evidence shapes."""


@dataclass(frozen=True)
class AccountPortfolioView(PortfolioView):
    """JR: one daily row with arm_id/fill_id; CSV/v7: current native state.

    Missing arm/fill identity remains missing, never a combined JR account.
    Positions/lots are copied structurally, never regrouped by symbol.
    """


@dataclass(frozen=True)
class GridInstancePortfolioView(PortfolioView):
    spec_id: Evidence
    instance_id: Evidence


@dataclass(frozen=True)
class GridSpecPortfolioView(PortfolioView):
    spec_id: Evidence


T = TypeVar("T")


@dataclass(frozen=True)
class Projection(Generic[T]):
    rows: tuple[T, ...]
    provenance: Provenance
    unknown_reason: str | None = None
    excluded: tuple[Evidence, ...] = ()


def _origin(family, run_id, source):
    if family not in _FAMILIES:
        raise ValueError(f"unknown projection family: {family!r}")
    if run_id is not None and (not isinstance(run_id, str) or not run_id):
        raise ValueError("run_id must be a nonempty string or None")
    if source is not None and (not isinstance(source, str) or not source):
        raise ValueError("source must be a nonempty file label or None")
    reasons = tuple(reason for missing, reason in (
        (run_id is None, "run_id_not_supplied"),
        (source is None, "source_file_not_supplied"),
    ) if missing)
    return Provenance(family, run_id, source, unknown_reasons=reasons)


def _record(cls, row, origin, **kwargs):
    row = _members(row)
    native_run = row.get("run_id")
    if native_run is not None:
        if not isinstance(native_run, str) or not native_run:
            raise ValueError("native run_id must be a nonempty string")
        if origin.run_id is not None and origin.run_id != native_run:
            raise ValueError("native run_id conflicts with projection run_id")
        origin = replace(origin, run_id=native_run, unknown_reasons=tuple(
            reason for reason in origin.unknown_reasons if reason != "run_id_not_supplied"))
    return cls(origin, _freeze(row), **kwargs)


def _rows(native, key, origin):
    if isinstance(native, (list, tuple)):
        rows, location = native, origin
    else:
        rows, location = _members(native).get(key, _MISSING), origin.at(key)
    if rows is _MISSING or rows is None:
        return None, location
    if not isinstance(rows, (list, tuple)):
        raise TypeError(f"{key} must be preloaded list/tuple records")
    return rows, location


def project_orders(family: Family, native_result, *, run_id=None, source=None) -> Projection[OrderView]:
    """Project only explicit orders records; never derive orders from trades."""
    origin = _origin(family, run_id, source)
    rows, location = _rows(native_result, "orders", origin)
    if rows is None:
        reason = "native_orders_missing" if family == "joint_return" else "family_has_no_order_lifecycle"
        return Projection((), location, reason)
    return Projection(tuple(_record(OrderView, row, location.at(i)) for i, row in enumerate(rows)), location)


def _fill_rejection(row, family):
    # Positive classification of the native collection plus exclusion of
    # marker rows. Never use cumulative quantities, order price, or a fee total.
    for key in ("side", "status", "event", "reason", "status_reason"):
        marker = row.get(key)
        if isinstance(marker, str):
            marker = marker.upper()
            if marker.startswith(("SKIP", "REJECT", "EOD_MARK")) or marker in ("MARK", "MARK_END"):
                return "non_fill_marker"
    side = row.get("side")
    if family == "v7" and isinstance(side, str):
        # Native v7 uses lowercase sides; classify without rewriting evidence.
        side = side.upper()
    if side not in ("BUY", "SELL"):
        return "no_native_fill_side"
    if family == "joint_return" and row.get("status") not in ("FILLED", "PARTIAL"):
        return "no_native_fill_status"
    key = "executed_quantity" if family == "joint_return" else "shares"
    quantity = row.get(key)
    if isinstance(quantity, bool) or not isinstance(quantity, (int, float, Decimal)):
        return "incremental_quantity_missing_or_invalid"
    if not (quantity.is_finite() if isinstance(quantity, Decimal) else float("-inf") < quantity < float("inf")):
        return "incremental_quantity_missing_or_invalid"
    if quantity <= 0:
        return "nonpositive_incremental_quantity"
    return None


def project_fills(family: Family, native_result, *, run_id=None, source=None) -> Projection[FillView]:
    """JR fills / CSV-v7 trades only. Grid exits are experiment evidence."""
    origin = _origin(family, run_id, source)
    if family == "grid_modeb":
        return Projection((), origin, "family_has_no_incremental_fill_records")
    key = "fills" if family == "joint_return" else "trades"
    rows, location = _rows(native_result, key, origin)
    if rows is None:
        return Projection((), location, "native_fill_records_missing")
    accepted, excluded = [], []
    for i, row in enumerate(rows):
        view = _record(FillView, row, location.at(i))
        reason = _fill_rejection(view.native_fields, family)
        if reason is None:
            accepted.append(view)
        else:
            excluded.append(Evidence(None, view.provenance, reason))
    return Projection(tuple(accepted), location, excluded=tuple(excluded))


def _grid_portfolio(native, origin):
    native = _members(native)
    projected = []
    # Keep the matrix keys themselves as identity evidence, not generated IDs.
    for spec, instances in _members(native.get("matrix", {})).items():
        for instance, row in _members(instances).items():
            location = origin.at("matrix", spec, instance)
            projected.append(_record(GridInstancePortfolioView, row, location,
                spec_id=Evidence(spec, origin.at("matrix", spec)),
                instance_id=Evidence(instance, location)))
    for i, row in enumerate(native.get("instances", ())):
        location = origin.at("instances", i)
        projected.append(_record(GridInstancePortfolioView, row, location,
            spec_id=Evidence(None, location, "instance_is_not_spec_scoped"),
            instance_id=Evidence(None, location, "native_instance_id_not_reported")))
    for i, row in enumerate(native.get("ranked", ())):
        location = origin.at("ranked", i)
        row = _members(row)
        projected.append(_record(GridSpecPortfolioView, row, location,
            spec_id=_evidence(row.get("label", _MISSING), location.at("label"))))
    present = any(key in native for key in ("matrix", "instances", "ranked"))
    return Projection(tuple(projected), origin, None if present else "native_portfolio_records_missing")


def project_portfolio(family: Family, native_result, *, run_id=None, source=None) -> Projection[PortfolioView]:
    """Copy native units; no NAV normalization, ranking, mark or sellable math."""
    origin = _origin(family, run_id, source)
    if family == "grid_modeb":
        return _grid_portfolio(native_result, origin)
    if family == "joint_return":
        rows, location = _rows(native_result, "daily_nav", origin)
        if rows is None:
            return Projection((), location, "native_portfolio_records_missing")
        return Projection(tuple(_record(AccountPortfolioView, row, location.at(i))
                                for i, row in enumerate(rows)), location)
    native = _members(native_result)
    # Avoid unrelated live objects/callbacks on SimState / SimResult.
    selected = {key: native[key] for key in ("cash", "positions", "equity_curve", "run_id") if key in native}
    if not any(key in selected for key in ("cash", "positions", "equity_curve")):
        return Projection((), origin, "native_portfolio_records_missing")
    return Projection((_record(AccountPortfolioView, selected, origin),), origin)


@dataclass(frozen=True)
class TimeEvidence:
    schedule_parameters: Mapping[str, Evidence]
    effective_clocks: Mapping[str, Evidence]


def project_time_evidence(family: Family, native_record, *, run_id=None, source=None) -> TimeEvidence:
    """Separate reported parameters from clocks; missing clocks stay unknown.

    Accept an existing projected row (retaining its provenance) or a preloaded
    flat parameter/clock mapping. X-02=False never implies legacy scheduling;
    reference_price_at/actual_fill_at never supply submit/match/booked clocks.
    """
    if isinstance(native_record, _RecordView):
        row = native_record
        if family != row.provenance.family or run_id is not None or source is not None:
            raise ValueError("a projected row already owns its provenance")
    else:
        row = _record(_RecordView, native_record, _origin(family, run_id, source))
    parameters = ("fix_minute_cash_order", "minute_stop_trigger", "topk_exec", "tail_window_buy", "limit_walkdown")
    clocks = ("quote_at", "reference_price_at", "available_at", "decision_at", "submit_at",
              "effective_at", "expires_at", "legal_execution_at", "actual_fill_at",
              "match_at", "booked_at", "last_attempt_at", "mark_at", "last_valuation_at")
    return TimeEvidence(MappingProxyType({key: row.field(key) for key in parameters}),
                        MappingProxyType({key: row.field(key) for key in clocks}))
