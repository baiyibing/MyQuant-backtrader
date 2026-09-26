"""Strict original-parquet coverage for the opt-in s11 signal domain."""

import hashlib

import numpy as np
import pandas as pd
import pytest
from backtest.research import s11_exit_domain as domain
from backtest.research.csv_daily_loader import load_daily_bars
from oskh_data.symbol_format import to_partition_key

CODE = "600000.SH"
START, END = "20240902", "20240904"


def frame():
    return pd.DataFrame(
        {"open": [10.2, 9.45, 9.7], "high": [10.5, 9.7, 9.8],
         "low": [10., 9.4, 9.6], "close": [10.5, 9.45, 9.7]},
        index=pd.bdate_range(START, periods=3).as_unit("ms"), dtype=float,
    )


def write_partition(root, bars, kind="front", code=CODE, volume=None):
    path = root / f"dividend_type={kind}" / f"symbol={to_partition_key(code)}" / "data.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    data = bars.reset_index(drop=True)
    data.insert(0, "time", [int(stamp.timestamp() * 1000) for stamp in bars.index.tz_localize("UTC")])
    if volume is not None:
        data["volume"] = volume
    data.to_parquet(path, index=False)
    return path


def lake(root, *, raw=None, front=None, raw_volume=None, front_volume=None):
    raw = frame() if raw is None else raw
    front = raw * .9 if front is None else front
    paths = (
        write_partition(root, raw, "none", volume=raw_volume),
        write_partition(root, front, "front", volume=front_volume),
    )
    consumed = load_daily_bars({CODE}, START, END, workers=1, daily_root=root)
    return consumed, paths


def load(root, raw):
    return domain.load_signal_bars_front(raw, {CODE}, START, END, daily_root=root)


