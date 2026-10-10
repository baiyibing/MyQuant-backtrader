"""G2: synthetic cache identity tests; no configured market lake required."""
import json
import os

import pandas as pd
import pytest

from backtest.research import ashare_bars as bars

START, END = "20260901", "20260902"
A, B = "600000.SH", "600001.SH"


@pytest.fixture
def case(tmp_path, monkeypatch):
    monkeypatch.setenv("OSKH_BAR_MEM", "0")
    root = tmp_path / "lake"
    root.mkdir()
    cache = tmp_path / "cache"
    frame = bars.annotate_session(pd.DataFrame(
        {key: [10.0] for key in ("open", "high", "low", "close")},
        index=pd.to_datetime(["2026-09-01 09:30"]).as_unit("ns"))).astype({"hm": "int64"})
    calls = []

    def load(codes, start, end, **kwargs):
        calls.append((set(codes), kwargs))
        return {code: frame.copy() for code in codes}

    monkeypatch.setattr(bars, "load_minute_from_lake", load)
    return dict(lake_root=root, cache_dir=cache, source_snapshot="snapshot-a"), frame, calls


def load(options, codes=(A,), **kwargs):
    status = {}
    result = bars.load_minute_ohlc(codes, START, END, status=status, **(options | kwargs))
    return result, status["cache"]


def test_same_identity_hits_and_partial_preserves_other_symbols(case, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("explicit lake_root must not call the data root resolver")

    monkeypatch.setattr("common.infra.data_root.resolve_period_root", forbidden)
    options, frame, calls = case
    assert load(options)[1] == "miss"
    result, status = load(options)
    assert status == "hit" and len(calls) == 1
    pd.testing.assert_frame_equal(result[A], frame.rename_axis("time"))
    assert load(options, (B,))[1] == "partial"
    assert calls[-1][0] == {B}
    assert load(options, (A, B))[1] == "hit"
    path = bars.minute_cache_path(START, END, **options)
    meta = json.loads(path.with_suffix(".json").read_text())
    identity = bars.minute_cache_identity(START, END, **{k: v for k, v in options.items() if k != "cache_dir"})
    assert all(meta[k] == v for k, v in identity.items())
    assert meta["resolver_identity"] == str(options["lake_root"].resolve())
    assert len(path.stem.rsplit("_", 1)[-1]) == 12


@pytest.mark.parametrize("change", ["snapshot", "root"])
def test_different_source_does_not_reuse_or_clobber(case, change):
    options, _, calls = case
    load(options)
    old_path = bars.minute_cache_path(START, END, **options)
    old_bytes = old_path.read_bytes()
    different = options.copy()
    if change == "snapshot":
        different["source_snapshot"] = "snapshot-b"
    else:
        different["lake_root"] = options["lake_root"].parent / "other-lake"
        different["lake_root"].mkdir()
    assert load(different)[1] == "miss"
    assert len(calls) == 2
    assert bars.minute_cache_path(START, END, **different) != old_path
    assert old_path.read_bytes() == old_bytes


@pytest.mark.parametrize("field", ["identity_version", "start", "end", "dividend_type", "schema",
                                   "resolver_identity", "source_snapshot"])
@pytest.mark.parametrize("action", ["missing", "mismatch"])
def test_every_auth_field_is_required_and_must_match(case, field, action):
    options, frame, calls = case
    bars.write_minute_cache({A: frame, B: frame}, START, END, **options)
    path = bars.minute_cache_path(START, END, **options)
    sidecar = path.with_suffix(".json")
    meta = json.loads(sidecar.read_text())
    if action == "missing":
        del meta[field]
    else:
        meta[field] = "different"
    sidecar.write_text(json.dumps(meta), encoding="utf-8")
    assert load(options)[1] == "miss:identity"
    assert len(calls) == 1
    # Failed authentication also forbids merging unrequested cached symbols.
    assert set(bars.read_minute_cache(path)) == {A}


def test_same_type_wrong_identity_version_fails_closed(case):
    options, frame, calls = case
    stale = frame.copy()
    stale["close"] = 99.0
    path = bars.write_minute_cache({A: stale, B: stale}, START, END, **options)
    sidecar = path.with_suffix(".json")
    meta = json.loads(sidecar.read_text())
    meta["identity_version"] = 2
    sidecar.write_text(json.dumps(meta), encoding="utf-8")

    result, status = load(options)
    assert status == "miss:identity"
    assert len(calls) == 1 and calls[0][0] == {A}
    pd.testing.assert_frame_equal(result[A], frame)
    # Failed authentication also forbids merging unrequested cached symbols.
    assert set(bars.read_minute_cache(path)) == {A}


@pytest.mark.parametrize("metadata", [None, "{broken", "[]", '{"start":"20260901","end":"20260902"}'])
def test_missing_malformed_or_legacy_sidecar_fails_closed(case, metadata):
    options, frame, _ = case
    path = bars.write_minute_cache({A: frame}, START, END, **options)
    sidecar = path.with_suffix(".json")
    if metadata is None:
        sidecar.unlink()
    else:
        sidecar.write_text(metadata, encoding="utf-8")
    assert load(options)[1] == "miss:identity"


def test_old_window_only_path_is_never_reused(case):
    options, frame, calls = case
    path = bars.write_minute_cache({A: frame}, START, END, **options)
    legacy = path.parent / f"minute_none_{START}_{END}.parquet"
    path.rename(legacy)
    path.with_suffix(".json").unlink()
    legacy.with_suffix(".json").write_text(json.dumps({"start": START, "end": END}), encoding="utf-8")
    before = legacy.read_bytes()
    assert load(options)[1] == "miss"
    assert len(calls) == 1 and legacy.read_bytes() == before


def test_no_cache_rebuild_and_volume_amount_bypass(case, monkeypatch):
    options, _, calls = case
    load(options)
    assert load(options, rebuild_cache=True)[1] == "rebuild"
    assert len(calls) == 2

    def forbidden(*a, **kw):
        pytest.fail("bypass must not build a cache identity")

    monkeypatch.setattr(bars, "minute_cache_identity", forbidden)
    assert load(options, use_cache=False)[1] == "off"
    assert load(options, include_volume=True)[1] == "off:volume_required"
    assert load(options, include_amount=True)[1] == "off:volume_required"
    assert calls[-1][1]["include_amount"] is True


def test_default_snapshot_is_shallow_deterministic_and_detects_metadata(tmp_path):
    root = tmp_path / "lake"
    root.mkdir()
    partition = root / "symbol=600000_SH"
    partition.mkdir()
    def identity():
        return bars.minute_cache_identity(START, END, lake_root=root)
    first = identity()
    assert identity() == first
    stat = partition.stat()
    os.utime(partition, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))
    assert identity()["source_snapshot"] != first["source_snapshot"]
    second = identity()
    (root / "symbol=600001_SH").mkdir()
    assert identity()["source_snapshot"] != second["source_snapshot"]


def test_resolver_root_is_pinned_for_fill(case, monkeypatch):
    options, _, calls = case
    period = options["lake_root"]
    (period / "dividend_type=none").mkdir()
    monkeypatch.setattr("common.infra.data_root.resolve_period_root", lambda _: period)
    options.pop("lake_root")
    load(options)
    assert calls[-1][1]["lake_root"] == (period / "dividend_type=none").resolve()


def test_missing_source_fails_even_with_snapshot(tmp_path):
    with pytest.raises(FileNotFoundError):
        bars.minute_cache_identity(START, END, lake_root=tmp_path / "missing", source_snapshot="a")
