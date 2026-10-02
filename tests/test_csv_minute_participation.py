"""共享 CLI/run 的 opt-in 边界；全部 data-free，不把合成分数当收益。"""

from copy import deepcopy

import pandas as pd
import pytest

from backtest.research import csv_minute_backtest as minute
from backtest.research.ashare_volume_cap import VolumeCap
from backtest.research.csv_minute_volume import completed_minute_volumes

CODE = "600000.SH"
DAY = "20251024"


@pytest.fixture
def loaded(monkeypatch, tmp_path):
    pool = tmp_path / "pool"
    pool.mkdir()
    (pool / f"{DAY}.csv").write_text("600000,浦发银行\n", encoding="utf-8")
    bars = {CODE: pd.DataFrame({"ymd": [DAY, DAY], "hm": [570, 895],
                               "open": [10., 10.], "high": [10., 10.],
                               "low": [10., 10.], "close": [10., 10.], "volume": [10**9, 2500]},
                              index=pd.to_datetime(["2025-10-24 09:30", "2025-10-24 14:55"]))}
    daily = {CODE: pd.DataFrame({name: [10., 10.] for name in ("open", "high", "low", "close")},
                               index=pd.to_datetime(["2025-10-23", "2025-10-24"]))}
    loads = []

    def load(*args, **kwargs):
        loads.append(kwargs)
        return deepcopy(bars)

    monkeypatch.setattr(minute, "load_minute_bars", load)
    monkeypatch.setattr(minute, "load_daily_ohlc", lambda *a, **k: deepcopy(daily))
    monkeypatch.setattr(minute, "load_exdiv_ratios", lambda *a, **k: None)
    monkeypatch.setattr(minute, "warn_stale_period_env", lambda: None)
    monkeypatch.setattr(minute.time, "perf_counter", lambda: 1.)
    return dict(strategy="version6", pool_dir=pool, daily_quota=5000), bars, loads


def buys(state):
    return [trade["shares"] for trade in state.trades if trade["side"] == "BUY"]


def test_run_omitted_equals_none_and_never_requests_or_reads_volume(loaded, monkeypatch):
    options, bars, loads = loaded
    bars[CODE] = bars[CODE].drop(columns="volume")
    monkeypatch.setattr(minute, "completed_minute_volumes", lambda *_: pytest.fail("cap off consulted volume"))
    omitted = minute.run(DAY, DAY, **options)
    explicit = minute.run(DAY, DAY, participation_rate=None, **options)
    assert vars(omitted) == vars(explicit)
    assert omitted.volume_cap is None
    assert buys(omitted) == [500]
    assert all("include_volume" not in call for call in loads)


@pytest.mark.parametrize("rate,want", [(0., []), (.1, [200]), (1., [500])])
def test_run_cap_from_loaded_minute_clamps_in_shares(loaded, rate, want):
    options, _, loads = loaded
    state = minute.run(DAY, DAY, participation_rate=rate, **options)
    assert buys(state) == want
    assert isinstance(state.volume_cap, VolumeCap)
    assert loads[0]["include_volume"] is True
    assert state.run_metadata["volume_capacity"]["available_at"] == "bucket_end"


def test_topk_defaults_stay_50_5_with_loaded_cap(loaded):
    options, _, _ = loaded
    options.update(strategy="topk_dropout", scores_by_day={DAY: {CODE: 1.0}})
    state = minute.run(DAY, DAY, participation_rate=.1, **options)
    assert (state.stats["topk"], state.stats["n_drop"]) == (50, 5)
    assert buys(state) == [200]  # 合成接线断言，不报告组合收益。


@pytest.mark.parametrize("flag,expected", [([], None), (["--participation-rate", "0.1"], .1),
                                           (["--participation-rate", "0"], 0.)])
def test_cli_parses_optional_rate(monkeypatch, flag, expected):
    class Captured(Exception):
        pass

    def run(*args, **kwargs):
        assert kwargs.get("participation_rate") == expected
        if expected is None:
            assert "participation_rate" not in kwargs
        raise Captured

    monkeypatch.setattr(minute, "run", run)
    with pytest.raises(Captured):
        minute.main(["--strategy", "version6", *flag])


@pytest.mark.parametrize("value", ["nan", "inf", "-inf", "-0.01", "1.01"])
def test_invalid_rate_raises_value_error_before_io(monkeypatch, value):
    monkeypatch.setattr(minute, "run", lambda *a, **k: pytest.fail("invalid rate reached run"))
    with pytest.raises(ValueError, match="finite and in"):
        minute.main(["--strategy", "version6", f"--participation-rate={value}"])


@pytest.mark.parametrize("change", ["missing_volume", "missing_frame", "fractional", "nan", "negative", "duplicate"])
def test_bad_volume_fail_closed(loaded, change):
    options, bars, _ = loaded
    if change == "missing_volume":
        bars[CODE] = bars[CODE].drop(columns="volume")
    elif change == "missing_frame":
        bars.clear()
    elif change == "duplicate":
        bars[CODE] = pd.concat([bars[CODE], bars[CODE].iloc[[-1]]])
    else:
        bars[CODE]["volume"] = {"fractional": 1.5, "nan": float("nan"), "negative": -1}[change]
    with pytest.raises(ValueError):
        minute.run(DAY, DAY, participation_rate=.1, **options)


def test_auction_and_missing_lookup_never_borrow_daily_or_next_volume(loaded):
    _, bars, _ = loaded
    lookup = completed_minute_volumes(bars)
    cap = VolumeCap(.1, lookup)
    assert (CODE, DAY, 570) not in lookup
    assert lookup[CODE, DAY, 895].shares == 2500
    for hm in (570, 894, 896):
        quantity, reason = cap.clamp((CODE, DAY, hm), hm, 500, buy=True)
        assert quantity == 0 and reason.startswith("skip_volume_unavailable")


@pytest.mark.parametrize("kwargs", [{"minute_source": "qlib_1min"}, {"dividend_type": "front"},
                                     {"tail_window_buy": True, "tail_volume_unit": "lots"}])
def test_cap_rejects_unattested_domains_before_loading(loaded, kwargs):
    options, _, loads = loaded
    with pytest.raises(ValueError, match="shares"):
        minute.run(DAY, DAY, participation_rate=.1, **options, **kwargs)
    assert loads == []


def test_cli_cap_emits_rate_and_assumption_manifest(loaded, monkeypatch, tmp_path):
    import json

    options, _, _ = loaded
    monkeypatch.setattr(minute, "maybe_compare_daily", lambda *a, **k: None)
    out = tmp_path / "arm"
    assert minute.main(["--strategy", "version6", "--start", DAY, "--end", DAY,
                        "--pool-dir", str(options["pool_dir"]), "--out-dir", str(out),
                        "--participation-rate", ".1"]) == 0
    manifest = json.loads((out / "run-manifest.json").read_text())
    assert manifest["participation_rate"] == .1
    metadata = json.loads((out / "run-metadata.json").read_text())
    assert metadata["volume_capacity"]["unit"] == "raw_shares_incremental"