def test_actual_source_hashes_and_resolver_only(tmp_path, monkeypatch):
    raw, paths = lake(tmp_path)
    monkeypatch.setattr(domain, "resolve_period_root", lambda period: tmp_path if period == "1d" else None)
    actual, meta = domain.load_signal_bars_front(raw, {CODE}, START, END)
    pd.testing.assert_frame_equal(actual[CODE], frame() * .9, check_freq=False)
    assert meta["loaded_start"] == START and meta["loaded_end"] == END
    for key, path in zip(("raw_sources", "front_sources"), paths):
        assert meta[key] == [{"code": CODE, "path": str(path),
                             "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                             "rows": 3, "effective_rows": 3}]
        assert len(meta[f"{key}_sha256"]) == 64


@pytest.mark.parametrize("missing", ["directory", "symbol", "raw_directory", "raw_symbol"])
def test_missing_source_fails_closed(tmp_path, missing):
    raw, paths = lake(tmp_path)
    index = 0 if missing.startswith("raw") else 1
    path = paths[index]
    path.unlink()
    if missing.endswith("directory"):
        path.parent.rmdir()
        path.parent.parent.rmdir()
    with pytest.raises(FileNotFoundError, match="s11 exit domain.*missing"):
        load(tmp_path, raw)


@pytest.mark.parametrize("missing_row", [0, 1, 2])
def test_front_missing_history_or_t_fails_closed(tmp_path, missing_row):
    raw, _ = lake(tmp_path)
    write_partition(tmp_path, (frame() * .9).drop(frame().index[missing_row]))
    with pytest.raises(ValueError, match=f"date={frame().index[missing_row]:%Y%m%d}.*front.*missing"):
        load(tmp_path, raw)


def test_front_only_date_is_snapshot_conflict(tmp_path):
    raw, _ = lake(tmp_path)
    extra = frame() * .9
    extra.index = pd.to_datetime(["2024-09-01", "2024-09-03", "2024-09-04"])
    write_partition(tmp_path, extra)
    with pytest.raises(ValueError, match="missing raw observation"):
        load(tmp_path, raw)
    # Unlike the case above, this date lies inside the requested scope.
    extra = frame().iloc[:2] * .9
    raw_bars = frame().iloc[[0, 2]]
    raw, _ = lake(tmp_path, raw=raw_bars, front=extra)
    with pytest.raises(ValueError, match="missing raw observation"):
        load(tmp_path, raw)
    write_partition(tmp_path, frame() * .9)
    with pytest.raises(ValueError, match="date=20240903.*date conflict: front-only"):
        load(tmp_path, raw)


@pytest.mark.parametrize("kind", ["none", "front"])
@pytest.mark.parametrize("bad", [np.nan, np.inf, 0., -1.])
def test_invalid_price_on_suspended_day_skipped_not_rejected(tmp_path, kind, bad):
    """Industry standard (2026-09-26): zero-volume rows with 0/NaN price are
    suspension (skip); nonzero-volume rows with bad prices are data corruption
    (fail). Both domains get the same volume pattern so the date-set is symmetric."""
    vol = [100., 0., 100.]
    raw, _ = lake(tmp_path, raw_volume=vol, front_volume=vol)
    broken = frame() * (.9 if kind == "front" else 1.)
    broken.loc[broken.index[1], "close"] = bad
    write_partition(tmp_path, broken, kind, volume=vol)
    actual, _ = load(tmp_path, raw)
    assert actual is not None


@pytest.mark.parametrize("kind", ["none", "front"])
@pytest.mark.parametrize("bad", [np.nan, np.inf, 0., -1.])
def test_invalid_price_on_trading_day_still_fails(tmp_path, kind, bad):
    """Bad price on a nonzero-volume (trading) day is still data corruption."""
    raw, _ = lake(tmp_path)
    broken = frame() * (.9 if kind == "front" else 1.)
    broken.loc[broken.index[1], "close"] = bad
    write_partition(tmp_path, broken, kind, volume=[100., 100., 100.])
    with pytest.raises(ValueError, match=f"date=20240903.*domain={kind}.*nonfinite or nonpositive price on tradable"):
        load(tmp_path, raw)


@pytest.mark.parametrize("kind", ["none", "front"])
def test_duplicate_original_rows_rejected_before_legacy_keep_last(tmp_path, kind):
    raw, _ = lake(tmp_path)
    duplicate = pd.concat([frame(), frame().iloc[[1]]])
    write_partition(tmp_path, duplicate * (.9 if kind == "front" else 1.), kind)
    with pytest.raises(ValueError, match=f"date=20240903.*domain={kind}.*duplicate"):
        load(tmp_path, raw)


def test_same_suspension_filter_is_allowed_but_one_domain_filter_is_not(tmp_path):
    raw, _ = lake(tmp_path, raw_volume=[100., 0., 100.], front_volume=[100., 0., 100.])
    actual, _ = load(tmp_path, raw)
    assert list(actual[CODE].index) == [pd.Timestamp(START), pd.Timestamp(END)]
    write_partition(tmp_path, frame() * .9, volume=[100., 100., 100.])
    with pytest.raises(ValueError, match="date=20240903.*date conflict: front-only"):
        load(tmp_path, raw)


def test_consumed_raw_snapshot_change_is_rejected(tmp_path):
    raw, _ = lake(tmp_path)
    write_partition(tmp_path, frame() * 1.01, "none")
    with pytest.raises(ValueError, match="raw snapshot conflict"):
        load(tmp_path, raw)


def test_corrupt_partition_carries_code_domain_path(tmp_path):
    raw, paths = lake(tmp_path)
    paths[1].write_bytes(b"broken parquet")
    with pytest.raises(ValueError) as caught:
        load(tmp_path, raw)
    assert all(value in str(caught.value) for value in (CODE, "domain=front", str(paths[1])))


def test_missing_consumed_code_rejected(tmp_path):
    lake(tmp_path)
    with pytest.raises(ValueError, match="domain=none.*missing bars"):
        load(tmp_path, {})


def test_natural_short_history_is_not_missing_history(tmp_path):
    raw, _ = lake(tmp_path, raw=frame().iloc[-1:])
    actual, _ = load(tmp_path, raw)
    assert len(actual[CODE]) == 1


def test_memory_validation_includes_warmup_and_excludes_future_prices():
    raw, front = {CODE: frame()}, {CODE: frame() * .9}
    domain.validate_signal_bars(raw, front, start=END, end=END)
    front[CODE] = front[CODE].iloc[1:]
    with pytest.raises(ValueError, match="date=20240902.*missing"):
        domain.validate_signal_bars(raw, front, start=END, end=END)
    front = {CODE: frame() * .9}
    front[CODE].loc[pd.Timestamp(END)] = np.nan
    domain.validate_signal_bars(raw, front, start=START, end="20240903")


@pytest.mark.parametrize("engine_name", ["daily", "minute"])
def test_future_index_interleaving_fails_before_engine_initialization(engine_name, monkeypatch):
    from backtest.research import csv_daily_backtest, csv_minute_backtest

    engine = csv_daily_backtest if engine_name == "daily" else csv_minute_backtest
    raw = {CODE: frame()}
    front = {CODE: (frame() * .9).iloc[[0, 2, 1]]}
    # The <=START prefix alone is sorted; the original index is not safe for
    # day_bar_and_prev_closes/searchsorted and must be rejected as a whole.
    assert front[CODE].loc[:pd.Timestamp(START)].index.is_monotonic_increasing

    def forbidden(*_args, **_kwargs):
        pytest.fail("invalid full index must fail before account initialization")

    monkeypatch.setattr(engine, "init_sim_state", forbidden)
    minutes = frame().assign(volume=100., hm=570, ymd=frame().index.strftime("%Y%m%d"))
    minutes.index += pd.Timedelta(minutes=570)
    args = (raw,) if engine_name == "daily" else ({CODE: minutes}, raw)
    with pytest.raises(ValueError, match="daily dates must be sorted"):
        engine.simulate(*args, {START: [CODE]}, START, START, strategy="version11",
                        fix_s11_exit_domain=True, signal_bars_front=front)


@pytest.mark.parametrize("problem", ["duplicate", "nonfinite", "unsorted", "missing_code", "non_daily"])
def test_memory_validation_fails_closed(problem):
    raw, front = {CODE: frame()}, {CODE: frame() * .9}
    if problem == "duplicate":
        front[CODE] = pd.concat([front[CODE], front[CODE].iloc[[0]]])
    elif problem == "nonfinite":
        front[CODE].iloc[0, 3] = np.nan
    elif problem == "unsorted":
        front[CODE] = front[CODE].iloc[::-1]
    elif problem == "missing_code":
        front = {}
    else:
        front[CODE].index += pd.Timedelta(hours=1)
    with pytest.raises(ValueError, match="s11 exit domain"):
        domain.validate_signal_bars(raw, front, start=START, end=END)


def test_metadata_off_has_no_disk_reads_and_truthful_domains(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("OFF metadata must not read a source")

    monkeypatch.setattr(domain, "resolve_period_root", forbidden)
    monkeypatch.setattr(domain.Path, "read_bytes", forbidden)
    meta = domain.build_run_metadata(
        enabled=False, execution_domain="front", daily_source="qlib_day", exdiv=None,
        raw_bars={CODE: frame()},
    )
    assert meta["exit_signal_domain"] == "legacy_execution_bars"
    assert meta["fill_domain"] == meta["mark_domain"] == "front"
    assert meta["execution_reference_policy"] == "legacy_unmapped"
    assert meta["execution_reference_map_loaded"] is False
    assert meta["sources"] is None
    assert len(meta["consumed_execution_bars_sha256"]) == 64


def test_metadata_on_separates_signal_from_execution_map():
    meta = domain.build_run_metadata(
        enabled=True, execution_domain="none", daily_source="lake", minute_source="lake",
        exdiv={CODE: {END: .9}}, source_metadata={"front_sources_sha256": "input hash"},
    )
    assert meta["exit_signal_domain"] == "front"
    assert meta["fill_domain"] == meta["mark_domain"] == "none"
    assert meta["execution_reference_policy"] == "legacy_none_reference_map"
    assert meta["execution_reference_map_loaded"] is True
    assert meta["signal_exdiv_remap"] is False
