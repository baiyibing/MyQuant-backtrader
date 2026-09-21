"""Data-free integration pins for PR #156's binding Q2 + full H2 cut."""

from datetime import date, timedelta
import json

import pandas as pd
import pytest

from backtest.research import csv_ledger as ledger
from backtest.research import csv_minute_backtest as book
from backtest.research import csv_minute_backtest_v7 as v7
from backtest.research import unified_exit_modea as modea
from backtest.research import unified_exit_modeb as modeb
from backtest.research.fullstrat_research_hooks import (
    NEXT_OPEN,
    OpenCandidate,
    ResearchFillConfig,
    ResearchOrder,
    ResearchSession,
    available_at,
    simulate_book,
    simulate_v7,
    stamp,
    run_modeb,
)
from scripts.research import run_minute_sensitivity_b_batch4_fullstrat as harness

CODE = "600000.SH"
DAY = date(2026, 9, 1)


def bars(rows):
    """(day offset, hm, open, close) in START wall-clock labels."""
    data = [
        dict(
            ymd=(DAY + timedelta(days=d)).strftime("%Y%m%d"),
            hm=hm,
            open=op,
            high=max(op, close),
            low=min(op, close),
            close=close,
        )
        for d, hm, op, close in rows
    ]
    frame = pd.DataFrame(data)
    frame.index = pd.DatetimeIndex(
        [stamp(DAY + timedelta(days=d), hm) for d, hm, _, _ in rows]
    )
    return {CODE: frame}


def daily(values):
    return {
        CODE: pd.DataFrame(
            dict(open=values, high=values, low=values, close=values),
            index=pd.date_range(DAY - timedelta(days=1), periods=len(values)),
        )
    }


def candidate(day, hm, px):
    return OpenCandidate(stamp(day, hm), px, (11.0, 9.0))


@pytest.mark.parametrize("bp", [5, 10, 20])
def test_clock_xor_slip(bp):
    with pytest.raises(ValueError, match="XOR"):
        ResearchFillConfig(NEXT_OPEN, bp)
    with pytest.raises(ValueError):
        harness.run_book(
            "version1",
            start="x",
            end="y",
            pool_dir=None,
            qlib_root=None,
            work_root=None,
            clock_mode=NEXT_OPEN,
            slip_bp_per_side=bp,
        )


@pytest.mark.parametrize(
    "clock,bp,fill",
    [
        (NEXT_OPEN, 0, 10.1),
        ("production_default", 5, 10.005),
        ("production_default", 10, 10.01),
        ("production_default", 20, 10.02),
    ],
)
def test_q2_resizes_tentative_1000_and_fills_instead_of_q1_terminal_reject(
    clock, bp, fill
):
    state = ledger.SimState(cash=10050)
    initial_shares, _ = ledger._buy_size(10000, 10)
    assert initial_shares == 1000
    if clock == NEXT_OPEN:
        assert 1000 * fill * 1.001 > state.cash  # Q1 anti-pattern would reject.
    audit = []
    session = ResearchSession(ResearchFillConfig(clock, bp), DAY, audit)
    session.submit(
        ResearchOrder(
            CODE,
            "buy",
            available_at(DAY, 585),
            10,
            initial_shares,
            lambda px, at: ledger.execute_buy(state, CODE, px, 10000, 0, DAY),
            [candidate(DAY, 587, 10.1)],
        )
    )
    assert state.cash == 10050 if clock == NEXT_OPEN else state.cash < 10050
    session.run()
    trade = state.trades[0]
    assert trade["shares"] == 900
    assert trade["price"] == pytest.approx(fill)
    assert trade["commission"] == pytest.approx(900 * fill * 0.001)
    assert state.cash == pytest.approx(10050 - 900 * fill * 1.001)
    assert audit[0]["status"] == "FILLED"
    assert "cash_reject_terminal" not in json.dumps(audit)


