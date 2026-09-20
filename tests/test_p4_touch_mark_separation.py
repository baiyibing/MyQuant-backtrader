"""Human GO P4=A closure (2026-09-20): touch eligibility != close/NAV mark.

P1 stays A and P2 stays B. Even a hypothetical future P1=C cannot answer P4:
marking requires its own decision, never a coupled minute/phase filter.
Only synthetic frames and ASTs are used; the fixed hot-path list is reused.
"""

from __future__ import annotations

import ast

import pandas as pd
import pytest

import backtest.research.csv_ledger as ledger
import backtest.research.csv_minute_backtest as minute_sim
from tests.test_ashare_simulate_import_fence import ROOT, SIMULATE_HOT_PATH


RESEARCH = ROOT / "backtest/research"
MARK_NAMES = {
    "market_close_mark", "last_close_mark", "append_equity_and_eod_marks",
    "EOD_MARK", "equity_curve",
}
TOUCH_NAMES = {
    "SessionPhase", "session_phase", "_session_phase", "closing_call",
    "CLOSING_CALL_OPEN", "PM_CLOSE", "_in_session", "minute_bars", "day_m",
    "scan_held_day", "scan_held_day_python", "14:57", "15:00",
}


def _tree(name):
    return ast.parse((RESEARCH / f"{name}.py").read_text(encoding="utf-8"))


def _function(tree, name):
    return next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)


def _references(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            yield node.id
        elif isinstance(node, ast.Attribute):
            yield node.attr
        elif isinstance(node, ast.arg):
            yield node.arg
        elif isinstance(node, ast.alias):
            yield node.name
            if node.asname:
                yield node.asname
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            yield node.value


def _touch_references(tree):
    return {
        name for name in _references(tree)
        if name in TOUCH_NAMES or name == "hm" or name.endswith("_hm")
    }


def _coupled_mark_controls(tree):
    """Reject a time/phase control enclosing a mark read/write (P4=B)."""
    bad = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.If, ast.IfExp, ast.While)):
            controls = [node.test]
        elif isinstance(node, (ast.For, ast.AsyncFor)):
            # Literal CSV field lists (v7 includes "hm") are not time gates.
            controls = [part for part in ast.walk(node.iter) if isinstance(
                part, (ast.Name, ast.Attribute, ast.Compare, ast.Subscript, ast.Call),
            )]
        elif isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            controls = [part for gen in node.generators for part in [gen.iter, *gen.ifs]]
        elif isinstance(node, ast.BoolOp):
            controls = node.values  # Include short-circuit mark calls.
        else:
            continue
        if any(_touch_references(part) for part in controls) and MARK_NAMES.intersection(_references(node)):
            bad.append(node.lineno)
    return bad


@pytest.mark.parametrize("module,function", [
    ("csv_ledger", "market_close_mark"),
    ("csv_simulate_loop", "append_equity_and_eod_marks"),
])
def test_mark_functions_have_no_minute_touch_dependency(module, function):
    mark = _function(_tree(module), function)
    # P2=B's literal empty output label is permitted, not an input/branch.
    label_keys = set()
    for node in ast.walk(mark):
        if isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                if isinstance(key, ast.Constant) and key.value == "session_phase":
                    assert isinstance(value, ast.Constant) and value.value == ""
                    label_keys.add(key)
    for node in ast.walk(mark):
        if node in label_keys:
            continue
        if isinstance(node, (ast.Name, ast.Attribute, ast.arg, ast.alias, ast.Constant)):
            assert not _touch_references(node), (module, function, ast.unparse(node))
    assert _coupled_mark_controls(mark) == []


@pytest.mark.parametrize("module", SIMULATE_HOT_PATH)
def test_fixed_hot_path_has_no_coupled_touch_mark_control(module):
    # P1 label-only pins separately forbid new phase filters in scanners.
    # Do not ban P2 annotation writes or expand this into a research rglob.
    assert _coupled_mark_controls(_tree(module)) == [], module


def _assert_daily_mark_schedule(tree, bars_name):
    simulate = _function(tree, "simulate")
    day_loop, = [
        node for node in simulate.body
        if isinstance(node, ast.For) and ast.unparse(node.iter) == "enumerate(calendar)"
    ]
    calls = [
        node for node in ast.walk(simulate)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        and node.func.id == "append_equity_and_eod_marks"
    ]
    assert len(calls) == 1
    call = calls[0]
    # A mark is an unconditional statement of the day loop, outside touch loops.
    assert any(isinstance(node, ast.Expr) and node.value is call for node in day_loop.body)
    kwargs = {kw.arg: ast.unparse(kw.value) for kw in call.keywords}
    assert kwargs == {
        "ds": "ds", "day": "day", "calendar_last": "calendar[-1]", "mark_bars": bars_name,
    }

    def assert_no_day_bypass(node, nested_loops=0):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            return  # Local quote helpers have their own returns.
        assert not isinstance(node, ast.Return), ast.unparse(node)
        if nested_loops == 0:
            assert not isinstance(node, (ast.Continue, ast.Break)), ast.unparse(node)
        if isinstance(node, (ast.For, ast.AsyncFor, ast.While)):
            nested_loops += 1
        for child in ast.iter_child_nodes(node):
            assert_no_day_bypass(child, nested_loops)

    for statement in day_loop.body:
        assert_no_day_bypass(statement)


