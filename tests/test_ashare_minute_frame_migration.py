"""Slice A human ruling: this fixture family has exactly seven migrations."""

from collections import Counter
from datetime import date
import hashlib

import pandas as pd
import pyarrow.parquet as pq
import pytest

from backtest.research import ashare_bars as bars
from backtest.research import csv_minute_backtest_v7 as v7
from backtest.research import csv_minute_backtest_topk_app_dropout as topk
from oskh_data.symbol_format import to_partition_key


SYMBOL = "600000.SH"  # Synthetic data only.
MISSING = "600001.SH"
D0, D1, D2 = date(2026, 8, 31), date(2026, 9, 1), date(2026, 9, 2)
POOLS = {D1: [SYMBOL]}
DAILY = {SYMBOL: {D0: 100.0, D1: 98.0}}
BUY_STOP = {"buy:trial": 1, "stop:trial_a090": 1}
BUY = {"buy:trial": 1}
SKIP = {"skip_no_1455": 1}


def row(day, clock, price, volume=100):
    stamp = pd.Timestamp(f"{day.isoformat()} {clock}", tz="UTC")
    return {"time": stamp.value // 1_000_000, "open": float(price),
            "high": float(price), "low": float(price), "close": float(price),
            "volume": volume}


def cases():
    # Identical row family to the pre-migration, out-of-repo parquet evidence.
    buy, sell = row(D1, "14:55", 100), row(D2, "09:30", 89)
    return {
        "clean": {"data.parquet": [buy, sell]},
        "01_out_of_session": {"data.parquet": [buy, row(D2, "09:00", 90), row(D2, "09:30", 100)]},
        "02_zero_volume_day": {"data.parquet": [row(D1, "14:55", 100, 0), sell]},
        "03_duplicate_timestamp": {"data.parquet": [buy, row(D1, "14:55", 102), sell]},
        "04_parts_only": {"part-0.parquet": [buy], "part-1.parquet": [sell]},
        "05_compact_output_without_low": {
            "data.parquet": [row(D1, "14:54", 100)], "part-0.parquet": [buy, sell],
        },
        "06_data_plus_part": {"data.parquet": [buy], "part-0.parquet": [sell]},
    }


# rows and complete reason/price vectors; null is a skip trade's price=None.
EXPECTED = {
    "clean": (2, 2, [100, 89], BUY_STOP, [100, 89]),
    "01_out_of_session": (3, 2, [100, 90], BUY, [100]),
    "02_zero_volume_day": (2, 1, [100, 89], SKIP, [None]),
    "03_duplicate_timestamp": (3, 2, [100, 89], BUY_STOP, [102, 89]),
    "04_parts_only": (2, 0, [100, 89], SKIP, [None]),
    "05_compact_output_without_low": (3, 1, [100, 89], SKIP, [None]),
    "06_data_plus_part": (2, 1, [100, 89], BUY, [100]),
}


def write_case(root, case):
    directory = root / "dividend_type=none" / f"symbol={to_partition_key(SYMBOL)}"
    directory.mkdir(parents=True)
    for filename, rows in cases()[case].items():
        pd.DataFrame(rows).to_parquet(directory / filename, index=False)
    paths = sorted(directory.glob("*.parquet"))
    assert all("low" in pq.read_schema(path).names for path in paths)
    return {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}


