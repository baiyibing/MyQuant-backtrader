# -*- coding: utf-8 -*-
"""Data-free contracts for the fill-clock naming leaf.

Human GO P1=A closure (2026-09-20): scan-window labels only, no real
closing call auction model; session/fill eligibility stays as-built.
FillPriceRule names seven existing book-engine paths. That set is not an
exhaustive price selector and does not cover v7.
Human GO P2=B adds trade labels at write sites only; P1 eligibility stays A.
"""

from __future__ import annotations

import ast
import io
import sys
import tokenize
from importlib.util import resolve_name

import numpy as np
import pandas as pd
import pytest

import backtest.research.ashare_bars as bars
import backtest.research.ashare_fill_clock as clock
import backtest.research.csv_daily_backtest as daily_sim
import backtest.research.csv_minute_backtest as minute_sim
from backtest.research.ashare_bars import _in_session
from backtest.research.csv_common import build_calendar
from backtest.research.csv_ledger import SimState, chase_decision
from backtest.research.csv_pool import load_pool_day_map
from backtest.research.csv_simulate_loop import run_chase_due_day
from backtest.research.market_layer import limit_prices
from tests.test_ashare_simulate_import_fence import (
    ROOT,
    SIMULATE_HOT_PATH,
    forbidden_imports,
    test_hot_path_list_matches_plan_bytes,
)

LEAF = ROOT / "backtest" / "research" / "ashare_fill_clock.py"
BOUND_NAMES = ("AM_OPEN", "AM_CLOSE", "PM_OPEN", "PM_CLOSE")
BARS_MODULE = "backtest.research.ashare_bars"
PACKAGE = "backtest.research"
SCAN_WINDOW_NOTE = "标签描述当前扫描窗口，不是交易所忠实 closing-call 撮合"
PHASE_FILTER_NAMES = {"continuous", "closing_call", "session_phase", "CLOSING_CALL_OPEN", "SessionPhase"}
# Only these trade writers may contain phase labels. Scanners remain forbidden.
PHASE_LABEL_WRITE_PATHS = {"csv_ledger", "csv_simulate_loop"}
# Existing time comparisons only; no 14:57 (897 minutes) auction-policy cutoff.
AS_BUILT_SCAN_HM_COMPARISONS = {
    "hm is not None",
    "new_peak_hm >= 0",
    "force_sell_hm is not None",
    "cur_hm >= int(force_sell_hm)",
}
# FillPriceRule 是具名路径，不是全量选价器，不含 v7。
NAMED_PRICE_RULES = (
    "daily_open_board_same_close",
    "daily_stop_gap_open",
    "daily_stop_touch_at_trigger",
    "daily_stop_close",
    "daily_pending_next_open",
    "minute_gap_open",
    "minute_trigger_bar_close",
)
TARGET = "600000.SH"
ANCHOR = "000001.SZ"


def _leaf_source() -> str:
    return LEAF.read_text(encoding="utf-8")