@pytest.mark.parametrize("module,bars_name", [
    ("csv_daily_backtest", "bars"),
    ("csv_minute_backtest", "daily_bars"),
])
def test_book_mark_calls_use_daily_bars_without_touch_or_day_bypass(module, bars_name):
    _assert_daily_mark_schedule(_tree(module), bars_name)


@pytest.mark.parametrize("source", [
    "if session_phase(hm) != 'closing_call':\n    append_equity_and_eod_marks(st)",
    "if cur_hm < 15 * 60:\n    mark = market_close_mark(df, day)",
    "if hm < CLOSING_CALL_OPEN:\n    st.trades.append({'side': 'EOD_MARK'})",
    "if clock.SessionPhase.closing_call != phase:\n    st.equity_curve.append((ds, eq))",
    "hm < 900 and append_equity_and_eod_marks(st)",
])
def test_ast_pin_rejects_coupled_phase_and_hm_mark_controls(source):
    assert _coupled_mark_controls(ast.parse(source))


@pytest.mark.parametrize("mutation", ["gate", "continue", "break", "return", "minute_bars"])
def test_schedule_pin_rejects_gating_bypassing_or_replacing_daily_marks(mutation):
    # Mutate an in-memory AST only; production files remain untouched.
    tree = _tree("csv_minute_backtest")
    simulate = _function(tree, "simulate")
    day_loop = next(n for n in simulate.body if isinstance(n, ast.For))
    mark = next(n for n in day_loop.body if isinstance(n, ast.Expr)
                and isinstance(n.value, ast.Call)
                and isinstance(n.value.func, ast.Name)
                and n.value.func.id == "append_equity_and_eod_marks")
    if mutation == "gate":
        day_loop.body[day_loop.body.index(mark)] = ast.If(
            test=ast.parse("hm < 900", mode="eval").body, body=[mark], orelse=[],
        )
    elif mutation == "minute_bars":
        next(kw for kw in mark.value.keywords if kw.arg == "mark_bars").value.id = "minute_bars"
    else:
        day_loop.body.insert(0, ast.parse(f"if hm >= 900:\n    {mutation}").body[0])
    with pytest.raises(AssertionError):
        _assert_daily_mark_schedule(tree, "daily_bars")


def _daily_frame(closes):
    return pd.DataFrame({"close": list(closes.values())}, index=pd.to_datetime(list(closes)))


@pytest.mark.parametrize("minute_hm", [None, 14 * 60 + 56, 14 * 60 + 57, 15 * 60],
                         ids=["no_minutes", "continuous", "closing_call", "1500"])
@pytest.mark.parametrize("mark_case", ["on_day", "halt", "no_daily_history"])
def test_public_minute_engine_marks_daily_close_independently_of_minutes(
    monkeypatch, minute_hm, mark_case,
):
    """Human GO P4=A closure: absent touch data never implies absent NAV/EOD."""
    day = pd.Timestamp("2025-11-05")
    code = "600000.SH"
    daily = {"000001.SZ": _daily_frame({"2025-11-05": 10.0})}  # Keep the session on halt.
    if mark_case != "no_daily_history":
        closes = {"2025-11-04": 12.0}
        if mark_case == "on_day":
            closes["2025-11-05"] = 12.5
        daily[code] = _daily_frame(closes)
    minutes = {}
    if minute_hm is not None:
        # Deliberately different from daily/prior close and both lot costs.
        frame = pd.DataFrame(
            {key: [11.5] for key in ("open", "high", "low", "close")},
            index=pd.DatetimeIndex([day + pd.Timedelta(minutes=minute_hm)]),
        )
        minutes[code] = minute_sim._annotate(frame)

    real_init = minute_sim.init_sim_state

    def init_with_lots(*args, **kwargs):
        st, pending, names = real_init(*args, **kwargs)
        # Same-day lots are T+1-ineligible; marking must still cover every lot.
        st.positions[code] = [
            ledger.Position(code=code, shares=100, cost=10.0, peak=10.0, entry_idx=0, lot_id=1),
            ledger.Position(code=code, shares=200, cost=11.0, peak=11.0, entry_idx=0, lot_id=2),
        ]
        return st, pending, names

    def forbid_phase_lookup(*args, **kwargs):
        pytest.fail("P4 mark must not consult minute session-phase eligibility")

    monkeypatch.setattr(minute_sim, "init_sim_state", init_with_lots)
    monkeypatch.setattr(ledger, "_session_phase", forbid_phase_lookup)
    st = minute_sim.simulate(
        minutes, daily, {}, "20251105", "20251105", strategy="version6", total_cash=500.0,
    )
    prices = {"on_day": [12.5, 12.5], "halt": [12.0, 12.0], "no_daily_history": [10.0, 11.0]}[mark_case]
    assert st.cash == 500.0
    assert st.equity_curve == [("20251105", 500.0 + 100 * prices[0] + 200 * prices[1])]
    assert [(t["side"], t["lot"], t["shares"], t["price"]) for t in st.trades] == [
        ("EOD_MARK", 1, 100, prices[0]), ("EOD_MARK", 2, 200, prices[1]),
    ]
    assert all(t["session_phase"] == t["price_rule"] == "" for t in st.trades)
    assert all(t["commission"] == 0.0 for t in st.trades)
