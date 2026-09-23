"""Opt-in K1 research validation; never called by the production replay path.

Axes are prebuilt from sessions, with sorted intent/initial-universe instruments.
When converting bar labels to minute indices, CLOSE_TIME shifts by -60 seconds,
exactly as v1 does. No session expansion or fill/fee/clock kernel lives here.
Float64 comparisons are inclusive, without epsilon: equal represented values
pass, including limit ties; distinct decimal literals may round to the same float.
High/low are optional passthrough evidence, never synthesized.
"""
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
import hashlib
from pathlib import Path
from typing import Mapping

import numpy as np

from backtest.research.joint_return_replay import ReplayError, content_hash, require, stamp

COLUMNS = ("open", "close", "limit_up", "limit_down", "capacity", "suspended")
OPTIONAL = ("high", "low")


@dataclass(frozen=True)
class DensePanel:
    """Borrowed arrays; callers must not mutate during validation or view usage.

    Columns must be 2-D row-major logical grids (contiguous storage not required).
    Missing observations require a false validity cell, never a fabricated bar.
    """

    columns: Mapping[str, np.ndarray]
    n_minutes: int
    instruments: tuple[str, ...]
    execution_symbols: tuple[str, ...]
    minute_iso: tuple[str, ...]  # session-derived OPEN_TIME axis
    validity: np.ndarray | None = None

    @property
    def shape(self):
        return self.n_minutes, len(self.instruments)

    @property
    def size(self):
        return self.columns["open"].size


@dataclass(frozen=True)
class ValidatedPanel:
    """K1 borrowed view, not certification of full v1 metadata/event parity."""

    panel: DensePanel

    def bar_decimal(self, column, minute_i, inst_i):
        require(column in COLUMNS + OPTIONAL and column != "suspended",
                "not a Decimal bar column")
        require(column in self.panel.columns, f"absent bar column: {column}")
        require(0 <= minute_i < self.panel.n_minutes
                and 0 <= inst_i < len(self.panel.instruments), "bar index outside panel")
        return Decimal(str(float(self.panel.columns[column][minute_i, inst_i])))

    def bar_open(self, minute_i, inst_i):
        return self.bar_decimal("open", minute_i, inst_i)

    def bar_capacity(self, minute_i, inst_i):
        return self.bar_decimal("capacity", minute_i, inst_i)


def minute_axis_from_labels(labels, *, bar_label):
    """Normalize labels only; caller supplies/proves the session-derived axis."""
    require(bar_label in ("OPEN_TIME", "CLOSE_TIME"), "minute label unproven")
    shift = timedelta(seconds=60 if bar_label == "CLOSE_TIME" else 0)
    return tuple((stamp(label) - shift).isoformat(timespec="seconds") for label in labels)


def _verify_seal(root, manifest, metadata, corporate_actions):
    require(isinstance(manifest, dict), "MANIFEST required", "CONTRACT_MISMATCH")
    files = manifest.get("payload_files")
    require(isinstance(files, list) and bool(files)
            and all(isinstance(p, str) and p for p in files),
            "MANIFEST payload_files pinned order required", "CONTRACT_MISMATCH")
    require(len(set(files)) == len(files), "duplicate payload files", "CONTRACT_MISMATCH")
    root = Path(root).resolve()
    digest = hashlib.sha256()
    for name in files:  # Deliberately never sort this list.
        path = (root / name).resolve()
        require(not Path(name).is_absolute() and path.is_relative_to(root),
                "payload outside pack root", "CONTRACT_MISMATCH")
        try:
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
        except OSError as exc:
            raise ReplayError("INPUT_BLOCKED", f"payload unavailable: {name}") from exc
    require(digest.hexdigest() == manifest.get("bars_payload_raw_sha256"),
            "bars payload byte hash drift", "CONTRACT_MISMATCH")
    for name, value in (("metadata", metadata), ("corporate_actions", corporate_actions)):
        require(content_hash(value) == manifest.get(f"{name}_content_sha256"),
                f"{name} hash drift", "CONTRACT_MISMATCH")


