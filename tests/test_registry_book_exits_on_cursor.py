"""Replace the wire's per-book tables with registry hooks on the main cursor.

B1/B2: stop basis and take-profit come from the registry hooks and shared
HeldMinuteCursor, not hand-copied rule tables. Synthetic arrays require no lake.
The wire, bar_scan_exit and their tests remain until the final removal PR.
"""

import math

import numpy as np
import pandas as pd
import pytest

from backtest.research.minute_held_scan_core import HeldMinuteCursor
from backtest.research.csv_strategy_books import apply_csv_strategy, csv_strategy_names
from backtest.research.minute_classification import CLI_MINUTE, minute_strategy_entries
from backtest.research.strategy9_rules import evaluate_stop_range


def _hooks(name):
    kwargs = ({"scores_by_day": {"20260102": {"000001.SZ": 1.0}}}
              if name.startswith("topk_") else {})
    hooks = apply_csv_strategy(name, **kwargs)
    if name.startswith("topk_"):
        # Bind an empty opening roster: no planned dropout/SX0 sells today.
        hooks["bind_opening_held"]("20260102", [])
    return hooks


def _percent(name):
    hooks = _hooks(name)
    stop = hooks["stop_pct"]
    return (isinstance(stop, float) and math.isfinite(stop)
            and 0 < stop < 1 and callable(hooks["take_profit"]))


PERCENT_BOOKS = tuple(name for name in csv_strategy_names() if _percent(name))
TAKE_BOOKS = tuple(
    name for name in csv_strategy_names()
    if name in {"version1", "version2", "version3", "version5"}
    or name in {"version6", "version6_1"} or name.startswith("version8")
)


def _scan(hooks, *, open=10.0, high=10.01, close=10.008, peak=10.0,
          n_days=1, can_sell=True, hm=600, **kwargs):
    # Mirror csv_minute_backtest's scan kwargs (profit_base defaults to 0,
    # trail_ratio is always 0). Advance an ordinary minute, not EOD.
    params = dict(
        cost=10.0, peak=peak, n_days=n_days, can_sell=can_sell,
        stop_pct=hooks["stop_pct"], take_profit=hooks["take_profit"],
        profit_base=0.0, trail_ratio=0.0,
        sell_gate=hooks.get("sell_gate"), gate_code="000001.SZ",
        gate_day=pd.Timestamp("2026-01-02"),
        daily_closes_ending_yesterday=[10.0] * 30,
        hm=np.array([hm, hm + 1]), peak_gap_min=int(hooks["peak_gap_min"]),
        force_sell_hm=hooks.get("force_sell_hm"),
        reserve_limit_up=bool(hooks.get("reserve_limit_up")),
        defer_limit_up=bool(hooks.get("defer_limit_up")),
        close_clear=hooks.get("close_clear"),
    )
    params.update(kwargs)
    # Omit minute_stop_trigger and FillConfig: use engine defaults, close.
    # A following row marks this as an ordinary minute. In particular v8.6's
    # close_clear fallback belongs to the day boundary, not a quiet-bar probe.
    cursor = HeldMinuteCursor(
        np.array([open, open]), np.array([high, high]),
        np.array([close, close]), **params)
    for phase in ("open", "close"):
        event = cursor.advance(0, phase)
        if event is not None:
            return (*event, cursor.peak, cursor.peak_hm)
    return -1, float("nan"), "", cursor.peak, cursor.peak_hm


def _no_exit(result):
    assert result[0] == -1
    assert math.isnan(result[1])
    assert result[2] == ""


def _exit(result, price, reason):
    assert result[0] == 0
    assert result[1] == pytest.approx(price)
    assert result[2] == reason


@pytest.mark.parametrize("name", csv_strategy_names())
def test_every_registered_book_has_main_engine_dispatch(name):
    hooks = _hooks(name)
    entry = next(e for e in minute_strategy_entries() if e.name == name)
    assert (entry.cli, entry.status, entry.missing_field) == (CLI_MINUTE, "wired", None)
    if name in {"version9_2", "version12"}:
        assert callable(hooks["minute_session"])
        assert callable(hooks["exit_plan"])
    elif name == "version11":
        assert hooks["minute_open"] is True
    elif name == "version9_1":
        assert callable(hooks["bind_absolute_exit"])
    elif name == "version9":
        assert callable(hooks["stop_range"])
    elif name == "version4":
        assert callable(hooks["sell_gate"])
    elif name == "version5":
        assert hooks["force_sell_hm"] is not None
    else:
        assert _percent(name)
    # Special folds/absolute exits stay in test_v92_minute_fold.py,
    # test_v12_minute_fold.py and test_minute_fill_config.py (including v11).


@pytest.mark.parametrize("name", PERCENT_BOOKS)
def test_quiet_bar_does_not_exit(name):
    _no_exit(_scan(_hooks(name)))


