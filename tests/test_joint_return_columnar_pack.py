"""Interop parity, direct column ingest, and corrupt payload rejection."""
import ast
import inspect
import json

import numpy as np
import pyarrow as pa
import pyarrow.ipc as ipc
import pyarrow.parquet as pq
import pytest

from backtest.research import joint_return_columnar_pack as pack
from backtest.research import joint_return_qlib_bin_pack as bin_pack
from tests.test_joint_return_qlib_bin_pack import bundle  # shared two-instrument fixture


@pytest.fixture(params=["parquet", "arrow_ipc"])
def fmt(request):
    return request.param


def write(source, target, fmt):
    writer = pack.write_pack_parquet if fmt == "parquet" else pack.write_pack_arrow
    return writer(source, target)


def read_table(root, fmt):
    path = root / pack.FORMATS[fmt][1]
    return pq.ParquetFile(path).read() if fmt == "parquet" else ipc.open_file(path).read_all()


def save_table(root, fmt, table):
    path = root / pack.FORMATS[fmt][1]
    if fmt == "parquet":
        pq.write_table(table, path)
    else:
        with ipc.new_file(path, table.schema) as stream:
            stream.write_table(table)


@pytest.mark.parametrize("label", ["OPEN_TIME", "CLOSE_TIME"])
@pytest.mark.parametrize("extrema", ["full", "absent", "partial"])
@pytest.mark.parametrize("source_kind", ["bundle", "json", "bin"])
def test_exact_bin_parity(tmp_path, bundle, monkeypatch, fmt, label, extrema, source_kind):
    bundle["metadata"]["bar_label"] = label
    for row in bundle["bars"]:
        if extrema == "absent" or (extrema == "partial" and row["instrument"] == "SH600519"):
            row.pop("high")
            row.pop("low")
    bin_root = bin_pack.write_pack(bundle, tmp_path / "bin")
    expected = bin_pack.read_pack_panel(bin_root)
    monkeypatch.setattr(bin_pack, "read_pack", lambda *a: pytest.fail("bar materialization"))
    source = bundle
    if source_kind == "bin":
        source = bin_root
    elif source_kind == "json":
        source = tmp_path / "bundle.json"
        source.write_text(json.dumps(bundle, default=str), encoding="utf-8")
    root = write(source, tmp_path / "twin", fmt)
    # Readers must not round-trip through any bin writer/reader either.
    monkeypatch.setattr(bin_pack, "write_pack", lambda *a: pytest.fail("staging in reader"))
    monkeypatch.setattr(bin_pack, "read_pack_panel", lambda *a: pytest.fail("bin reader"))
    got = pack.read_columnar_panel(root)
    assert got.shape == expected.shape
    assert got.instruments == expected.instruments
    assert got.execution_symbols == expected.execution_symbols
    assert got.minute_iso == expected.minute_iso
    assert got.validity is None
    assert got.columns.keys() == expected.columns.keys()
    for name, column in got.columns.items():
        assert column.dtype == expected.columns[name].dtype
        np.testing.assert_array_equal(column, expected.columns[name])
    assert bin_pack._read_json(root / "metadata.json") == bundle["metadata"]
    assert bin_pack._read_json(root / "corporate_actions.json") == bundle["corporate_actions"]
    assert "payload_files" not in bin_pack._read_json(root / "MANIFEST.json")
    with pytest.raises(FileExistsError):
        write(source, root, fmt)


def assert_no_row_conversion(source):
    # Check all reader-side helpers, including future ones. Only these write-only
    # functions may stage/construct records; the reader may not call them.
    writers = {"_write", "write_pack_parquet", "write_pack_arrow"}
    forbidden = writers | {"append", "extend", "to_pylist", "to_pydict", "to_pandas",
                           "read_pack", "read_pack_panel", "write_pack", "validate_json_replay"}
    for function in ast.parse(source).body:
        if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if function.name in writers:
            continue
        for node in ast.walk(function):
            name = node.attr if isinstance(node, ast.Attribute) else node.id if isinstance(node, ast.Name) else None
            assert name not in forbidden, f"{function.name}: forbidden row API {name}"
            # Empty column maps are allowed; populated dicts/comprehensions could
            # rebuild bars, including inside a list/generator comprehension.
            assert not isinstance(node, ast.DictComp), f"{function.name}: dict comprehension"
            assert not isinstance(node, ast.Dict) or not node.keys, f"{function.name}: populated dict"
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "dict":
                # The one shared layout helper returns only pinned path names.
                assert (function.name == "_paths" and not node.args
                        and {kw.arg for kw in node.keywords} == {
                            "metadata", "corporate_actions", "bars", "index", "minutes"
                        }), f"{function.name}: dict constructor"


