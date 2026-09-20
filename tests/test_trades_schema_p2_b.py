"""Human GO P2=B: additive book labels, data-free prices and reader contracts."""

import csv

import pandas as pd
import pytest

from backtest.research.ashare_fill_clock import FillPriceRule, SessionPhase
from backtest.research.ashare_volume_cap import BucketVolume, VolumeCap
from backtest.research.capital_ration_probe import report_capital_ration
from backtest.research.csv_artifacts import write_run_artifacts
from backtest.research.csv_ledger import SimState, _sell, execute_buy
from backtest.research.csv_simulate_loop import append_equity_and_eod_marks
from backtest.research.exdiv_hold_hits import parse_hold_lots
from tests.test_ashare_fill_clock import (
    TARGET, _assert_book_labels, _daily_marks, _minute_day, _sells, minute_sim,
)

DAY = pd.Timestamp("2025-11-03")
NEXT_DAY = pd.Timestamp("2025-11-04")
LABELS = {"session_phase", "price_rule"}


def _minute_state(hhmm, row):
    days = ["2025-11-03", "2025-11-04"]
    return minute_sim.simulate(
        {TARGET: pd.concat([
            _minute_day(days[0], [(1455, 10.0, 10.0, 10.0, 10.0)]),
            _minute_day(days[1], [(hhmm, *row)]),
        ])},
        {TARGET: _daily_marks(days, [10.0, row[-1]])},
        {"20251103": [TARGET]}, "20251103", "20251104",
        strategy="version6", stop_pct=0.02,
    )


@pytest.mark.parametrize("hhmm,phase", [
    (930, SessionPhase.continuous), (1456, SessionPhase.continuous),
    (1457, SessionPhase.closing_call), (1500, SessionPhase.closing_call),
])
@pytest.mark.parametrize("row,price,reason,rule", [
    ((9.40, 9.50, 9.30, 9.45), 9.40, "stop_loss:gap_open", FillPriceRule.minute_gap_open),
    ((9.90, 9.95, 9.60, 9.70), 9.70, "stop_loss:touch", FillPriceRule.minute_trigger_bar_close),
])
def test_minute_price_oracles_emit_labels_without_changing_p1_eligibility(
    hhmm, phase, row, price, reason, rule,
):
    # Same open/close oracles as the fill-clock scanner tests, through real writers.
    st = _minute_state(hhmm, row)
    sell = _sells(st)[0]
    assert sell["date"] == "20251104"
    assert sell["price"] == pytest.approx(price)
    assert sell["reason"] == reason
    _assert_book_labels(st, rule, phase.value)
    assert st.cash == pytest.approx(21_000_000 - 1_001_000 + price * 100_000 * .999)
    assert st.equity_curve[-1][1] == st.cash
    assert not st.positions


@pytest.mark.parametrize("reason", [
    "trail:T+1", "profit_take:drawdown:50", "force_sell:time", "open_board", "ma_signal:MA5",
])
def test_unmapped_minute_sells_keep_both_labels_empty(monkeypatch, reason):
    # Isolate the writer mapping: a successful scanner result remains unchanged.
    monkeypatch.setattr(minute_sim, "scan_held_day", lambda *a, **k: (0, 10.1, reason, 10.1, 897))
    st = _minute_state(1457, (10.1, 10.1, 10.1, 10.1))
    sell = _sells(st)[0]
    assert (sell["price"], sell["shares"], sell["reason"]) == (10.1, 100_000, reason)
    assert sell["session_phase"] == sell["price_rule"] == ""


@pytest.mark.parametrize("hm,phase", [
    (None, ""), (9 * 60 + 24, ""), (11 * 60 + 31, ""), (12 * 60 + 59, ""),
    (15 * 60 + 1, ""), (9 * 60 + 30, "continuous"), (14 * 60 + 57, "closing_call"),
])
def test_ledger_unknown_phase_never_rejects_a_fill(hm, phase):
    st = SimState(cash=2000.0)
    assert execute_buy(st, TARGET, 10.0, 1000.0, 0, DAY)
    _sell(st, TARGET, st.positions[TARGET][0], 9.4, NEXT_DAY, "stop_loss:gap_open",
          hm=hm, price_rule=FillPriceRule.minute_gap_open.value)
    sell = _sells(st)[0]
    assert (sell["price"], sell["shares"], sell["reason"]) == (9.4, 100, "stop_loss:gap_open")
    assert sell["session_phase"] == phase
    assert sell["price_rule"] == "minute_gap_open"
    assert st.cash == pytest.approx(1938.06)
    assert not st.positions


