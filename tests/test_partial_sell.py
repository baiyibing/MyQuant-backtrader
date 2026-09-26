"""S1 share/cash conservation and untouched-book output fingerprints."""

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from backtest.research.csv_ledger import Position, SimState, _sell, execute_buy
from backtest.research.ashare_volume_cap import BucketVolume, VolumeCap

CODE = "600000.SH"
BASELINE = Path(__file__).parent / "fixtures/strategy12_default_outputs.json"
BASELINE_SHA256 = "2f578d6fe9e601ad84a94bb6a269e1b5193c51ca4dd908366022769f0e1f31c2"
S8_BASELINE = Path(__file__).parent / "fixtures/strategy12_default_outputs_s8_independent_20260926.json"
S8_BASELINE_BOOKS = ("version8", "version8_2", "version8_3")
LEGACY_BOOKS = ("version1", "version2", "version3", "version4", "version5",
                "version6", "version8", "version8_1", "version8_2", "version8_3",
                "version9", "version10")


def legacy_outputs(books=LEGACY_BOOKS):
    from backtest.research.csv_daily_backtest import simulate as daily
    from backtest.research.csv_minute_backtest import simulate as minute

    dates = pd.bdate_range("2025-10-13", periods=25)
    closes = [10.] * 12 + [10, 10.5, 10.9, 11, 10.6, 9.9, 9.1, 9.6, 10.3, 10, 9.8, 10.3, 10.1]
    bars = pd.DataFrame({"open": closes, "high": [v * 1.02 for v in closes],
                         "low": [v * .98 for v in closes], "close": closes}, index=dates)
    rows = []
    for day, px in zip(dates, closes):
        for hm, mult in ((570, .99), (585, 1.), (870, 1.01), (895, 1.)):
            rows.append(dict(time=day + pd.Timedelta(minutes=hm), open=px * .99,
                             high=px * 1.02, close=px * mult, ymd=day.strftime("%Y%m%d"), hm=hm))
    mins = pd.DataFrame(rows).set_index("time")
    start, end = dates[12].strftime("%Y%m%d"), dates[-1].strftime("%Y%m%d")
    pool = {dates[j].strftime("%Y%m%d"): [CODE] for j in (12, 14, 18)}
    out = {}
    for book in books:
        for engine, run in (("daily", lambda: daily({CODE: bars}, pool, start, end, strategy=book)),
                            ("minute", lambda: minute({CODE: mins}, {CODE: bars}, pool, start, end, strategy=book))):
            st = run()
            out[f"{book}/{engine}"] = {
                # Golden bytes are LF-pinned: pandas to_csv defaults to
                # os.linesep, which made the fixture platform-dependent.
                name: hashlib.sha256(pd.DataFrame(value).to_csv(index=False, lineterminator="\n").encode("utf-8")).hexdigest()
                for name, value in (("trades", st.trades), ("equity", st.equity_curve))
            }
    return out


def test_default_trades_and_equity_byte_identical_to_pre_s1_head():
    """Keep all 18 untouched cases; only six authorized S8 cases use the overlay."""
    assert hashlib.sha256(BASELINE.read_bytes()).hexdigest() == BASELINE_SHA256
    expected = json.loads(BASELINE.read_text(encoding="utf-8"))
    assert expected["source"] == "9fa8b27 (before slice B ledger/engine changes)"
    correction = json.loads(S8_BASELINE.read_text(encoding="utf-8"))
    assert correction["rule_revision"] == "s8-independent-positions-2026-09-26"
    assert correction["historical_sha256"] == BASELINE_SHA256
    corrected_cases = correction["sha256_csv_bytes"]
    assert set(corrected_cases) == {
        f"{book}/{engine}" for book in S8_BASELINE_BOOKS for engine in ("daily", "minute")
    }
    assert len(corrected_cases) == 6
    assert len(set(expected["sha256_csv_bytes"]) - set(corrected_cases)) == 18
    assert legacy_outputs() == {**expected["sha256_csv_bytes"], **corrected_cases}


