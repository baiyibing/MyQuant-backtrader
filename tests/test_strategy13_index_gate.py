import pandas as pd
import pytest
from backtest.research import strategy13_rules as rules, strategy13_engine as engine
from backtest.research.strategy_book_helpers import load_book_index_gate
from tests.test_strategy13_book import state, open_base, CODE, DAY


def test_gate_prior_session_dual_caps_and_loader_dispatch(monkeypatch):
    days = pd.bdate_range("20250101", periods=124).date
    closes = dict(zip(days, [100.]*120+[90., 200., 90., 1.]))
    caps = rules.build_index_caps(closes)
    assert caps[days[120]] == 1
    assert caps[days[121]] == .3
    assert caps[days[122]] == 1
    changed = dict(closes)
    changed[days[121]] = 1
    assert rules.build_index_caps(changed)[days[121]] == caps[days[121]]
    monkeypatch.setattr(rules, "load_sse_ma10_block_new", lambda *a: caps)
    assert load_book_index_gate("version13", "20260101", "20260201") is caps


def test_ma60_only_half_cap():
    days = pd.bdate_range("20250101", periods=121).date
    closes = dict(zip(days, [50.]*60 + [100.]*59 + [90., 90.]))
    assert rules.build_index_caps(closes)[days[-1]] == .5


def test_gate_blocks_opens_and_adds_without_forced_sell():
    st, h = state(1e6, index_block_new={DAY.date(): .3})
    assert open_base(st, h)
    st.book_state["beidou_marks"] = {CODE: 16}
    st.cash = 50000  # force total exposure above 30%
    before = sum(p.shares for p in st.positions[CODE])
    assert not engine.buy(st, CODE, 16, [15]*120, hooks=h, day_i=1, day=DAY,
                          ds="20260105", names={}, exdiv=None, adding=True)
    assert sum(p.shares for p in st.positions[CODE]) == before
    assert not [t for t in st.trades if t["side"] == "SELL"]
    h["beidou_index_gate"] = {}
    with pytest.raises(ValueError, match="missing HS300"):
        engine.buy(st, CODE, 16, [15]*120, hooks=h, day_i=1, day=DAY,
                   ds="20260105", names={}, exdiv=None, adding=True)


def test_gate_requires_warmup_and_partition(tmp_path):
    with pytest.raises(ValueError, match="120 preload"):
        rules.build_index_caps({DAY.date(): 10})
    with pytest.raises(FileNotFoundError, match="HS300"):
        rules.load_sse_ma10_block_new("20260101", "20260201", root=tmp_path)


def test_gate_blocks_a_new_name_after_portfolio_cap():
    st, h = state(100000, index_block_new={DAY.date(): .3})
    for code in ("600000.SH", "600001.SH"):
        assert engine.buy(st, code, 10, [10]*120, hooks=h, day_i=0, day=DAY,
                          ds="20260105", names={}, exdiv=None)
    assert not engine.buy(st, "600002.SH", 10, [10]*120, hooks=h, day_i=0, day=DAY,
                          ds="20260105", names={}, exdiv=None)
    assert len(st.positions) == 2
    assert not [t for t in st.trades if t["side"] == "SELL"]
