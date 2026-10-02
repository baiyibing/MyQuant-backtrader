"""Opt-in research validation and JSON/pack replay adapters; default remains v1.

Axes are prebuilt from sessions, with sorted intent/initial-universe instruments.
When converting bar labels to minute indices, CLOSE_TIME shifts by -60 seconds,
exactly as v1 does. No session expansion or fill/fee/clock kernel lives here.
Float64 comparisons are inclusive, without epsilon: equal represented values
pass, including limit ties; distinct decimal literals may round to the same float.
High/low are optional passthrough evidence, never synthesized.
"""
from collections.abc import Mapping as MappingABC
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
import hashlib
from pathlib import Path
from typing import Mapping

import numpy as np

from backtest.research.joint_return_replay import (
    ReplayError, _PhaseTimings, content_hash, require, stamp,
)

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

    def _bar_decimal_unchecked(self, column, minute_i, inst_i):
        """Internal replay only: scanned columns and adapter-proven indices.

        Public accessors retain their guards. Replay uses fixed numeric column
        names on cells from _PanelBars after validation; borrowed arrays must
        remain immutable for the lifetime of the view (DensePanel contract).
        """
        return Decimal(str(float(self.panel.columns[column][minute_i, inst_i])))


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
                     corporate_actions, enabled=False, seal_mode="byte", bundle=None,
                     _timings=None):
    """V0 seals, minimal V1 axes, V2 NumPy gates and V3 dense coverage.

    Explicit opt-in only. Byte-mode V4 semantics remain deferred: events fail
    closed. The canonical JSON replay adapter validates metadata/events using
    shared v1 predicates before calling this panel validator.
    Payload decoding and its association with this prebuilt panel belong to the
    caller; table hash, when supplied, additionally binds the loaded projection.
    """
    require(enabled is True, "validate-v2 research default off", "SEMANTICS_BLOCKED")
    timings = _timings if _timings is not None else _PhaseTimings()
    with timings.phase("validate_seal"):
        if seal_mode == "byte":
            _verify_seal(payload_root, manifest, metadata, corporate_actions)
        else:
            require(seal_mode == "canonical_json" and isinstance(bundle, dict),
                    "canonical JSON bundle required", "CONTRACT_MISMATCH")
            require(bundle["content_sha256"] == content_hash(
                {k: v for k, v in bundle.items() if k != "content_sha256"}),
                "bars content hash drift", "CONTRACT_MISMATCH")
    require(isinstance(metadata, dict), "metadata must be an object")
    require(isinstance(corporate_actions, list), "corporate_actions must be a list")
    require(seal_mode == "canonical_json" or not corporate_actions,
            "K1 corporate-action semantics deferred", "SEMANTICS_BLOCKED")
    with timings.phase("validate_panel_scan"):
        return _scan_panel(panel, manifest or {}, timings)


def _scan_panel(panel, manifest, _timings=None):
    timings = _timings if _timings is not None else _PhaseTimings()
    with timings.phase("axes"):
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
    timings.count("panel_cells", panel.size)

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
        with timings.phase("table_sha256"):
            require(panel_table_sha256(panel) == manifest["bars_table_sha256"],
                    "bars table hash drift", "CONTRACT_MISMATCH")
    with timings.phase("cells"):
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


class _Cell:
    """Ephemeral fill view: no cached per-cell records or eager Decimals."""

    def __init__(self, validated, minute_i, inst_i):
        self.validated, self.minute_i, self.inst_i = validated, minute_i, inst_i

    def __getitem__(self, key):
        panel = self.validated.panel
        if key == "instrument":
            return panel.instruments[self.inst_i]
        if key == "suspended":
            return bool(panel.columns[key][self.minute_i, self.inst_i])
        raise KeyError(key)

    def decimal(self, key):
        return self.validated._bar_decimal_unchecked(key, self.minute_i, self.inst_i)


