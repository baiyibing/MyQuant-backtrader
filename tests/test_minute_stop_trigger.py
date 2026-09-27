"""P1 opt-in H/L contract, including both shared-minute sell implementations."""

import json
from dataclasses import asdict

import numpy as np
import pandas as pd
import pytest

from backtest.research import csv_minute_backtest as minute
from backtest.research.csv_minute_backtest_v7 import build_parser
from backtest.research.minute_cash_order import HeldMinuteCursor
from backtest.research.strategy5_rules import take_profit_reason


@pytest.fixture(params=["python", "dispatcher", "cursor"])
def scan(request):
    def run(rows, **overrides):
        o, h, l, c = np.asarray(rows, dtype=float).T
        opts = dict(cost=10., peak=10., n_days=1, can_sell=True,
                    stop_pct=0.05, profit_base=100., trail_ratio=0.,
                    minute_stop_trigger="hl", l=l, take_profit=take_profit_reason,
                    take_profit_pct=0.02, limit_down=9.)
        opts.update(overrides)
        if request.param == "cursor":
            cursor = HeldMinuteCursor(o, h, c, **opts)
            for i in range(len(c)):
                for phase in ("open", "close"):
                    event = cursor.advance(i, phase)
                    if event is not None:
                        return event
            return (-1, float("nan"), "")
        scanner = minute.scan_held_day_python if request.param == "python" else minute.scan_held_day
        if request.param == "dispatcher":
            opts["use_numba"] = True  # hl must not silently use the close-only kernel
        return scanner(o, h, c, **opts)[:3]
    return run


@pytest.mark.parametrize("rows,expected", [
    ([(10, 10.1, 9.4, 10)], (0, 9.5, "stop_loss:touch")),
    ([(10, 10.3, 9.8, 10)], (0, 10.2, "profit_take:target")),
    ([(9.4, 10, 9.3, 9.8)], (0, 9.4, "stop_loss:gap_open")),
    ([(10.3, 10.4, 9.8, 10)], (0, 10.3, "profit_take:target")),
    ([(10, 10.3, 9.4, 10)], (0, 9.5, "stop_loss:touch")),
    ([(10.3, 10.4, 9.4, 10)], (0, 9.5, "stop_loss:touch")),
    ([(9, 9, 9, 9), (9.4, 9.6, 9.3, 9.5)], (1, 9.4, "stop_loss:gap_open")),
])
def test_hl_contract(scan, rows, expected):
    idx, px, reason = scan(rows)
    assert (idx, reason) == (expected[0], expected[2])
    assert px == pytest.approx(expected[1])


@pytest.mark.parametrize("overrides", [{"n_days": 0}, {"can_sell": False}])
def test_t1_unchanged(scan, overrides):
    assert scan([(10, 11, 9.1, 9.2)], **overrides)[0] == -1


def test_floor_locked_bar_cannot_fill(scan):
    assert scan([(9, 9, 9, 9)])[0] == -1


def test_close_keeps_rebound_and_close_fill(scan):
    assert scan([(10, 10.3, 9.4, 10)], minute_stop_trigger="close")[0] == -1
    assert scan([(10, 10.1, 9.3, 9.4)], minute_stop_trigger="close")[1] == 9.4


def test_hl_requires_low(scan):
    with pytest.raises(ValueError, match="low"):
        scan([(10, 10, 9, 10)], l=None)


def case(strategy="version5", cash_order=False, rows=None):
    rows = rows or [(10, 10.3, 9.8, 10)]
    days = ["20260901"] + ["20260902"] * len(rows)
    hm = [895] + list(range(600, 600 + len(rows)))
    frame = pd.DataFrame([(10, 10, 10, 10)] + rows, columns=["open", "high", "low", "close"])
    frame["ymd"], frame["hm"], frame["volume"] = days, hm, 100_000
    frame.index = pd.to_datetime(days) + pd.to_timedelta(hm, unit="m")
    daily = pd.DataFrame({k: [10., 10., 10.] for k in ["open", "high", "low", "close"]},
                         index=pd.to_datetime(["20260831", "20260901", "20260902"]))
    return dict(minute_bars={"600000.SH": frame}, daily_bars={"600000.SH": daily},
                pool_days={"20260901": ["600000.SH"]}, start="20260901", end="20260902",
                strategy=strategy, total_cash=100_000., daily_quota=10_000., name_budget=10_000.,
                stop_pct=0.05, fix_minute_cash_order=cash_order)


