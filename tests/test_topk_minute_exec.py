"""#208 P1: frozen master-close products and opt-in minute execution."""

import json
from pathlib import Path

import pandas as pd
import pytest

from backtest.research import csv_minute_backtest as minute
from backtest.research.csv_artifacts import summarize, write_run_artifacts
from backtest.research.topk_minute_exec import VWAP_SLICE_CLOCKS

A, B, C = "600000.SH", "600001.SH", "600002.SH"
D1, D2 = "20260901", "20260902"
GOLDEN = Path(__file__).parent / "fixtures/topk_exec_master_close"


def frames(rows):
    minutes, daily = {}, {}
    for code, values in rows.items():
        frame = pd.DataFrame(values, columns=["ymd", "hm", "open", "close"])
        frame["high"] = frame[["open", "close"]].max(axis=1)
        frame["low"] = frame[["open", "close"]].min(axis=1)
        frame["volume"] = 100_000.0
        frame.index = pd.to_datetime(frame["ymd"]) + pd.to_timedelta(frame["hm"], unit="m")
        minutes[code] = frame
        daily[code] = pd.DataFrame(
            {"open": 10., "high": 10., "low": 10., "close": 10.},
            index=pd.to_datetime(["20260831", D1, D2]),
        )
    return minutes, daily


def run_case(rows, *, scores=None, end=D1, **kwargs):
    ms, ds = frames(rows)
    options = dict(strategy="topk_dropout", total_cash=100_000.,
                   daily_quota=100_000., stop_pct=0, topk=1, n_drop=1)
    options.update(kwargs)
    scores = scores or {D1: {code: float(len(rows) - i) for i, code in enumerate(rows)}}
    return minute.simulate(ms, ds, {day: list(rank) for day, rank in scores.items()},
                           D1, end, scores_by_day=scores, **options)


def close_case(case, **kwargs):
    buying = {
        "exact": [(D1, 570, 9.7, 9.8), (D1, 890, 10.1, 10.2), (D1, 895, 10.3, 10.4)],
        "fallback": [(D1, 570, 9.7, 9.8), (D1, 870, 10., 10.1), (D1, 892, 10.2, 10.3),
                     (D1, 896, 10.4, 10.5)],
        "empty": [(D1, 570, 9.7, 9.8), (D1, 869, 10., 10.1), (D1, 896, 10.4, 10.5)],
    }[case]
    return run_case(
        {A: buying + [(D2, 570, 10., 10.1), (D2, 895, 10., 10.)],
         B: [(D1, 895, 10., 10.), (D2, 570, 9.8, 9.9), (D2, 895, 10.1, 10.2)]},
        scores={D1: {A: 2., B: 1.}, D2: {A: 1., B: 2.}}, end=D2, **kwargs,
    )