@pytest.mark.parametrize("capacity", [None, 150])
def test_s1_partial_sell_conserves_cash_and_nonzero_lot(capacity):
    pos = Position(CODE, 1000, 10, 0, 10)
    st = SimState(cash=1000, positions={CODE: [pos]}, sell_cost_rate=.001)
    if capacity is not None:
        st.volume_cap = VolumeCap(1, {(CODE, "20251104", 600): BucketVolume(capacity, 600, "raw_shares_incremental")})
    filled = _sell(st, CODE, pos, 10, "20251104", "ma_signal:MA5-derisk", wanted_shares=500, day_i=1, bucket_id=600)
    expected = 500 if capacity is None else capacity
    assert filled == expected
    assert st.positions[CODE] == [pos]
    assert pos.shares == 1000 - expected
    assert sum(p.shares for p in st.positions[CODE]) + filled == 1000
    assert st.cash == pytest.approx(1000 + expected * 10 * .999)
    assert st.cash + pos.shares * 10 + st.trades[-1]["commission"] == pytest.approx(11000)


def test_s1_deletes_only_empty_and_t1_blocks_override():
    pos = Position(CODE, 150, 10, 1, 10)
    st = SimState(positions={CODE: [pos]})
    assert _sell(st, CODE, pos, 10, "20251104", "ma_signal:x", wanted_shares=100, day_i=1) == 0
    assert not st.trades
    assert _sell(st, CODE, pos, 10, "20251105", "ma_signal:x", wanted_shares=100, day_i=2) == 100
    assert pos.shares == 50 and st.positions[CODE] == [pos]
    assert _sell(st, CODE, pos, 10, "20251105", "ma_signal:x", wanted_shares=50, day_i=2) == 50
    assert pos.shares == 0 and CODE not in st.positions


@pytest.mark.parametrize("capacity", [None, 150])
def test_buy_override_records_actual_notional_without_supplement(capacity):
    st = SimState(cash=10000)
    if capacity is not None:
        st.volume_cap = VolumeCap(1, {(CODE, "20251104", 600): BucketVolume(capacity, 600, "raw_shares_incremental")})
    assert execute_buy(st, CODE, 10, 1, 1, "20251104", shares_override=300, bucket_id=600)
    shares = 300 if capacity is None else 100
    assert st.positions[CODE][0].shares == shares
    assert st.daily_quota_used == st.stats["invested_notional"] == shares * 10
    assert st.stats["supplementary_used"] == 0
    assert st.cash == pytest.approx(10000 - shares * 10 * 1.001)


def test_buy_override_never_force_min_or_overdraw():
    st = SimState(cash=1000)
    assert not execute_buy(st, CODE, 10, 1_000_000, 0, "20251104", shares_override=50)
    assert not execute_buy(st, CODE, 10, 1, 0, "20251104", shares_override=100)
    assert st.cash == 1000 and not st.trades


def test_partial_sell_deducts_locked_bonus_before_wanted_cap():
    from backtest.research.ashare_exdiv_economics import ExDivEconomics

    pos = Position(CODE, 1200, 10, 0, 10)
    st = SimState(positions={CODE: [pos]}, exdiv_economics=ExDivEconomics({}))
    st.exdiv_economics.bonus_locks[id(pos)] = {"20251105": 200}
    assert _sell(st, CODE, pos, 10, "20251104", "ma_signal:x", wanted_shares=500, day_i=1) == 500
    assert pos.shares == 700
    assert st.exdiv_economics.bonus_locks[id(pos)] == {"20251105": 200}
    assert _sell(st, CODE, pos, 10, "20251104", "ma_signal:x", wanted_shares=700, day_i=1) == 500
    assert pos.shares == 200 and st.positions[CODE] == [pos]
