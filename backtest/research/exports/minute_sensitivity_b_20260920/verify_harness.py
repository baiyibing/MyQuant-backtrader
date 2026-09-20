"""Opt-in evidence checks for the research harness, not production behavior pins."""

from dataclasses import replace
from datetime import timedelta
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.research import run_minute_sensitivity_b as h


def schedule(bars, *, engine="Book", side="buy", at=None, cash=100_000., previous=None, **kwargs):
    return h.next_open(engine=engine, side=side, decision_at=at or h.stamp(h.DAY, 585),
                       candidates=bars, previous_by_day=previous if previous is not None else
                       {h.DAY: 10., h.NEXT_DAY: 10.}, shares=100, cash=cash, **kwargs)


def test_strict_submit_time_rejects_adjacent_boundary_and_ignores_future_close():
    bars = [h.Bar(h.DAY, 586, 10.1, 100.), h.Bar(h.DAY, 587, 10.2, 1.)]
    result, attempts = schedule(bars)
    assert result["fill_at"] == h.stamp(h.DAY, 586)
    assert result["fill_px"] == 10.2
    assert attempts[0]["outcome"] == "before_submit"
    changed = [replace(b, close=12345.) for b in bars]
    assert schedule(changed) == (result, attempts)


def test_fallback_does_not_backdate_decision_or_order():
    case = next(c for c in h.fixtures() if c.case_id == "fallback_0943")
    rows, _ = h.clock_rows([case])
    row = rows[0]
    assert row["quote_age_seconds"] == 120
    assert row["baseline_fill_at"] == h.stamp(h.DAY, 585)
    assert row["next_fill_at"] > row["submit_at"] > row["quote_at"]


def test_first_eligible_open_not_best_later_price_and_no_cash_retry():
    bars = [h.Bar(h.DAY, 587, 10.5, 10.5), h.Bar(h.DAY, 588, 9.8, 9.8)]
    result, _ = schedule(bars)
    assert result["fill_px"] == 10.5
    result, attempts = schedule(bars, cash=1020.)
    assert result["status"] == "UNFILLED"
    assert result["reason"] == "cash_reject_terminal" and len(attempts) == 1
    assert result["cash_after"] == 1020.


def test_limit_release_and_overnight_use_that_sessions_reference():
    bars = [h.Bar(h.DAY, 587, 11., 11.), h.Bar(h.NEXT_DAY, 571, 11., 11.)]
    result, attempts = schedule(bars, previous={h.DAY: 10., h.NEXT_DAY: 10.2})
    assert attempts[0]["outcome"] == "limit_up"
    assert result["fill_at"].date() == h.NEXT_DAY and result["fill_px"] == 11.
    no_ref, _ = schedule(bars, previous={})
    assert no_ref["status"] == "UNFILLED" and no_ref["reason"] == "missing_limit_reference"


def test_buy_limit_down_is_engine_specific_and_sell_limit_is_preserved():
    bars = [h.Bar(h.DAY, 587, 9., 9.)]
    assert schedule(bars)[0]["status"] == "FILLED"
    assert schedule(bars, engine="v7")[0]["reason"] == "limit_down"
    assert schedule(bars, side="sell")[0]["reason"] == "limit_down"


def test_lunch_t1_missing_and_closing_call_boundaries():
    rows = {r["case_id"]: r for r in h.boundary_rows()}
    assert rows["lunch"]["fill_at"] == h.stamp(h.DAY, 780)
    assert rows["t1_same_day"]["reason"] == "t1_locked"
    assert rows["t1_next_session"]["status"] == "FILLED"
    assert rows["closing_call_skip"]["reason"] == "outside_continuous_session"
    assert rows["missing_quote_pending_next_session"]["reason"] == "chase:T+1"
    assert schedule([])[0]["fill_px"] is None