def write_close_products(target, state):
    write_run_artifacts(
        target, state, summarize(state, 100_000., D1, D2, engine="csv_minute_topk_dropout"),
        minute.help_lock_for("topk_dropout", shared=minute.HELP_LOCK),
    )
    (target / "stats.json").write_text(
        json.dumps(state.stats, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )


@pytest.mark.parametrize("case,price", [("exact", 10.4), ("fallback", 10.3), ("empty", None)])
@pytest.mark.parametrize("mode", [None, "close"])
def test_close_matches_frozen_master_bytes(tmp_path, case, price, mode):
    state = close_case(case, **({} if mode is None else {"topk_exec": mode}))
    buys = [t for t in state.trades if t["date"] == D1 and t["side"] == "BUY"]
    assert [t["price"] for t in buys] == ([] if price is None else [price])
    assert all(t["reason"] == "pool" and "hm" not in t for t in buys)
    write_close_products(tmp_path, state)
    for name in ("trades.csv", "daily_equity.csv", "summary.txt", "stats.json"):
        assert (tmp_path / name).read_bytes() == (GOLDEN / case / name).read_bytes()


def buys(state):
    return [t for t in state.trades if t["side"] == "BUY"]


@pytest.mark.parametrize("mode", ["open", "intraday"])
def test_opening_open_not_close_and_audit(mode):
    st = run_case({A: [(D1, 570, 10.1, 10.4), (D1, 630, 10.2, 10.5)]}, topk_exec=mode)
    assert [(t["price"], t["hm"], t["reason"]) for t in buys(st)] == [(10.1, 570, f"pool:{mode}")]
    row = st.topk_exec_audit[-1]
    assert (row["selection_hm"], row["quote_hm"], row["execution_hm"]) == (570, 570, 570)
    assert (row["seat"], row["original_code"], row["quota"], row["denominator"]) == (0, A, 95_000., 1)
    assert st.stats["limit_retry_fills"] == st.stats["limit_retry_expired"] == 0


@pytest.mark.parametrize("mode,expected", [("open", []), ("intraday", [(631, 10.2)])])
def test_missing_open_never_borrows_or_backdates(mode, expected):
    st = run_case({A: [(D1, 565, 10., 10.), (D1, 631, 10.2, 10.3)]}, topk_exec=mode)
    assert [(t["hm"], t["price"]) for t in buys(st)] == expected
    assert st.stats["limit_retry_expired"] == 0
    assert st.stats["skip_no_bar"] == (mode == "open")


def test_all_session_opens_at_or_above_limit_expire_without_substitute():
    st = run_case({A: [(D1, 565, 10., 10.), (D1, 570, 10.95, 10.),
                      (D1, 720, 10., 10.), (D1, 780, 11., 10.), (D1, 900, 10.95, 10.)],
                   B: [(D1, 570, 10., 10.)]}, topk_exec="intraday")
    assert buys(st) == []
    assert st.stats["limit_retry_fills"] == 0
    assert st.stats["limit_retry_expired"] == 1
    assert st.topk_exec_audit[-1]["reason"] == "limit_retry_expired"
    assert st.topk_exec_audit[-1]["decision_hm"] == 900
    assert {row["code"] for row in st.topk_exec_audit} == {A}


def test_first_board_opening_fills_exact_bar_open():
    st = run_case({A: [(D1, 565, 9.9, 9.9), (D1, 570, 10.95, 10.),
                      (D1, 629, 10.95, 10.), (D1, 630, 10.8, 10.2),
                      (D1, 631, 10.1, 10.)]}, topk_exec="intraday")
    assert [(t["hm"], t["price"]) for t in buys(st)] == [(630, 10.8)]
    assert st.stats["limit_retry_fills"] == 1
    assert st.stats["limit_retry_expired"] == 0


@pytest.mark.parametrize("hm", [690, 780, 900])
def test_inclusive_session_boundaries_and_lunch_excluded(hm):
    rows = sorted([(D1, 565, 10., 10.), (D1, 570, 10.95, 10.),
                   (D1, 691, 10., 10.), (D1, 779, 10., 10.), (D1, hm, 10.8, 10.2)],
                  key=lambda row: row[1])
    st = run_case({A: rows}, topk_exec="intraday")
    assert [(t["hm"], t["price"]) for t in buys(st)] == [(hm, 10.8)]


@pytest.mark.parametrize("rows", [
    [(D1, 565, 10., 10.), (D1, 720, 10., 10.), (D1, 901, 10., 10.)],
    [(D1, 570, float("nan"), 10.), (D1, 630, 0., 10.)],
    [(D2, 570, 10., 10.)],
])
def test_no_valid_session_quotes_are_data_skip_not_expiry(rows):
    st = run_case({A: rows}, topk_exec="intraday")
    assert buys(st) == []
    assert st.stats["skip_no_bar"] == 1
    assert st.stats["limit_retry_expired"] == 0
    assert st.topk_exec_audit[-1]["reason"] == "skip_no_bar"


@pytest.mark.parametrize("mode", ["open", "intraday"])
def test_upper_band_comparison_is_strict_even_within_legacy_epsilon(mode):
    st = run_case({A: [(D1, 570, 10.9495, 10.)]}, topk_exec=mode)
    assert [t["price"] for t in buys(st)] == [10.9495]


def test_open_limit_block_is_once_without_intraday_retry():
    st = run_case({A: [(D1, 570, 10.95, 10.), (D1, 630, 10.8, 10.)]}, topk_exec="open")
    assert buys(st) == []
    assert st.stats["limit_retry_expired"] == st.stats["limit_retry_fills"] == 0
    assert st.topk_exec_audit[-1]["reason"] == "skip_limit_up"


@pytest.mark.parametrize("gate", ["limit_down", "buy_gate", "cash", "volume"])
def test_other_gates_stop_order_without_retry_or_expiry(monkeypatch, gate):
    from backtest.research.ashare_volume_cap import BucketVolume

    opts = {}
    if gate == "buy_gate":
        original = minute.apply_csv_strategy

        def apply(*args, **kwargs):
            hooks = original(*args, **kwargs)
            hooks["buy_gate"] = lambda *_: False
            return hooks

        monkeypatch.setattr(minute, "apply_csv_strategy", apply)
    if gate == "cash":
        opts["total_cash"] = 1000.  # 100 shares + fee cannot be paid.
    if gate == "volume":
        opts.update(participation_rate=1., volume_for_bucket={
            (A, D1, 630): BucketVolume(100_000, 630, "raw_shares_incremental"),
        })
    px = 9.05 if gate == "limit_down" else 10.
    st = run_case({A: [(D1, 570, 10.95, 10.), (D1, 630, px, 10.),
                      (D1, 631, 10., 10.)]}, topk_exec="intraday", **opts)
    assert buys(st) == []
    assert st.stats["limit_retry_expired"] == st.stats["limit_retry_fills"] == 0
    expected = {"limit_down": "skip_limit_down", "buy_gate": "skip_buy_gate",
                "cash": "skip_cash", "volume": "skip_volume_unavailable:bucket_not_completed"}[gate]
    assert st.topk_exec_audit[-1]["reason"] == expected
    assert st.topk_exec_audit[-1]["decision_hm"] == 630
    if gate == "cash":
        assert st.stats["skip_cash"] == 1


@pytest.mark.parametrize("vacancy", [False, True])
def test_original_denominator_not_successful_count(vacancy):
    opts = dict(keep_buy_vacancy=True, eligible_buy=lambda code, _day: code == B) if vacancy else {}
    st = run_case({A: [(D1, 570, 10.95, 10.)], B: [(D1, 570, 10., 10.)]},
                  topk_exec="intraday", topk=2, **opts)
    assert [(t["code"], t["shares"]) for t in buys(st)] == [(B, 4700)]
    fill = next(row for row in st.topk_exec_audit if row.get("side") == "BUY")
    assert (fill["quota"], fill["denominator"]) == (47_500., 2)


def test_same_minute_buys_keep_planned_order_and_frozen_cash():
    st = run_case({A: [(D1, 570, 10.95, 10.), (D1, 630, 10., 10.)],
                   B: [(D1, 570, 10.95, 10.), (D1, 630, 10., 10.)]},
                  topk_exec="intraday", topk=2)
    assert [(t["code"], t["hm"], t["shares"]) for t in buys(st)] == [(A, 630, 4700), (B, 630, 4700)]
    assert {row["allocation_cash"] for row in st.topk_exec_audit} == {100_000.}


@pytest.mark.parametrize("sell_hm", [629, 630, 631])
def test_frozen_quota_excludes_later_sales_even_when_cash_sufficient(sell_hm):
    st = run_case(
        {A: [(D1, 570, 10., 10.), (D2, sell_hm, 10., 10.)],
         B: [(D1, 570, 10., 10.), (D2, 570, 10.95, 10.), (D2, 630, 10., 10.)]},
        topk_exec="intraday", total_cash=2002., daily_quota=2002., end=D2,
        scores={D1: {A: 2., B: 1.}, D2: {A: 1., B: 2.}},
    )
    # D1 spends 1001, D2 opens with 1001; quota=950.95 requests 100 shares
    # (1001 including fees). Earlier sales must not enlarge this quota.
    assert st.topk_exec_audit[-1]["quota"] == pytest.approx(950.95)
    sells = [t for t in st.trades if t["side"] == "SELL"]
    assert [(t["price"], t["reason"]) for t in sells] == [(10., "topk_drop:bottom")]
    # Cash basis stays fixed even when the earlier sale makes more cash available.
    assert [t["shares"] for t in buys(st)] == [100, 100]


@pytest.mark.parametrize("sell_hm,can_buy", [(629, True), (630, False), (631, False)])
def test_no_future_or_same_close_sale_credit_and_cash_failure_not_retry(sell_hm, can_buy):
    st = run_case(
        {A: [(D1, 570, 10., 10.), (D2, sell_hm, 10., 10.)],
         B: [(D1, 570, 10., 10.), (D2, 570, 10.95, 10.), (D2, 630, 10., 10.)]},
        topk_exec="intraday", total_cash=1500., daily_quota=1500., end=D2,
        scores={D1: {A: 2., B: 1.}, D2: {A: 1., B: 2.}},
    )
    assert [t["code"] for t in buys(st)] == ([A, B] if can_buy else [A])
    assert st.topk_exec_audit[-1]["quota"] == pytest.approx(499. * .95)
    assert st.topk_exec_audit[-1]["reason"] == ("pool:intraday" if can_buy else "skip_cash")
    assert st.stats["limit_retry_fills"] == int(can_buy)
    assert st.stats["limit_retry_expired"] == 0


@pytest.mark.parametrize("mode,message", [("bad", "unknown --topk-exec")])
def test_api_rejects_unshipped_modes_before_data_loading(mode, message):
    with pytest.raises(ValueError, match=message):
        minute.run(D1, D1, strategy="topk_dropout", topk_exec=mode)


@pytest.mark.parametrize("strategy", ["version6", "topk_score_exit"])
@pytest.mark.parametrize("mode", ["open", "intraday", "vwap"])
def test_api_scope_is_topk_dropout_only(strategy, mode):
    with pytest.raises(ValueError, match="only to topk_dropout"):
        minute.simulate({}, {}, {}, D1, D1, strategy=strategy, topk_exec=mode)


def test_cli_help_and_rejections(capsys):
    with pytest.raises(SystemExit) as exit:
        minute.main(["--help"])
    assert exit.value.code == 0
    help_text = capsys.readouterr().out
    assert "--topk-exec {close,open,intraday,vwap}" in help_text
    assert "default close" in help_text and "open (opt-in)" in help_text
    assert "intraday (opt-in)" in help_text
    assert "vwap x --limit-walkdown is refused" in help_text
    assert "equal-notional fixed-clock TWAP-style" in help_text
    assert "no roll-forward" in help_text
    for args, message in [(["--topk-exec", "bad"], "unknown --topk-exec"),
                          (["--limit-walkdown"], "unrecognized arguments")]:
        with pytest.raises(SystemExit) as exit:
            minute.main(["--strategy", "topk_dropout", *args])
        assert exit.value.code == 2
        assert message in capsys.readouterr().err


@pytest.mark.parametrize("mode", ["open", "intraday"])
@pytest.mark.parametrize("gap_open,expected", [(False, False), (True, True)])
def test_open_buy_cash_freezes_after_open_sales_before_close_sales(mode, gap_open, expected):
    trace = []
    st = run_case(
        {A: [(D1, 570, 10., 10.), (D2, 570, 9.4 if gap_open else 10., 9.4)],
         B: [(D1, 570, 10., 10.), (D2, 570, 10., 10.)]},
        topk_exec=mode, total_cash=1500., daily_quota=1500., end=D2, stop_pct=.05,
        scores={D1: {A: 2., B: 1.}, D2: {A: 1., B: 2.}}, audit_sink=trace,
    )
    assert [t["code"] for t in buys(st)] == ([A, B] if expected else [A])
    assert st.topk_exec_audit[-1]["allocation_cash"] == pytest.approx(1438.06 if gap_open else 499.)
    sell = next(row for row in trace if row["side"] == "SELL")
    assert (sell["hm"], sell["phase"], sell["price"]) == (570, "open" if gap_open else "close", 9.4)


@pytest.mark.parametrize("mode", ["open", "intraday"])
def test_intraday_and_open_do_not_need_cash_order_flag_or_mutate_close_path(mode):
    rows = {A: [(D1, 570, 10.1, 10.2)]}
    implicit = run_case(rows, topk_exec=mode)
    explicit = run_case(rows, topk_exec=mode, fix_minute_cash_order=True)
    assert implicit.trades == explicit.trades
    assert implicit.stats == explicit.stats
    assert implicit.topk_exec_audit == explicit.topk_exec_audit


@pytest.fixture
def synthetic_loaders(monkeypatch):
    from types import SimpleNamespace

    ms, ds = frames({A: [(D1, 570, 10.95, 10.), (D1, 630, 10.2, 10.3), (D1, 895, 10.3, 10.4)]})
    monkeypatch.setattr(minute, "warn_stale_period_env", lambda: None)
    monkeypatch.setattr(minute, "load_pool_day_map", lambda *args, **kwargs: {D1: [A]})
    monkeypatch.setattr(minute, "load_pool_names_by_day", lambda *args: {})
    monkeypatch.setattr(minute, "load_daily_ohlc", lambda *args, **kwargs: ds)
    monkeypatch.setattr(minute, "load_exdiv_ratios", lambda *args, **kwargs: None)
    monkeypatch.setattr(minute, "load_minute_bars", lambda *args, **kwargs: ms)
    monkeypatch.setattr(minute, "time", SimpleNamespace(perf_counter=lambda: 0.0))
    monkeypatch.setattr(minute, "maybe_compare_daily", lambda *args, **kwargs: None)
    monkeypatch.setattr(minute, "csv_run_kwargs_from_args", lambda args: dict(
        strategy=args.strategy, scores_by_day={D1: {A: 1.}}, topk=1, n_drop=1, stop_pct=0,
    ))


@pytest.mark.parametrize("mode", [None, "close", "open", "intraday", "vwap"])
def test_cli_run_simulate_and_artifact_contract(tmp_path, synthetic_loaders, mode):
    out = tmp_path / "out"
    args = ["--strategy", "topk_dropout", "--start", D1, "--end", D1,
            "--pool-dir", str(tmp_path), "--out-dir", str(out), "--cash-total", "100000",
            "--emit-run-manifest"]
    assert minute.main(args + ([] if mode is None else ["--topk-exec", mode])) == 0
    manifest = json.loads((out / "run-manifest.json").read_text())
    if mode in (None, "close"):
        assert not (out / "topk_execution.json").exists()
        assert "topk_exec" not in json.dumps(manifest)
        assert "#208 P1" not in (out / "summary.txt").read_text()
        trades = pd.read_csv(out / "trades.csv", keep_default_na=False)
        assert list(zip(trades["side"], trades["price"], trades["reason"])) == [
            ("BUY", 10.4, "pool"), ("EOD_MARK", 10., ""),
        ]
        assert "hm" not in trades
    else:
        audit = json.loads((out / "topk_execution.json").read_text())
        assert audit["topk_exec"] == mode
        assert audit["limit_retry_fills"] == int(mode == "intraday")
        assert "#208 P1" in (out / "summary.txt").read_text()
        if mode == "intraday":
            assert audit["events"][-1]["execution_hm"] == 630
            assert audit["events"][-1]["price"] == 10.2


def test_run_close_default_and_explicit_products_match(tmp_path, synthetic_loaders):
    options = dict(strategy="topk_dropout", scores_by_day={D1: {A: 1.}}, topk=1,
                   n_drop=1, stop_pct=0, total_cash=100_000., daily_quota=100_000., pool_dir=tmp_path)
    implicit = minute.run(D1, D1, **options)
    explicit = minute.run(D1, D1, **options, topk_exec="close")
    assert implicit.stats == explicit.stats
    assert implicit.trades == explicit.trades
    assert implicit.equity_curve == explicit.equity_curve
    assert not hasattr(implicit, "topk_exec_audit")


def vwap_rows(prices=None):
    prices = prices or [10. + i * .1 for i in range(6)]
    return [(D1, hm, px, 10.6) for hm, px in zip(VWAP_SLICE_CLOCKS, prices)]


def slices(st):
    return [row for row in st.topk_exec_audit if "slice_index" in row]


def test_vwap_equal_notional_open_quotes_accumulate_and_cash_bound():
    st = run_case({A: vwap_rows()}, topk_exec="vwap")
    events = slices(st)
    assert len(events) == 6
    q = events[0]["quota"]
    assert sum(row["slice_budget"] for row in events) == pytest.approx(q)
    assert {row["slice_budget"] for row in events} == {q / 6}
    assert [(t["hm"], t["price"], t["reason"]) for t in buys(st)] == [
        (hm, px, "pool:vwap") for _, hm, px, _ in vwap_rows()]
    spent = sum(t["notional"] for t in buys(st))
    fees = sum(t["commission"] for t in buys(st))
    assert spent <= q
    assert st.cash == pytest.approx(100_000. - spent - fees)
    assert st.cash >= 100_000. - q - fees
    assert sum(p.shares for p in st.positions[A]) == sum(t["shares"] for t in buys(st))
    assert st.stats["skip_held"] == st.stats["supplementary_used"] == 0
    for i, row in enumerate(events):
        assert (row["slice_index"], row["slice_hm"], row["selection_hm"], row["decision_hm"],
                row["quote_hm"], row["execution_hm"], row["phase"]) == (
                    i, VWAP_SLICE_CLOCKS[i], 570, VWAP_SLICE_CLOCKS[i],
                    VWAP_SLICE_CLOCKS[i], VWAP_SLICE_CLOCKS[i], "open")


@pytest.mark.parametrize("cash", [6000., 6400.])
def test_vwap_sublot_never_supplements_or_rolls_forward(cash):
    st = run_case({A: vwap_rows([10.] * 6)}, topk_exec="vwap", total_cash=cash)
    assert len(buys(st)) == (0 if cash == 6000 else 6)
    assert st.stats["supplementary_used"] == 0
    assert all(t["notional"] <= cash * .95 / 6 for t in buys(st))
    assert st.cash >= cash - cash * .95 - sum(t["commission"] for t in buys(st))


@pytest.mark.parametrize("bad", [None, float("nan"), 0., -1., float("inf")])
def test_vwap_missing_or_invalid_clock_no_borrow(bad):
    rows = vwap_rows()
    rows = [row for row in rows if row[1] != 630]
    if bad is not None:
        rows.append((D1, 630, bad, 10.))
    rows += [(D1, 629, 10., 10.), (D1, 631, 10., 10.)]
    st = run_case({A: sorted(rows, key=lambda r: r[1])}, topk_exec="vwap")
    assert [t["hm"] for t in buys(st)] == [hm for hm in VWAP_SLICE_CLOCKS if hm != 630]
    assert slices(st)[1]["reason"] == "skip_no_bar"
    assert slices(st)[1]["quote_hm"] is None
    assert len({row["slice_budget"] for row in slices(st)}) == 1


def test_vwap_session_and_window_exclude_other_rows():
    st = run_case({A: [(D1, hm, 10., 10.) for hm in [565, 570, 574, 691, 720, 779, 896, 900]]},
                  topk_exec="vwap")
    assert buys(st) == []
    assert len(slices(st)) == 6
    assert st.stats["skip_no_bar"] == 1
    assert st.stats["limit_retry_expired"] == 0


@pytest.mark.parametrize("all_blocked", [False, True])
def test_vwap_limit_skips_continue_without_intraday_counters(all_blocked):
    st = run_case({A: vwap_rows([10.95] * 6 if all_blocked else [10.95] + [10.9495] * 5)},
                  topk_exec="vwap")
    assert len(buys(st)) == (0 if all_blocked else 5)
    assert slices(st)[0]["reason"] == "skip_limit_up"
    assert st.stats["skip_limit_up"] == int(all_blocked)
    assert st.stats["limit_retry_expired"] == st.stats["limit_retry_fills"] == 0
    assert st.topk_exec_audit[-1]["reason"] == ("skip_limit_up" if all_blocked else "pool:vwap")


def test_vwap_volume_failure_is_slice_local_and_uses_completed_volume():
    from backtest.research.ashare_volume_cap import BucketVolume
    st = run_case({A: vwap_rows()}, topk_exec="vwap", participation_rate=1.,
                  volume_for_bucket={(A, D1, hm - 1): BucketVolume(100_000, hm if i == 0 else hm - 1,
                                                               "raw_shares_incremental")
                                     for i, hm in enumerate(VWAP_SLICE_CLOCKS)})
    assert slices(st)[0]["reason"] == "skip_volume_unavailable:available_at"
    assert [t["hm"] for t in buys(st)] == list(VWAP_SLICE_CLOCKS[1:])
    assert st.stats["skip_limit_up"] == st.stats["limit_retry_expired"] == 0


def test_vwap_mixed_zero_fills_uses_last_concrete_reason():
    st = run_case({A: [(D1, 575, 10.95, 10.), (D1, 630, 9.05, 10.)]}, topk_exec="vwap")
    assert buys(st) == []
    assert [row["reason"] for row in slices(st)][:2] == ["skip_limit_up", "skip_limit_down"]
    assert st.topk_exec_audit[-1]["reason"] == "skip_limit_down"
    assert st.stats["skip_limit_up"] == st.stats["limit_retry_expired"] == 0


@pytest.mark.parametrize("vacancy", [False, True])
def test_vwap_original_denominator_and_same_clock_order(vacancy):
    opts = dict(keep_buy_vacancy=True, eligible_buy=lambda code, _day: code == B) if vacancy else {}
    st = run_case({A: vwap_rows(), B: vwap_rows()}, topk_exec="vwap", topk=2, **opts)
    assert {row["denominator"] for row in slices(st)} == {2}
    assert {row["quota"] for row in slices(st)} == {47_500.}
    assert {row["allocation_cash"] for row in slices(st)} == {100_000.}
    assert [t["code"] for t in buys(st)] == ([B] if vacancy else [A, B]) * 6


def test_vwap_cash_freezes_at_0930_before_later_sale():
    st = run_case(
        {A: vwap_rows([10.] * 6) + [(D2, 574, 10., 10.)],
         B: vwap_rows([10.] * 6) + [(D2, hm, 10., 10.) for hm in VWAP_SLICE_CLOCKS]},
        topk_exec="vwap", total_cash=20_000., daily_quota=20_000., end=D2,
        scores={D1: {A: 2., B: 1.}, D2: {A: 1., B: 2.}},
    )
    d1_buys = [t for t in buys(st) if t["date"] == D1]
    cash_basis = 20_000. - sum(t["notional"] + t["commission"] for t in d1_buys)
    events = [row for row in slices(st) if row["date"] == D2]
    assert {row["allocation_cash"] for row in events} == {cash_basis}
    assert {row["quota"] for row in events} == {cash_basis * .95}
    assert any(t["side"] == "SELL" and t["date"] == D2 for t in st.trades)
    assert not [t for t in buys(st) if t["date"] == D2]  # Later sale cannot enlarge slices.
    assert all(row["reason"] == "skip_budget" for row in events)


def test_vwap_buy_gate_failure_does_not_end_seat(monkeypatch):
    original = minute.apply_csv_strategy

    def apply(*args, **kwargs):
        hooks = original(*args, **kwargs)
        hooks["buy_gate"] = lambda code, px, day, closes: px > 10.
        return hooks

    monkeypatch.setattr(minute, "apply_csv_strategy", apply)
    st = run_case({A: vwap_rows()}, topk_exec="vwap")
    assert slices(st)[0]["reason"] == "skip_buy_gate"
    assert len(buys(st)) == 5
    assert st.stats["skip_buy_gate"] == 0


def test_vwap_cash_failure_continues_each_slice(monkeypatch):
    original = minute.apply_csv_strategy

    def apply(*args, **kwargs):
        hooks = original(*args, **kwargs)
        hooks["cash_deploy_frac"] = 1.
        return hooks

    monkeypatch.setattr(minute, "apply_csv_strategy", apply)
    st = run_case({A: vwap_rows([10.] * 6)}, topk_exec="vwap", total_cash=6000.)
    assert len(buys(st)) == 5
    assert slices(st)[-1]["reason"] == "skip_cash"
    assert st.topk_exec_audit[-1]["reason"] == "pool:vwap"
    assert st.stats.get("skip_cash", 0) == 0