def _phase_filter_references(source: str) -> set[str]:
    """Reject phase names (including imports/attributes) and exact string labels.

    Comments and prose docstrings may document P1=A without becoming filters.
    """
    names = {
        token.string
        for token in tokenize.generate_tokens(io.StringIO(source).readline)
        if token.type == tokenize.NAME
    }
    strings = {
        node.value
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    return PHASE_FILTER_NAMES & (names | strings)


def _scan_hm_comparisons(tree: ast.AST) -> set[str]:
    """Pin direct hm comparisons without interpreting prices or executing code."""
    return {
        ast.unparse(node)
        for node in ast.walk(tree)
        if isinstance(node, ast.Compare)
        and any(
            isinstance(part, ast.Name) and (part.id == "hm" or part.id.endswith("_hm"))
            for part in ast.walk(node)
        )
    }


def _resolved_from(node: ast.ImportFrom) -> str:
    module = node.module or ""
    if node.level:
        return resolve_name("." * node.level + module, PACKAGE)
    return module


def _bound_import_problems(source: str) -> list[str]:
    """AM_*/PM_* must come only from ashare_bars, with no local rebinding."""
    tree = ast.parse(source)
    problems = []
    imported: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        origin = _resolved_from(node)
        for alias in node.names:
            bound = alias.asname or alias.name
            if alias.name not in BOUND_NAMES and bound not in BOUND_NAMES:
                continue
            if origin != BARS_MODULE or alias.asname or alias.name not in BOUND_NAMES:
                problems.append(f"{bound} imported from {origin}")
            else:
                imported.add(alias.name)
    missing = [name for name in BOUND_NAMES if name not in imported]
    if missing:
        problems.append("missing ashare_bars import: " + ",".join(missing))
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            if node.id in BOUND_NAMES:
                problems.append(f"local assignment {node.id}")
    return problems


def _leaf_import_problems(source: str) -> list[str]:
    """Stdlib plus the four ashare_bars bounds; nothing else."""
    tree = ast.parse(source)
    problems = []
    stdlib = sys.stdlib_module_names
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                if root not in stdlib:
                    problems.append(alias.name)
                _flag_forbidden_module(alias.name, problems)
        elif isinstance(node, ast.ImportFrom):
            origin = _resolved_from(node)
            names = [alias.name for alias in node.names]
            if origin == BARS_MODULE and node.level == 0:
                extra = [name for name in names if name not in BOUND_NAMES]
                if extra or any(alias.asname for alias in node.names):
                    problems.append(f"ashare_bars import not limited to bounds: {names}")
                continue
            if origin == BARS_MODULE and set(names) <= set(BOUND_NAMES):
                continue
            root = origin.split(".", 1)[0]
            if node.level or root not in stdlib:
                problems.append(origin or "<relative>")
            _flag_forbidden_module(origin, problems)
            for name in names:
                _flag_forbidden_module(name, problems)
    return problems


def _flag_forbidden_module(name: str, problems: list[str]) -> None:
    text = name or ""
    parts = text.split(".")
    needles = (
        "qlib",
        "trade_fee_policy",
        "lebs",
        "simulate",
        "scan_held_day",
        "csv_simulate_loop",
    )
    if any(needle in parts or needle in text for needle in needles):
        problems.append(text)


def _daily_frame(days: list[str], rows: list[tuple]) -> pd.DataFrame:
    idx = pd.to_datetime(days)
    pre = pd.Timestamp(days[0]) - pd.Timedelta(days=2)
    frame = pd.DataFrame(
        {
            "open": [10.0] + [row[0] for row in rows],
            "high": [10.0] + [row[1] for row in rows],
            "low": [10.0] + [row[2] for row in rows],
            "close": [10.0] + [row[3] for row in rows],
        },
        index=pd.DatetimeIndex([pre]).append(idx),
    )
    return frame.astype(np.float64)


def _flat_anchor(days: list[str]) -> pd.DataFrame:
    return _daily_frame(days, [(10.0, 10.1, 9.9, 10.0)] * len(days))


def _minute_day(date: str, rows: list[tuple]) -> pd.DataFrame:
    idx, opens, highs, lows, closes = [], [], [], [], []
    day = pd.Timestamp(date)
    for hm, oo, hh, ll, cc in rows:
        hour, minute = divmod(int(hm), 100)
        idx.append(day + pd.Timedelta(hours=hour, minutes=minute))
        opens.append(oo)
        highs.append(hh)
        lows.append(ll)
        closes.append(cc)
    frame = pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes},
        index=pd.DatetimeIndex(idx),
    ).astype(np.float64)
    return minute_sim._annotate(frame)


def _daily_marks(dates: list[str], closes: list[float], prev: float = 10.0) -> pd.DataFrame:
    pre = pd.Timestamp(dates[0]) - pd.Timedelta(days=2)
    idx = pd.DatetimeIndex([pre] + [pd.Timestamp(d) for d in dates])
    px = [prev] + list(closes)
    return pd.DataFrame(
        {"open": px, "high": px, "low": px, "close": px},
        index=idx,
    ).astype(np.float64)


def _buys(st):
    return [trade for trade in st.trades if trade["side"] == "BUY"]


def _sells(st):
    return [trade for trade in st.trades if trade["side"] == "SELL"]


