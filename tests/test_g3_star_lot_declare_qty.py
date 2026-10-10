"""G3 declaration/fill/residual counterexamples; synthetic data only."""
from dataclasses import asdict
from datetime import date
import hashlib
import json

import pandas as pd
import pytest

from backtest.research import csv_ledger as ledger
from backtest.research.ashare_volume_cap import BucketVolume, VolumeCap
from backtest.research.minute_audit import audit_scope

DAY = date(2026, 9, 1)
CODE = "688001.SH"


def buy(st, qty, *, code=CODE, override=True, **kwargs):
    return ledger.execute_buy(st, code, 10., qty * 10., 0, DAY,
                              shares_override=qty if override else None, **kwargs)


@pytest.mark.parametrize("code", [CODE, "689001.SH", "SH688001", "688001"])
@pytest.mark.parametrize("override", [False, True])
@pytest.mark.parametrize("qty", [0, 1, 100, 199, 200, 201, 250])
def test_star_declare_boundaries(code, override, qty):
    st = ledger.SimState(star_lot_declare_check=True)
    cash = st.cash
    events = []
    with audit_scope(events, decision_hm=895, phase="test"):
        accepted = buy(st, qty, code=code, override=override)
    assert accepted == (qty >= 200)
    if accepted:
        assert st.trades[0]["shares"] == qty
        assert st.positions[code][0].shares == qty
        assert st.stats["supplementary_used"] == 0
    else:
        assert st.cash == cash
        assert st.daily_quota_used == 0
        assert not st.positions and not st.trades
        assert st.stats["skip_star_buy_declare_qty"] == 1
        assert events[0]["reason"] == "skip_star_buy_declare_qty"


@pytest.mark.parametrize("qty", [True, 199.5, "201"])
def test_override_retains_integer_validation(qty):
    st = ledger.SimState(star_lot_declare_check=True)
    with pytest.raises(ValueError, match="integer share count"):
        ledger.execute_buy(st, CODE, 10., 3000., 0, DAY, shares_override=qty)


@pytest.mark.parametrize("code", ["600000.SH", "300001.SZ", "920001.BJ"])
@pytest.mark.parametrize("override", [False, True])
def test_non_star_keeps_floor_100(code, override):
    st = ledger.SimState(star_lot_declare_check=True)
    assert buy(st, 199, code=code, override=override)
    assert st.trades[0]["shares"] == 100


def test_partial_fill_is_not_declaration_and_residual_cannot_be_redeclared():
    key = (CODE, "20260901", 895)
    st = ledger.SimState(star_lot_declare_check=True,
                         volume_cap=VolumeCap(1, {key: BucketVolume(100, 895, "raw_shares_incremental")}))
    assert buy(st, 201, bucket_id=895)
    assert st.trades[0]["shares"] == 100  # Legal partial fill of accepted 201.
    assert st.volume_cap.used == {key: 100}
    cash = st.cash
    pos = st.positions[CODE][0]
    # Even a same-day merge retry cannot treat residual 101 as a legal order.
    assert not buy(st, 101, bucket_id=896, merge_lot=pos)
    assert st.stats["skip_star_buy_declare_qty"] == 1
    assert st.cash == cash and pos.shares == 100
    assert st.volume_cap.used == {key: 100}
    assert len(st.trades) == 1


@pytest.mark.parametrize("qty", [1, 101, 199, 201])
def test_held_odd_lot_sell_unwind_is_unchanged(qty):
    pos = ledger.Position(CODE, qty, 10., 0, 10.)
    st = ledger.SimState(star_lot_declare_check=True, positions={CODE: [pos]})
    assert ledger._sell(st, CODE, pos, 10., date(2026, 9, 2), "force_sell", day_i=1) == qty
    assert st.trades[0]["shares"] == qty
    assert not st.positions


def snapshot(st):
    return json.dumps({"cash": st.cash, "positions": {c: [asdict(p) for p in ps]
                       for c, ps in st.positions.items()}, "trades": st.trades,
                       "stats": st.stats, "daily_quota_used": st.daily_quota_used,
                       "supplementary_used": st.supplementary_used}, sort_keys=True).encode()


def test_off_matches_frozen_base_bytes():
    # Frozen SHA-256 of snapshot(SimState()) after the matrix below, generated
    # with pre-G3 backtest/research/csv_ledger.py at
    # 3f1586f77e94a31ba0c4b86d5c03ff13f332d382. Never regenerate from G3 code:
    # this golden preserves the legacy floor-100 behavior without Git history.
    expected_sha256 = "512fadfbc8a768bdfbe63084126708e6f21a9ec2e9372d41464a3c9b8b387758"
    states = [ledger.SimState(), ledger.SimState(star_lot_declare_check=False)]
    for st in states:
        for qty in [1, 100, 199, 200, 201, 250]:
            for override in [None, qty]:
                ledger.execute_buy(st, CODE, 10., qty * 10., 0, DAY, shares_override=override)
        assert hashlib.sha256(snapshot(st)).hexdigest() == expected_sha256
        assert [t["shares"] for t in st.trades] == [100] * 5 + [200] * 6
    assert snapshot(states[0]) == snapshot(states[1])


@pytest.mark.parametrize("engine", ["daily", "minute"])
@pytest.mark.parametrize("enabled,quota,expected", [
    (False, 1500., 100), (True, 1500., 0),
    (True, 2000., 200), (True, 2010., 201), (True, 2500., 250),
])
def test_shared_simulate_wiring(engine, enabled, quota, expected):
    from backtest.research import csv_daily_backtest as daily
    from backtest.research import csv_minute_backtest as minute
    days = pd.to_datetime(["2026-08-31", "2026-09-01"])
    ds = {CODE: pd.DataFrame({c: [10., 10.] for c in ["open", "high", "low", "close"]}, index=days)}
    ms = {CODE: pd.DataFrame({"open": [10.], "high": [10.], "low": [10.], "close": [10.],
                             "ymd": ["20260901"], "hm": [895]}, index=pd.to_datetime(["2026-09-01 14:55"]))}
    args = (ds,) if engine == "daily" else (ms, ds)
    fn = daily.simulate if engine == "daily" else minute.simulate
    st = fn(*args, {"20260901": [CODE]}, "20260901", "20260901", strategy="version6",
            daily_quota=quota, star_lot_declare_check=enabled, rule_profile="legacy")
    buys = [t for t in st.trades if t["side"] == "BUY"]
    assert sum(t["shares"] for t in buys) == expected
    if enabled:
        assert st.stats.get("skip_star_buy_declare_qty", 0) == (1 if expected == 0 else 0)
        if expected >= 200:
            assert buys
            # No volume cap here: each fill is the full declaration.
            assert all(t["shares"] >= 200 for t in buys)