def test_future_volume_cannot_fund_open_and_gap_passes_t1_first():
    rows = h.gap_rows()
    for row in rows:
        if row["cap_on"]:
            assert row["shares"] == 0
            assert row["reason"] == "skip_volume_unavailable:bucket_not_completed"
        else:
            assert row["shares"] == 1000 and row["fill_px"] == 9.4
    boundary = next(r for r in h.boundary_rows() if r["case_id"] == "next_open_future_volume")
    assert boundary["reason"] == "skip_volume_unavailable:bucket_not_completed"


def test_capacity_partial_missing_late_and_shared_buy_sell_budget():
    for row in h.capacity_rows():
        if row["cap_on"] and row["case_id"] == "partial":
            assert row["shares"] == 300
        if row["cap_on"] and row["case_id"] in ("missing", "late"):
            assert row["shares"] == 0
    for engine in ("Book", "v7"):
        rows = [r for r in h.shared_capacity_rows() if r["engine"] == engine and r["cap_on"]]
        assert [r["shares"] for r in rows] == [300, 50]
        assert all(r["final_bucket_used"] == 350 for r in rows)


def test_clock_cohorts_keep_unfilled_out_of_returns_and_rank_only_within_engine():
    rows, _ = h.clock_rows(h.fixtures())
    for row in rows:
        if not row["matched_fill"]:
            assert row["next_local_return"] is None
            assert "local_rank_delta" not in row
        else:
            assert row["next_shares"] == row["baseline_shares"]
            assert row["next_cash_after"] >= 0
        if row["case_id"] == "unchanged_price":
            assert row["local_pnl_delta"] == 0 and row["same_price"]
    for group in h.summaries(rows)[:2]:
        assert group["matched_fill_rate"] == group["common_fills"] / group["baseline_fills"]
        assert group["full_replay_status"] == "DATA_GAP"
        assert group["max_drawdown"] is None


def test_fee_math_no_double_count_and_cost_pressure_monotonic():
    fee = h.economics(10., 11., 1000)
    assert fee["buy_fee"] == 10. and fee["sell_fee"] == 11.
    assert fee["net_pnl"] == 979.
    alternative = h.economics(10., 11., 1000, scheme="REPLACE_COMMISSION_3BP_MIN5_STAMP_SELL5BP")
    assert alternative["buy_fee"] == 5. and alternative["sell_fee"] == 5.
    assert alternative["stamp_fee"] == 5.5 and alternative["net_pnl"] == 984.5
    pnl = [h.economics(10., 11., 1000, slip_bp=bp)["net_pnl"] for bp in (0, 5, 10, 20)]
    assert pnl == sorted(pnl, reverse=True) and len(set(pnl)) == 4
    granularity = [r for r in h.fee_granularity_rows() if r["scheme"].startswith("REPLACE")]
    assert [r["sell_commission"] for r in granularity] == [10., 5.]


def test_v7_baseline_sizes_and_prices_match_public_ladder_sequence():
    trial = h.Bar(h.PREV_DAY, 895, 10., 10.).record()
    cases = [c for c in h.fixtures() if c.engine == "v7" and c.case_id.endswith("_add")]
    bars = [trial] + [h.Bar(h.DAY, 885 + i * 3, c.price, c.price).record() for i, c in enumerate(cases)]
    daily = {h.SYMBOL: {h.PREV_DAY - timedelta(days=1): 10., h.PREV_DAY: 11.}}
    result = h.v7.simulate_v7({h.SYMBOL: bars}, daily, {h.PREV_DAY: [h.SYMBOL]},
                             [h.PREV_DAY, h.DAY], cash_total=2_000_000.)
    trades = [t for t in result.trades if t["reason"].startswith("buy:add_")]
    assert len(trades) == 4 and result.positions[h.SYMBOL].stage == "full"
    for case, trade in zip(cases, trades):
        base = h.baseline(case)
        assert (base["fill_px"], base["shares"], base["reason"]) == (trade["price"], trade["shares"], trade["reason"])