def _assert_book_labels(st, rule, phase=""):
    assert {t["session_phase"] for t in st.trades} <= {"", *(p.value for p in clock.SessionPhase)}
    assert {t["price_rule"] for t in st.trades} <= {"", *(p.value for p in clock.FillPriceRule)}
    buy, sell = _buys(st)[0], _sells(st)[0]
    # Baseline six-path fixtures all buy/sell the same 100,000 shares at cost 10.
    assert buy["price"] == pytest.approx(10.0)
    assert buy["reason"] == "pool"
    assert buy["shares"] == sell["shares"] == 100_000
    assert buy["session_phase"] == buy["price_rule"] == ""
    assert sell["session_phase"] == phase
    assert sell["price_rule"] == rule.value


def _watch_chase(monkeypatch, engine):
    """Wrap run_chase_due_day; record the production quotes callback and pending."""
    real = run_chase_due_day
    log = []

    def wrapped(st, pending_chase, **kwargs):
        quotes_for = kwargs["quotes_for"]
        seen = {}

        def recording(code):
            quoted = quotes_for(code)
            seen[code] = quoted
            return quoted

        held_before = set(st.positions)
        call = dict(kwargs)
        call["quotes_for"] = recording
        real(st, pending_chase, **call)
        gate = call.get("allow_new_name")
        log.append(
            {
                "day": pd.Timestamp(call["day"]),
                "quotes": seen,
                "pending_after": set(pending_chase),
                "held_before": held_before,
                "index_gate_open": (not callable(gate)) or bool(gate(call["day"])),
            }
        )

    monkeypatch.setattr(engine, "run_chase_due_day", wrapped)
    return log


def _t1_row(log, ymd: str = "20251104"):
    return next(row for row in log if row["day"].strftime("%Y%m%d") == ymd)


def test_fill_clock_bounds_import_only_ashare_bars():
    # Human GO P1=A closure (2026-09-20): 14:57 remains a label only.
    source = _leaf_source()
    assert _bound_import_problems(source) == []
    assert clock.AM_OPEN == bars.AM_OPEN
    assert clock.AM_CLOSE == bars.AM_CLOSE
    assert clock.PM_OPEN == bars.PM_OPEN
    assert clock.PM_CLOSE == bars.PM_CLOSE
    assert clock.CLOSING_CALL_OPEN == 14 * 60 + 57
    assert clock.CLOSING_CALL_OPEN != bars.PM_CLOSE
    assert not hasattr(bars, "CLOSING_CALL_OPEN")


def test_session_phase_labels_current_scan_window():
    # Human GO P1=A closure (2026-09-20): 标签描述当前扫描窗口，不是交易所忠实 closing-call 撮合。
    for hm in (9 * 60 + 24, 11 * 60 + 31, 12 * 60 + 59, 15 * 60 + 1):
        with pytest.raises(ValueError):
            clock.session_phase(hm)
    for hm in (9 * 60 + 30, 11 * 60 + 30, 13 * 60, 14 * 60 + 56):
        assert clock.session_phase(hm) == clock.SessionPhase.continuous, SCAN_WINDOW_NOTE
        assert clock.session_phase(hm) == "continuous", SCAN_WINDOW_NOTE
    for hm in range(14 * 60 + 57, 15 * 60 + 1):
        assert clock.session_phase(hm) == clock.SessionPhase.closing_call, SCAN_WINDOW_NOTE
        assert clock.session_phase(hm) == "closing_call", SCAN_WINDOW_NOTE
    accepted = np.asarray(_in_session(list(range(14 * 60 + 57, 15 * 60 + 1))))
    assert accepted.all(), SCAN_WINDOW_NOTE


@pytest.mark.parametrize("name", [n for n in SIMULATE_HOT_PATH if n not in PHASE_LABEL_WRITE_PATHS])
def test_simulate_hot_path_has_no_phase_filter_identifiers(name):
    # P2=B narrows only write sites; P1=A still bans phase names in all scanners.
    path = ROOT / "backtest" / "research" / f"{name}.py"
    assert _phase_filter_references(path.read_text(encoding="utf-8")) == set(), name


@pytest.mark.parametrize("source", [
    "if session_phase(hm):\n    pass",
    "if clock.SessionPhase.closing_call == phase:\n    pass",
    "if cur_hm >= CLOSING_CALL_OPEN:\n    pass",
    "from policy import session_phase as phase",
    "if phase == 'closing_call':\n    pass",
])
def test_phase_filter_pin_rejects_names_aliases_and_string_labels(source):
    assert _phase_filter_references(source)


