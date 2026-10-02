"""Identified analysis exports retain zero-cost bonus shares in their source lot."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from backtest.research.ashare_exdiv_economics import ExDivEvent
from backtest.research.csv_analysis_export import (
    BUNDLE_CSV,
    load_nav,
    load_trades,
    pair_round_trips,
    positions_daily,
    write_bundle,
)
from backtest.research.csv_artifacts import write_run_artifacts
from tests.test_s8_independent_positions import CODE, _ds, _run

OLD = "600000.SH@20260106"
NEW = "600000.SH@20260107"


def _input(tmp_path: Path, rows: list[str], *, lot: bool = True) -> Path:
    run = tmp_path / "run"
    run.mkdir()
    header = "date,code,side,price,shares,commission,reason,position_id,lot"
    if not lot:
        header = header.rsplit(",", 1)[0]
        rows = [row.rsplit(",", 1)[0] for row in rows]
    (run / "trades.csv").write_text(header + "\n" + "\n".join(rows) + "\n", encoding="utf-8")
    (run / "daily_equity.csv").write_text(
        "date,equity\n20260106,10000\n20260107,10000\n20260108,10000\n"
        "20260109,10000\n20260112,10000\n",
        encoding="utf-8",
    )
    return run


def _assert_costs_and_proceeds(trades: pd.DataFrame, trips: pd.DataFrame) -> None:
    buys = trades[trades.side == "BUY"]
    sells = trades[trades.side == "SELL"]
    closed = trips[trips.status == "closed"]
    assert trips.buy_notional.sum() == pytest.approx(buys.notional.sum())
    assert trips.buy_commission.sum() == pytest.approx(buys.commission.sum())
    assert closed.shares.sum() == pytest.approx(sells.shares.sum())
    assert closed.sell_notional.sum() == pytest.approx(sells.notional.sum())
    assert closed.sell_commission.sum() == pytest.approx(sells.commission.sum())
    assert (closed.sell_notional - closed.sell_commission).sum() == pytest.approx(
        (sells.notional - sells.commission).sum()
    )


@pytest.mark.parametrize("lot", [False, True])
def test_identified_sell_above_bought_shares_has_no_extra_cost(tmp_path: Path, lot: bool):
    run = _input(tmp_path, [
        f"20260106,600000.SH,BUY,10,100000,1000,pool,{OLD},0",
        f"20260108,600000.SH,SELL,9.5,200000,1900,open_board,{OLD},0",
    ], lot=lot)
    trades = load_trades(run)
    _, trips, ledger = pair_round_trips(trades, load_nav(run))
    _assert_costs_and_proceeds(trades, trips)
    assert set(trips.position_id) == {OLD}
    assert set(trips.buy_date) == {"2026-01-06"}
    assert set(trips.sell_date) == {"2026-01-08"}
    assert set(trips.sell_reason) == {"open_board"}
    assert trips.realized_pnl.sum() == pytest.approx(897100)
    assert set(trips.status) == {"closed"}
    if lot:
        assert set(trips.lot) == {0}
    sell_ledger = ledger[ledger.event == "sell"]
    assert set(sell_ledger.position_id) == {OLD}
    assert sell_ledger.amount_after.iloc[-1] == 0


@pytest.mark.parametrize("lot", [False, True])
def test_identified_bonus_defer_lines_keep_exhausted_buy_origin(tmp_path: Path, lot: bool):
    run = _input(tmp_path, [
        f"20260106,600000.SH,BUY,10,100,1,pool,{OLD},0",
        f"20260107,600000.SH,SELL,11,40,0.4,exit,{OLD},0",
        f"20260108,600000.SH,SELL,12,60,0.6,exit|t1_deferred,{OLD},0",
        f"20260109,600000.SH,SELL,13,50,0.5,exit|t1_deferred,{OLD},0",
        f"20260112,600000.SH,SELL,14,50,0.5,exit|t1_deferred,{OLD},0",
    ], lot=lot)
    trades = load_trades(run)
    _, trips, ledger = pair_round_trips(trades, load_nav(run))
    _assert_costs_and_proceeds(trades, trips)
    assert set(trips.position_id) == {OLD}
    assert set(trips.buy_date) == {"2026-01-06"}
    if lot:
        assert set(trips.lot) == {0}
    assert trips.groupby("sell_date").shares.sum().to_dict() == {
        "2026-01-07": 40, "2026-01-08": 60, "2026-01-09": 50, "2026-01-12": 50,
    }
    bonus = trips[trips.sell_date >= "2026-01-09"]
    assert set(bonus.sell_reason) == {"exit|t1_deferred"}
    assert bonus.buy_notional.sum() == 0
    assert bonus.buy_commission.sum() == 0
    assert set(ledger[ledger.event == "sell"].position_id) == {OLD}
    assert trips.realized_pnl.sum() == pytest.approx(1507)


def test_bonus_excess_does_not_consume_other_positions_or_lots(tmp_path: Path):
    run = _input(tmp_path, [
        f"20260106,600000.SH,BUY,10,100,1,pool,{OLD},0",
        f"20260107,600000.SH,BUY,20,200,2,add,{OLD},1",
        f"20260107,600000.SH,BUY,30,100,3,pool,{NEW},0",
        f"20260108,600000.SH,SELL,11,250,2.5,exit_old,{OLD},0",
        f"20260109,600000.SH,SELL,31,200,2,exit_new,{NEW},0",
        f"20260112,600000.SH,EOD_MARK,21,200,0,,{OLD},1",
    ])
    trades = load_trades(run)
    nav = load_nav(run)
    _, trips, _ = pair_round_trips(trades, nav)
    _assert_costs_and_proceeds(trades, trips)
    old_closed = trips[(trips.position_id == OLD) & (trips.status == "closed")]
    assert set(old_closed.lot) == {0}
    assert old_closed.shares.sum() == 250
    assert old_closed.buy_notional.sum() == 1000
    assert old_closed.buy_commission.sum() == 1
    assert old_closed.realized_pnl.sum() == pytest.approx(1746.5)
    newer = trips[trips.position_id == NEW]
    assert set(newer.lot) == {0}
    assert newer.shares.sum() == 200
    assert newer.buy_notional.sum() == 3000
    assert newer.buy_commission.sum() == 3
    assert newer.realized_pnl.sum() == pytest.approx(3195)
    opened = trips[trips.status == "open_eod"]
    assert opened[["position_id", "lot", "shares"]].to_dict("records") == [
        {"position_id": OLD, "lot": 1, "shares": 200},
    ]
    assert opened.mtm_pnl.sum() == 198
    positions = positions_daily(trades, nav)
    final = positions[positions.date == "2026-01-12"]
    assert final.position_id.tolist() == [OLD]
    assert final.shares.tolist() == [200]


def test_bonus_after_merged_tail_buys_allocates_buy_cost_only_once(tmp_path: Path):
    run = _input(tmp_path, [
        f"20260106,600000.SH,BUY,10,100,1,tail,{OLD},0",
        f"20260106,600000.SH,BUY,12,100,2,tail,{OLD},0",
        f"20260108,600000.SH,SELL,7,400,4,exit,{OLD},0",
    ])
    trades = load_trades(run)
    _, trips, _ = pair_round_trips(trades, load_nav(run))
    _assert_costs_and_proceeds(trades, trips)
    assert set(trips.position_id) == {OLD}
    assert set(trips.lot) == {0}
    assert trips.realized_pnl.sum() == pytest.approx(593)


@pytest.mark.parametrize("buy_source", ["other_position", "legacy", "future"])
def test_unknown_identified_sell_cannot_invent_buy_origin(tmp_path: Path, buy_source: str):
    prior_id = "" if buy_source == "legacy" else OLD
    rows = [
        f"20260106,600000.SH,BUY,10,100,1,pool,{prior_id},0",
        f"20260107,600000.SH,SELL,11,200,2,exit,{NEW},0",
    ]
    if buy_source == "future":
        rows.append(f"20260108,600000.SH,BUY,10,100,1,pool,{NEW},0")
    run = _input(tmp_path, rows)
    with pytest.raises(SystemExit, match=rf"unmatched SELL.*position_id={NEW}"):
        write_bundle(run, tmp_path / "analysis", account=10000)


@pytest.mark.parametrize("mode,deferred", [
    pytest.param("daily", False, id="kimi_bonus_unlocked"),
    pytest.param("daily", True, id="bonus_defer_daily"),
    pytest.param("minute_off", True, id="bonus_defer_minute_off"),
    pytest.param("minute_on", True, id="bonus_defer_minute_on"),
])
def test_s8_bonus_engine_writer_analysis_conserves_nav(tmp_path: Path, mode: str, deferred: bool):
    # Unlocked daily reproduces Kimi s5: 100k BUY -> one 200k SELL at 9.5.
    # Defer separates original and bonus shares into more SELL rows than BUY lots.
    prices = [10.0, 4.5, 4.6, 4.7] if deferred else [10.0, 10.0, 9.5, 9.5]
    st = _run(
        mode, "version8", prices, [0],
        exdiv={CODE: {_ds(1): 0.5}},
        exdiv_economics={
            (CODE, _ds(1)): ExDivEvent("bonus", 1, 0, _ds(1), _ds(1), _ds(2 if deferred else 1)),
        },
    )
    buys = [trade for trade in st.trades if trade["side"] == "BUY"]
    sells = [trade for trade in st.trades if trade["side"] == "SELL"]
    assert len(buys) == 1
    assert sum(trade["shares"] for trade in buys) == 100000
    assert sum(trade["shares"] for trade in sells) == 200000
    if deferred:
        assert len(sells) > len(buys)
        assert sells[-1]["reason"].endswith("|t1_deferred")
    else:
        assert len(sells) == 1
        assert sells[0]["price"] == 9.5
    assert not st.positions
    run = tmp_path / "run"
    write_run_artifacts(run, st, text="s8 explicit bonus economics", help_lock="")
    before = {name: (run / name).read_bytes() for name in ("trades.csv", "daily_equity.csv")}
    out = tmp_path / "analysis"
    product = write_bundle(run, out, account=21_000_000)
    for name in BUNDLE_CSV:
        assert (out / name).is_file()
    assert {name: (run / name).read_bytes() for name in before} == before
    trades = load_trades(run)
    trips = pd.read_csv(out / "round_trips.csv")
    _assert_costs_and_proceeds(trades, trips)
    assert set(trips.position_id) == {f"{CODE}@{_ds(0)}"}
    assert set(trips.lot) == {0}
    assert set(trips.status) == {"closed"}
    for sell in sells:
        date = pd.Timestamp(sell["date"]).strftime("%Y-%m-%d")
        rows = trips[(trips.sell_date == date) & (trips.sell_reason == sell["reason"])]
        assert rows.shares.sum() == sell["shares"]
        assert rows.sell_notional.sum() == pytest.approx(sell["notional"])
        assert rows.sell_commission.sum() == pytest.approx(sell["commission"])
    nav_delta = float(load_nav(run).equity.iloc[-1]) - 21_000_000
    assert trips.realized_pnl.sum() + trips.mtm_pnl.sum() == pytest.approx(nav_delta)
    assert product["summary"]["pnl_total"] == pytest.approx(nav_delta)
    assert nav_delta == pytest.approx(-81920 if deferred else 897100)
    positions = pd.read_csv(out / "positions_daily.csv")
    final_day = pd.Timestamp(_ds(3)).strftime("%Y-%m-%d")
    assert positions[positions.date == final_day].empty