def test_modeb_baseline_fee_overlay_agrees_with_public_result():
    for row in h.modeb_baselines():
        econ = h.economics(row["entry_px"], row["fill_px"], row["shares"])
        assert econ["net_pnl"] == pytest.approx(row["local_pnl"])
        assert econ["net_return"] == pytest.approx(row["local_return"])
        assert row["oracle"] == "NOT_RUN_EX_POST_UPPER_BOUND_NOT_EXECUTABLE"


def test_output_is_reproducible_and_refuses_overwrite(tmp_path):
    before = h.source_hashes()
    first, second = tmp_path / "first", tmp_path / "second"
    h.run(first)
    with pytest.raises(FileExistsError):
        h.run(first)
    h.run(second)
    assert before == h.source_hashes()
    for path in first.iterdir():
        assert path.read_bytes() == (second / path.name).read_bytes()
        assert b"\x00" not in path.read_bytes()
        assert b"\r" not in path.read_bytes()
        assert not path.read_bytes().startswith(b"\xef\xbb\xbf")


def read_rows(path):
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def clear_lake_env(monkeypatch):
    for key in ("OSKH_SOURCE_PARQUET_ROOT", "OSKH_AUTHORITY_HINT_ROOT", "OSKH_PERIOD_1M_ROOT",
                "QLIB_1MIN_ROOT", "OSKH_QLIB_1MIN_ROOT"):
        monkeypatch.delenv(key, raising=False)


def assert_full_gaps(output):
    for filename in ("clock_trades.csv", "clock_summary.csv", "cost_sensitivity.csv",
                     "capacity.csv", "modeb_baseline.csv"):
        for row in read_rows(output / filename):
            assert row["production_replay"] == "DATA_GAP"
            for field in ("full_strategy_nav", "full_strategy_return", "max_drawdown",
                          "strategy_rank", "strategy_rank_delta"):
                assert row[field] == ""


@pytest.mark.parametrize("configured", [False, True])
def test_lake_unset_or_nonexistent_root_writes_gaps_and_refuses_overwrite(tmp_path, monkeypatch, configured):
    clear_lake_env(monkeypatch)
    if configured:
        monkeypatch.setenv("OSKH_SOURCE_PARQUET_ROOT", str(tmp_path / "missing_lake"))
    output = tmp_path / "gaps"
    result = h.run_lake(output)
    assert result["status"] == result["lake_read_status"] == "DATA_GAP"
    manifest = json.loads((output / "manifest.json").read_text())
    assert manifest["base"] == "f2fe15124ffbc62d3c0526fc90fed78d014b1bb1"
    assert manifest["bar_label_semantics"] == "lake_index_is_bar_start_wallclock"
    assert manifest["source"] == "parquet_lineage"
    assert manifest["access"] in (None, "qlib_bin_1min", "oskh_parquet_1m")
    assert manifest["access_preference"] == "qlib_bin_1min_then_oskh_parquet_1m"
    assert bool(manifest["resolved_1m_root"]) == configured
    assert (manifest["OSKH_SOURCE_PARQUET_ROOT"] != "unset") == configured
    assert set(manifest["source_hashes_before"]) == set(h.source_hashes())
    assert manifest["source_hashes_before"] == manifest["source_hashes_after"]
    for row in read_rows(output / "clock_trades.csv"):
        assert row["baseline_status"] == row["next_status"] == "DATA_GAP"
        for field in ("decision_px", "baseline_fill_px", "next_fill_px", "baseline_shares",
                      "next_shares", "baseline_local_pnl", "next_local_return", "local_rank_delta"):
            assert row[field] == ""
    assert not read_rows(output / "clock_candidates.csv")
    assert_full_gaps(output)
    with pytest.raises(FileExistsError):
        h.run_lake(output)
    for name, digest in manifest["files"].items():
        data = (output / name).read_bytes()
        assert hashlib.sha256(data).hexdigest() == digest
        assert b"\x00" not in data and not data.startswith(b"\xef\xbb\xbf")


