"""Timing-only Mode B pack I/O; float32 is NOT a Decimal seal authority.

Direct bin-to-panel research ingest is available for opt-in v2. Sidecars remain JSON values; source content_sha256 is
intentionally not copied onto the lossy reconstruction. Never synthesize high/low.
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

from backtest.research.joint_return_replay import (
    SCHEMA_VERSION, canonical_bytes, load_json_bytes,
)
from backtest.research.qlib_bin_1min import load_qlib_1min_calendar
from backtest.research.qlib_bin_daily import qlib_inst_dir, read_qlib_bin

FORMAT_VERSION = "joint-return-bars-qlib-bin-marks-v1"
REQUIRED = ("open", "close", "limit_up", "limit_down", "suspended", "capacity")
OPTIONAL = ("high", "low")
PATHS = dict(metadata="metadata.json", corporate_actions="corporate_actions.json",
             qlib_bin="qlib_bin/", index="index/")
SHANGHAI = timezone(timedelta(hours=8))


def _timestamp(value):
    """Normalize to Shanghai minute labels; naive input means Shanghai local time."""
    t = datetime.fromisoformat(value)
    t = t.replace(tzinfo=SHANGHAI) if t.tzinfo is None else t.astimezone(SHANGHAI)
    if t.second or t.microsecond:
        raise ValueError("bar timestamp must be minute aligned")
    return t.isoformat(timespec="seconds")


def _json(path, value):
    path.write_bytes(canonical_bytes(value) + b"\n")


def _read_json(path):
    return load_json_bytes(path.read_bytes())


def _float32(value):
    with np.errstate(over="ignore", invalid="ignore"):
        result = np.float32(value)
    if not np.isfinite(result):
        raise ValueError("source feature must be finite and representable as float32")
    return result


def write_pack(bundle: dict | str | Path, pack_root: str | Path) -> Path:
    """Write a nonempty dense bundle to a new directory (never overwrite a pack).

    Density is measured against sorted unique source timestamps, not a claim of
    session coverage. high/low are source-only: null/missing cells use NaN in an
    otherwise present optional bin, then reconstruct as absent keys.
    """
    if not isinstance(bundle, dict):
        bundle = _read_json(Path(bundle))
    if bundle["schema_version"] != SCHEMA_VERSION or bundle["kind"] not in (
        "frozen_explicit", "synthetic"
    ):
        raise ValueError("unsupported schema_version/kind")
    if not isinstance(bundle["metadata"], dict) or not isinstance(bundle["corporate_actions"], list):
        raise ValueError("metadata object and corporate_actions array required")
    # Validate JSON sidecars without transforming reference_marks or events.
    canonical_bytes(bundle["metadata"])
    canonical_bytes(bundle["corporate_actions"])
    grouped, symbols, folders, reverse = {}, {}, {}, {}
    timestamps = set()
    for bar in bundle["bars"]:
        inst, symbol = bar["instrument"], bar["execution_symbol"]
        folder = qlib_inst_dir(inst)
        if folder is None or not isinstance(symbol, str) or not symbol:
            raise ValueError("invalid instrument/execution_symbol")
        if symbols.setdefault(inst, symbol) != symbol or reverse.setdefault(symbol, inst) != inst:
            raise ValueError("execution_symbol mapping collision/drift")
        if folders.setdefault(folder, inst) != inst:
            raise ValueError("qlib instrument folder collision")
        timestamp = _timestamp(bar["timestamp"])
        rows = grouped.setdefault(inst, {})
        if timestamp in rows:
            raise ValueError("duplicate instrument/timestamp")
        if type(bar["suspended"]) is not bool:
            raise ValueError("suspended must be bool")
        rows[timestamp] = bar
        timestamps.add(timestamp)
    calendar = sorted(timestamps)
    if not calendar or any(len(rows) != len(calendar) for rows in grouped.values()):
        raise ValueError("nonempty dense calendar x instrument bars required")
    root = Path(pack_root)
    root.mkdir(parents=True, exist_ok=False)
    qroot = root / "qlib_bin"
    (qroot / "calendars").mkdir(parents=True)
    # Standard qlib calendar uses local wall-clock labels, logical rows use +08:00.
    (qroot / "calendars/1min.txt").write_text(
        "".join(t[:19].replace("T", " ") + "\n" for t in calendar), encoding="utf-8"
    )
    index = {}
    has_high_low = False
    for inst, rows in sorted(grouped.items()):
        folder = qroot / "features" / qlib_inst_dir(inst)
        folder.mkdir(parents=True)
        features = list(REQUIRED)
        for name in OPTIONAL:
            # HARD BAN: passthrough only; never derive extrema from open/close.
            if any(row.get(name) is not None for row in rows.values()):
                features.append(name)
                has_high_low = True
        for name in features:
            values = np.empty(len(calendar) + 1, dtype="<f4")
            values[0] = 0  # qlib ref start index
            for i, timestamp in enumerate(calendar, 1):
                value = rows[timestamp].get(name)
                values[i] = np.nan if name in OPTIONAL and value is None else _float32(value)
            (folder / f"{name}.1min.bin").write_bytes(values.tobytes())
        index[inst] = dict(execution_symbol=symbols[inst], features=features)
    (root / "index").mkdir()
    _json(root / "index/instruments.json", index)
    _json(root / "metadata.json", bundle["metadata"])
    _json(root / "corporate_actions.json", bundle["corporate_actions"])
    _json(root / "MANIFEST.json", dict(
        format="qlib_bin", format_version=FORMAT_VERSION, schema_version=SCHEMA_VERSION,
        kind=bundle["kind"], paths=PATHS, row_order="timestamp_asc_instrument_asc",
        dense_complete=True, n_rows=len(calendar) * len(index), n_instruments=len(index),
        n_opportunity_minutes=len(calendar), high_low="passthrough" if has_high_low else "source_absent",
        note="Timing only; float32, no seal hashes. Density uses source timestamps; session coverage unvalidated.",
    ))
    return root


def read_pack(pack_root: str | Path) -> dict:
    """Reconstruct research rows; does not validate intent marks or certify a seal.

    Symbols come from index/instruments.json, never a guessed symbol conversion.
    Required bins must be complete; absent optional cells are never invented.
    """
    root = Path(pack_root)
    manifest, timestamps, index = _pack_axes(root)
    bars = []
    for inst, symbol, columns in _pack_columns(root, timestamps, index):
        for i, timestamp in enumerate(timestamps):
            bar = dict(instrument=inst, execution_symbol=symbol, timestamp=timestamp)
            for name, values in columns.items():
                if not np.isnan(values[i]):
                    bar[name] = bool(values[i]) if name == "suspended" else float(values[i])
            bars.append(bar)
    bars.sort(key=lambda row: (row["timestamp"], row["instrument"]))
    return dict(schema_version=SCHEMA_VERSION, kind=manifest["kind"],
                metadata=_read_json(root / "metadata.json"), bars=bars,
                corporate_actions=_read_json(root / "corporate_actions.json"))


def _pack_axes(root):
    manifest = _read_json(root / "MANIFEST.json")
    if (manifest["format"], manifest["format_version"], manifest["schema_version"]) != (
        "qlib_bin", FORMAT_VERSION, SCHEMA_VERSION
    ) or manifest["kind"] not in ("frozen_explicit", "synthetic"):
        raise ValueError("unsupported pack format/schema/kind")
    if manifest["paths"] != PATHS or manifest["row_order"] != "timestamp_asc_instrument_asc":
        raise ValueError("unsupported pack paths/order")
    calendar = load_qlib_1min_calendar(root / "qlib_bin")
    timestamps = [_timestamp(t) for t in calendar]
    if not timestamps or timestamps != sorted(set(timestamps)):
        raise ValueError("calendar must be nonempty, sorted and unique")
    index = _read_json(root / "index/instruments.json")
    if (manifest["dense_complete"] is not True or not index
            or manifest["n_instruments"] != len(index)
            or manifest["n_opportunity_minutes"] != len(calendar)
            or manifest["n_rows"] != len(calendar) * len(index)):
        raise ValueError("pack counts/density mismatch")
    return manifest, timestamps, index


def _pack_columns(root, timestamps, index):
    """Yield one instrument's checked arrays; never construct bar records."""
    seen_folders, seen_symbols = set(), set()
    for inst, entry in sorted(index.items()):
        dirname = qlib_inst_dir(inst)
        symbol = entry["execution_symbol"]
        if (dirname is None or dirname in seen_folders or not isinstance(symbol, str)
                or not symbol or symbol in seen_symbols):
            raise ValueError("invalid/colliding instrument mapping")
        seen_folders.add(dirname)
        seen_symbols.add(symbol)
        folder = root / "qlib_bin/features" / dirname
        features = entry["features"]
        if (len(features) != len(set(features)) or not set(REQUIRED) <= set(features)
                or not set(features) <= set(REQUIRED + OPTIONAL)):
            raise ValueError("invalid feature index")
        columns = {}
        for name in REQUIRED + OPTIONAL:
            path = folder / f"{name}.1min.bin"
            if name not in features:
                if path.exists():
                    raise ValueError("unindexed feature bin")
                continue
            if not path.is_file() or path.stat().st_size != 4 * (len(timestamps) + 1):
                raise ValueError(f"missing/truncated feature bin: {path}")
            with path.open("rb") as stream:
                if stream.read(4) != np.array([0], dtype="<f4").tobytes():
                    raise ValueError("pack bin ref must be zero")
            values = read_qlib_bin(path, 0, len(timestamps) - 1).to_numpy()
            if np.isinf(values).any() or (name in REQUIRED and np.isnan(values).any()):
                raise ValueError("invalid nonfinite feature")
            if name == "suspended" and not np.isin(values, [0, 1]).all():
                raise ValueError("suspended bin must contain 0/1")
            columns[name] = values
        yield inst, symbol, columns