def panel_table_sha256(panel):
    """LE typed column concat, each flattened in (minute_i, inst_i) order.

    Caller must first check shapes/dtypes. Hash one column at a time, without
    constructing Python bar records or a concatenated full-table buffer.
    """
    digest = hashlib.sha256()
    for name in COLUMNS + OPTIONAL:
        if name in panel.columns:
            dtype = "u1" if name == "suspended" else "<f8"
            column = np.ascontiguousarray(panel.columns[name], dtype=dtype)
            digest.update(memoryview(column).cast("B"))
    return digest.hexdigest()


def validate_bars_v2(panel, manifest, *, payload_root, metadata,
                     corporate_actions, enabled=False):
    """V0 seals, minimal V1 axes, V2 NumPy gates and V3 dense coverage.

    Explicit opt-in only. V4 semantics are deferred: nonempty events fail closed.
    Payload decoding and its association with this prebuilt panel belong to the
    caller; table hash, when supplied, additionally binds the loaded projection.
    """
    require(enabled is True, "validate-v2 research default off", "SEMANTICS_BLOCKED")
    _verify_seal(payload_root, manifest, metadata, corporate_actions)
    require(isinstance(metadata, dict), "metadata must be an object")
    require(isinstance(corporate_actions, list), "corporate_actions must be a list")
    require(not corporate_actions, "K1 corporate-action semantics deferred", "SEMANTICS_BLOCKED")
    require(type(panel.n_minutes) is int and panel.n_minutes > 0, "invalid n_minutes")
    inst = panel.instruments
    symbols = panel.execution_symbols
    require(bool(inst) and all(isinstance(x, str) and x for x in inst), "invalid instruments")
    require(tuple(sorted(set(inst))) == tuple(inst), "instruments must be sorted and unique")
    require(len(symbols) == len(inst) and all(isinstance(x, str) and x for x in symbols)
            and len(set(symbols)) == len(symbols), "execution mapping drift/collision", "SEMANTICS_BLOCKED")
    require(len(panel.minute_iso) == panel.n_minutes, "minute axis coverage incomplete")
    minutes = tuple(stamp(t) for t in panel.minute_iso)
    require(all(t.second == 0 for t in minutes)
            and all(a < b for a, b in zip(minutes, minutes[1:])), "minute axis order/alignment invalid")
    require(set(COLUMNS) <= set(panel.columns) <= set(COLUMNS + OPTIONAL), "panel columns missing/extra")
    for name, column in panel.columns.items():
        require(isinstance(column, np.ndarray) and column.shape == panel.shape,
                f"{name}: dense coverage shape mismatch")
        expected = np.dtype("uint8" if name == "suspended" else "float64")
        require(column.dtype == expected, f"{name}: expected {expected}")
    require(panel.size == panel.n_minutes * len(inst), "dense coverage incomplete")

    def check_cells(ok, detail):
        if not np.all(ok):
            flat = int(np.argmin(ok))
            minute_i, inst_i = divmod(flat, len(inst))
            raise ReplayError("INPUT_BLOCKED",
                              f"{detail}: {inst[inst_i]} at {panel.minute_iso[minute_i]}")

    if panel.validity is not None:
        require(isinstance(panel.validity, np.ndarray) and panel.validity.shape == panel.shape
                and panel.validity.dtype == np.dtype("bool"), "invalid coverage bitmap")
        check_cells(panel.validity, "dense coverage hole")
    if "bars_table_sha256" in manifest:
        require(panel_table_sha256(panel) == manifest["bars_table_sha256"],
                "bars table hash drift", "CONTRACT_MISMATCH")
    cols = panel.columns
    for name in ("open", "close", "limit_up", "limit_down") + OPTIONAL:
        if name in cols:
            check_cells(np.isfinite(cols[name]) & (cols[name] > 0), f"{name} nonfinite/nonpositive")
    check_cells(np.isfinite(cols["capacity"]) & (cols["capacity"] >= 0), "invalid capacity")
    check_cells((cols["suspended"] == 0) | (cols["suspended"] == 1), "invalid suspended")
    for name in ("open", "close"):
        check_cells((cols["limit_down"] <= cols[name]) & (cols[name] <= cols["limit_up"]),
                    f"{name} outside explicit price limits")
    return ValidatedPanel(panel)
