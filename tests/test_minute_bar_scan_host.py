"""Wired book scans and explicit read-only sources; only synthetic data."""

import ast
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from backtest.research.bar_scan_exit import OhlcBar
from backtest.research import minute_bar_scan_host as host
from backtest.research.minute_bar_scan_host import (
    load_scan_bars,
    main,
    run_scan,
    scan_held_bars,
)
from backtest.research.minute_true_core_wire import wired_names
from backtest.research.topk_dropout_rules import decide_topk_dropout
from backtest.research.topk_score_exit_rules import decide_topk_score_exit

ROOT = Path(__file__).resolve().parents[1]
SYMBOL = "000739.SZ"
DAY = "20260106"
OTHER = "600000.SH"
UNIVERSE_BOOKS = ("topk_dropout", "topk_score_exit")
SINGLE_BOOKS = tuple(name for name in wired_names() if name not in UNIVERSE_BOOKS)
FLAT_BARS = [OhlcBar(10, 10, 10, 10), OhlcBar(10, 10, 10, 10)]


def test_scan_counts_current_bar_fill_and_skip():
    result = scan_held_bars(
        [OhlcBar(10.0, 10.1, 9.95, 10.05), OhlcBar(9.70, 9.80, 9.60, 9.75)],
        cost=10.0, peak=10.0,
    )
    assert result.fills == 1
    assert result.skips == 1
    assert result.bars == 2


def test_scan_carries_peak_into_the_next_bar():
    result = scan_held_bars(
        [OhlcBar(11.0, 12.0, 10.9, 11.8), OhlcBar(10.9, 11.0, 10.8, 10.9)],
        cost=10.0, peak=10.0,
    )
    assert (result.bars, result.fills, result.skips) == (2, 1, 1)


def test_empty_bars_raise():
    with pytest.raises(ValueError, match="empty"):
        scan_held_bars([], cost=10.0, peak=10.0)


@pytest.mark.parametrize("strategy", wired_names())
@pytest.mark.parametrize("n_days", [0, 2])
def test_scan_keeps_n_days_one(n_days, strategy):
    with pytest.raises(ValueError, match="n_days"):
        scan_held_bars(FLAT_BARS, cost=10, peak=10, n_days=n_days, strategy=strategy)


def test_default_scan_still_invokes_version1():
    from scripts.research.bench_minute_bar_scan_host import assert_scan_equivalence
    assert_scan_equivalence()


@pytest.mark.parametrize("strategy", SINGLE_BOOKS)
def test_all_twenty_single_symbol_books_scan_two_flat_bars(strategy):
    assert len(SINGLE_BOOKS) == 20
    fields = {}
    if strategy in ("version4", "version11", "version12"):
        fields["level"] = 10
    if strategy in ("version7", "topk_app_dropout"):
        fields["stage"] = "full"
    result = scan_held_bars(FLAT_BARS, cost=10, peak=10, strategy=strategy, **fields)
    assert result.bars == 2
    assert result.fills + result.skips == 2


@pytest.mark.parametrize("strategy,field", [
    ("version4", "sma5"), ("version11", "sma5"), ("version12", "ma10"),
    ("version7", "stage"), ("topk_app_dropout", "stage"),
])
def test_required_caller_fields_raise(strategy, field):
    with pytest.raises(ValueError, match=field):
        scan_held_bars(FLAT_BARS, cost=10, peak=10, strategy=strategy)


@pytest.mark.parametrize("strategy", ["version4", "version11", "version12"])
@pytest.mark.parametrize("level", [0, -1, np.nan, np.inf, -np.inf])
def test_levels_must_be_finite_positive(strategy, level):
    with pytest.raises(ValueError, match="finite number > 0"):
        scan_held_bars(FLAT_BARS, cost=10, peak=10, strategy=strategy, level=level)


@pytest.mark.parametrize("strategy", ["version7", "topk_app_dropout"])
def test_undated_stage_bars_keep_wire_session_open_default(strategy):
    bars = [OhlcBar(8.9, 9.2, 8.8, 9.1)] * 2
    result = scan_held_bars(bars, cost=10, peak=10, strategy=strategy, stage="trial")
    assert (result.fills, result.skips) == (2, 0)
    dated = scan_held_bars(bars, cost=10, peak=10, strategy=strategy, stage="trial",
                           bar_dates=[DAY, DAY])
    assert (dated.fills, dated.skips) == (1, 1)
    next_day = scan_held_bars(bars, cost=10, peak=10, strategy=strategy, stage="trial",
                            bar_dates=[DAY, "20260107"])
    assert next_day.fills == 2


@pytest.mark.parametrize("strategy", ["version7", "topk_app_dropout"])
def test_stage_entry_a_is_optional_and_passed_to_wire(strategy):
    bars = [OhlcBar(9.5, 10, 9.4, 10)]
    anchored_cost = scan_held_bars(bars, cost=10, peak=10, strategy=strategy, stage="trial")
    anchored_entry = scan_held_bars(bars, cost=10, peak=10, strategy=strategy,
                                  stage="trial", entry_a=11)
    assert (anchored_cost.fills, anchored_entry.fills) == (0, 1)