def read_pack_panel(pack_root: str | Path):
    """Decode marks-v1 directly to float64/uint8 DensePanel (no bar dicts).

    This is a reader, not seal certification. CLOSE_TIME labels shift -60s;
    replay separately proves session coverage and the byte seal. Missing optional
    cells remain NaN (v2 validation rejects partial extrema), never synthesized.
    Required bins are dense, so no validity bitmap allocation is needed.
    """
    from backtest.research.joint_return_validate_v2 import (
        COLUMNS, DensePanel, minute_axis_from_labels,
    )
    root = Path(pack_root)
    _, timestamps, index = _pack_axes(root)
    metadata = _read_json(root / "metadata.json")
    minutes = minute_axis_from_labels(timestamps, bar_label=metadata.get("bar_label"))
    instruments = tuple(sorted(index))
    shape = len(minutes), len(instruments)
    columns = {name: np.empty(shape, dtype="uint8" if name == "suspended" else "float64")
               for name in COLUMNS}
    for j, (_, _, values) in enumerate(_pack_columns(root, timestamps, index)):
        for name, column in values.items():
            if name not in columns:
                columns[name] = np.full(shape, np.nan, dtype="float64")
            columns[name][:, j] = column
    return DensePanel(columns, len(minutes), instruments,
                      tuple(index[i]["execution_symbol"] for i in instruments), minutes)
