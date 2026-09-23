"""Tiny synthetic K1 grids; no lake or replay integration required."""
from dataclasses import replace
from decimal import Decimal
import hashlib

import numpy as np
import pytest

from backtest.research.joint_return_replay import ReplayError, content_hash
from backtest.research.joint_return_validate_v2 import (
    DensePanel, ValidatedPanel, minute_axis_from_labels, panel_table_sha256,
    validate_bars_v2,
)


@pytest.fixture
def case(tmp_path):
    columns = {name: np.full((3, 2), value, dtype=np.float64) for name, value in
               (("open", 10.1), ("close", 10.2), ("limit_up", 11),
                ("limit_down", 9), ("capacity", 100))}
    columns["suspended"] = np.zeros((3, 2), dtype=np.uint8)
    panel = DensePanel(columns, 3, ("A", "B"), ("A.SYN", "B.SYN"),
                       tuple(f"2026-09-07T09:{m}:00+08:00" for m in (30, 31, 32)))
    # Independent canonical byte oracle, with nonalphabetical pinned file order.
    raw = b"".join(columns[k].astype("u1" if k == "suspended" else "<f8").tobytes()
                   for k in ("open", "close", "limit_up", "limit_down", "capacity", "suspended"))
    (tmp_path / "z.bin").write_bytes(raw[:23])
    (tmp_path / "a.bin").write_bytes(raw[23:])
    metadata = {"source": "synthetic K1 prebuilt session axis"}
    manifest = dict(payload_files=["z.bin", "a.bin"],
                    bars_payload_raw_sha256=hashlib.sha256(raw).hexdigest(),
                    bars_table_sha256=hashlib.sha256(raw).hexdigest(),
                    metadata_content_sha256=content_hash(metadata),
                    corporate_actions_content_sha256=content_hash([]))
    return panel, manifest, dict(payload_root=tmp_path, metadata=metadata,
                                corporate_actions=[], enabled=True)


def test_happy_and_lazy_accessor(case):
    panel, manifest, kwargs = case
    result = validate_bars_v2(panel, manifest, **kwargs)
    assert isinstance(result, ValidatedPanel)
    assert result.bar_open(0, 0) == Decimal(str(float(panel.columns["open"][0, 0])))
    assert result.bar_capacity(2, 1) == Decimal("100.0")
    assert panel.columns["open"].dtype == np.float64
    assert panel_table_sha256(panel) == manifest["bars_table_sha256"]


@pytest.mark.parametrize("fault", ["payload", "order", "missing_order", "table", "metadata", "events"])
def test_seal_fail_closed(case, fault):
    panel, manifest, kwargs = case
    if fault == "payload":
        (kwargs["payload_root"] / "z.bin").write_bytes(b"tampered")
    elif fault == "order":
        manifest["payload_files"].reverse()
    elif fault == "missing_order":
        del manifest["payload_files"]
    else:
        key = {"table": "bars_table_sha256", "metadata": "metadata_content_sha256",
               "events": "corporate_actions_content_sha256"}[fault]
        manifest[key] = "0" * 64
    with pytest.raises(ReplayError, match="CONTRACT_MISMATCH"):
        validate_bars_v2(panel, manifest, **kwargs)


def test_default_off(case):
    panel, manifest, kwargs = case
    del kwargs["enabled"]
    with pytest.raises(ReplayError, match="default off"):
        validate_bars_v2(panel, manifest, **kwargs)


@pytest.mark.parametrize("fault", ["bitmap", "shape"])
def test_coverage_hole(case, fault):
    panel, manifest, kwargs = case
    if fault == "bitmap":
        valid = np.ones(panel.shape, dtype=bool)
        valid[1, 1] = False
        panel = replace(panel, validity=valid)
    else:
        panel.columns["close"] = panel.columns["close"][:-1]
    with pytest.raises(ReplayError, match="coverage"):
        validate_bars_v2(panel, manifest, **kwargs)


@pytest.mark.parametrize("column,value,message", [
    ("open", 11.01, "outside explicit price limits"),
    ("close", 8.99, "outside explicit price limits"),
    ("open", 0, "nonpositive"), ("close", np.nan, "nonfinite"),
    ("limit_up", np.inf, "nonfinite"), ("capacity", -1, "invalid capacity"),
    ("capacity", np.inf, "invalid capacity"), ("suspended", 2, "invalid suspended"),
])
def test_semantic_failures(case, column, value, message):
    panel, manifest, kwargs = case
    # Without optional table seal, isolate V2 gates from V0 table mismatch.
    del manifest["bars_table_sha256"]
    panel.columns[column][1, 1] = value
    with pytest.raises(ReplayError, match=message) as exc:
        validate_bars_v2(panel, manifest, **kwargs)
    assert "B at 2026-09-07T09:31:00+08:00" in exc.value.detail


def test_limits_tie_and_suspended(case):
    # v1's limit_down <= min(open, close) <= max(...) <= limit_up is inclusive.
    # Float64 v2 uses the same inclusive boundary, with no epsilon allowance.
    panel, manifest, kwargs = case
    del manifest["bars_table_sha256"]
    panel.columns["open"][:] = panel.columns["limit_down"]
    panel.columns["close"][:] = panel.columns["limit_up"]
    panel.columns["suspended"][0, 0] = 1
    panel.columns["capacity"][0, 0] = 0
    assert validate_bars_v2(panel, manifest, **kwargs)
    panel.columns["close"][0, 0] = np.nextafter(11.0, np.inf)
    with pytest.raises(ReplayError, match="outside explicit price limits"):
        validate_bars_v2(panel, manifest, **kwargs)


def test_high_low_absent_or_passthrough(case):
    panel, manifest, kwargs = case
    result = validate_bars_v2(panel, manifest, **kwargs)
    assert "high" not in result.panel.columns and "low" not in result.panel.columns
    with pytest.raises(ReplayError, match="absent bar column"):
        result.bar_decimal("high", 0, 0)
    high = np.full(panel.shape, 10.8)
    low = np.full(panel.shape, 9.2)
    panel.columns.update(high=high, low=low)
    raw = b"".join(panel.columns[k].astype("u1" if k == "suspended" else "<f8").tobytes()
                   for k in ("open", "close", "limit_up", "limit_down", "capacity", "suspended", "high", "low"))
    manifest["bars_table_sha256"] = hashlib.sha256(raw).hexdigest()
    result = validate_bars_v2(panel, manifest, **kwargs)
    assert result.panel.columns["high"] is high
    assert result.panel.columns["low"] is low


def test_close_time_axis():
    assert minute_axis_from_labels(["2026-09-07T09:31:00+08:00"], bar_label="CLOSE_TIME") == (
        "2026-09-07T09:30:00+08:00",)


@pytest.mark.parametrize("fault", ["dtype", "mapping", "axis", "events"])
def test_minimal_contracts(case, fault):
    panel, manifest, kwargs = case
    if fault == "dtype":
        panel.columns["open"] = panel.columns["open"].astype(np.float32)
    elif fault == "mapping":
        panel = replace(panel, execution_symbols=("A.SYN", "A.SYN"))
    elif fault == "axis":
        panel = replace(panel, minute_iso=tuple(reversed(panel.minute_iso)))
    else:
        kwargs["corporate_actions"] = [{"event_id": "deferred"}]
        manifest["corporate_actions_content_sha256"] = content_hash(kwargs["corporate_actions"])
    with pytest.raises(ReplayError):
        validate_bars_v2(panel, manifest, **kwargs)
