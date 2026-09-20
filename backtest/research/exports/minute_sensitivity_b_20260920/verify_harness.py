"""Opt-in evidence checks for the research harness, not production behavior pins."""

from dataclasses import replace
from datetime import timedelta
from pathlib import Path
import sys

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
