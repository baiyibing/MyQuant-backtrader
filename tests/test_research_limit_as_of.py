"""Data-free coverage of session-dated limits in the research exit paths."""
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from backtest.research import unified_exit_modea as a
from backtest.research import unified_exit_modeb as b
from backtest.research import unified_exit_precheck as precheck
from backtest.research import fullstrat_research_modeb as full

CODE = "600000.SH"
DAYS = ["20260702", "20260703", "20260706", "20260707"]


def inputs():
    inst = a.Instance(CODE, "ST测试", DAYS[0], 100., True)
    daily = {CODE: pd.DataFrame({"close": [100., 94., 88.36, 88.36],
                                 "open": [100., 94., 88.36, 88.36]},
                                index=pd.to_datetime(DAYS))}
    minute = {CODE: pd.DataFrame({"ymd": DAYS[1:], "hm": [900, 900, 570],
                                  "open": [94., 88.36, 88.36],
                                  "close": [94., 88.36, 88.36]})}
    return inst, daily, minute


def test_modea_assembly_and_exits_use_session(tmp_path):
    inst, daily, _ = inputs()
    (tmp_path / f"{DAYS[2]}.csv").write_text(f"code,name\n{CODE},ST测试\n")
    buy_bars = {CODE: pd.DataFrame({"close": [100., 106.]},
                                   index=pd.to_datetime(DAYS[1:3]))}
    assert a.assemble_instances(tmp_path, DAYS, buy_bars)[0].opened
    assert not a._is_limit_up(106., 100., CODE, inst.name, as_of=DAYS[2])
    got = a.evaluate_exit(inst, a.StrategySpec(1, 1), daily, DAYS, end=DAYS[-1])
    assert got.sell_date == DAYS[2] and got.is_trade
    oracle = a.oracle_exits([inst], daily, DAYS, end=DAYS[-1])
    assert oracle[a.instance_key(inst)].sell_date == DAYS[2]


@pytest.mark.parametrize("impl", ["fast", "ref", "matrix", "oracle", "path_oracle", "full"])
def test_modeb_crosses_st_switch(impl):
    inst, daily, minute = inputs()
    spec = a.StrategySpec(1, 1)
    if impl in {"fast", "ref"}:
        got = b.evaluate_exit_modeb(inst, spec, daily, minute, DAYS, end=DAYS[-1], impl=impl)
    elif impl == "matrix":
        got = b.evaluate_matrix([inst], [spec], daily, minute, DAYS, end=DAYS[-1])[spec.label()][a.instance_key(inst)]
    elif impl == "oracle":
        got = b.oracle_exits([inst], daily, minute, DAYS, end=DAYS[-1])[a.instance_key(inst)]
    elif impl == "path_oracle":
        prepared = a._prepare_bars(daily)
        path = b._instance_path(inst, b._prepare_minutes(minute), DAYS,
                                b._previous_refs(prepared, CODE, None), end=DAYS[-1], exdiv=None)
        got = b._oracle_from_path(inst, path, tol=a.DEFAULT_TOL)
    else:
        # A post-switch stop can fill at the next minute open that session.
        from backtest.research.fullstrat_research_hooks import NEXT_OPEN
        from backtest.research.fullstrat_research_hooks import ResearchFillConfig
        minute[CODE]["hm"] = 600
        extra = minute[CODE].iloc[[1]].copy()
        extra["hm"] = 601
        minute[CODE] = pd.concat([minute[CODE], extra], ignore_index=True)
        spec = a.StrategySpec(2, 8, None, 5)
        audit = []
        got = full.evaluate_exit(inst, spec, a._prepare_bars(daily), b._prepare_minutes(minute), DAYS,
                                 config=ResearchFillConfig(NEXT_OPEN), end=DAYS[-1],
                                 tol=a.DEFAULT_TOL, exdiv={}, index_block={}, audit=audit)
        assert got.sell_date == DAYS[2] and got.is_trade
        return
    assert got.sell_date == DAYS[2] and got.is_trade


def test_path_limits_empty_and_unknown_board():
    inst = SimpleNamespace(symbol="UNKNOWN", name="")
    assert b._path_limit_pct(inst, SimpleNamespace(ymd=[])).size == 0
    lp = b._path_limit_pct(inst, SimpleNamespace(ymd=DAYS))
    assert not b._ld_mask(np.ones(4), np.ones(4), lp, a.DEFAULT_TOL).any()


def test_precheck_uses_pool_session(tmp_path, monkeypatch):
    frame = pd.DataFrame({"close": [100., 106.]}, index=pd.to_datetime(DAYS[1:3]))
    monkeypatch.setattr(precheck, "_read_one_daily", lambda *args: frame)
    got = precheck._limit_boundary({DAYS[2]: [(CODE, "ST测试")]}, [CODE], tmp_path,
                                   DAYS[1], DAYS[2], a.DEFAULT_TOL, 1)
    assert got == {}