def test_book_q2_actual_adapter_fallback_fill_and_late_entry_all_cash():
    minute = bars([(0, 893, 10, 10), (0, 896, 10.1, 10.1)])
    kwargs = dict(strategy="version1", total_cash=10050, daily_quota=10000)
    state = simulate_book(
        minute,
        daily([10, 10.1]),
        {"20260901": [CODE]},
        "20260901",
        "20260901",
        clock_mode=NEXT_OPEN,
        **kwargs,
    )
    buys = [t for t in state.trades if t["side"] == "BUY"]
    assert len(buys) == 1
    assert buys[0]["shares"] == 900
    assert buys[0]["price"] == 10.1
    assert state.cash == pytest.approx(950.91)
    assert buys[0]["research_fill_at"].endswith("14:56:00")
    late = bars([(0, hm, 10, 10) for hm in range(895, 901)])
    state = simulate_book(
        late,
        daily([10, 10]),
        {"20260901": [CODE]},
        "20260901",
        "20260901",
        clock_mode=NEXT_OPEN,
        **kwargs,
    )
    assert not state.positions and not state.trades
    assert state.equity_curve == [("20260901", 10050)]
    assert state.stats.get("skip_cash", 0) == 0
    assert state.stats["research_buy_expired"] == 1
    assert state.research_orders[0]["reason"] == "same_day_expiry"


@pytest.mark.parametrize("bp", [5, 10, 20])
def test_book_slip_resizes_all_buys_reprices_sell_fees_and_marks(bp):
    minute = bars([(0, 895, 10, 10), (1, 570, 9.7, 9.7)])
    state = simulate_book(
        minute,
        daily([10, 10, 9.7]),
        {"20260901": [CODE]},
        "20260901",
        "20260902",
        strategy="version1",
        total_cash=10050,
        daily_quota=10000,
        slip_bp_per_side=bp,
    )
    buy, sell = [t for t in state.trades if t["side"] in ("BUY", "SELL")]
    assert buy["shares"] == 900
    assert buy["price"] == pytest.approx(10 * (1 + bp / 10000))
    assert sell["price"] == pytest.approx(9.7 * (1 - bp / 10000))
    assert sell["commission"] == pytest.approx(sell["shares"] * sell["price"] * 0.001)
    assert state.equity_curve[0][1] == pytest.approx(
        10050 - buy["notional"] - buy["commission"] + 900 * 10
    )
    assert state.cash == pytest.approx(
        10050
        - buy["notional"]
        - buy["commission"]
        + sell["notional"]
        - sell["commission"]
    )


def test_book_sell_expiry_rechecks_strategy_next_session():
    minute = bars(
        [
            (0, 893, 10, 10),
            (0, 896, 10, 10),
            (1, 895, 10, 9.7),
            (1, 896, 9.7, 9.7),
            (2, 570, 10, 10),
            (2, 572, 10, 10),
            (3, 570, 9.7, 9.7),
            (3, 571, 9.6, 9.6),
        ]
    )
    state = simulate_book(
        minute,
        daily([10, 10, 9.7, 10, 9.6]),
        {"20260901": [CODE]},
        "20260901",
        "20260904",
        strategy="version1",
        total_cash=10050,
        daily_quota=10000,
        clock_mode=NEXT_OPEN,
    )
    sells = [t for t in state.trades if t["side"] == "SELL"]
    assert [t["date"] for t in sells] == ["20260904"]
    audits = [r for r in state.research_orders if r["side"] == "sell"]
    assert [r["status"] for r in audits] == ["UNFILLED", "FILLED"]
    assert audits[0]["reason"] == "same_day_expiry"