def test_scan_held_day_python_hm_comparisons_stay_as_built():
    # Human GO P1=A closure (2026-09-20): no B/C cutoff, no new eligibility.
    path = ROOT / "backtest" / "research" / "csv_minute_backtest.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    scan = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "scan_held_day_python"
    )
    assert _scan_hm_comparisons(scan) == AS_BUILT_SCAN_HM_COMPARISONS


@pytest.mark.parametrize("condition", [
    "cur_hm >= 897",
    "cur_hm >= 14 * 60 + 57",
    "14 * 60 + 57 <= cur_hm <= 14 * 60 + 59",
    "14 * 60 + 57 <= cur_hm <= 15 * 60",
    "hm[i] < 14 * 60 + 57",
])
def test_scan_hm_pin_rejects_b_c_style_comparisons(condition):
    tree = ast.parse(f"if {condition}:\n    pass")
    assert _scan_hm_comparisons(tree) - AS_BUILT_SCAN_HM_COMPARISONS


def test_pool_file_day_is_decision_and_buy_day(tmp_path):
    assert clock.POOL_FILE_DAY_RULE == "filename_day_is_decision_and_buy_day"
    (tmp_path / "20251103.csv").write_text("600000\n", encoding="utf-8")
    pool = load_pool_day_map(tmp_path, "20251103", "20251104")
    assert pool == {"20251103": [TARGET]}

    days = ["2025-11-03", "2025-11-04"]
    daily_bars = {
        TARGET: _daily_frame(days, [(10.10, 10.50, 10.00, 10.40), (10.90, 10.95, 10.80, 10.92)]),
        ANCHOR: _flat_anchor(days),
    }
    daily_state = daily_sim.simulate(
        daily_bars, pool, "20251103", "20251104", strategy="version6"
    )
    daily_buy = _buys(daily_state)[0]
    assert daily_buy["date"] == "20251103"
    assert daily_buy["reason"] == "pool"
    assert daily_buy["price"] == pytest.approx(10.40)
    assert daily_buy["price"] != pytest.approx(10.90)

    t_bars = _minute_day(
        "2025-11-03",
        [(930, 10.0, 10.1, 9.9, 10.0), (1455, 10.20, 10.30, 10.15, 10.25), (1500, 10.70, 10.85, 10.60, 10.80)],
    )
    t1_bars = _minute_day(
        "2025-11-04",
        [(930, 10.90, 10.95, 10.85, 10.92), (1455, 10.90, 10.95, 10.85, 10.92)],
    )
    minute_state = minute_sim.simulate(
        {TARGET: pd.concat([t_bars, t1_bars])},
        {TARGET: _daily_marks(days, [10.40, 10.92]), ANCHOR: _daily_marks(days, [10.0, 10.0])},
        pool,
        "20251103",
        "20251104",
        strategy="version6",
    )
    minute_buy = _buys(minute_state)[0]
    assert minute_buy["date"] == "20251103"
    assert minute_buy["reason"] == "pool"
    assert minute_buy["price"] == pytest.approx(10.25)
    assert minute_buy["price"] != pytest.approx(10.80)
    assert minute_buy["price"] != pytest.approx(10.90)

    fallback = _minute_day(
        "2025-11-03",
        [(1430, 10.05, 10.12, 10.00, 10.11), (1445, 10.20, 10.40, 10.18, 10.33), (1500, 10.90, 11.05, 10.80, 10.99)],
    )
    fallback_state = minute_sim.simulate(
        {TARGET: pd.concat([fallback, t1_bars])},
        {TARGET: _daily_marks(days, [10.33, 10.92]), ANCHOR: _daily_marks(days, [10.0, 10.0])},
        pool,
        "20251103",
        "20251104",
        strategy="version6",
    )
    fallback_buy = _buys(fallback_state)[0]
    assert fallback_buy["date"] == "20251103"
    assert fallback_buy["price"] == pytest.approx(10.33)
    assert fallback_buy["price"] != pytest.approx(10.11)
    assert fallback_buy["price"] != pytest.approx(10.99)
    assert fallback_buy["price"] != pytest.approx(10.90)


