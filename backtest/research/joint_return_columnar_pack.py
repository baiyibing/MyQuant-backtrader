"""Research Arrow IPC/Parquet twins; seal default remains qlib_bin.

Feature rows are minute-major/instrument-minor, with explicit integer coordinates.
Bundle writers stage through the existing bin writer for exact float32 parity.
Readers only decode typed columns and reshape arrays; no bar records are built.
"""
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import pyarrow as pa
import pyarrow.ipc as ipc
import pyarrow.parquet as pq

from backtest.research import joint_return_qlib_bin_pack as bin_pack
from backtest.research.joint_return_replay import SCHEMA_VERSION, _PhaseTimings
from backtest.research.joint_return_validate_v2 import DensePanel, minute_axis_from_labels

FORMATS = {
    "parquet": ("joint-return-bars-parquet-panel-v1", "bars.parquet"),
    "arrow_ipc": ("joint-return-bars-arrow-ipc-panel-v1", "bars.arrow"),
}


def _paths(fmt):
    return dict(metadata="metadata.json", corporate_actions="corporate_actions.json",
                bars=FORMATS[fmt][1], index="index/", minutes="index/minutes.json")


def write_pack_parquet(bundle, pack_root):
    """Write a bundle, JSON path, or existing bin pack to a new research pack."""
    return _write(bundle, pack_root, "parquet")


def write_pack_arrow(bundle, pack_root):
    """Write an Arrow IPC file pack (not IPC stream); never overwrite."""
    return _write(bundle, pack_root, "arrow_ipc")


def _write(source, pack_root, fmt):
    if Path(pack_root).exists():
        raise FileExistsError(pack_root)
    if isinstance(source, dict) or not Path(source).is_dir():
        # Research writer only: reuse source validation and float32 rounding.
        with TemporaryDirectory(prefix="joint-return-twin-") as temporary:
            source = bin_pack.write_pack(source, Path(temporary) / "bin")
            return _write(source, pack_root, fmt)
    source = Path(source)
    manifest, timestamps, index = bin_pack._pack_axes(source)
    metadata = bin_pack._read_json(source / "metadata.json")
    events = bin_pack._read_json(source / "corporate_actions.json")
    if not isinstance(metadata, dict) or not isinstance(events, list):
        raise ValueError("metadata object and corporate_actions array required")
    minute_axis_from_labels(timestamps, bar_label=metadata.get("bar_label"))
    shape = len(timestamps), len(index)
    names = tuple(k for k in bin_pack.REQUIRED + bin_pack.OPTIONAL
                  if any(k in entry["features"] for entry in index.values()))
    columns = {k: np.full(shape, 0 if k == "suspended" else np.nan,
                         dtype="uint8" if k == "suspended" else "float32") for k in names}
    written = {k: np.zeros(shape[1], dtype=bool) for k in bin_pack.REQUIRED}
    for j, (_, _, values) in enumerate(bin_pack._pack_columns(source, timestamps, index)):
        for k, values_k in values.items():
            columns[k][:, j] = values_k
            if k in written:
                written[k][j] = True
    if not all(coverage.all() for coverage in written.values()):
        raise ValueError("incomplete required feature coverage from bin pack")
    arrays = dict(minute_i=np.repeat(np.arange(shape[0], dtype="uint32"), shape[1]),
                  inst_i=np.tile(np.arange(shape[1], dtype="uint32"), shape[0]))
    arrays.update({k: v.reshape(-1) for k, v in columns.items()})
    table = pa.table(arrays)
    root = Path(pack_root)
    root.mkdir(parents=True, exist_ok=False)
    (root / "index").mkdir()
    payload = root / FORMATS[fmt][1]
    if fmt == "parquet":
        pq.write_table(table, payload)
    else:
        with ipc.new_file(payload, table.schema) as writer:
            writer.write_table(table)
    bin_pack._json(root / "index/instruments.json", index)
    bin_pack._json(root / "index/minutes.json", timestamps)
    bin_pack._json(root / "metadata.json", metadata)
    bin_pack._json(root / "corporate_actions.json", events)
    # Deliberately do not carry source seal hashes onto a different payload.
    manifest = {k: manifest[k] for k in (
        "schema_version", "kind", "row_order", "dense_complete", "n_rows",
        "n_instruments", "n_opportunity_minutes", "high_low")}
    manifest.update(format=fmt, format_version=FORMATS[fmt][0], paths=_paths(fmt),
                    note="Research interop only; float32 bin parity; no seal hashes.")
    bin_pack._json(root / "MANIFEST.json", manifest)
    return root