def test_lake_start_clock_frozen_order_rejects_close_available_open():
    day = h.DAY
    bars = [h.LakeBar(day, 586, 21.1, 999.), h.LakeBar(day, 587, 21.2, 1.)]
    args = dict(engine="Book", side="buy", decision_at=h.stamp(day, 586), candidates=bars,
                previous_by_day={day: 21.}, shares=100, cash=100_000.,
                symbol="600000.SH", sessions=(day,))
    result, attempts = h.next_open(**args)
    assert bars[0].start == h.stamp(day, 586)
    assert bars[0].end == h.stamp(day, 587)
    assert attempts[0]["outcome"] == "before_submit"
    assert result["fill_at"] == h.stamp(day, 587) and result["fill_px"] == 21.2
    assert result["shares"] == 100
    changed = dict(args, candidates=[replace(b, close=123.) for b in bars])
    assert h.next_open(**changed) == (result, attempts)
    capped, _ = h.next_open(**args, cap=h.VolumeCap(.1, {
        ("600000.SH", day.strftime("%Y%m%d"), 588): h.BucketVolume(100_000, 588, "raw_shares_incremental")}))
    assert capped["reason"] == "skip_volume_unavailable:bucket_not_completed"


def write_test_parquet(container):
    """Constructed test input ONLY. Never committed/exported as a 4090 sample."""
    import pyarrow as pa
    import pyarrow.parquet as pq
    from oskh_data.symbol_format import to_partition_key
    path = container / "stock/period=1m/dividend_type=none" / f"symbol={to_partition_key(h.SYMBOL)}" / "data.parquet"
    path.parent.mkdir(parents=True)
    rows = []
    for day in (h.PREV_DAY, h.DAY, h.NEXT_DAY):
        for hm, op, close in ((570, 20., 20.5), (585, 20.8, 21.), (586, 21.1, 21.15),
                              (587, 21.2, 21.25), (884, 21.1, 21.2), (885, 21.1, 21.2),
                              (886, 21.25, 21.3), (887, 21.3, 21.4), (895, 21.3, 21.4),
                              (896, 21.45, 21.5), (897, 21.5, 21.5), (900, 21.5, 21.5)):
            rows.append(dict(time=pd.Timestamp(h.stamp(day, hm), tz="UTC").value // 1_000_000,
                             open=op, close=close, high=max(op, close), low=min(op, close), volume=100_000))
    pq.write_table(pa.Table.from_pylist(rows), path)
    return path