def test_no_row_conversion():
    assert_no_row_conversion(inspect.getsource(pack))


@pytest.mark.parametrize("expression", [
    "table.to_pylist()", "table.to_pydict()", "table.to_pandas()",
    "bin_pack.read_pack(root)", "read_pack(root)", "_write(source, root, fmt)",
    '{"open": value}', "dict(open=value)", "dict(pairs)",
    '[{"open": value} for value in values]', "{key: value for key, value in pairs}",
])
def test_no_row_conversion_catches_reader_helpers(expression):
    source = inspect.getsource(pack) + f"\n\ndef _future_reader_helper():\n    return {expression}\n"
    with pytest.raises(AssertionError, match="_future_reader_helper"):
        assert_no_row_conversion(source)


@pytest.mark.parametrize("missing", ["instrument", *bin_pack.REQUIRED])
def test_writer_rejects_partial_columns(tmp_path, bundle, monkeypatch, fmt, missing):
    bundle["metadata"]["bar_label"] = "OPEN_TIME"
    source = bin_pack.write_pack(bundle, tmp_path / "bin")
    pack_columns = bin_pack._pack_columns

    def partial_columns(*args):
        for j, (inst, symbol, columns) in enumerate(pack_columns(*args)):
            if j == 1:
                if missing == "instrument":
                    return
                columns.pop(missing)
            yield inst, symbol, columns

    monkeypatch.setattr(bin_pack, "_pack_columns", partial_columns)
    target = tmp_path / "twin"
    with pytest.raises(ValueError, match="required feature coverage"):
        write(source, target, fmt)
    assert not target.exists()


@pytest.mark.parametrize("fault", ["missing", "truncated", "count", "version", "labels", "mapping",
                                   "feature_index", "metadata", "events", "schema", "row_order",
                                   "nan", "inf", "suspended", "null", "missing_column", "extra_column"])
def test_corrupt_fail_closed(tmp_path, bundle, fmt, fault):
    bundle["metadata"]["bar_label"] = "OPEN_TIME"
    root = write(bundle, tmp_path / "pack", fmt)
    path = root / pack.FORMATS[fmt][1]
    if fault == "missing":
        path.unlink()
    elif fault == "truncated":
        path.write_bytes(path.read_bytes()[:32])
    elif fault in ("count", "version"):
        manifest = bin_pack._read_json(root / "MANIFEST.json")
        manifest["n_rows" if fault == "count" else "format_version"] = 123
        bin_pack._json(root / "MANIFEST.json", manifest)
    elif fault == "labels":
        labels = bin_pack._read_json(root / "index/minutes.json")
        bin_pack._json(root / "index/minutes.json", labels[::-1])
    elif fault in ("mapping", "feature_index"):
        index = bin_pack._read_json(root / "index/instruments.json")
        if fault == "mapping":
            index["SZ000001"]["execution_symbol"] = index["SH600519"]["execution_symbol"]
        else:
            index["SH600519"]["features"].remove("high")
        bin_pack._json(root / "index/instruments.json", index)
    elif fault in ("metadata", "events"):
        bin_pack._json(root / ("metadata.json" if fault == "metadata" else "corporate_actions.json"), None)
    else:
        table = read_table(root, fmt)
        name = "suspended" if fault == "suspended" else "open"
        if fault == "row_order":
            table = table.take(pa.array(list(reversed(range(table.num_rows)))))
        elif fault == "missing_column":
            table = table.drop(["close"])
        elif fault == "extra_column":
            table = table.append_column("unknown", table["open"])
        else:
            dtype = pa.float64() if fault == "schema" else table[name].type
            value = {"nan": np.nan, "inf": np.inf, "suspended": 2, "null": None}.get(fault, 10)
            table = table.set_column(table.schema.get_field_index(name), name,
                                     pa.array([value] * table.num_rows, type=dtype))
        save_table(root, fmt, table)
    with pytest.raises((ValueError, OSError, TypeError, KeyError)):
        pack.read_columnar_panel(root)