def test_linked_lots_inherit_labels_and_keep_price_shares_reason():
    st = SimState(cash=5000.0)
    assert execute_buy(st, TARGET, 10.0, 1000.0, 0, DAY)
    assert execute_buy(st, TARGET, 10.0, 2000.0, 0, DAY, ride_with=0)
    _sell(st, TARGET, st.positions[TARGET][0], 9.7, NEXT_DAY, "stop_loss:touch",
          hm=897, price_rule="minute_trigger_bar_close")
    sells = _sells(st)
    assert [(t["price"], t["shares"], t["reason"]) for t in sells] == [
        (9.7, 100, "stop_loss:touch"), (9.7, 200, "stop_loss:touch"),
    ]
    assert {(t["session_phase"], t["price_rule"]) for t in sells} == {
        ("closing_call", "minute_trigger_bar_close"),
    }
    assert st.cash == pytest.approx(4904.09)
    assert not st.positions


def _zero_cap():
    return VolumeCap(.1, {
        (TARGET, "20251104", 897): BucketVolume(0, 897, "raw_shares_incremental"),
    })


def test_skips_do_not_inherit_attempted_fill_labels():
    st = SimState(cash=3000.0)
    assert execute_buy(st, TARGET, 10.0, 1000.0, 0, DAY)
    st.volume_cap = _zero_cap()
    _sell(st, TARGET, st.positions[TARGET][0], 9.7, NEXT_DAY, "stop_loss:touch",
          day_i=1, bucket_id=897, hm=897, price_rule="minute_trigger_bar_close")
    assert not execute_buy(st, TARGET, 10.0, 500.0, 1, NEXT_DAY, bucket_id=897)
    assert [t["side"] for t in st.trades] == ["BUY", "SKIP", "SKIP"]
    assert all(t["session_phase"] == t["price_rule"] == "" for t in st.trades)
    assert st.cash == 1999.0
    assert st.positions[TARGET][0].shares == 100


@pytest.mark.parametrize("side", ["BUY", "SELL", "SKIP", "EOD_MARK"])
def test_each_canonical_writer_supplies_csv_label_columns(tmp_path, side):
    st = SimState(cash=3000.0)
    assert execute_buy(st, TARGET, 10.0, 1000.0, 0, DAY)
    if side == "SELL":
        _sell(st, TARGET, st.positions[TARGET][0], 9.7, NEXT_DAY, "stop_loss:touch",
              hm=897, price_rule="minute_trigger_bar_close")
    elif side == "SKIP":
        st.volume_cap = _zero_cap()
        assert not execute_buy(st, TARGET, 10.0, 500.0, 1, NEXT_DAY, bucket_id=897)
    elif side == "EOD_MARK":
        append_equity_and_eod_marks(st, ds="20251103", day=DAY, calendar_last=DAY, mark_bars={})
    row = st.trades[-1]
    assert row["side"] == side
    assert LABELS <= row.keys()
    if side != "SELL":
        assert row["session_phase"] == row["price_rule"] == ""
    # Even when this is the only row, the writer derives both columns from it.
    st.trades = [row]
    write_run_artifacts(tmp_path, st, "summary", "help")
    with (tmp_path / "trades.csv").open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        assert LABELS <= set(reader.fieldnames)
        written = next(reader)
    assert {key: written[key] for key in LABELS} == {key: row[key] for key in LABELS}


def test_downstream_readers_keep_old_required_columns_and_ignore_additions(tmp_path):
    def hold_intervals(path):
        lots, ignored = parse_hold_lots(path)
        # Raw source rows retain optional columns; interpreted holds stay identical.
        return [(p.code, p.lot, p.entry_date, p.exit_date, p.sell_reason) for p in lots], ignored

    trades = tmp_path / "trades.csv"
    pool = tmp_path / "pool"
    pool.mkdir()
    (pool / "20251103.csv").write_text("600000\n", encoding="utf-8")
    old = ("date,code,side,price,shares,notional,commission,reason,lot\n"
           "20251103,600000.SH,BUY,10.0,100,1000.0,1.0,pool,0\n"
           "20251104,600000.SH,SELL,9.4,100,940.0,0.94,stop_loss:gap_open,0\n")
    trades.write_text(old, encoding="utf-8")
    holds = hold_intervals(trades)
    ration = report_capital_ration(trades, pool)
    header, buy, sell = old.splitlines()
    trades.write_text(
        header + ",session_phase,price_rule,future_column\n"
        + buy + ",,,unused\n"
        + sell + ",closing_call,minute_gap_open,unused\n", encoding="utf-8",
    )
    assert hold_intervals(trades) == holds
    assert report_capital_ration(trades, pool) == ration
    # exdiv_hold_hits still needs only these five historical columns.
    trades.write_text("date,code,side,reason,lot\n"
                      "20251103,600000.SH,BUY,pool,0\n"
                      "20251104,600000.SH,SELL,stop_loss:gap_open,0\n", encoding="utf-8")
    assert hold_intervals(trades) == holds