def test_lake_actual_reader_on_temporary_parquet_no_production_monkeypatch(tmp_path, monkeypatch):
    clear_lake_env(monkeypatch)
    container = tmp_path / "constructed_test_input_not_production"
    path = write_test_parquet(container)
    before = path.read_bytes()
    monkeypatch.setenv("OSKH_SOURCE_PARQUET_ROOT", str(container))
    output = tmp_path / "output"
    h.run_lake(output, symbols=[h.SYMBOL])
    assert path.read_bytes() == before
    manifest = json.loads((output / "manifest.json").read_text())
    assert manifest["lake_read_status"] == "READ_OK"
    assert manifest["input_files"][0]["size"] == len(before)
    clocks = read_rows(output / "clock_trades.csv")
    book = next(r for r in clocks if r["engine"] == "Book" and r["date"] == "2026-09-17")
    assert book["baseline_fill_px"] == "21.0"
    assert book["baseline_fill_at"] == "2026-09-17 09:46:00"
    assert book["submit_at"] == "2026-09-17 09:46:00.001000"
    assert book["next_fill_at"] == "2026-09-17 09:47:00"
    assert book["next_fill_px"] == "21.2"
    assert book["next_shares"] == book["baseline_shares"]
    trial = next(r for r in clocks if r["engine"] == "v7" and r["date"] == "2026-09-17"
                 and r["stage"] == "trial" and r["signal_hm"] == "885")
    assert trial["baseline_status"] == trial["next_status"] == "FILLED"
    assert trial["injected_entry_a"] == "20.0" and trial["next_fill_px"] == "21.3"
    assert trial["next_shares"] == trial["baseline_shares"]
    for r in clocks:
        if r["date"] == "2026-09-16":
            assert r["baseline_status"] == "DATA_GAP"  # no invented prior close
        if r["date"] == "2026-09-18" and r["baseline_status"] == "FILLED":
            assert r["local_pair_status"] == "DATA_GAP"  # no fabricated future mark
        if r["engine"] == "v7" and r["date"] == "2026-09-17" and r["signal_hm"] == "884":
            assert r["baseline_reason"] == "outside_add_window"
        assert r["local_rank_delta"] == ""
    capacities = [r for r in read_rows(output / "capacity.csv") if r["case_id"] == trial["case_id"]]
    assert [r["shares"] for r in capacities] == [trial["baseline_shares"], "0"]
    assert capacities[1]["reason"] == "skip_volume_unavailable:missing_or_untyped"
    assert all(r["volume_status"] == "DATA_GAP" and r["raw_volume"] == "" for r in capacities)
    costs = [r for r in read_rows(output / "cost_sensitivity.csv")
             if r["case_id"] == book["case_id"] and r["axis"] == "slippage"]
    pnl = [float(r["net_pnl"]) for r in costs]
    assert pnl == sorted(pnl, reverse=True) and len(set(pnl)) == 4
    assert_full_gaps(output)


def test_lake_missing_partition_and_corrupt_partition_are_visible(tmp_path, monkeypatch):
    clear_lake_env(monkeypatch)
    container = tmp_path / "bad_input"
    path = write_test_parquet(container)
    path.write_bytes(b"explicitly invalid test parquet")
    monkeypatch.setenv("OSKH_SOURCE_PARQUET_ROOT", str(container))
    output = tmp_path / "output"
    h.run_lake(output, symbols=["600000.SH,000001.SZ"])
    manifest = json.loads((output / "manifest.json").read_text())
    assert manifest["lake_read_status"] == "DATA_GAP"
    assert len([r for r in read_rows(output / "data_gaps.csv") if r["item"] == "symbol_window"]) == 2
    assert all(r["baseline_status"] == "DATA_GAP" for r in read_rows(output / "clock_trades.csv"))
    assert_full_gaps(output)


def test_lake_cli_batch_alias_dates_and_conflicts(tmp_path, monkeypatch):
    clear_lake_env(monkeypatch)
    script = ROOT / "scripts/research/run_minute_sensitivity_b.py"
    output = tmp_path / "alias"
    run = subprocess.run([sys.executable, str(script), "--batch", "2", "--output-dir", str(output),
                          "--symbols", "600000.SH,000001.SZ", "--symbols", "600000.SH"],
                         capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    assert json.loads((output / "manifest.json").read_text())["symbols"] == ["000001.SZ", "600000.SH"]
    for options in (("--mode", "synthetic", "--batch", "2"),
                    ("--mode", "lake", "--start", "2026-09-16"),
                    ("--mode", "lake", "--start", "20260919", "--end", "20260918")):
        bad = subprocess.run([sys.executable, str(script), "--output-dir", str(tmp_path / "bad"), *options],
                             capture_output=True, text=True)
        assert bad.returncode != 0 and not (tmp_path / "bad").exists()


def test_lake_source_fence_is_fatal_before_artifacts(tmp_path, monkeypatch):
    hashes = h.source_hashes()
    hashes[next(iter(hashes))] = "0" * 64
    # Only the research harness evidence hook is replaced; production is untouched.
    monkeypatch.setattr(h, "source_hashes", lambda: hashes)
    for run in (h.run, h.run_lake):
        with pytest.raises(ValueError, match="Production source differs"):
            run(tmp_path / "must_not_exist")
        assert not (tmp_path / "must_not_exist").exists()