def test_next_open_limits_t1_expiry_and_no_future_sell_funding():
    state = ledger.SimState(cash=50)
    audit = []
    session = ResearchSession(ResearchFillConfig(NEXT_OPEN), DAY, audit)
    session.submit(
        ResearchOrder(
            CODE,
            "buy",
            available_at(DAY, 585),
            10,
            1000,
            lambda px, at: ledger.execute_buy(state, CODE, px, 10000, 0, DAY),
            [candidate(DAY, 587, 10)],
        )
    )
    session.at(stamp(DAY, 600), lambda: setattr(state, "cash", state.cash + 10000))
    session.run()
    assert not state.positions and state.cash == 10050
    assert audit[0]["status"] == "UNFILLED"
    for side, buy_day, px in [
        ("sell", DAY, 10),
        ("sell", DAY - timedelta(days=1), 9),
        ("buy", None, 11),
    ]:
        audit = []
        calls = []
        session = ResearchSession(ResearchFillConfig(NEXT_OPEN), DAY, audit)
        session.submit(
            ResearchOrder(
                CODE,
                side,
                available_at(DAY, 585),
                10,
                100,
                lambda *args: calls.append(args),
                [candidate(DAY, 587, px), candidate(DAY + timedelta(days=1), 570, 10)],
                buy_day=buy_day,
            )
        )
        session.run()
        assert not calls and not session.orders
        assert audit[0]["reason"] == "same_day_expiry"


def test_v7_late_trial_is_unfilled_and_all_cash():
    minute = bars([(0, hm, 10, 10) for hm in range(895, 901)])
    state = simulate_v7(
        minute, daily([10, 10]), {DAY: [CODE]}, [DAY], clock_mode=NEXT_OPEN
    )
    assert not state.positions
    assert not [t for t in state.trades if t["side"] == "buy"]
    assert state.equity_curve[0]["equity"] == 21_000_000
    assert state.research_orders[0]["status"] == "UNFILLED"


def v7_seed():
    state = v7.SimResult(500000)
    pos = v7.Position(CODE, 10, avg_cost=10, last_add_date=DAY - timedelta(days=1))
    pos.lots = [v7.Lot(1000, DAY - timedelta(days=1), 10, "trial")]
    state.positions[CODE] = pos
    return state


def test_v7_expired_sell_then_recovery_does_not_keep_exit_intent():
    minute = bars(
        [(0, 895, 10, 8.9), (0, 896, 8.9, 8.9), (1, 570, 10, 10), (1, 572, 10, 10)]
    )
    # A 20% board lets the trial stop remain above today's limit-down.
    code = "300001.SZ"
    minute = {code: minute[CODE]}
    seed = v7_seed()
    pos = seed.positions.pop(CODE)
    pos.symbol = code
    seed.positions[code] = pos
    state = simulate_v7(
        minute,
        {code: daily([10, 8.9, 10])[CODE]},
        {},
        [DAY - timedelta(days=1), DAY, DAY + timedelta(days=1)],
        clock_mode=NEXT_OPEN,
        initial_state=seed,
    )
    assert state.positions[code].shares == 1000
    assert not [t for t in state.trades if t["side"] == "sell"]
    assert [r["status"] for r in state.research_orders] == ["UNFILLED"]


def test_v7_add_stage_changes_at_fill_and_actual_buy_day_t1():
    minute = bars(
        [
            (0, 885, 10.4, 10.4),
            (0, 886, 10.4, 10.4),
            (0, 887, 10.5, 10.5),
            (0, 888, 10.5, 10.5),
        ]
    )
    state = simulate_v7(
        minute,
        daily([10, 10.5]),
        {},
        [DAY - timedelta(days=1), DAY],
        clock_mode=NEXT_OPEN,
        initial_state=v7_seed(),
    )
    pos = state.positions[CODE]
    assert pos.stage == v7.FOUR
    added = pos.lots[-1]
    assert added.buy_date == DAY and added.price == 10.5
    assert added.shares == int(v7.NAME_BUDGET * 0.2 / 10.5 / 100) * 100
    assert len([t for t in state.trades if t["side"] == "buy"]) == 1
    assert state.trades[-1]["research_fill_at"].endswith("14:47:00")


@pytest.mark.parametrize("bp", [5, 10, 20])
def test_v7_slip_q2_and_post_impact_fees(bp):
    minute = bars([(0, 895, 10, 10)])
    state = simulate_v7(
        minute,
        daily([10, 10]),
        {DAY: [CODE]},
        [DAY],
        cash_total=200050,
        slip_bp_per_side=bp,
    )
    buy = state.trades[0]
    assert buy["hm"] == 895  # Slip keeps the original START bar label.
    px = 10 * (1 + bp / 10000)
    assert buy["shares"] == int(v7.NAME_BUDGET * v7.TRIAL_FRACTION / px / 100) * 100
    assert state.cash == pytest.approx(200050 - buy["shares"] * px * 1.001)
    assert state.equity_curve[0]["holdings"] == buy["shares"] * 10