class _LazyMapping(MappingABC):
    def __init__(self, keys, getter):
        self.keys_index, self.getter = keys, getter

    def __iter__(self):
        return iter(self.keys_index)

    def __len__(self):
        return len(self.keys_index)

    def __getitem__(self, key):
        if key not in self.keys_index:
            raise KeyError(key)
        return self.getter(key)


class _PanelBars:
    def __init__(self, validated, opportunities):
        self.validated = validated
        self.minutes = {t: i for i, t in enumerate(sorted(opportunities))}
        self.instruments = {inst: i for i, inst in enumerate(validated.panel.instruments)}
        self.bars_at = _LazyMapping(self.minutes, lambda t: _LazyMapping(
            self.instruments, lambda inst: self.get((t, inst))))
        self.closes = _LazyMapping(
            {t + timedelta(seconds=60): i for t, i in self.minutes.items()},
            lambda t: self.bars_at[t - timedelta(seconds=60)].values())
        self.bar_days = {(day, inst) for day in set(opportunities.values())
                         for inst in self.instruments}

    def get(self, key, default=None):
        t, inst = key
        if t not in self.minutes or inst not in self.instruments:
            return default
        return _Cell(self.validated, self.minutes[t], self.instruments[inst])


def validate_json_replay(bundle, m, intents, timings):
    """One JSON-to-panel conversion, then vectorized validation and lazy access.

    Caller-owned JSON is immutable and may remain alive; neither scan nor replay
    references its bar records. Canonical seal still pays the JSON traversal.
    Metadata/events share v1 predicates. Dense coverage is required even for
    synthetic v2 inputs (sparse synthetic inputs remain supported only in v1).
    """
    from backtest.research.joint_return_replay import (
        fields, _validate_bar_metadata, _validate_bar_events,
    )
    fields(bundle, ("schema_version", "kind", "metadata", "bars",
                    "corporate_actions", "content_sha256"), "bars snapshot")
    with timings.phase("validate_metadata"):
        with timings.phase("bar_metadata"):
            opportunities, ends, mapping = _validate_bar_metadata(bundle, m, intents, timings)
        with timings.phase("bar_events"):
            _validate_bar_events(bundle, intents, opportunities, ends, mapping)
    with timings.phase("validate_panel_load"):
        require(isinstance(bundle["bars"], list), "bars must be explicit list")
        instruments = tuple(sorted(mapping))
        minutes = tuple(sorted(opportunities))
        mi = {t: i for i, t in enumerate(minutes)}
        ii = {inst: i for i, inst in enumerate(instruments)}
        shape = (len(minutes), len(instruments))
        names = COLUMNS + tuple(k for k in OPTIONAL if any(k in r for r in bundle["bars"]))
        columns = {k: np.empty(shape, dtype="uint8" if k == "suspended" else "float64")
                   for k in names}
        valid = np.zeros(shape, dtype=bool)
        shift = timedelta(seconds=60 if bundle["metadata"]["bar_label"] == "CLOSE_TIME" else 0)
        with timings.phase("json_rows"):
            for raw in bundle["bars"]:
                fields(raw, ("instrument", "execution_symbol", "timestamp", *names), "minute bar")
                inst = raw["instrument"]
                require(inst in ii, "bar instrument not in input intent/initial universe")
                require(raw["execution_symbol"] == mapping[inst],
                        "minute execution mapping drift/collision", "SEMANTICS_BLOCKED")
                t = stamp(raw["timestamp"]) - shift
                require(t in mi, "bar outside frozen session endpoints")
                cell = mi[t], ii[inst]
                require(not valid[cell], "duplicate minute bar")
                require(type(raw["suspended"]) is bool, "suspension evidence missing")
                for k in names:
                    if k != "suspended":
                        require(type(raw[k]) in (int, float), f"{k}: finite number required")
                    try:
                        columns[k][cell] = raw[k]
                    except (OverflowError, ValueError) as exc:
                        raise ReplayError("INPUT_BLOCKED", f"{k}: invalid number") from exc
                valid[cell] = True
        timings.count("bar_rows", len(bundle["bars"]))
        panel = DensePanel(columns, len(minutes), instruments,
                           tuple(mapping[i] for i in instruments),
                           tuple(t.isoformat(timespec="seconds") for t in minutes), valid)
    validated = validate_bars_v2(
        panel, None, payload_root=None, metadata=bundle["metadata"],
        corporate_actions=bundle["corporate_actions"], enabled=True,
        seal_mode="canonical_json", bundle=bundle, _timings=timings)
    bars = _PanelBars(validated, opportunities)
    return opportunities, ends, bars, bars.closes