@pytest.mark.parametrize("strategy", UNIVERSE_BOOKS)
@pytest.mark.parametrize("scores", [None, {}, {DAY: {SYMBOL: 1}}])
def test_universe_books_refuse_absent_or_single_name_cross_section(monkeypatch, strategy, scores):
    def forbidden_decide(*args, **kwargs):
        pytest.fail("must not rank an absent or one-name cross-section")

    monkeypatch.setattr(host, "decide_topk_dropout", forbidden_decide)
    monkeypatch.setattr(host, "decide_topk_score_exit", forbidden_decide)
    with pytest.raises(ValueError, match="single-symbol.*cross-section.*full score universe"):
        scan_held_bars(FLAT_BARS, cost=10, peak=10, strategy=strategy, symbol=SYMBOL,
                       held=[SYMBOL], scores_by_day=scores, topk=1, n_drop=1)


@pytest.mark.parametrize("symbol", [SYMBOL, OTHER])
def test_dropout_bools_come_from_full_universe_rank(symbol):
    scores = {SYMBOL: 1, OTHER: 2}
    held = [SYMBOL, OTHER]
    _buy, sell = decide_topk_dropout(held, scores, topk=1, n_drop=1)
    result = scan_held_bars(
        FLAT_BARS, cost=10, peak=10, strategy="topk_dropout", symbol=symbol,
        held=held, scores_by_day={DAY: scores}, topk=1, n_drop=1, bar_dates=[DAY, DAY],
    )
    expected_fills = 2 if symbol in sell else 0
    assert (result.bars, result.fills, result.skips) == (2, expected_fills, 2 - expected_fills)


@pytest.mark.parametrize("symbol", [SYMBOL, OTHER])
def test_score_exit_sx0_bools_come_from_existing_plan(symbol):
    scores = {SYMBOL: 0, OTHER: 2}
    held = [SYMBOL, OTHER]
    plan = decide_topk_score_exit(held, scores, topk=2, n_drop=0)
    assert not plan.sell_bottom
    result = scan_held_bars(
        FLAT_BARS, cost=10, peak=10, strategy="topk_score_exit", symbol=symbol,
        held=held, scores_by_day={DAY: scores}, topk=2, n_drop=0,
    )
    expected_fills = 2 if symbol in plan.sell_sx0 else 0
    assert (result.bars, result.fills, result.skips) == (2, expected_fills, 2 - expected_fills)


@pytest.mark.parametrize("strategy", UNIVERSE_BOOKS)
def test_universe_rank_is_frozen_per_day_and_recomputed_on_new_day(monkeypatch, strategy):
    scores = {DAY: {SYMBOL: -1, OTHER: 2}, "20260107": {SYMBOL: 2, OTHER: -1}}
    decider_name = "decide_" + strategy
    original = getattr(host, decider_name)
    calls = []

    def decide(held, day_scores, **kwargs):
        calls.append(day_scores)
        return original(held, day_scores, **kwargs)

    monkeypatch.setattr(host, decider_name, decide)
    result = scan_held_bars(
        FLAT_BARS * 2, cost=10, peak=10, strategy=strategy, symbol=SYMBOL,
        held=[SYMBOL, OTHER], scores_by_day=scores, topk=1, n_drop=1,
        bar_dates=[DAY, DAY, "20260107", "20260107"],
    )
    assert calls == list(scores.values())
    assert (result.bars, result.fills, result.skips) == (4, 2, 2)


@pytest.mark.parametrize("strategy", UNIVERSE_BOOKS)
def test_missing_score_day_raises(strategy):
    with pytest.raises(RuntimeError, match="missing scores.*20260107"):
        scan_held_bars(FLAT_BARS, cost=10, peak=10, strategy=strategy, symbol=SYMBOL,
                       held=[SYMBOL, OTHER], scores_by_day={DAY: {SYMBOL: 1, OTHER: 2}},
                       topk=1, n_drop=1, bar_dates=[DAY, "20260107"])


@pytest.mark.parametrize("strategy", UNIVERSE_BOOKS)
@pytest.mark.parametrize("fields,match", [
    ({"held": None}, "held"), ({"held": [OTHER]}, "symbol.*held"),
    ({"held": [SYMBOL, "600000"]}, "canonical"),
    ({"topk": None}, "topk"), ({"n_drop": None}, "n_drop"),
    ({"topk": -1}, "topk"), ({"n_drop": -1}, "n_drop"),
    ({"topk": 1.5}, "topk"), ({"n_drop": 1.5}, "n_drop"),
])
def test_universe_requires_opening_book_and_nonnegative_integers(strategy, fields, match):
    kwargs = dict(symbol=SYMBOL, held=[SYMBOL, OTHER],
                  scores_by_day={DAY: {SYMBOL: 1, OTHER: 2}}, topk=1, n_drop=1)
    kwargs.update(fields)
    with pytest.raises(ValueError, match=match):
        scan_held_bars(FLAT_BARS, cost=10, peak=10, strategy=strategy, **kwargs)


def test_unknown_strategy_raises():
    with pytest.raises(ValueError, match="unknown minute strategy"):
        scan_held_bars(FLAT_BARS, cost=10, peak=10, strategy="unknown")


