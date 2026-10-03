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


def test_default_scan_still_invokes_version1(monkeypatch):
    original = host.invoke_minute_strategy
    calls = []

    def invoke(name, bar, **kwargs):
        calls.append((name, kwargs))
        return original(name, bar, **kwargs)

    monkeypatch.setattr(host, "invoke_minute_strategy", invoke)
    scan_held_bars(FLAT_BARS, cost=10, peak=10)
    assert [name for name, _ in calls] == ["version1", "version1"]
    assert all(fields["n_days"] == 1 and fields["timing"] == "same_bar"
               and fields["cost"] == 10 for _, fields in calls)


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
    assert isinstance(calls[0].args[0], ast.Name)
    assert calls[0].args[0].id == "strategy"
    for flag in ("dropout_sell", "sx0_sell"):
        assert f"{flag}=True" not in source.replace(" ", "")