def test_chase_buy_prices_use_existing_t1_quotes():
    # Locks the first attempt day that already has a quote, not the only fill day.
    days = ["2025-11-03", "2025-11-04", "2025-11-05", "2025-11-06", "2025-11-07"]
    rows = [
        (10.5, 11.0, 10.5, 11.0),
        (11.05, 11.40, 10.90, 11.20),
        (11.2, 11.3, 11.0, 11.1),
        (11.1, 11.2, 10.9, 11.0),
        (11.0, 11.1, 10.8, 10.9),
    ]
    st = daily_sim.simulate(
        {TARGET: _daily_frame(days, rows), ANCHOR: _flat_anchor(days)},
        {"20251103": [TARGET]},
        "20251103",
        "20251107",
        strategy="version6",
    )
    assert st.stats["skip_held"] == 0
    assert st.stats["skip_index_gate"] == 0
    assert st.stats["chase_buy"] == 1
    buy = _buys(st)[0]
    assert buy["date"] == "20251104"
    assert buy["reason"] == "chase:T+1"
    assert buy["price"] == pytest.approx(11.20)
    assert buy["price"] != pytest.approx(11.05)
    assert buy["price"] != pytest.approx(11.0)
    up, _ = limit_prices(TARGET, 11.0, "")
    assert chase_decision(11.05, 11.20, up) == "buy"

    dates = ["2025-11-03", "2025-11-04"]
    signal = _minute_day(
        "2025-11-03",
        [(930, 10.5, 11.0, 10.5, 10.8), (1455, 11.0, 11.0, 11.0, 11.0)],
    )
    quote_day = _minute_day(
        "2025-11-04",
        [
            (930, 11.04, 11.08, 11.00, 11.06),
            (945, 11.08, 11.12, 11.06, 11.10),
            (1455, 11.10, 11.20, 11.00, 11.15),
        ],
    )
    minute = {TARGET: pd.concat([signal, quote_day])}
    minute_state = minute_sim.simulate(
        minute,
        {TARGET: _daily_marks(dates, [11.0, 11.15]), ANCHOR: _daily_marks(dates, [10.0, 10.0])},
        {"20251103": [TARGET]},
        "20251103",
        "20251104",
        strategy="version6",
    )
    assert minute_state.stats["skip_held"] == 0
    assert minute_state.stats["skip_index_gate"] == 0
    minute_buy = _buys(minute_state)[0]
    open_px, px = minute_sim._chase_quotes(quote_day)
    assert minute_buy["reason"] == "chase:T+1"
    assert minute_buy["date"] == "20251104"
    assert minute_buy["price"] == pytest.approx(px)
    assert minute_buy["price"] == pytest.approx(11.10)
    assert minute_buy["price"] != pytest.approx(open_px)
    assert minute_buy["price"] != pytest.approx(11.04)
    assert minute_buy["price"] != pytest.approx(11.0)

    fallback_day = _minute_day(
        "2025-11-04",
        [
            (930, 11.04, 11.08, 11.00, 11.02),
            (940, 11.05, 11.09, 11.03, 11.08),
            (1455, 11.10, 11.20, 11.00, 11.15),
        ],
    )
    fallback_state = minute_sim.simulate(
        {TARGET: pd.concat([signal, fallback_day])},
        {TARGET: _daily_marks(dates, [11.0, 11.15]), ANCHOR: _daily_marks(dates, [10.0, 10.0])},
        {"20251103": [TARGET]},
        "20251103",
        "20251104",
        strategy="version6",
    )
    fallback_buy = _buys(fallback_state)[0]
    _open, fallback_px = minute_sim._chase_quotes(fallback_day)
    assert 9 * 60 + 45 not in set(fallback_day["hm"])
    assert fallback_buy["reason"] == "chase:T+1"
    assert fallback_buy["price"] == pytest.approx(fallback_px)
    assert fallback_buy["price"] == pytest.approx(11.08)
    assert fallback_buy["price"] != pytest.approx(11.04)
    assert fallback_buy["price"] != pytest.approx(11.02)
    assert fallback_buy["price"] != pytest.approx(11.0)
    assert fallback_buy["price"] != pytest.approx(11.15)