@pytest.mark.parametrize("source,root_arg", [("qlib_1min", "qlib_root"), ("lake", "lake_root")])
@pytest.mark.parametrize("existing_root", [False, True])
@pytest.mark.parametrize("runner", [load_scan_bars, run_scan])
def test_missing_data_never_becomes_a_zero_summary(tmp_path, source, root_arg, existing_root, runner):
    root = tmp_path if existing_root else tmp_path / "missing"
    kwargs = {root_arg: root}
    if runner is run_scan:
        kwargs.update(cost=10, peak=10)
    with pytest.raises(FileNotFoundError) as error:
        runner(SYMBOL, DAY, DAY, source=source, **kwargs)
    assert SYMBOL in str(error.value)
    assert str(root) in str(error.value)


@pytest.mark.parametrize("source,root_arg", [("qlib_1min", "qlib_root"), ("lake", "lake_root")])
def test_source_requires_its_explicit_root(source, root_arg):
    with pytest.raises(ValueError, match=root_arg):
        load_scan_bars(SYMBOL, DAY, DAY, source=source)


def test_unknown_source_lists_both_allowed_sources():
    with pytest.raises(ValueError, match="qlib_1min.*lake"):
        load_scan_bars(SYMBOL, DAY, DAY, source="csv")


def _write_bin(path, ref, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(np.asarray([ref, *values], dtype="<f").tobytes())


@pytest.fixture
def qlib_root(tmp_path):
    calendar = tmp_path / "calendars" / "1min.txt"
    calendar.parent.mkdir()
    calendar.write_text(
        "2026-01-05 14:55:00\n2026-01-06 09:30:00\n2026-01-06 09:31:00\n"
        "2026-01-06 09:32:00\n2026-01-06 09:33:00\n2026-01-07 09:30:00\n",
        encoding="utf-8",
    )
    feature = tmp_path / "features" / "sz000739"
    _write_bin(feature / "close.1min.bin", 0, [999, 10.05, np.nan, np.inf, 9.75, 999])
    _write_bin(feature / "open.1min.bin", 0, [999, 10.0, 10, 10, 9.7, 999])
    _write_bin(feature / "high.1min.bin", 0, [999, 10.1, 10, 10, 9.8, 999])
    # Different feature offset; missing low is legal only on dropped-close rows.
    _write_bin(feature / "low.1min.bin", 1, [9.95, np.nan, np.nan, 9.6])
    return tmp_path


def test_qlib_low_aligns_by_kept_calendar_positions_without_preload(qlib_root):
    bars = load_scan_bars("000739_SZ", date(2026, 1, 6), date(2026, 1, 6),
                          source="qlib_1min", qlib_root=qlib_root)
    assert len(bars) == 2
    assert [bar.low for bar in bars] == pytest.approx([9.95, 9.6])
    assert [bar.close for bar in bars] == pytest.approx([10.05, 9.75])
    assert [bar.open for bar in bars] == pytest.approx([10.0, 9.7])
    assert [bar.high for bar in bars] == pytest.approx([10.1, 9.8])


@pytest.mark.parametrize("values", [None, [], [np.nan], [np.inf], [9.95]])
def test_qlib_missing_or_nonfinite_kept_low_raises(qlib_root, values):
    path = qlib_root / "features" / "sz000739" / "low.1min.bin"
    if values is None:
        path.unlink()
    else:
        _write_bin(path, 1, values)
    with pytest.raises((FileNotFoundError, ValueError), match="low"):
        load_scan_bars(SYMBOL, DAY, DAY, source="qlib_1min", qlib_root=qlib_root)


def test_qlib_absent_symbol_raises(qlib_root):
    with pytest.raises(FileNotFoundError, match="600000.SH"):
        load_scan_bars("600000.SH", DAY, DAY, source="qlib_1min", qlib_root=qlib_root)


@pytest.fixture
def lake_root(tmp_path):
    directory = tmp_path / "symbol=000739_SZ"
    directory.mkdir()
    pd.DataFrame({
        "time": [pd.Timestamp(stamp, tz="UTC").value // 1_000_000 for stamp in
                 ["2026-01-06 09:31", "2026-01-06 09:30"]],
        "open": [9.7, 10.0], "high": [9.8, 10.1],
        "low": [9.6, 9.95], "close": [9.75, 10.05],
    }).to_parquet(directory / "data.parquet", index=False)
    return tmp_path


def test_lake_walks_the_reader_index_in_time_order(lake_root):
    bars = load_scan_bars(SYMBOL, DAY, DAY, source="lake", lake_root=lake_root)
    assert bars == [OhlcBar(10.0, 10.1, 9.95, 10.05), OhlcBar(9.7, 9.8, 9.6, 9.75)]


@pytest.mark.parametrize("source,root_arg", [("qlib_1min", "qlib_root"), ("lake", "lake_root")])
def test_loader_keeps_source_dates_aligned_with_bars(request, source, root_arg):
    dates = []
    bars = load_scan_bars(SYMBOL, DAY, DAY, source=source,
                          **{root_arg: request.getfixturevalue(root_arg)}, bar_dates=dates)
    assert dates == [date(2026, 1, 6)] * len(bars)
    assert len(bars) == 2


@pytest.mark.parametrize("source,root_arg", [("qlib_1min", "qlib_root"), ("lake", "lake_root")])
def test_run_scan_uses_each_source_date_for_universe_rank(request, source, root_arg):
    root = request.getfixturevalue(root_arg)
    if source == "lake":
        path = root / "symbol=000739_SZ" / "data.parquet"
        frame = pd.read_parquet(path)
        next_day = frame.copy()
        next_day["time"] += 24 * 60 * 60 * 1000
        pd.concat([frame, next_day]).to_parquet(path, index=False)
    else:
        feature = root / "features" / "sz000739"
        for name, values in {
            "open": [999, 10, 10, 10, 9.7, 10],
            "high": [999, 10.1, 10, 10, 9.8, 10.1],
            "close": [999, 10.05, np.nan, np.inf, 9.75, 10.05],
            "low": [999, 9.95, np.nan, np.nan, 9.6, 9.95],
        }.items():
            _write_bin(feature / f"{name}.1min.bin", 0, values)
    scores = {DAY: {SYMBOL: 1, OTHER: 2}, "20260107": {SYMBOL: 2, OTHER: 1}}
    result = run_scan(
        SYMBOL, DAY, "20260107", source=source, **{root_arg: root}, cost=10, peak=10,
        strategy="topk_dropout", held=[SYMBOL, OTHER], scores_by_day=scores, topk=1, n_drop=1,
    )
    assert result.fills == 2
    assert result.skips == (2 if source == "lake" else 1)


@pytest.mark.parametrize("column", ["open", "high", "low", "close"])
def test_lake_missing_ohlc_raises(lake_root, column):
    path = lake_root / "symbol=000739_SZ" / "data.parquet"
    pd.read_parquet(path).drop(columns=column).to_parquet(path, index=False)
    with pytest.raises(FileNotFoundError) as error:
        load_scan_bars(SYMBOL, DAY, DAY, source="lake", lake_root=lake_root)
    assert SYMBOL in str(error.value)
    assert str(lake_root) in str(error.value)


def test_lake_empty_window_raises(lake_root):
    with pytest.raises(FileNotFoundError, match=SYMBOL):
        load_scan_bars(SYMBOL, "20260107", "20260107", source="lake", lake_root=lake_root)


@pytest.mark.parametrize("source,root_flag", [("qlib_1min", "--qlib-root"), ("lake", "--lake-root")])
def test_cli_missing_data_exits_nonzero(tmp_path, capsys, source, root_flag):
    assert main(["--source", source, "--symbol", SYMBOL, "--start", DAY, "--end", DAY,
                 root_flag, str(tmp_path), "--cost", "10", "--peak", "10"]) != 0
    output = capsys.readouterr()
    assert output.out == ""
    assert SYMBOL in output.err
    assert str(tmp_path) in output.err


def test_cli_prints_one_summary_line(lake_root, capsys):
    assert main(["--source", "lake", "--symbol", SYMBOL, "--start", DAY, "--end", DAY,
                 "--lake-root", str(lake_root), "--cost", "10", "--peak", "10"]) == 0
    assert capsys.readouterr().out == f"symbol={SYMBOL} source=lake version1 bars=2 fills=1 skips=1\n"


def _lake_cli_args(lake_root):
    return ["--source", "lake", "--symbol", SYMBOL, "--start", DAY, "--end", DAY,
            "--lake-root", str(lake_root), "--cost", "10", "--peak", "10"]


def test_cli_can_select_version2(lake_root, capsys):
    assert main(_lake_cli_args(lake_root) + ["--strategy", "version2"]) == 0
    assert capsys.readouterr().out == f"symbol={SYMBOL} source=lake version2 bars=2 fills=1 skips=1\n"


@pytest.fixture
def scores_dir(tmp_path):
    directory = tmp_path / "scores"
    directory.mkdir()
    pd.DataFrame({"code": [SYMBOL, OTHER], "score": [-1, 2]}).to_csv(
        directory / f"{DAY}.csv", index=False,
    )
    return directory


def _universe_cli_args(strategy, scores_dir):
    return ["--strategy", strategy, "--scores-dir", str(scores_dir),
            "--held", f"{SYMBOL},{OTHER}", "--topk", "1", "--n-drop", "1"]


@pytest.mark.parametrize("strategy", UNIVERSE_BOOKS)
def test_cli_universe_uses_full_scores_dir(lake_root, scores_dir, capsys, strategy):
    assert main(_lake_cli_args(lake_root) + _universe_cli_args(strategy, scores_dir)) == 0
    assert capsys.readouterr().out == (
        f"symbol={SYMBOL} source=lake {strategy} bars=2 fills=2 skips=0\n"
    )


@pytest.mark.parametrize("strategy", UNIVERSE_BOOKS)
def test_cli_single_code_scores_dir_errors_without_summary(lake_root, scores_dir, capsys, strategy):
    pd.DataFrame({"code": [SYMBOL], "score": [-1]}).to_csv(scores_dir / f"{DAY}.csv", index=False)
    assert main(_lake_cli_args(lake_root) + _universe_cli_args(strategy, scores_dir)) == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert "cross-section" in output.err
    assert "full score universe" in output.err


@pytest.mark.parametrize("strategy", UNIVERSE_BOOKS)
def test_cli_pred_csv_keeps_loader_buy_day_keys(lake_root, tmp_path, capsys, strategy):
    pred = tmp_path / "pred.csv"
    pd.DataFrame({
        "date": ["2026-01-05"] * 2 + ["2026-01-06"] * 2,
        "code": [SYMBOL, OTHER] * 2, "score": [-1, 2, 2, -1],
    }).to_csv(pred, index=False)
    assert main(_lake_cli_args(lake_root) + [
        "--strategy", strategy, "--pred-csv", str(pred),
        "--held", f"{SYMBOL},{OTHER}", "--topk", "1", "--n-drop", "1",
    ]) == 0
    assert capsys.readouterr().out == (
        f"symbol={SYMBOL} source=lake {strategy} bars=2 fills=2 skips=0\n"
    )


@pytest.mark.parametrize("strategy", UNIVERSE_BOOKS)
@pytest.mark.parametrize("use_both", [False, True])
def test_cli_requires_exactly_one_score_source(lake_root, scores_dir, capsys, strategy, use_both):
    flags = ["--strategy", strategy, "--held", f"{SYMBOL},{OTHER}",
             "--topk", "1", "--n-drop", "1"]
    if use_both:
        flags += ["--scores-dir", str(scores_dir), "--pred-csv", str(scores_dir / f"{DAY}.csv")]
    assert main(_lake_cli_args(lake_root) + flags) == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert "--pred-csv" in output.err and "--scores-dir" in output.err


def test_cli_unknown_strategy_exits_one(lake_root, capsys):
    assert main(_lake_cli_args(lake_root) + ["--strategy", "unknown"]) == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert "invalid choice" in output.err


def test_cli_strategy_choices_are_exactly_wired_names(lake_root, capsys):
    assert main(_lake_cli_args(lake_root) + ["--strategy", "unknown"]) == 1
    error = capsys.readouterr().err
    choices = error.split("(choose from ", 1)[1].split(")", 1)[0]
    assert tuple(choice.strip("'\"") for choice in choices.split(", ")) == wired_names()


def test_source_guards():
    old_source = (ROOT / "backtest/research/csv_minute_backtest.py").read_text(encoding="utf-8")
    assert "minute_bar_scan_host" not in old_source
    source = (ROOT / "backtest/research/minute_bar_scan_host.py").read_text(encoding="utf-8")
    for forbidden in ("write_minute_cache", "load_minute_ohlc", "_read_lake_minute", "MatchCore", "simulate"):
        assert forbidden not in source
    calls = [node for node in ast.walk(ast.parse(source)) if isinstance(node, ast.Call)
             and isinstance(node.func, ast.Name) and node.func.id == "invoke_minute_strategy"]
    assert len(calls) == 1
    assert all(isinstance(call.args[0], ast.Name) and call.args[0].id == "strategy"
               for call in calls)
    for flag in ("dropout_sell", "sx0_sell"):
        assert f"{flag}=True" not in source.replace(" ", "")


@pytest.mark.parametrize("source", ["lake", "qlib_1min"])
@pytest.mark.parametrize("membership", ["000739", "600000", ""])
def test_round_trip_cli_buys_only_pool_member(tmp_path, capsys, source, membership):
    pool = tmp_path / "pool"
    pool.mkdir()
    (pool / f"{DAY}.csv").write_text(membership + "\n", encoding="utf-8")
    root = tmp_path / "bars"
    root.mkdir()
    stamps = ["2026-01-06 14:54", "2026-01-06 14:55", "2026-01-06 14:56"]
    values = {"open": [10, 10, 9.7], "high": [12, 10, 9.8],
              "low": [9, 10, 9.6], "close": [10, 10, 9.75]}
    if source == "lake":
        directory = root / "symbol=000739_SZ"
        directory.mkdir()
        pd.DataFrame(dict(time=[pd.Timestamp(stamp, tz="UTC").value // 1_000_000
                                for stamp in stamps], **values)).to_parquet(
            directory / "data.parquet", index=False)
        root_flag = "--lake-root"
    else:
        calendar = root / "calendars"
        calendar.mkdir()
        (calendar / "1min.txt").write_text("\n".join(stamps) + "\n", encoding="utf-8")
        for name, prices in values.items():
            _write_bin(root / "features" / "sz000739" / f"{name}.1min.bin", 0, prices)
        root_flag = "--qlib-root"
    assert main(["--source", source, "--symbol", SYMBOL, "--start", DAY, "--end", DAY,
                 root_flag, str(root), "--pool-dir", str(pool), "--cash", "2000",
                 "--daily-quota", "1001"]) == 0
    output = capsys.readouterr().out
    assert len(output.splitlines()) == 1
    if membership == "000739":
        assert "bars=3 buys=1 sells=0 skips=2 equity=1974.00" in output
        assert float(output.split("return_pct=")[1]) == pytest.approx(-1.3, abs=0.000002)
    else:
        assert "buys=0 sells=0 skips=3 equity=2000.00 return_pct=0.000000" in output


@pytest.mark.parametrize("hms,buys", [([870, 894, 896], 1), ([869, 896, 897], 0)])
def test_round_trip_existing_buy_window_fallback(hms, buys):
    frame = pd.DataFrame({"date": [date(2026, 1, 6)] * 3, "hm": hms,
                          "open": [10, 10, 9.7], "high": [10, 10, 9.8],
                          "low": [10, 10, 9.6], "close": [10, 10, 9.75]})
    result = host.scan_version1_round_trip(frame, symbol=SYMBOL,
                                          daily_quota=1001, pool_days={date(2026, 1, 6): [SYMBOL]})
    assert (result.buys, result.sells) == (buys, 0)


@pytest.mark.parametrize("buy_hm", [895, 894])
def test_round_trip_rebuys_after_same_day_sell(buy_hm):
    first, second = date(2026, 1, 6), date(2026, 1, 7)
    frame = pd.DataFrame({
        "date": [first, second, second, second],
        "hm": [895, 870, buy_hm, 896],
        "open": [10, 9.7, 10, 10.5], "high": [10, 9.8, 10, 11],
        "low": [10, 9.6, 10, 10.5], "close": [10, 9.75, 10, 11],
    })
    result = host.scan_version1_round_trip(
        frame, symbol=SYMBOL, cash=2000, daily_quota=1001,
        pool_days={first: [SYMBOL], second: [SYMBOL]},
    )
    assert (result.buys, result.sells, result.skips) == (2, 1, 1)
    assert result.equity == pytest.approx(2067.03)


def test_round_trip_reenters_later_pool_day_and_marks_open_shares():
    first, second = date(2026, 1, 6), date(2026, 1, 7)
    frame = pd.DataFrame({
        "date": [first, first, second, second, second],
        "hm": [895, 896, 870, 895, 896],
        "open": [10, 9.7, 9.7, 10, 10.5], "high": [10, 9.8, 9.8, 10, 11],
        "low": [10, 9.6, 9.6, 10, 10.5], "close": [10, 9.75, 9.75, 10, 11],
    })
    result = host.scan_version1_round_trip(frame, symbol=SYMBOL, cash=2000, daily_quota=1001,
                                          pool_days={first: [SYMBOL], second: [SYMBOL]})
    assert (result.buys, result.sells, result.skips) == (2, 1, 2)
    assert result.equity == pytest.approx(2067.03)


@pytest.mark.parametrize("quota", [0, -100, float("inf"), float("nan"), True])
def test_round_trip_rejects_invalid_daily_quota(quota):
    with pytest.raises(ValueError, match="daily_quota"):
        host.scan_version1_round_trip(pd.DataFrame(), symbol=SYMBOL, pool_days={}, daily_quota=quota)


@pytest.mark.parametrize("symbol", [SYMBOL, "688001.SH"])
@pytest.mark.parametrize("cash,quota,members,budget", [
    (2000, 999, 1, 999),
    (999, 2000, 1, 999),
    (2000, 1998, 2, 999),
    (2000, 1000, 1, 1000),
])
def test_round_trip_unaffordable_buy_stops_before_fill(
    monkeypatch, symbol, cash, quota, members, budget,
):
    day = date(2026, 1, 6)
    frame = pd.DataFrame({"date": [day, day], "hm": [895, 896],
                          **{name: [10, 10] for name in host.OHLC}})
    def unexpected_exit(*args, **kwargs):
        pytest.fail("unaffordable buy must stop before holding or scanning an exit")
    monkeypatch.setattr(host, "scan_bar_exit", unexpected_exit)
    pool = [symbol] + (["600000.SH"] if members == 2 else [])
    with pytest.raises(RuntimeError) as error:
        host.scan_version1_round_trip(
            frame, symbol=symbol, cash=cash, daily_quota=quota, pool_days={day: pool},
        )
    assert str(error.value) == (
        f"Insufficient buy budget: symbol={symbol} needed=1001.00000000 "
        f"budget={budget:.8f} cash={cash:.8f}"
    )


def test_round_trip_one_lot_budget_includes_existing_fee():
    from backtest.research.ashare_fees import COMMISSION, trade_commission
    day = date(2026, 1, 6)
    frame = pd.DataFrame({"date": [day], "hm": [895],
                          **{name: [10] for name in host.OHLC}})
    result = host.scan_version1_round_trip(
        frame, symbol=SYMBOL, cash=1001, daily_quota=1001, pool_days={day: [SYMBOL]},
    )
    assert (result.buys, result.sells, result.skips) == (1, 0, 0)
    assert result.equity == pytest.approx(1001 - trade_commission(1000, COMMISSION))


def test_round_trip_existing_fee_reduces_equity(monkeypatch):
    day = date(2026, 1, 6)
    frame = pd.DataFrame({"date": [day, date(2026, 1, 7)], "hm": [895, 896],
                          "open": [10, 9.7], "high": [10, 9.8],
                          "low": [10, 9.6], "close": [10, 9.75]})
    args = dict(symbol=SYMBOL, pool_days={day: [SYMBOL]}, cash=10000, daily_quota=5005)
    paid = host.scan_version1_round_trip(frame, **args)
    monkeypatch.setattr(host, "COMMISSION", 0.0)
    free = host.scan_version1_round_trip(frame, **args)
    assert (paid.buys, paid.sells) == (free.buys, free.sells) == (1, 1)
    assert paid.equity < free.equity
    assert free.equity - paid.equity == pytest.approx(5 + 4.85)


def test_round_trip_size_matches_existing_sizer_when_fee_fits():
    from backtest.research.csv_ledger import _buy_size
    day = date(2026, 1, 6)
    frame = pd.DataFrame({"date": [day, day], "hm": [895, 896],
                          "open": [10, 11], "high": [10, 11],
                          "low": [10, 11], "close": [10, 11]})
    result = host.scan_version1_round_trip(
        frame, symbol=SYMBOL, cash=10000, daily_quota=8008,
        pool_days={day: [SYMBOL, "600000.SH"]},
    )
    expected, _ = _buy_size(4004, 10)
    assert expected > 100
    assert result.buys == 1 and result.sells == 0
    assert result.equity == pytest.approx(10000 - 4000 - 4 + expected * 11)


@pytest.mark.parametrize("cash", [1_000_000, 21_000_000])
def test_round_trip_million_quota_sizes_whole_lots_including_fee(cash):
    from backtest.research.ashare_fees import COMMISSION, trade_commission
    day = date(2026, 1, 6)
    price = 23.74
    quota = 1_000_000
    frame = pd.DataFrame({"date": [day, day], "hm": [895, 896],
                          **{name: [price, price + 0.01] for name in host.OHLC}})
    result = host.scan_version1_round_trip(
        frame, symbol="603196.SH", cash=cash, daily_quota=quota,
        pool_days={day: ["603196.SH"]},
    )
    shares = 42_000
    notional = shares * price
    debit = notional + trade_commission(notional, COMMISSION)
    assert COMMISSION == 0.001
    assert shares > 100 and shares % 100 == 0
    assert debit <= quota and debit <= cash
    next_notional = (shares + 100) * price
    assert next_notional + trade_commission(next_notional, COMMISSION) > quota
    assert (result.buys, result.sells) == (1, 0)
    assert result.equity == pytest.approx(cash - debit + shares * (price + 0.01))


def test_scan_matches_before_style_decisions():
    from scripts.research.bench_minute_bar_scan_host import assert_scan_equivalence
    assert_scan_equivalence()


def test_qlib_reads_calendar_and_each_bin_once(qlib_root, monkeypatch):
    import backtest.research.minute_bar_scan_host as host
    calendar_calls = []
    bin_calls = []
    calendar_reader, bin_reader = host.load_qlib_1min_calendar, host.read_qlib_bin
    def calendar(root):
        calendar_calls.append(root)
        return calendar_reader(root)
    def feature(path, i0, i1):
        bin_calls.append((path.name, i0, i1))
        return bin_reader(path, i0, i1)
    monkeypatch.setattr(host, "load_qlib_1min_calendar", calendar)
    monkeypatch.setattr(host, "read_qlib_bin", feature)
    load_scan_bars(SYMBOL, DAY, DAY, source="qlib_1min", qlib_root=qlib_root)
    assert calendar_calls == [qlib_root]
    assert bin_calls == [(f"{name}.1min.bin", 1, 4) for name in host.OHLC]


@pytest.mark.parametrize("name", ["open", "high", "close"])
@pytest.mark.parametrize("values", [None, [], [np.nan], [np.inf]])
def test_qlib_required_bins_fail_closed(qlib_root, name, values):
    path = qlib_root / "features" / "sz000739" / f"{name}.1min.bin"
    if values is None:
        path.unlink()
    else:
        _write_bin(path, 1, values)
    with pytest.raises((FileNotFoundError, ValueError)):
        load_scan_bars(SYMBOL, DAY, DAY, source="qlib_1min", qlib_root=qlib_root)


def test_qlib_empty_window_raises(qlib_root):
    with pytest.raises(FileNotFoundError, match="window"):
        load_scan_bars(SYMBOL, "20270101", "20270101", source="qlib_1min", qlib_root=qlib_root)


def test_scan_resolves_catalog_once(monkeypatch):
    import backtest.research.minute_bar_scan_host as host
    calls = []
    original = host.minute_strategy_entries
    def entries():
        calls.append(1)
        return original()
    monkeypatch.setattr(host, "minute_strategy_entries", entries)
    scan_held_bars([OhlcBar(10, 10.1, 9.95, 10.05)] * 100, cost=10, peak=10)
    assert calls == [1]


def test_scan_preserves_first_catalog_validation(monkeypatch):
    import backtest.research.minute_true_core_wire as wire
    monkeypatch.setattr(wire, "minute_strategy_names", lambda: ("unclassified",))
    with pytest.raises(RuntimeError, match="not classified"):
        scan_held_bars([OhlcBar(10, 10.1, 9.95, 10.05)], cost=10, peak=10)


def test_qlib_kept_close_alignment_matches_public_reader(qlib_root):
    from backtest.research.qlib_bin_1min import load_qlib_bin_1min_bars
    frame = load_qlib_bin_1min_bars([SYMBOL], date(2026, 1, 6), date(2026, 1, 6),
                                    qlib_root=qlib_root, workers=1, preload_days=0)[SYMBOL]
    dates, frames = [], []
    bars = load_scan_bars(SYMBOL, DAY, DAY, source="qlib_1min", qlib_root=qlib_root,
                          bar_dates=dates, source_frames=frames)
    assert dates == list(frame["date"])
    pd.testing.assert_frame_equal(frames[0][["date", "hm"]], frame[["date", "hm"]])
    for name in ("open", "high", "close"):
        np.testing.assert_array_equal([getattr(bar, name) for bar in bars], frame[name])


def test_round_trip_resolves_once_and_matches_wire_sells(monkeypatch):
    import backtest.research.minute_bar_scan_host as host
    from backtest.research.minute_true_core_wire import invoke_minute_strategy
    day = date(2026, 1, 6)
    frame = pd.DataFrame({
        "date": [day] + [date(2026, 1, 7)] * 4, "hm": [895, 896, 897, 898, 899],
        "open": [10, 11, 10.9, 10, 10], "high": [10, 12, 11, 10.1, 10.1],
        "low": [10, 10.9, 10.8, 9.95, 9.95], "close": [10, 11.8, 10.9, 10, 10],
    })
    calls, decisions = [], []
    entries, scan = host.minute_strategy_entries, host.scan_bar_exit
    def catalog():
        calls.append(1)
        return entries()
    def checked(bar, position, **fields):
        result = scan(bar, position, **fields)
        expected = invoke_minute_strategy("version1", bar, cost=10,
                                         peak=10 if not decisions else decisions[-1].peak,
                                         n_days=1, timing="same_bar")
        assert result == expected
        decisions.append(result)
        return result
    monkeypatch.setattr(host, "minute_strategy_entries", catalog)
    monkeypatch.setattr(host, "scan_bar_exit", checked)
    result = host.scan_version1_round_trip(frame, symbol=SYMBOL, daily_quota=1001, pool_days={day: [SYMBOL]})
    assert result.buys >= 1 and result.sells == 1
    assert calls == [1]
    assert [result.reason for result in decisions] == ["", "profit_take:drawdown:50"]


def test_lake_window_matches_public_reader_normalization(tmp_path, monkeypatch):
    import pyarrow.parquet as pq
    from backtest.research.ashare_bars import load_minute_from_lake
    from backtest.research.market_layer import utc_ms_range

    folder = tmp_path / "symbol=000739_SZ"
    folder.mkdir()
    stamps = ["2026-01-05 09:30", "2026-01-06 09:31", "2026-01-06 09:30",
              "2026-01-06 12:00", "2026-01-06 09:31", "2026-01-07 09:30",
              "2026-01-08 09:30", "2026-01-09 09:30"]
    prices = np.arange(len(stamps), dtype=float) + 10
    pd.DataFrame({
        "time": pd.to_datetime(stamps, utc=True).asi8 // 1_000_000,
        **{name: prices for name in host.OHLC},
        "volume": [100, 999, 100, 100, 100, 0, 100, 100],
    }).to_parquet(folder / "data.parquet", index=False, row_group_size=2)
    expected = load_minute_from_lake([SYMBOL], DAY, "20260108", workers=1,
                                     lake_root=tmp_path)[SYMBOL]
    original = pq.read_table
    calls = []

    def read_table(*args, **kwargs):
        calls.append(kwargs)
        return original(*args, **kwargs)

    monkeypatch.setattr(pq, "read_table", read_table)
    dates, frames = [], []
    bars = load_scan_bars(SYMBOL, DAY, "20260108", source="lake", lake_root=tmp_path,
                          bar_dates=dates, source_frames=frames)
    assert bars == [OhlcBar(*row) for row in expected[list(host.OHLC)].itertuples(index=False, name=None)]
    assert [bar.close for bar in bars] == [12, 14, 16]
    assert dates == list(expected.index.date)
    assert dates == [date(2026, 1, 6), date(2026, 1, 6), date(2026, 1, 8)]
    assert frames[0]["hm"].tolist() == expected["hm"].tolist()
    t0, t1 = utc_ms_range(DAY, "20260108")
    assert len(calls) == 1
    assert calls[0]["filters"] == [("time", ">=", t0), ("time", "<=", t1)]


@pytest.mark.parametrize("buy_day", [date(2025, 10, 27), date(2025, 10, 31), date(2025, 11, 4)])
def test_round_trip_same_day_take_profit_waits_until_next_day(buy_day):
    from datetime import timedelta
    from backtest.research.bar_scan_exit import HeldPosition, OhlcBar, scan_bar_exit

    symbol = "603196.SH"
    next_day = buy_day + timedelta(days=1)
    frame = pd.DataFrame({
        "date": [buy_day, buy_day, next_day], "hm": [895, 896, 570],
        "open": [24.28, 27, 27], "high": [24.28, 30, 30],
        "low": [24.28, 27, 27], "close": [24.28, 27, 27],
    })
    book = host._version1_book()
    exit_result = scan_bar_exit(
        OhlcBar(27, 30, 27, 27),
        HeldPosition(24.28, 24.28, book.stop_pct, book.drawdown_of(1)),
        timing="same_bar",
    )
    assert exit_result.decision == "fill"
    assert exit_result.reason.startswith("profit_take:")
    args = dict(symbol=symbol, pool_days={buy_day: [symbol]}, cash=10000, daily_quota=10000)
    same_day = host.scan_version1_round_trip(frame.iloc[:2], **args)
    assert (same_day.buys, same_day.sells, same_day.skips) == (1, 0, 1)
    next_day_result = host.scan_version1_round_trip(frame, **args)
    assert (next_day_result.buys, next_day_result.sells, next_day_result.skips) == (1, 1, 1)
