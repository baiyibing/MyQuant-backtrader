"""G3 declaration/fill/residual counterexamples; synthetic data only."""
from dataclasses import asdict
from datetime import date
import importlib.util
import json
from pathlib import Path
import subprocess

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


def test_off_matches_frozen_base_bytes(tmp_path, monkeypatch):
    # Compare actual baseline code, not a second invocation of the new branch.
    base = "3f1586f77e94a31ba0c4b86d5c03ff13f332d382"
    root = Path(__file__).resolve().parents[1]
    source = subprocess.check_output(["git", "show", f"{base}:backtest/research/csv_ledger.py"], cwd=root)
    path = tmp_path / "g3_base_ledger.py"
    path.write_bytes(source)
    spec = importlib.util.spec_from_file_location("g3_base_ledger", path)
    old = importlib.util.module_from_spec(spec)
    import sys
    monkeypatch.setitem(sys.modules, spec.name, old)
    spec.loader.exec_module(old)
    states = [old.SimState(), ledger.SimState(), ledger.SimState(star_lot_declare_check=False)]
    for module, st in zip([old, ledger, ledger], states):
        for qty in [1, 100, 199, 200, 201, 250]:
            for override in [None, qty]:
                module.execute_buy(st, CODE, 10., qty * 10., 0, DAY, shares_override=override)
    assert snapshot(states[0]) == snapshot(states[1]) == snapshot(states[2])
    assert states[1].trades[0]["shares"] == 100


@pytest.mark.parametrize("engine", ["daily", "minute"])
@pytest.mark.parametrize("enabled,expected", [(False, 100), (True, 0)])
def test_shared_simulate_wiring(engine, enabled, expected):
    from backtest.research import csv_daily_backtest as daily
    from backtest.research import csv_minute_backtest as minute
    days = pd.to_datetime(["2026-08-31", "2026-09-01"])
    ds = {CODE: pd.DataFrame({c: [10., 10.] for c in ["open", "high", "low", "close"]}, index=days)}
    ms = {CODE: pd.DataFrame({"open": [10.], "high": [10.], "low": [10.], "close": [10.],
                             "ymd": ["20260901"], "hm": [895]}, index=pd.to_datetime(["2026-09-01 14:55"]))}
    args = (ds,) if engine == "daily" else (ms, ds)
    fn = daily.simulate if engine == "daily" else minute.simulate
    st = fn(*args, {"20260901": [CODE]}, "20260901", "20260901", strategy="version6",
            daily_quota=1500., star_lot_declare_check=enabled)
    assert sum(t["shares"] for t in st.trades if t["side"] == "BUY") == expected
    if enabled:
        assert st.stats["skip_star_buy_declare_qty"] == 1