@pytest.mark.parametrize("engine", ["book", "v7"])
def test_default_zero_trade_and_equity_bytes_equal_original(engine):
    minute = bars([(0, 895, 10, 10), (1, 570, 9.7, 9.7)])
    ds = daily([10, 10, 9.7])
    if engine == "book":
        args = (minute, ds, {"20260901": [CODE]}, "20260901", "20260902")
        base = book.simulate(*args, strategy="version1")
        actual = simulate_book(*args, strategy="version1")
    else:
        args = (minute, ds, {DAY: [CODE]}, [DAY, DAY + timedelta(days=1)])
        base, actual = v7.simulate_v7(*args), simulate_v7(*args)

    def serialized(st):
        return json.dumps([st.trades, st.equity_curve], sort_keys=True).encode()

    assert serialized(actual) == serialized(base)


def modeb_inputs(tmp_path):
    pool = tmp_path / "pool"
    pool.mkdir()
    (pool / "20260901.csv").write_text("code,name\n600000,浦发银行\n", encoding="utf-8")
    minute = bars(
        [(0, 895, 10, 10), (0, 899, 10, 10), (1, 570, 10, 10), (1, 899, 10, 10)]
    )
    return dict(
        pool_dir=pool,
        start="20260901",
        end="20260902",
        sessions=["20260901", "20260902"],
        bars=daily([10, 10, 10]),
        minute_bars=minute,
        exdiv={},
        index_block={},
    )


def test_modeb_h2_all_entry_fills_expire_all_cash(tmp_path):
    result = run_modeb(
        **modeb_inputs(tmp_path), out_dir=tmp_path / "clock", clock_mode=NEXT_OPEN
    )
    assert result["ranked"]
    assert all(m.total_return == 0 and m.n_instances == 0 for m in result["ranked"])
    assert result["research_orders"]
    assert {r["status"] for r in result["research_orders"]} == {"UNFILLED"}
    equity = pd.read_csv(tmp_path / "clock/daily_equity.csv")
    assert (equity.equity == modea.CASH_POOL).all()


@pytest.mark.parametrize("bp", [5, 10, 20])
def test_modeb_slip_q2_fees_and_equity(tmp_path, bp):
    result = run_modeb(
        **modeb_inputs(tmp_path), out_dir=tmp_path / "slip", slip_bp_per_side=bp
    )
    metric = next(m for m in result["ranked"] if m.label == "r1_n1")
    buy_px, sell_px = 10 * (1 + bp / 10000), 10 * (1 - bp / 10000)
    qty = modea._lot_shares(buy_px)
    assert qty < modea._lot_shares(10)
    pnl = qty * (sell_px * 0.999 - buy_px * 1.001)
    assert metric.total_return == pytest.approx(pnl / modea.CASH_POOL)
    assert result["matrix"]["r1_n1"][f"{CODE}|20260901"].sell_price == pytest.approx(
        sell_px
    )


def test_modeb_default_matches_original(tmp_path):
    kwargs = modeb_inputs(tmp_path)
    baseline = modeb.run_modeb(**kwargs, out_dir=tmp_path / "base")
    actual = run_modeb(**kwargs, out_dir=tmp_path / "adapter")
    assert actual["ranked"] == baseline["ranked"]
    assert (tmp_path / "base/ranking.csv").read_bytes() == (
        tmp_path / "adapter/ranking.csv"
    ).read_bytes()


def test_matrix_capability_only_empty_numbers_and_axis_validation(tmp_path):
    harness.emit_stubs(tmp_path, start="20260901", end="20260902", force=True)
    import csv

    rows = list(csv.DictReader((tmp_path / "matrix.csv").open()))
    assert len(rows) == 15
    assert {r["fill_status"] for r in rows} == {"FILLABLE"}
    for row in rows:
        assert all(
            row[k] == ""
            for k in ("nav", "total_return", "max_drawdown", "within_engine_rank")
        )
    with pytest.raises(ValueError, match="unknown"):
        harness.selected_cells("invented")
    assert (
        len(
            harness.selected_cells(",".join(c["cell_id"] for c in harness.MATRIX_CELLS))
        )
        == 5
    )