@pytest.mark.parametrize("case", EXPECTED)
def test_compact_to_book_matches_human_ruling(case, tmp_path, monkeypatch):
    hashes = write_case(tmp_path, case)
    monkeypatch.setattr("common.infra.data_root.resolve_period_root", lambda _: tmp_path)
    monkeypatch.setattr(bars, "load_daily_closes", lambda *a, **kw: DAILY)
    compact = bars._load_minute_compact([SYMBOL], D1, D2, workers=1)
    minute, daily = v7._load_cli_bars(POOLS, D1, D2)
    before = v7.simulate_v7(compact, DAILY, POOLS, [D1, D2])
    after = v7.simulate_v7(minute, daily, POOLS, [D1, D2])
    before_rows, after_rows, before_prices, after_reasons, after_prices = EXPECTED[case]
    assert sum(len(frame) for frame in compact.values()) == before_rows
    assert sum(len(frame) for frame in minute.values()) == after_rows
    assert "low" not in compact[SYMBOL].columns  # OUTPUT only; every source has low.
    assert Counter(t["reason"] for t in before.trades) == BUY_STOP
    assert [t["price"] for t in before.trades] == before_prices
    assert Counter(t["reason"] for t in after.trades) == after_reasons
    assert [t["price"] for t in after.trades] == after_prices
    assert hashes == {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in hashes}
    if case == "clean":
        assert after_rows > 0 and after.trades == before.trades
        assert topk._load_cli_bars is v7._load_cli_bars
        topk_minute, topk_daily = topk._load_cli_bars(POOLS, D1, D2)
        assert sum(len(frame) for frame in topk_minute.values()) > 0
        assert topk.simulate_v7(topk_minute, topk_daily, POOLS, [D1, D2]).trades == after.trades


@pytest.mark.parametrize("contract", ["ymd", "datetime_index", "compact_date"])
def test_day_records_materialize_only_requested_day(contract, monkeypatch):
    frame = pd.DataFrame({"close": [100, 89], "hm": [895, 570]},
                         index=pd.to_datetime(["2026-09-01 14:55", "2026-09-02 09:30"]))
    if contract == "ymd":
        frame["ymd"] = frame.index.strftime("%Y%m%d")
    elif contract == "compact_date":
        frame["date"] = frame.index.date
        frame = frame.reset_index(drop=True)
    original = pd.DataFrame.to_dict

    def bounded_records(self, *args, **kwargs):
        assert len(self) <= 1  # Never flatten the full two-day frame.
        return original(self, *args, **kwargs)

    monkeypatch.setattr(pd.DataFrame, "to_dict", bounded_records)
    assert [r["close"] for r in v7._day_frame_records(frame, D1)] == [100]
    assert [r["close"] for r in v7._day_frame_records(frame, D2)] == [89]
    assert v7._day_frame_records(frame, D0) == []


def test_pool_missing_symbol_never_materializes_shared_cache(tmp_path, monkeypatch):
    write_case(tmp_path / "lake", "clean")
    monkeypatch.setattr("common.infra.data_root.resolve_period_root", lambda _: tmp_path / "lake")
    monkeypatch.setattr(bars, "CACHE_ROOT", tmp_path / "cache")
    cache = bars.minute_cache_path("20260901", "20260902")
    cache.parent.mkdir()
    cache.write_bytes(b"sentinel shared cache; must not be read or overwritten")
    old_cache = cache.read_bytes()
    monkeypatch.setattr(bars, "load_daily_closes", lambda *a, **kw: DAILY)

    def forbidden(*args, **kwargs):
        pytest.fail("pool load must not read/merge/write the shared cache or use compact lake")

    for name in ("read_minute_cache", "write_minute_cache", "_load_minute_compact"):
        monkeypatch.setattr(bars, name, forbidden)
    load = bars.load_minute_ohlc
    calls = []

    def bounded_load(codes, start, end, **kwargs):
        assert set(codes) == {SYMBOL, MISSING}
        assert kwargs["use_cache"] is False
        result = load(codes, start, end, **kwargs)
        assert sum(len(frame) for frame in result.values()) <= 2
        calls.append((start, end))
        return result

    monkeypatch.setattr(bars, "load_minute_ohlc", bounded_load)
    minute, _ = v7._load_cli_bars({D1: [SYMBOL], D2: [SYMBOL, MISSING]}, D1, D2)
    assert calls == [("20260901", "20260902")]  # One window, not one loader per day.
    assert set(minute) == {SYMBOL} and len(minute[SYMBOL]) == 2
    assert cache.read_bytes() == old_cache