def read_columnar_panel(pack_root, _timings=None):
    """Load a pinned columnar layout directly into DensePanel arrays.

    ``_timings`` is the research-only opt-in span sink; default off reads no clock.
    """
    timings = _timings if _timings is not None else _PhaseTimings()
    root = Path(pack_root)
    manifest = bin_pack._read_json(root / "MANIFEST.json")
    fmt = manifest["format"]
    if (fmt not in FORMATS or manifest["format_version"] != FORMATS[fmt][0]
            or manifest["schema_version"] != SCHEMA_VERSION
            or manifest["kind"] not in ("synthetic", "frozen_explicit")
            or manifest["paths"] != _paths(fmt)
            or manifest["row_order"] != "timestamp_asc_instrument_asc"):
        raise ValueError("unsupported columnar pack format/schema/kind/paths/order")
    with timings.phase("pack_axes"):
        labels = bin_pack._read_json(root / "index/minutes.json")
        if (not isinstance(labels, list) or not labels
                or labels != sorted(set(labels))
                or any(bin_pack._timestamp(t) != t for t in labels)):
            raise ValueError("minute labels must be normalized, sorted and unique")
        index = bin_pack._read_json(root / "index/instruments.json")
        if not isinstance(index, dict) or not index:
            raise ValueError("nonempty instrument index required")
        instruments = tuple(sorted(index))
        symbols, folders = set(), set()
        for inst in instruments:
            entry = index[inst]
            symbol, folder = entry["execution_symbol"], bin_pack.qlib_inst_dir(inst)
            features = entry["features"]
            if (not isinstance(symbol, str) or not symbol or symbol in symbols
                    or folder is None or folder in folders
                    or not isinstance(features, list) or len(features) != len(set(features))
                    or not set(bin_pack.REQUIRED) <= set(features)
                    or not set(features) <= set(bin_pack.REQUIRED + bin_pack.OPTIONAL)):
                raise ValueError("invalid instrument mapping/features")
            symbols.add(symbol)
            folders.add(folder)
        shape = len(labels), len(index)
        if (manifest["dense_complete"] is not True
                or any(type(manifest[k]) is not int or manifest[k] != n for k, n in (
                    ("n_rows", shape[0] * shape[1]), ("n_instruments", shape[1]),
                    ("n_opportunity_minutes", shape[0])))):
            raise ValueError("pack counts/density mismatch")
        names = tuple(k for k in bin_pack.REQUIRED + bin_pack.OPTIONAL
                      if any(k in entry["features"] for entry in index.values()))
        if manifest["high_low"] != ("passthrough" if set(names) & set(bin_pack.OPTIONAL) else "source_absent"):
            raise ValueError("high_low declaration mismatch")
    payload = root / FORMATS[fmt][1]
    with timings.phase("pack_decode"):
        if fmt == "parquet":
            table = pq.ParquetFile(payload).read()
        else:
            with pa.memory_map(str(payload), "r") as stream:
                table = ipc.open_file(stream).read_all()
        expected = pa.schema([(k, pa.uint32()) for k in ("minute_i", "inst_i")] + [
            (k, pa.uint8() if k == "suspended" else pa.float32()) for k in names])
        if not table.schema.equals(expected) or table.num_rows != shape[0] * shape[1]:
            raise ValueError("columnar schema/row count mismatch")
    timings.count("decoded_rows", table.num_rows)
    with timings.phase("pack_assemble"):
        arrays = {}
        for k in table.column_names:
            if table[k].null_count:
                raise ValueError("null cells forbidden; optional absence uses NaN")
            arrays[k] = table[k].to_numpy(zero_copy_only=False).reshape(shape)
        if (not np.all(arrays.pop("minute_i") == np.arange(shape[0])[:, None])
                or not np.all(arrays.pop("inst_i") == np.arange(shape[1])[None, :])):
            raise ValueError("dense row coordinates/order mismatch")
        columns = {}
        for k, values in arrays.items():
            if np.isinf(values).any() or (k in bin_pack.REQUIRED and np.isnan(values).any()):
                raise ValueError("invalid nonfinite feature")
            if k == "suspended" and not np.isin(values, [0, 1]).all():
                raise ValueError("suspended must contain 0/1")
            for j, inst in enumerate(instruments):
                if k not in index[inst]["features"] and not np.isnan(values[:, j]).all():
                    raise ValueError("unindexed optional feature")
            columns[k] = values.astype("uint8" if k == "suspended" else "float64")
        metadata = bin_pack._read_json(root / "metadata.json")
        events = bin_pack._read_json(root / "corporate_actions.json")
        if not isinstance(metadata, dict) or not isinstance(events, list):
            raise ValueError("metadata object and corporate_actions array required")
        minutes = minute_axis_from_labels(labels, bar_label=metadata.get("bar_label"))
    return DensePanel(columns, shape[0], instruments,
                      tuple(index[i]["execution_symbol"] for i in instruments), minutes)