def test_chase_missing_quote_fills_on_later_session_keeps_t1_reason(monkeypatch):
    # Do not delete the T+1 session. Only the target quote is None that day.
    st = SimState()
    pending = {TARGET: (1_000_000.0, 0)}
    assert TARGET not in st.positions

    def missing_quote(_code):
        return None

    run_chase_due_day(
        st,
        pending,
        day_i=1,
        day=pd.Timestamp("2025-11-04"),
        names={},
        allow_add=False,
        buy_gate=None,
        quotes_for=missing_quote,
        allow_new_name=lambda _day: True,
    )
    assert TARGET in pending
    assert pending[TARGET][1] == 0
    assert st.stats["skip_held"] == 0
    assert st.stats["skip_index_gate"] == 0
    up, _ = limit_prices(TARGET, 11.0, "")
    assert chase_decision(11.20, 11.50, up) == "buy"

    days = ["2025-11-03", "2025-11-04", "2025-11-05"]
    daily_rows = {
        TARGET: _daily_frame(
            days,
            [
                (10.5, 11.0, 10.5, 11.0),
                (11.0, 11.1, 10.9, 11.0),
                (11.20, 11.60, 11.10, 11.50),
            ],
        ),
        ANCHOR: _flat_anchor(days),
    }
    daily_rows[TARGET] = daily_rows[TARGET].drop(pd.Timestamp("2025-11-04"))
    calendar = build_calendar(daily_rows, "20251103", "20251105")
    assert pd.Timestamp("2025-11-04") in calendar
    assert pd.Timestamp("2025-11-04") in daily_rows[ANCHOR].index
    assert pd.Timestamp("2025-11-04") not in daily_rows[TARGET].index
    daily_log = _watch_chase(monkeypatch, daily_sim)
    daily_state = daily_sim.simulate(
        daily_rows,
        {"20251103": [TARGET]},
        "20251103",
        "20251105",
        strategy="version6",
    )
    t1 = _t1_row(daily_log)
    assert t1["quotes"][TARGET] is None
    assert TARGET in t1["pending_after"]
    assert TARGET not in t1["held_before"]
    assert t1["index_gate_open"]
    assert daily_state.stats["skip_held"] == 0
    assert daily_state.stats["skip_index_gate"] == 0
    daily_buy = _buys(daily_state)[0]
    assert daily_buy["date"] == "20251105"
    assert daily_buy["reason"] == "chase:T+1"
    assert daily_buy["price"] == pytest.approx(11.50)
    assert daily_buy["price"] != pytest.approx(11.20)
    assert TARGET not in _t1_row(daily_log, "20251105")["pending_after"]

    dates = ["2025-11-03", "2025-11-04", "2025-11-05"]
    signal = _minute_day(
        "2025-11-03",
        [(930, 10.5, 11.0, 10.5, 10.8), (1455, 11.0, 11.0, 11.0, 11.0)],
    )
    later = _minute_day(
        "2025-11-05",
        [
            (930, 11.04, 11.08, 11.00, 11.02),
            (945, 11.08, 11.12, 11.06, 11.10),
            (1455, 11.20, 11.30, 11.00, 11.25),
        ],
    )
    minute = {TARGET: pd.concat([signal, later])}
    daily = {
        TARGET: _daily_marks(dates, [11.0, 11.0, 11.25]),
        ANCHOR: _daily_marks(dates, [10.0, 10.0, 10.0]),
    }
    minute_calendar = build_calendar(daily, "20251103", "20251105")
    assert pd.Timestamp("2025-11-04") in minute_calendar
    assert "20251104" not in set(minute[TARGET]["ymd"])
    minute_log = _watch_chase(monkeypatch, minute_sim)
    minute_state = minute_sim.simulate(
        minute,
        daily,
        {"20251103": [TARGET]},
        "20251103",
        "20251105",
        strategy="version6",
    )
    minute_t1 = _t1_row(minute_log)
    assert minute_t1["quotes"][TARGET] is None
    assert TARGET in minute_t1["pending_after"]
    assert TARGET not in minute_t1["held_before"]
    assert minute_t1["index_gate_open"]
    assert minute_state.stats["skip_held"] == 0
    assert minute_state.stats["skip_index_gate"] == 0
    minute_buy = _buys(minute_state)[0]
    _open, px = minute_sim._chase_quotes(later)
    assert minute_buy["date"] == "20251105"
    assert minute_buy["reason"] == "chase:T+1"
    assert minute_buy["price"] == pytest.approx(px)
    assert minute_buy["price"] == pytest.approx(11.10)
    assert minute_buy["price"] != pytest.approx(11.04)
    assert minute_buy["price"] != pytest.approx(11.0)
    assert minute_buy["price"] != pytest.approx(11.25)


