"""Research pack fidelity and fail-closed I/O (no lake or seal authority)."""
import ast
import inspect
import json
from decimal import Decimal

import numpy as np
import pytest

from backtest.research import joint_return_qlib_bin_pack as pack
from backtest.research.joint_return_replay import validate_reference_marks


@pytest.fixture
def bundle():
    bars = [dict(instrument=inst, execution_symbol=symbol,
                 timestamp=f"2026-09-22T09:{minute}:00+08:00",
                 open="10.12", close=Decimal("10.24"), limit_up="11.0", limit_down="9.0",
                 suspended=minute == 32, capacity=0 if minute == 32 else 12345,
                 high="10.87", low="9.31")
            for inst, symbol in [("SH600519", "600519.SH"), ("SZ000001", "000001.SZ")]
            for minute in (30, 31, 32)]
    mark = dict(instrument="SH600519", execution_symbol="600519.SH", mark_price=10.123456789,
                mark_at="2026-09-21T15:00:00+08:00", price_domain="none", source_kind="lake_bar",
                source="fixture", source_sha256="a" * 64)
    return dict(schema_version="joint-return-v1", kind="frozen_explicit",
                metadata=dict(reference_marks={"intent1": mark}, source="fixture", extra={"keep": [1, True]}),
                corporate_actions=[{"event_id": "fixture", "factor": "1.234567891"}],
                bars=list(reversed(bars)), content_sha256="b" * 64)


def test_round_trip_and_passthrough(tmp_path, bundle):
    root = pack.write_pack(bundle, tmp_path / "pack")
    got = pack.read_pack(root)
    assert got["metadata"] == bundle["metadata"]
    assert got["corporate_actions"] == bundle["corporate_actions"]
    assert got["schema_version"] == bundle["schema_version"]
    assert got["kind"] == bundle["kind"]
    assert "content_sha256" not in got  # Never promote a lossy twin to seal authority.
    mark = got["metadata"]["reference_marks"]["intent1"]
    validate_reference_marks(got, [dict(intent_id="intent1", instrument=mark["instrument"],
        execution_symbol=mark["execution_symbol"], reference_price_at=mark["mark_at"])])
    expected = sorted(bundle["bars"], key=lambda row: (row["timestamp"], row["instrument"]))
    for actual, source in zip(got["bars"], expected, strict=True):
        for name in ("instrument", "execution_symbol", "timestamp", "suspended"):
            assert actual[name] == source[name]
        assert type(actual["suspended"]) is bool
        for name in ("open", "close", "limit_up", "limit_down", "capacity", "high", "low"):
            assert actual[name] == pytest.approx(float(source[name]), rel=1e-6)
        # These true extrema differ from both endpoints: max/min invention fails.
        assert actual["high"] > max(actual["open"], actual["close"])
        assert actual["low"] < min(actual["open"], actual["close"])
    for dirname in ("sh600519", "sz000001"):
        for name in pack.REQUIRED + pack.OPTIONAL:
            raw = np.fromfile(root / f"qlib_bin/features/{dirname}/{name}.1min.bin", dtype="<f4")
            assert len(raw) == 4 and raw[0] == 0
    manifest = json.loads((root / "MANIFEST.json").read_text())
    assert manifest["high_low"] == "passthrough"
    assert manifest["n_rows"] == 6 and manifest["dense_complete"] is True
    assert manifest["format_version"] == pack.FORMAT_VERSION


def test_source_absent_never_synthesizes(tmp_path, bundle):
    for row in bundle["bars"]:
        del row["high"]
        row["low"] = None
    root = pack.write_pack(bundle, tmp_path / "pack")
    assert not list(root.rglob("high.1min.bin"))
    assert not list(root.rglob("low.1min.bin"))
    assert all("high" not in row and "low" not in row for row in pack.read_pack(root)["bars"])
    assert json.loads((root / "MANIFEST.json").read_text())["high_low"] == "source_absent"
    # Explicitly forbid the prior bench's max/min (including numpy variants)
    # anywhere in this writer module; behavior assertions above also catch fallback.
    tree = ast.parse(inspect.getsource(pack))
    forbidden = {"max", "min", "maximum", "minimum", "fmax", "fmin"}
    assert not [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                and ((isinstance(node.func, ast.Name) and node.func.id in forbidden)
                     or (isinstance(node.func, ast.Attribute) and node.func.attr in forbidden))]


def test_partial_high_low_and_timestamp_normalization(tmp_path, bundle):
    row = bundle["bars"][0]
    row.pop("high")
    row["low"] = None
    row["timestamp"] = "2026-09-22 09:32:00"
    got = pack.read_pack(pack.write_pack(bundle, tmp_path / "pack"))
    target = next(r for r in got["bars"] if r["instrument"] == row["instrument"]
                  and r["timestamp"] == "2026-09-22T09:32:00+08:00")
    assert "high" not in target and "low" not in target
    assert sum("high" in r for r in got["bars"]) == 5


@pytest.mark.parametrize("problem", ["duplicate", "sparse", "suspended", "collision", "nonfinite"])
def test_invalid_source(tmp_path, bundle, problem):
    if problem == "duplicate":
        bundle["bars"].append(bundle["bars"][0])
    elif problem == "sparse":
        bundle["bars"].pop()
    elif problem == "suspended":
        bundle["bars"][0]["suspended"] = "false"
    elif problem == "collision":
        bundle["bars"][0]["execution_symbol"] = "600519.SH"
    else:
        bundle["bars"][0]["high"] = "inf"
    with pytest.raises(ValueError):
        pack.write_pack(bundle, tmp_path / "pack")


@pytest.mark.parametrize("problem", ["missing", "truncated", "header", "suspended", "nan", "optional_missing"])
def test_corrupt_bin_rejected(tmp_path, bundle, problem):
    root = pack.write_pack(bundle, tmp_path / "pack")
    path = root / "qlib_bin/features/sh600519/suspended.1min.bin"
    if problem == "missing":
        path.unlink()
    elif problem == "optional_missing":
        path.with_name("high.1min.bin").unlink()
    elif problem == "truncated":
        path.write_bytes(path.read_bytes()[:-4])
    else:
        values = np.fromfile(path, dtype="<f4")
        values[0 if problem == "header" else 1] = np.nan if problem == "nan" else 2
        path.write_bytes(values.tobytes())
    with pytest.raises(ValueError):
        pack.read_pack(root)


def test_json_path_and_no_overwrite(tmp_path, bundle):
    source = tmp_path / "source.json"
    source.write_text(json.dumps(bundle, default=str), encoding="utf-8")
    root = pack.write_pack(source, tmp_path / "pack")
    assert len(pack.read_pack(root)["bars"]) == 6
    with pytest.raises(FileExistsError):
        pack.write_pack(source, root)