@pytest.mark.parametrize("cash_order", [False, True])
@pytest.mark.parametrize("strategy", ["version3", "version8", "version8_4", "version8_5"])
@pytest.mark.parametrize("rows,price", [
    ([(10, 10.1, 9.4, 10)], 9.5),
    ([(9, 9, 9, 9), (9.4, 9.6, 9.3, 9.5)], 9.4),
])
def test_engine_wiring_stop(cash_order, strategy, rows, price):
    st = minute.simulate(**case(strategy, cash_order, rows), minute_stop_trigger="hl")
    sells = [t for t in st.trades if t["side"] == "SELL"]
    assert len(sells) == 1
    assert sells[0]["price"] == pytest.approx(price)


@pytest.mark.parametrize("cash_order", [False, True])
@pytest.mark.parametrize("strategy,target", [("version3", 12.), ("version5", 10.2),
                                              ("version8_4", 12.), ("version8_5", 10.4)])
def test_engine_wiring_target(cash_order, strategy, target):
    st = minute.simulate(**case(strategy, cash_order, [(10, target, 9.8, 10)]), minute_stop_trigger="hl")
    sells = [t for t in st.trades if t["side"] == "SELL"]
    assert len(sells) == 1
    assert sells[0]["price"] == pytest.approx(target)


@pytest.mark.parametrize("cash_order", [False, True])
@pytest.mark.parametrize("strategy", ["version1", "version2", "version3", "version5", "version6",
                                      "version8", "version8_1", "version8_2", "version8_3",
                                      "version8_4", "version8_5", "version8_6"])
def test_omitted_and_explicit_close_byte_stable(cash_order, strategy):
    kwargs = case(strategy, cash_order, [(10, 10.3, 9.3, 9.4)])
    def frozen(st):
        return json.dumps(asdict(st), default=str, sort_keys=True).encode()
    assert frozen(minute.simulate(**kwargs)) == frozen(minute.simulate(**kwargs, minute_stop_trigger="close"))


@pytest.mark.parametrize("strategy,extra", [("version12", []), ("12", []), ("v12", []),
                                            ("version11", ["--fix-s11-exit-domain"])])
def test_cli_rejects_before_io(strategy, extra, capsys):
    with pytest.raises(SystemExit) as exc:
        minute.main(["--strategy", strategy, "--minute-stop-trigger", "hl"] + extra)
    assert exc.value.code == 2
    assert "--minute-stop-trigger hl rejects" in capsys.readouterr().err


@pytest.mark.parametrize("mode", ["hl", "close"])
def test_v7_rejects_flag(mode, capsys):
    parser = build_parser()
    assert "v7 不接 --minute-stop-trigger" in parser.format_help()
    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["--start", "20260901", "--end", "20260902", "--minute-stop-trigger", mode])
    assert exc.value.code == 2
    assert "unrecognized arguments" in capsys.readouterr().err


@pytest.mark.parametrize("entry", [minute.simulate, minute.run])
@pytest.mark.parametrize("extra", [{"strategy": "v12"}, {"strategy": "version11", "fix_s11_exit_domain": True}])
def test_api_rejects_before_io(entry, extra):
    kwargs = case()
    kwargs.update(extra, minute_stop_trigger="hl")
    if entry is minute.run:
        for key in ["minute_bars", "daily_bars", "pool_days"]:
            kwargs.pop(key)
    with pytest.raises(ValueError, match="--minute-stop-trigger hl rejects"):
        entry(**kwargs)


@pytest.mark.parametrize("flags,mode", [([], "close"), (["--minute-stop-trigger", "close"], "close"),
                                       (["--minute-stop-trigger", "hl"], "hl"),
                                       (["--minute-stop-trigger", "hl", "--fix-minute-cash-order"], "hl")])
def test_cli_passes_mode_to_run(monkeypatch, tmp_path, flags, mode):
    class ReachedRun(Exception):
        pass

    def capture(*args, **kwargs):
        assert kwargs["minute_stop_trigger"] == mode
        assert kwargs["fix_minute_cash_order"] == ("--fix-minute-cash-order" in flags)
        raise ReachedRun

    monkeypatch.setattr(minute, "run", capture)
    with pytest.raises(ReachedRun):
        minute.main(["--strategy", "version8", "--pool-dir", str(tmp_path)] + flags)


def test_s12_price_domain_retains_existing_version12_boundary():
    # The plan's nominally orthogonal flag is currently version12-only.
    # hl must not silently route into that strategy's separate scanner.
    with pytest.raises(ValueError, match="--minute-stop-trigger hl rejects"):
        minute.run("20260901", "20260902", strategy="version12",
                   minute_stop_trigger="hl", fix_s12_price_domain=True)
