"""X-04 review regressions at the production lake-reader boundary."""

from datetime import date

import pandas as pd
import pytest
from backtest.research import ashare_bars
from backtest.research import csv_minute_backtest as minute
from backtest.research import csv_minute_backtest_v7 as v7
from backtest.research.tail_window_buy import TAIL_MINUTES
from oskh_data.symbol_format import to_partition_key

SYMBOL = "600000.SH"
START, END = "20260901", "20260902"


def _write_lake(root, timestamps, prices, volumes, *, has_amount=True):
    frame = pd.DataFrame({
        "time": [pd.Timestamp(stamp, tz="UTC").value // 1_000_000 for stamp in timestamps],
        **{column: prices for column in ("open", "high", "low", "close")},
        "volume": volumes,
    })
    if has_amount:
        frame["amount"] = frame["close"] * frame["volume"]
    directory = root / f"symbol={to_partition_key(SYMBOL)}"
    directory.mkdir(parents=True)
    frame.to_parquet(directory / "data.parquet", index=False)


@pytest.mark.parametrize("has_amount", [False, True])
@pytest.mark.parametrize("via_loader", [False, True])
def test_tail_and_off_both_drop_grok_zero_day_but_v11_preserves_it(tmp_path, has_amount, via_loader):
    # Grok: 09-01 14:55 is 10 yuan / 10,000 shares; 09-02 is 8 yuan / 0 shares.
    _write_lake(tmp_path, ["2026-09-01 14:55", "2026-09-02 14:55"],
                [10.0, 8.0], [10_000.0, 0.0], has_amount=has_amount)

    def read(**options):
        if via_loader:
            return ashare_bars.load_minute_ohlc(
                [SYMBOL], START, END, workers=1, use_cache=False,
                lake_root=tmp_path, **options,
            )[SYMBOL]
        return ashare_bars.read_lake_minute_ohlc(SYMBOL, tmp_path, START, END, **options)

    off = read()
    on = read(include_amount=True)
    v11 = read(include_volume=True)
    assert list(zip(off["ymd"], off["hm"])) == [(START, 895)]
    # These are the exact frames passed to sell scanning; the zero day must be absent.
    assert list(zip(on["ymd"], on["hm"])) == [(START, 895)]
    pd.testing.assert_frame_equal(on[off.columns], off)
    assert on["volume"].tolist() == [10_000]
    assert ("amount" in on) is has_amount
    assert list(zip(v11["ymd"], v11["hm"], v11["volume"])) == [
        (START, 895, 10_000), (END, 895, 0),
    ]
    assert "_tail_duplicate" not in off and "_tail_duplicate" not in v11


@pytest.mark.parametrize("second_stamp", ["2026-09-01 14:55", "2026-09-01 14:55:30"])
def test_tail_marks_duplicate_minute_before_legacy_keep_last(tmp_path, second_stamp):
    _write_lake(tmp_path, ["2026-09-01 14:55", second_stamp, "2026-09-01 15:00"],
                [10.0, 10.1, 10.0], [10_000] * 3)
    off = ashare_bars.read_lake_minute_ohlc(SYMBOL, tmp_path, START, START)
    on = ashare_bars.read_lake_minute_ohlc(SYMBOL, tmp_path, START, START, include_amount=True)
    pd.testing.assert_frame_equal(on[off.columns], off)
    duplicate = on.loc[on["hm"] == 895]
    assert duplicate["_tail_duplicate"].all()
    assert not on.loc[on["hm"] == 900, "_tail_duplicate"].any()
    if second_stamp == "2026-09-01 14:55":
        assert duplicate["close"].tolist() == [10.1]
    assert "_tail_duplicate" not in off


@pytest.mark.parametrize("engine", ["shared", "v7"])
@pytest.mark.parametrize("duplicate_hm", [870, 875, 900])
def test_duplicate_lake_minute_cannot_fill_tail_child(tmp_path, engine, duplicate_hm):
    clocks = [*TAIL_MINUTES, duplicate_hm]
    timestamps = [f"2026-09-01 {hm // 60:02d}:{hm % 60:02d}" for hm in clocks]
    _write_lake(tmp_path, timestamps, [10.0] * len(clocks), [10_000] * len(clocks))
    frames = ashare_bars.load_minute_ohlc(
        [SYMBOL], START, START, lake_root=tmp_path, workers=1, include_amount=True,
    )
    on = {"tail_window_buy": True, "fix_minute_cash_order": True, "tail_volume_unit": "shares"}
    expected = [] if duplicate_hm == 870 else [hm for hm in TAIL_MINUTES if hm != duplicate_hm]
    if engine == "shared":
        daily = {SYMBOL: pd.DataFrame(
            {column: [10.0, 10.0] for column in ("open", "high", "low", "close")},
            index=pd.to_datetime(["20260831", START]),
        )}
        audit = []
        state = minute.simulate(
            frames, daily, {START: [SYMBOL]}, START, START, strategy="version8",
            total_cash=1_000_000, name_budget=28_000, audit_sink=audit,
            buy_cost_rate=0, sell_cost_rate=0, min_cost=0, **on,
        )
        assert [row["hm"] for row in audit if row["side"] == "BUY"] == expected
        assert sum(row["shares"] for row in state.trades if row["side"] == "BUY") == len(expected) * 100
    else:
        day = date(2026, 9, 1)
        state = v7.simulate_v7(
            frames, {SYMBOL: {date(2026, 8, 31): 10.0}}, {day: [SYMBOL]}, [day], **on,
        )
        fills = [row for row in state.trades if row["side"] == "buy"]
        assert [row["hm"] for row in fills] == expected
        assert sum(row["shares"] for row in fills) == len(expected) * 700