def test_daily_open_board_rule_uses_same_day_close():
    # Same 300001.SZ fixture as test_strategy3_daily_open_board_sells_same_close.
    # Not an exhaustive selector and not v7. Limit touch may defer; do not invent a no-limit OHLC.
    assert [rule.value for rule in clock.FillPriceRule] == list(NAMED_PRICE_RULES)
    days = ["2025-11-03", "2025-11-04", "2025-11-05", "2025-11-06", "2025-11-07"]
    rows = [
        (10.0, 10.0, 10.0, 10.0),
        (12.0, 12.0, 10.8, 11.8),
        (11.8, 11.8, 11.8, 11.8),
        (11.8, 11.8, 11.8, 11.8),
        (11.8, 11.8, 11.8, 11.8),
    ]
    code = "300001.SZ"
    st = daily_sim.simulate(
        {code: _daily_frame(days, rows)},
        {"20251103": [code]},
        "20251103",
        "20251107",
        strategy="version3",
    )
    buy = _buys(st)[0]
    sell = _sells(st)[0]
    assert buy["price"] == pytest.approx(10.0)
    assert sell["date"] == "20251104"
    assert sell["price"] == pytest.approx(11.8)
    assert sell["price"] != pytest.approx(12.0)
    assert sell["reason"] == "open_board"
    assert clock.FillPriceRule.daily_open_board_same_close == "daily_open_board_same_close"
    _assert_book_labels(st, clock.FillPriceRule.daily_open_board_same_close)


def test_daily_stop_gap_rule_uses_same_day_open():
    days = ["2025-11-03", "2025-11-04", "2025-11-05", "2025-11-06", "2025-11-07"]
    rows = [
        (10.0, 10.0, 10.0, 10.0),
        (9.4, 9.5, 9.3, 9.35),
        (9.3, 9.4, 9.2, 9.3),
        (9.3, 9.3, 9.2, 9.25),
        (9.2, 9.3, 9.1, 9.2),
    ]
    st = daily_sim.simulate(
        {TARGET: _daily_frame(days, rows)},
        {"20251103": [TARGET]},
        "20251103",
        "20251107",
        strategy="version6",
        stop_pct=0.04,
    )
    sell = _sells(st)[0]
    assert sell["reason"] == "stop_loss:gap_open"
    assert sell["date"] == "20251104"
    assert sell["price"] == pytest.approx(9.4)
    assert sell["price"] != pytest.approx(9.35)
    assert sell["price"] != pytest.approx(9.3)
    assert clock.FillPriceRule.daily_stop_gap_open == "daily_stop_gap_open"
    _assert_book_labels(st, clock.FillPriceRule.daily_stop_gap_open)


def test_daily_stop_touch_rule_uses_same_day_trigger():
    days = ["2025-11-03", "2025-11-04", "2025-11-05", "2025-11-06", "2025-11-07"]
    rows = [
        (10.2, 10.3, 9.4, 10.0),
        (9.85, 9.90, 9.50, 9.60),
        (9.4, 9.5, 9.2, 9.3),
        (9.3, 9.4, 9.1, 9.2),
        (9.2, 9.3, 9.0, 9.1),
    ]
    st = daily_sim.simulate(
        {TARGET: _daily_frame(days, rows)},
        {"20251103": [TARGET]},
        "20251103",
        "20251107",
        strategy="version6",
        stop_pct=0.02,
    )
    sell = _sells(st)[0]
    assert sell["reason"] == "stop_loss:touch"
    assert sell["date"] == "20251104"
    assert sell["price"] == pytest.approx(9.8)
    assert sell["price"] != pytest.approx(9.60)
    assert sell["price"] != pytest.approx(9.4)
    assert clock.FillPriceRule.daily_stop_touch_at_trigger == "daily_stop_touch_at_trigger"
    _assert_book_labels(st, clock.FillPriceRule.daily_stop_touch_at_trigger)