def test_book_chase_also_uses_next_open_and_q2():
    minute = bars(
        [
            (0, 895, 11, 11),
            (1, 570, 10.9, 10.9),
            (1, 585, 11.2, 11.2),
            (1, 586, 11.3, 11.3),
            (1, 587, 11.4, 11.4),
        ]
    )
    state = simulate_book(
        minute,
        daily([10, 11, 11.4]),
        {"20260901": [CODE]},
        "20260901",
        "20260902",
        strategy="version1",
        total_cash=10050,
        daily_quota=10000,
        clock_mode=NEXT_OPEN,
    )
    buy = next(t for t in state.trades if t["side"] == "BUY")
    assert buy["reason"] == "chase:T+1"
    assert buy["price"] == 11.4 and buy["shares"] == 800
    assert buy["research_fill_at"].endswith("09:47:00")


def test_modeb_expired_exit_reevaluates_without_sticky_take_profit():
    from backtest.research.fullstrat_research_modeb import evaluate_exit

    minute = bars(
        [
            (1, 895, 10, 10.6),
            (1, 896, 10.6, 10.6),
            (2, 570, 10, 10),
            (2, 572, 10, 10),
            (3, 570, 9.4, 9.4),
            (3, 571, 9.5, 9.5),
        ]
    )
    prepared = modea._prepare_bars(daily([10, 10, 10.6, 10, 9.5]))
    inst = modea.Instance(CODE, "", "20260901", 10, True)
    spec = modea.StrategySpec(2, 8, 5, 5)
    audit = []
    er = evaluate_exit(
        inst,
        spec,
        prepared,
        modeb._prepare_minutes(minute),
        ["20260901", "20260902", "20260903", "20260904"],
        config=ResearchFillConfig(NEXT_OPEN),
        end="20260904",
        tol=modea.DEFAULT_TOL,
        exdiv={},
        index_block={},
        audit=audit,
    )
    assert er.sell_date == "20260904" and er.sell_price == 9.5
    assert er.reason == "stop_loss"
    assert [row["status"] for row in audit] == ["UNFILLED", "FILLED"]


@pytest.mark.parametrize("strategy", harness.BOOK_STRATEGIES)
def test_every_book_has_a_research_fill_path(strategy):
    minute = bars([(0, 895, 10, 10), (1, 570, 9.7, 9.7)])
    state = simulate_book(
        minute,
        daily([10] * 20),
        {"20260901": [CODE]},
        "20260901",
        "20260902",
        strategy=strategy,
        slip_bp_per_side=5,
        index_block_new={},
    )
    # Some books legitimately filter this small fixture; every accepted buy
    # must be repriced and recorded by the research order path.
    for trade in state.trades:
        if trade["side"] == "BUY":
            assert trade["price"] == pytest.approx(10.005)
            assert "research_fill_at" in trade


def test_existing_open_fill_precedes_new_decision_at_same_timestamp():
    state = ledger.SimState(cash=10050)
    session = ResearchSession(ResearchFillConfig(NEXT_OPEN), DAY, [])
    observed = []
    # Strategy events are installed before orders have been submitted.
    session.at(stamp(DAY, 587), lambda: observed.append(state.cash))
    session.at(
        available_at(DAY, 585),
        lambda: session.submit(
            ResearchOrder(
                CODE,
                "buy",
                available_at(DAY, 585),
                10,
                1000,
                lambda px, at: ledger.execute_buy(state, CODE, px, 10000, 0, DAY),
                [candidate(DAY, 587, 10.1)],
            )
        ),
    )
    session.run()
    assert observed == pytest.approx([950.91])