def validate_pack_replay(pack_root, m, intents, timings):
    """Byte-sealed bin/columnar pack -> panel -> lazy replay; no row materialization.

    Timing-only packs without pinned payload hashes fail closed. Byte-mode
    corporate actions remain deferred, as in validate_bars_v2.
    """
    from backtest.research.joint_return_qlib_bin_pack import (
        _read_json, qlib_inst_dir, read_pack_panel,
    )
    from backtest.research.joint_return_replay import _validate_bar_metadata

    root = Path(pack_root)
    manifest = _read_json(root / "MANIFEST.json")
    fmt = manifest.get("format")
    require(isinstance(fmt, str) and fmt, "MANIFEST format must be a nonempty string")
    bundle = dict(schema_version=manifest["schema_version"], kind=manifest["kind"],
                  metadata=_read_json(root / "metadata.json"),
                  corporate_actions=_read_json(root / "corporate_actions.json"),
                  content_sha256=content_hash(manifest))
    # Pin every decoded payload, including the calendar and instrument mapping.
    # The manifest supplies hash order; set membership here never invents it.
    index = _read_json(root / "index/instruments.json")
    if fmt == "qlib_bin":
        reader = read_pack_panel
        required_files = {"qlib_bin/calendars/1min.txt", "index/instruments.json"}
        for inst, entry in index.items():
            for name in entry["features"]:
                required_files.add(f"qlib_bin/features/{qlib_inst_dir(inst)}/{name}.1min.bin")
    else:
        from backtest.research.joint_return_columnar_pack import FORMATS, read_columnar_panel
        require(fmt in FORMATS, "unsupported pack format", "CONTRACT_MISMATCH")
        reader = read_columnar_panel
        required_files = {FORMATS[fmt][1], "index/instruments.json",
                          "index/minutes.json"}
    files = manifest.get("payload_files")
    require(isinstance(files, list) and all(isinstance(p, str) for p in files)
            and required_files <= set(files),
            "MANIFEST payload_files must cover decoded axes/features", "CONTRACT_MISMATCH")
    with timings.phase("validate_metadata"):
        with timings.phase("bar_metadata"):
            opportunities, ends, mapping = _validate_bar_metadata(bundle, m, intents, timings)
    with timings.phase("validate_panel_load"):
        try:
            panel = reader(root, _timings=timings)
        except (ValueError, OSError, KeyError, TypeError) as exc:
            raise ReplayError("INPUT_BLOCKED", f"invalid {fmt} pack: {exc}") from exc
    require(panel.instruments == tuple(sorted(mapping))
            and panel.execution_symbols == tuple(mapping[i] for i in panel.instruments),
            "minute execution mapping drift/collision", "SEMANTICS_BLOCKED")
    require(panel.minute_iso == tuple(t.isoformat(timespec="seconds") for t in sorted(opportunities)),
            "panel/session minute coverage mismatch")
    validated = validate_bars_v2(
        panel, manifest, payload_root=root, metadata=bundle["metadata"],
        corporate_actions=bundle["corporate_actions"], enabled=True, _timings=timings)
    bars = _PanelBars(validated, opportunities)
    return bundle, (opportunities, ends, bars, bars.closes)