def test_daily_pending_exit_rule_uses_next_session_open():
    # One known pending_exit reason (ma_signal). Do not claim every non-same-bar reason.
    prior = pd.bdate_range(end="2025-10-31", periods=10)
    trade_days = ["2025-11-03", "2025-11-04", "2025-11-05"]
    rows = [(10, 10, 10, 10), (10, 10, 9, 9), (9.1, 9.1, 9.1, 9.1)]
    frame = pd.DataFrame(
        {
            "open": [10.0] * 10 + [row[0] for row in rows],
            "high": [10.0] * 10 + [row[1] for row in rows],
            "low": [10.0] * 10 + [row[2] for row in rows],
            "close": [10.0] * 10 + [row[3] for row in rows],
        },
        index=prior.append(pd.to_datetime(trade_days)),
    ).astype(np.float64)
    st = daily_sim.simulate(
        {TARGET: frame},
        {"20251103": [TARGET]},
        "20251103",
        "20251105",
        strategy="version4",
    )
    sell = _sells(st)[0]
    assert sell["reason"] == "ma_signal:MA5"
    assert not sell["reason"].startswith("open_board")
    assert sell["date"] == "20251105"
    assert sell["price"] == pytest.approx(9.1)
    assert sell["price"] != pytest.approx(9.0)
    assert clock.FillPriceRule.daily_pending_next_open == "daily_pending_next_open"
    _assert_book_labels(st, clock.FillPriceRule.daily_pending_next_open)


def test_minute_gap_stop_rule_uses_bar_open():
    idx, px, reason, _peak, _hm = minute_sim.scan_held_day_python(
        np.array([9.40, 9.50]),
        np.array([9.50, 9.55]),
        np.array([9.45, 9.50]),
        cost=10.0,
        peak=10.0,
        n_days=1,
        can_sell=True,
        stop_pct=0.02,
        profit_base=0.01,
        trail_ratio=0.50,
    )
    assert idx == 0
    assert reason == "stop_loss:gap_open"
    assert px == pytest.approx(9.40)
    assert px != pytest.approx(9.45)
    assert clock.FillPriceRule.minute_gap_open == "minute_gap_open"


def test_minute_touch_rule_uses_bar_close():
    idx, px, reason, _peak, _hm = minute_sim.scan_held_day_python(
        np.array([9.90]),
        np.array([9.95]),
        np.array([9.70]),
        cost=10.0,
        peak=10.0,
        n_days=1,
        can_sell=True,
        stop_pct=0.02,
        profit_base=0.01,
        trail_ratio=0.50,
    )
    assert idx == 0
    assert reason == "stop_loss:touch"
    assert px == pytest.approx(9.70)
    assert px != pytest.approx(9.90)
    assert clock.FillPriceRule.minute_trigger_bar_close == "minute_trigger_bar_close"


def test_fill_clock_leaf_imports_only_allowed_bounds():
    source = _leaf_source()
    assert _leaf_import_problems(source) == []
    assert _bound_import_problems(source) == []
    rejected = [
        "import qlib",
        "from qlib.backtest import exchange",
        "import trade_decision.trade_fee_policy as fees",
        "from trade_decision import trade_fee_policy",
        "import backtest.lebs.engine",
        "from backtest.lebs import engine",
        "from backtest.research.csv_simulate_loop import run_chase_due_day",
        "from backtest.research.csv_daily_backtest import simulate",
        "from backtest.research.csv_minute_backtest import scan_held_day",
        "import pandas",
        "from backtest.research.ashare_bars import AM_OPEN, load_minute_ohlc",
        "from backtest.research.ashare_bars import AM_OPEN\nAM_OPEN = 1\n",
    ]
    for snippet in rejected:
        assert _leaf_import_problems(snippet) or _bound_import_problems(snippet), snippet


def test_simulate_hot_path_forbids_fill_clock_import_except_writer():
    test_hot_path_list_matches_plan_bytes()
    assert "ashare_fill_clock" not in SIMULATE_HOT_PATH
    sources = [
        "import ashare_fill_clock",
        "from ashare_fill_clock import session_phase",
        "import backtest.research.ashare_fill_clock as clock",
        "from backtest.research.ashare_fill_clock import FillPriceRule",
        "from backtest.research import ashare_fill_clock",
        "from .ashare_fill_clock import SessionPhase",
        "from . import ashare_fill_clock",
    ]
    for source in sources:
        assert forbidden_imports(source), source
    for name in SIMULATE_HOT_PATH:
        path = ROOT / "backtest" / "research" / f"{name}.py"
        assert forbidden_imports(path.read_text(encoding="utf-8"), module_name=name) == [], name