def test_book_expiry_retains_observed_peak_but_clears_exit():
    minute = bars(
        [(0, 893, 10, 10), (0, 896, 10, 10), (1, 895, 10, 9.7), (1, 896, 9.7, 10)]
    )
    minute[CODE]["high"] = minute[CODE]["high"].astype(float)
    minute[CODE].iloc[-1, minute[CODE].columns.get_loc("high")] = 10.8
    state = simulate_book(
        minute,
        daily([10, 10, 10]),
        {"20260901": [CODE]},
        "20260901",
        "20260902",
        strategy="version1",
        total_cash=10050,
        daily_quota=10000,
        clock_mode=NEXT_OPEN,
    )
    pos = state.positions[CODE][0]
    assert pos.peak == 10.8 and not pos.pending_exit
    assert state.research_orders[-1]["reason"] == "same_day_expiry"


def test_book_limit_chase_gate_order_stays_a_strategy_signal():
    minute = bars([(0, 895, 11, 11)])
    state = simulate_book(
        minute,
        daily([10, 11]),
        {"20260901": [CODE]},
        "20260901",
        "20260901",
        strategy="version4",
        clock_mode=NEXT_OPEN,
    )
    # The original pool path queues limit-up chase before the SMA warmup gate.
    assert state.stats["skip_limit_up"] == 1
    assert state.stats["chase_pending_eod"] == 1
    assert not state.research_orders


def test_harness_cells_pass_explicit_axes_keep_artifacts_and_ranks_separate(
    tmp_path, monkeypatch
):
    seen = []

    def run(strategy, **kwargs):
        seen.append((strategy, kwargs))
        slip = kwargs["slip_bp_per_side"]
        ret = (1 if strategy == "version1" else 2) * (-1 if slip else 1) * 0.001
        return harness.blank_nav_row(
            engine="Book",
            strategy=strategy,
            status="OK",
            final_equity=21000000 * (1 + ret),
            total_return=ret,
            max_drawdown=-0.01,
            note="synthetic_pin",
        )

    monkeypatch.setattr(harness, "run_book", run)
    cells = harness.selected_cells("clock_next_open_fullstrat,slip_5bp_fullstrat")
    harness.execute(
        start="20260901",
        end="20260902",
        pool_dir=tmp_path / "pool",
        qlib_root=tmp_path / "qlib",
        out_dir=tmp_path / "out",
        engines={"book"},
        strategies=("version1", "version2"),
        force=False,
        cells=cells,
    )
    assert {
        (kwargs["clock_mode"], kwargs["slip_bp_per_side"]) for _, kwargs in seen
    } == {(NEXT_OPEN, 0), ("production_default", 5)}
    roots = {kwargs["work_root"] for _, kwargs in seen}
    assert len(roots) == 2
    for root in roots:
        manifest = json.loads((root / "research_config.json").read_text())
        assert manifest["sizing"] == "Q2" and manifest["coverage"] == "H2_all_fills"
    rows = pd.read_csv(tmp_path / "out/book_nav.csv")
    top = rows.loc[rows.within_engine_rank == 1]
    assert list(top.strategy) == ["version2", "version1"]
    matrix = pd.read_csv(tmp_path / "out/matrix.csv")
    assert len(matrix.loc[matrix.fill_status == "FILLED"]) == 2
    assert matrix.loc[matrix.fill_status == "FILLABLE", "nav"].isna().all()
    with pytest.raises(ValueError, match="fresh research output"):
        harness.execute(
            start="20260901",
            end="20260902",
            pool_dir=tmp_path / "pool",
            qlib_root=tmp_path / "qlib",
            out_dir=tmp_path / "out",
            engines={"book"},
            strategies=("version1",),
            force=True,
            cells=cells,
        )