@pytest.mark.parametrize("name", PERCENT_BOOKS)
def test_gap_stop_fills_at_open(name):
    hooks = _hooks(name)
    price = 10.0 * (1 - hooks["stop_pct"]) - 0.01
    _exit(_scan(hooks, open=price, close=price + 0.005),
          price, "stop_loss:gap_open")


@pytest.mark.parametrize("name", PERCENT_BOOKS)
def test_close_basis_stop_fills_at_close(name):
    hooks = _hooks(name)
    price = 10.0 * (1 - hooks["stop_pct"]) - 0.01
    _exit(_scan(hooks, close=price), price, "stop_loss:touch")


@pytest.mark.parametrize("name", PERCENT_BOOKS)
@pytest.mark.parametrize("can_sell,n_days", [(False, 1), (True, 0)])
def test_t0_stop_bar_does_not_exit(name, can_sell, n_days):
    hooks = _hooks(name)
    price = 10.0 * (1 - hooks["stop_pct"]) - 0.01
    _no_exit(_scan(hooks, open=price, close=price,
                   can_sell=can_sell, n_days=n_days))


@pytest.mark.parametrize("name", TAKE_BOOKS)
def test_book_take_profit_at_close_and_stop_precedence(name):
    hooks = _hooks(name)
    # Input probes cover drawdown, hold-day ladders, band thresholds and fixed
    # targets. Expected reasons are always obtained from the registered book.
    hits = 0
    for peak, close, n_days in [(12.0, 11.0, 1), (12.0, 11.7, 5),
                               (12.2, 12.0, 1), (10.3, 10.2, 1),
                               (10.5, 10.1, 1), (11.0, 10.0, 1),
                               (11.0, 10.7, 1), (11.0, 10.15, 1),
                               (10.3, 10.05, 2), (12.1, 12.0, 1),
                               (10.5, 10.4, 1), (11.0, 10.5, 1)]:
        reason = hooks["take_profit"](close, 10.0, peak, n_days)
        if not reason:
            _no_exit(_scan(hooks, open=close, high=peak, close=close,
                           peak=peak, n_days=n_days))
            continue
        hits += 1
        _exit(_scan(hooks, open=close, high=peak, close=close,
                    peak=peak, n_days=n_days), close, reason)
        if _percent(name):
            gap = 10.0 * (1 - hooks["stop_pct"]) - 0.01
            _exit(_scan(hooks, open=gap, high=peak, close=close,
                        peak=peak, n_days=n_days), gap, "stop_loss:gap_open")
    assert hits, f"no take-profit probe exercised {name}"


def test_version2_hold_day_drawdown_differs_from_version1():
    for name, days, expected in [("version2", 1, None),
                                 ("version2", 5, "profit_take:drawdown:T+5"),
                                 ("version1", 5, None)]:
        hooks = _hooks(name)
        assert hooks["take_profit"](11.7, 10.0, 12.0, days) == expected
        result = _scan(hooks, open=11.9, high=12.0, close=11.7,
                       peak=12.0, n_days=days)
        if expected:
            _exit(result, 11.7, expected)
        else:
            _no_exit(result)


def test_version5_target_precedes_force_time_and_quiet_bar_forces():
    hooks = _hooks("version5")
    due = hooks["force_sell_hm"]
    reason = hooks["take_profit"](10.2, 10.0, 10.3, 1)
    assert reason == "profit_take:target"
    _exit(_scan(hooks, open=10.1, high=10.3, close=10.2, hm=due), 10.2, reason)
    _no_exit(_scan(hooks, hm=due - 1))
    _exit(_scan(hooks, hm=due), 10.008, "force_sell:time")


def test_version9_prior_range_stop_on_cursor():
    hooks = _hooks("version9")
    days = pd.bdate_range("2025-09-01", periods=23)
    frame = pd.DataFrame({"open": 10.0, "high": 10.2,
                          "low": 10.0, "close": 10.0}, index=days)
    frame.loc[days[-1], "high"] = 100.0  # today's range must not leak in
    ratio = evaluate_stop_range(hooks, frame, days[-1], {})
    assert ratio == pytest.approx(0.02)
    _no_exit(_scan(hooks, close=9.5))  # no fixed eight-percent fallback
    _exit(_scan(hooks, close=9.5, stop_range_ratio=ratio), 9.5, "stop_loss:touch")
    _exit(_scan(hooks, open=9.5, close=9.6, stop_range_ratio=ratio),
          9.5, "stop_loss:gap_open")


def test_limit_down_open_blocks_stop_bar():
    # blocked_bar is the cursor gate; the outer defer_sell_open_or_fill gate
    # is covered by tests/test_limit_pair_b5.py.
    _no_exit(_scan(_hooks("version1"), open=9.0, high=9.1, close=9.05,
                   limit_down=9.0))


# topk_dropout / topk_score_exit participate in all percent-stop tests above.
# Dropout/SX0 sells are engine planned_for_day decisions, not cursor callbacks;
# planning/execution is covered by tests/test_topk_minute_exec.py and
# tests/test_topk_dropout_book_c.py.
