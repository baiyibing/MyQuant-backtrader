"""Process-local bar reuse and minute day-span sidecars."""

from __future__ import annotations

import json

import pandas as pd
import pytest

from backtest.research import ashare_bars as bars
from backtest.research import bar_store as store


START, END = "20260901", "20260902"
A, B = "600000.SH", "600001.SH"


@pytest.fixture(autouse=True)
def _clear_mem():
    store.mem_clear()
    yield
    store.mem_clear()


def _minute_frame():
    return bars.annotate_session(
        pd.DataFrame(
            {key: [10.0] for key in ("open", "high", "low", "close")},
            index=pd.to_datetime(["2026-09-01 09:30"]).as_unit("ns"),
        )
    ).astype({"hm": "int64"})


def test_build_day_spans_two_sessions_and_rejects_unsorted():
    frame = pd.DataFrame(
        {
            "ymd": ["20251103", "20251103", "20251104"],
            "close": [10.0, 10.1, 9.4],
        }
    )
    spans = store.build_day_spans(frame)
    assert spans == {"20251103": (0, 2), "20251104": (2, 3)}
    shuffled = frame.iloc[[2, 0, 1]].reset_index(drop=True)
    assert store.build_day_spans(shuffled) == {}


def test_span_sidecar_roundtrip_and_fingerprint_fail_closed(tmp_path):
    frame = _minute_frame()
    identity = {
        "start": START,
        "end": END,
        "resolver_identity": "lake",
        "source_snapshot": "snap-a",
    }
    cache = tmp_path / "minute_none_x.parquet"
    path = store.write_span_sidecar(cache, identity, {A: frame})
    assert path.name.endswith(".spans.json")
    hit = store.read_span_sidecar(cache, identity, {A: frame})
    assert hit is not None
    assert hit[A]["20260901"] == (0, 1)

    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["fingerprints"][A][0] = 99
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert store.read_span_sidecar(cache, identity, {A: frame}) is None


def test_resolve_day_spans_uses_mem_then_sidecar(tmp_path, monkeypatch):
    frame = _minute_frame()
    identity = {
        "start": START,
        "end": END,
        "resolver_identity": "lake",
        "source_snapshot": "snap-a",
    }
    cache = tmp_path / "minute_none_x.parquet"
    key = store.mem_key("minute", identity)
    first = store.resolve_day_spans({A: frame}, identity=identity, cache_path=cache, mem_id=key)
    builds = {"n": 0}
    original = store.build_day_spans_map

    def counted(bars_map):
        builds["n"] += 1
        return original(bars_map)

    monkeypatch.setattr(store, "build_day_spans_map", counted)
    again = store.resolve_day_spans({A: frame}, identity=identity, cache_path=cache, mem_id=key)
    assert builds["n"] == 0
    assert again[A] == first[A]

    store.mem_clear()
    from_file = store.resolve_day_spans({A: frame}, identity=identity, cache_path=cache, mem_id=key)
    assert builds["n"] == 0
    assert from_file[A] == first[A]


def test_minute_second_load_is_mem(tmp_path, monkeypatch):
    monkeypatch.delenv("OSKH_BAR_MEM", raising=False)
    root = tmp_path / "lake"
    root.mkdir()
    cache = tmp_path / "cache"
    frame = _minute_frame()
    calls = []

    def load(codes, start, end, **kwargs):
        calls.append(set(codes))
        return {code: frame.copy() for code in codes}

    monkeypatch.setattr(bars, "load_minute_from_lake", load)
    options = dict(lake_root=root, cache_dir=cache, source_snapshot="snapshot-a")
    status = {}
    first = bars.load_minute_ohlc({A}, START, END, status=status, **options)
    assert status["cache"] == "miss"
    assert "20260901" in status["day_spans"][A]
    assert store.span_sidecar_path(bars.minute_cache_path(START, END, **options)).is_file()

    status = {}
    second = bars.load_minute_ohlc({A}, START, END, status=status, **options)
    assert status["cache"] == "mem"
    assert len(calls) == 1
    pd.testing.assert_frame_equal(first[A], second[A])
    assert status["day_spans"][A]["20260901"] == (0, 1)


def test_minute_partial_does_not_claim_mem_for_missing_code(tmp_path, monkeypatch):
    monkeypatch.delenv("OSKH_BAR_MEM", raising=False)
    root = tmp_path / "lake"
    root.mkdir()
    cache = tmp_path / "cache"
    frame = _minute_frame()
    calls = []

    def load(codes, start, end, **kwargs):
        calls.append(set(codes))
        return {code: frame.copy() for code in codes}

    monkeypatch.setattr(bars, "load_minute_from_lake", load)
    options = dict(lake_root=root, cache_dir=cache, source_snapshot="snapshot-a")
    bars.load_minute_ohlc({A}, START, END, status={}, **options)
    status = {}
    bars.load_minute_ohlc({B}, START, END, status=status, **options)
    assert status["cache"] == "partial"
    assert calls[-1] == {B}


def test_simulate_reuses_passed_day_spans(monkeypatch):
    from backtest.research import csv_minute_backtest as sim

    idx = pd.to_datetime(["2025-11-03 09:30", "2025-11-03 14:55"]).as_unit("ns")
    minute = pd.DataFrame(
        {
            "open": [10.0, 10.0],
            "high": [10.1, 10.05],
            "low": [9.9, 9.98],
            "close": [10.0, 10.0],
            "ymd": ["20251103", "20251103"],
            "hm": [570, 895],
        },
        index=idx,
    )
    daily = pd.DataFrame(
        {"open": [10.0], "high": [10.1], "low": [9.9], "close": [10.0]},
        index=pd.to_datetime(["2025-11-03"]),
    )
    spans = {A: store.build_day_spans(minute)}

    def boom(df):
        raise AssertionError("simulate must reuse passed day_spans")

    monkeypatch.setattr(sim, "build_day_spans", boom)
    st = sim.simulate(
        {A: minute},
        {A: daily},
        {},
        "20251103",
        "20251103",
        strategy="version6",
        total_cash=100_000.0,
        name_budget=10_000.0,
        day_spans=spans,
    )
    assert st.equity_curve