def test_modeb_t1_exit_recycles_cash_before_next_close_admission(tmp_path):
    inputs = modeb_inputs(tmp_path)
    other = "600001.SH"
    (inputs["pool_dir"] / "20260901.csv").write_text(
        "code,name\n600000,A\n600001,B\n", encoding="utf-8"
    )
    (inputs["pool_dir"] / "20260902.csv").write_text(
        "code,name\n600001,B\n", encoding="utf-8"
    )
    inputs["bars"][other] = inputs["bars"][CODE].copy()
    inputs["minute_bars"][other] = inputs["minute_bars"][CODE].copy()
    capital = modea.LOT_NOTIONAL * 1.01
    result = run_modeb(
        **inputs, cash_pool=capital, out_dir=tmp_path / "recycling", slip_bp_per_side=10
    )
    exits = result["matrix"]["r1_n1"]
    assert set(exits) == {f"{CODE}|20260901", f"{other}|20260902"}
    assert exits[f"{CODE}|20260901"].sell_date == "20260902"
    metric = next(m for m in result["ranked"] if m.label == "r1_n1")
    assert metric.n_instances == 2  # B day 0 is cash-rejected; B day 1 uses A's sale.
    qty = modea._lot_shares(10.01)
    expected = capital - 2 * qty * 10.01 * 1.001 + qty * 9.99 * 0.999 + qty * 10
    assert metric.total_return == pytest.approx(expected / capital - 1)
    audit = [r for r in result["research_orders"] if r["strategy"] == "r1_n1"]
    assert [r["status"] for r in audit] == ["FILLED", "UNFILLED", "FILLED"]


@pytest.mark.parametrize("engine", ["book", "v7"])
def test_experimental_loop_same_economics_matches_original_at_zero_impact(engine):
    from backtest.research import fullstrat_research_book as research_book
    from backtest.research import fullstrat_research_v7 as research_v7

    minute = bars([(0, 895, 10, 10), (1, 570, 9.7, 9.7), (1, 895, 9.7, 9.7)])
    ds = daily([10, 10, 9.7])
    if engine == "book":
        args = (minute, ds, {"20260901": [CODE]}, "20260901", "20260902")
        baseline = book.simulate(*args, strategy="version1")
        actual = research_book.simulate(
            *args, strategy="version1", config=ResearchFillConfig()
        )
    else:
        args = (minute, ds, {DAY: [CODE]}, [DAY, DAY + timedelta(days=1)])
        baseline = v7.simulate_v7(*args)
        actual = research_v7.simulate(*args, config=ResearchFillConfig())

    def economics(state):
        return [
            {
                k: v
                for k, v in row.items()
                if k
                in {
                    "date",
                    "symbol",
                    "code",
                    "side",
                    "shares",
                    "price",
                    "notional",
                    "commission",
                    "reason",
                }
            }
            for row in state.trades
        ]

    assert economics(actual) == economics(baseline)
    assert actual.equity_curve == baseline.equity_curve


def test_modeb_experimental_zero_impact_ranking_matches_original(tmp_path):
    from backtest.research.fullstrat_research_modeb import run

    inputs = modeb_inputs(tmp_path)
    baseline = modeb.run_modeb(**inputs, out_dir=tmp_path / "original")
    actual = run(**inputs, out_dir=tmp_path / "replay", config=ResearchFillConfig())
    assert actual["ranked"] == baseline["ranked"]
    assert "anchor_hold_end" not in {m.label for m in baseline["ranked"]}


@pytest.mark.parametrize("factor", [1.0, 2.0])
def test_modeb_slip_entry_mark_freezes_at_market_price_across_missing_minutes(
    tmp_path, factor
):
    inputs = modeb_inputs(tmp_path)
    frame = inputs["minute_bars"][CODE]
    inputs["minute_bars"][CODE] = frame.loc[frame.ymd == "20260901"]
    inputs["exdiv"] = {CODE: {"20260902": factor}}
    result = run_modeb(**inputs, out_dir=tmp_path / "frozen", slip_bp_per_side=10)
    qty = modea._lot_shares(10.01)
    pnl = qty * (10 - 10.01 * 1.001)
    for metric in result["ranked"]:
        assert metric.total_return == pytest.approx(pnl / modea.CASH_POOL)
    er = result["matrix"]["r1_n1"][f"{CODE}|20260901"]
    assert not er.is_trade
    assert er.pnl == pytest.approx(pnl)
    equity = pd.read_csv(tmp_path / "frozen/daily_equity.csv")
    assert list(equity.equity) == pytest.approx([modea.CASH_POOL + pnl] * 2)
