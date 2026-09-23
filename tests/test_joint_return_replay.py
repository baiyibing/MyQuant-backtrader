"""Hand-computed data-free pins; no lake, network, PortAna or sibling dependency."""
from copy import deepcopy
import csv
from datetime import timedelta
import json
from pathlib import Path
import subprocess
import sys

import pytest

from backtest.research import joint_return_replay as jr

DAYS = ["2026-09-07", "2026-09-08", "2026-09-09"]


def ts(day=0, clock="09:30:00"):
    return f"{DAYS[day]}T{clock}+08:00"


def initial(cash=5000, **positions):
    return dict(cash=cash, quantity_unit="share", native_stop="N/A", positions={
        inst: dict(quantity=q, lot_id=f"lot-{inst}", instance_id=f"instance-{inst}") for inst, q in positions.items()})


def spec(inst="A", side="BUY", quantity=100, day=0, **kwargs):
    return dict(instrument=inst, side=side, quantity=quantity, day=day, **kwargs)


def bundle(specs=(), *, state=None, fees=None, days=3):
    """Build the exact MQ #92 wire layout with explicit independent reference plans.

    Numeric reference states are fixture bookkeeping only; actual replay cash
    and lots must be independent from these states.
    """
    state = deepcopy(state if state is not None else initial())
    fee_policy = dict(model="commission_only", buy_rate=0, sell_rate=0, minimum=0,
                      granularity="per_order", source="synthetic-explicit")
    fee_policy.update(fees or {})
    cal = DAYS[:days]
    md = dict(code_shas={"MQ": jr.BASE_MQ, "BT": jr.CONTRACT_BASE_BT},
        implementation_bases={"MQ": jr.BASE_MQ, "BT": jr.CONTRACT_BASE_BT}, contract_hash=jr.CONTRACT_HASH,
        pred_recorder_id="8a061ea428e04bb3a199a485ade49d0e", candidate_recorder_id="d03e8ffcb6d14668b4d6fc2b192bc8c7",
        sidecar_sha256="27320f8b7f6de3854802f97325f682039732470ce387f21bc9cd6c3083b7b348",
        generated_at=ts(2, "16:00:00"), window={"start": cal[0], "end": cal[-1]}, calendar=cal,
        timezone="Asia/Shanghai", price_domain="none", strategy=dict(topk=10, n_drop=3,
        source="frozen_original_intents", eligibility_version="synthetic", eligibility_rules={"frozen": True}, native_stop="N/A"),
        fees=fee_policy, risk_budget=1, valuation_version="synthetic-none-v1", benchmark_version="same-fill-P-BASE-v1",
        order_policy=jr.ORDER_POLICY.copy(), quantity_policy=dict(unit="share", buy_lot=100,
        sell="FULL_LOT_EXIT", corporate_actions="EXPLICIT_ONLY"), inputs={})
    rows, history = [], []
    states = {arm: deepcopy(state) for arm in jr.ARMS}
    plans = []
    for i, day in enumerate(cal):
        for arm in jr.ARMS:
            selected = [s for s in specs if s["day"] == i and s.get("arm", arm) == arm]
            before = deepcopy(states[arm])
            nav = before["cash"] + sum(p["quantity"] * 10 for p in before["positions"].values())
            clock = selected[0] if selected else {}
            available = clock.get("available_at", ts(i))
            decision = clock.get("decision_at", available)
            effective = clock.get("effective_at", available)
            expires = clock.get("expires_at", ts(days - 1, "09:34:00"))
            mark_at = clock.get("reference_price_at", ts(i, "09:29:00"))
            p = dict(date=day, arm_id=arm, source="frozen_original_intents", pre_state_hash=jr.content_hash(before),
                decision_at=decision, available_at=available, effective_at=effective, expires_at=expires,
                marks={inst: 10 for inst in before["positions"]}, mark_at=mark_at,
                sells=[], buys=[], buy_candidates=[], corporate_actions=[])
            for s in selected:
                inst, q = s["instrument"], s["quantity"]
                price = s.get("reference_price", 10)
                lot = s.get("lot_id", f"lot-{inst}")
                order = dict(instrument=inst, execution_symbol=f"{inst}.SYN", instance_id=f"instance-{inst}",
                    lot_id=lot, target_weight=0 if s["side"] == "SELL" else q * price / nav,
                    original_target_quantity=q, reference_price=price, reference_price_at=mark_at,
                    quantity_unit="share", quantity_conversion="SNAPSHOT_FIXED")
                p["marks"][inst] = price
                if s["side"] == "SELL":
                    p["sells"].append({**order, "approved": True, "approval_reason": "original snapshot"})
                else:
                    p["buys"].append(inst)
                    p["buy_candidates"].append({**order, "eligible": True, "eligibility_reason": "frozen eligibility"})
            for s in selected:
                candidates = p["sells"] if s["side"] == "SELL" else p["buy_candidates"]
                order = next(c for c in candidates if c["instrument"] == s["instrument"])
                r = {k: v for k, v in order.items() if k not in ("approved", "approval_reason", "eligible", "eligibility_reason")}
                r.update(arm_id=arm, decision_at=decision, available_at=available, side=s["side"],
                    reason=s.get("reason", f"ORIGINAL_10_3_{s['side']}"), reference_state_hash=p["pre_state_hash"],
                    source_plan_hash=jr.content_hash(p), effective_at=effective, expires_at=expires,
                    native_stop="N/A", **jr.ORDER_POLICY)
                r["intent_id"] = jr.content_hash(r)
                rows.append(r)
            after = deepcopy(before)
            for s in sorted(selected, key=lambda v: v["side"] != "SELL"):
                inst, q = s["instrument"], s["quantity"]
                value = q * s.get("reference_price", 10)
                fee = max(fee_policy["minimum"], value * fee_policy["buy_rate" if s["side"] == "BUY" else "sell_rate"])
                if s["side"] == "SELL":
                    after["positions"].pop(inst, None)
                    after["cash"] += value - fee
                else:
                    after["positions"][inst] = dict(quantity=q, lot_id=s.get("lot_id", f"lot-{inst}"), instance_id=f"instance-{inst}")
                    after["cash"] -= value + fee
            history.append(dict(date=day, arm_id=arm, before=before, after=after,
                before_hash=jr.content_hash(before), after_hash=jr.content_hash(after), source_plan=p,
                target_turnover=0, initial_build=not before["positions"], reference_nav=nav,
                pre_drift_weights={}, target_weights={}, reference_fees=0, native_stop="N/A"))
            plans.append(p)
            states[arm] = after
    rows = jr.sort_intents(rows)
    for name, value in (("initial_state", state), ("plans", plans), ("scores", []), ("pref", {})):
        md["inputs"][name] = dict(uri=f"synthetic://{name}", raw_sha256=jr.raw_hash(jr.canonical_bytes(value) + b"\n"),
                                 content_sha256=jr.content_hash(value), coverage="synthetic", version="v1")
    m = dict(schema_version=jr.SCHEMA_VERSION, run_id="synthetic-r1", kind="synthetic", status="MQ_DATA_FREE_PASS",
        input_status="SYNTHETIC_ONLY", execution_status="NOT_RUN", return_status="待实测", contract_hash=jr.CONTRACT_HASH,
        metadata=md, snapshot=dict(uri="synthetic://snapshot", raw_sha256="a" * 64, content_sha256="b" * 64, raw_verified=True),
        input_raw_hashes_verified=False, intent_hash=jr.content_hash(rows),
        arm_intent_hashes={a: jr.content_hash([r for r in rows if r["arm_id"] == a]) for a in jr.ARMS},
        artifacts={}, reference_states=history, initial_state=state,
        pairing=dict(arms=list(jr.ARMS), fills=list(jr.FILL_MODES), bt_acceptance="NOT_RUN"))
    return m, rows


def seal(b):
    b["content_sha256"] = jr.content_hash({k: v for k, v in b.items() if k != "content_sha256"})
    return b


def minute_bars(m, rows, *, price=10, capacity=10000):
    instruments = {r["instrument"] for r in rows} | set(m["initial_state"]["positions"])
    cal = m["metadata"]["calendar"]
    md = dict(calendar=cal.copy(), timezone="Asia/Shanghai", price_domain="none", bar_label="OPEN_TIME",
        interval_seconds=60, sessions={d: [[f"{d}T09:30:00+08:00", f"{d}T09:34:00+08:00"]] for d in cal},
        session_source="synthetic-explicit-session-fixture", initial_at=ts(0, "09:29:00"), initial_lots={},
        corporate_actions_complete=True, source="synthetic-hand-bars")
    for inst, p in m["initial_state"]["positions"].items():
        md["initial_lots"][p["lot_id"]] = dict(acquired_at="2026-09-04T09:30:00+08:00",
            execution_symbol=f"{inst}.SYN", mark_price=10, mark_at=ts(0, "09:29:00"))
    bars = [dict(instrument=inst, execution_symbol=f"{inst}.SYN", timestamp=f"{d}T09:{minute}:00+08:00",
        open=price, close=price, limit_up=100, limit_down=1, suspended=False, capacity=capacity)
        for d in cal for minute in range(30, 34) for inst in sorted(instruments)]
    return seal(dict(schema_version=jr.SCHEMA_VERSION, kind="synthetic", metadata=md, bars=bars, corporate_actions=[]))


def run(m, rows, bars=None, arm="P-BASE", mode="M-LAG"):
    return jr.replay(m, rows, seal(deepcopy(bars)) if bars is not None else minute_bars(m, rows), arm=arm, fill_mode=mode)


def write_bundle(tmp_path, m, rows):
    source = tmp_path / "mq"
    source.mkdir()
    artifacts = {"intents.csv": (rows, jr.csv_bytes(rows, jr.INTENT_FIELDS)),
                 "constraints.csv": ([], jr.csv_bytes([], jr.CONSTRAINT_FIELDS)),
                 "pref_check.json": ({"status": "SYNTHETIC_PASS"}, b'{"status":"SYNTHETIC_PASS"}\n')}
    for name, (value, raw) in artifacts.items():
        (source / name).write_bytes(raw)
        m["artifacts"][name] = dict(raw_sha256=jr.raw_hash(raw), content_sha256=jr.content_hash(value))
    (source / "manifest.json").write_bytes(jr.canonical_bytes(m) + b"\n")
    return source / "intents.csv"


def stats(out):
    return out["summary"]["results"][0]


def reasons(order):
    return {t["reason"] for t in order["transitions"]}


def test_ref_is_labeled_and_lag_strictly_after_available():
    m, rows = bundle([spec()])
    bars = minute_bars(m, rows, price=11)
    ref, lag = run(m, rows, bars, mode="M-REF"), run(m, rows, bars)
    assert ref["fills"][0]["actual_fill_at"] == ts()
    assert lag["fills"][0]["actual_fill_at"] == ts(0, "09:31:00")
    assert ref["fills"][0]["price"] == 10 and ref["fills"][0]["idealized_reference"] is True
    assert lag["fills"][0]["price"] == 11 and lag["fills"][0]["idealized_reference"] is False
    assert ref["summary"]["input_status"] == "SYNTHETIC_ONLY"
    assert ref["summary"]["return_status"] == "待实测"
    assert ref["summary"]["implementation_base_bt"] == jr.IMPLEMENTATION_BASE_BT
    assert ref["summary"]["input_implementation_bases"]["BT"] == jr.CONTRACT_BASE_BT


@pytest.mark.parametrize("label", ["OPEN_TIME", "CLOSE_TIME"])
def test_close_event_cannot_backfill_same_bar_open(label):
    m, rows = bundle([spec(available_at=ts(0, "09:31:00"))])
    b = minute_bars(m, rows)
    b["metadata"]["bar_label"] = label
    if label == "CLOSE_TIME":
        for bar in b["bars"]:
            bar["timestamp"] = (jr.stamp(bar["timestamp"]) + timedelta(minutes=1)).isoformat()
    out = run(m, rows, b)
    assert out["fills"][0]["actual_fill_at"] == ts(0, "09:32:00")


@pytest.mark.parametrize("available,expected", [("11:29:00", "13:00:00"), ("11:30:00", "13:00:00"),
                                                ("13:00:00", "13:01:00")])
def test_session_lunch_endpoints_from_metadata(available, expected):
    m, rows = bundle([spec(available_at=ts(0, available))])
    b = minute_bars(m, rows)
    b["metadata"]["sessions"][DAYS[0]] = [[ts(0, "11:29:00"), ts(0, "11:30:00")], [ts(0, "13:00:00"), ts(0, "13:02:00")]]
    first = deepcopy(b["bars"][0])
    b["bars"] = [v for v in b["bars"] if not v["timestamp"].startswith(DAYS[0])]
    b["bars"] += [{**first, "timestamp": ts(0, clock)} for clock in ("11:29:00", "13:00:00", "13:01:00")]
    assert run(m, rows, b)["fills"][0]["actual_fill_at"] == ts(0, expected)


def test_after_close_arrival_and_effective_date_are_respected():
    m, rows = bundle([spec(available_at=ts(0, "15:03:00"), effective_at=ts(1, "09:32:00"))])
    assert run(m, rows)["fills"][0]["actual_fill_at"] == ts(1, "09:32:00")


def test_t_plus_one_keeps_bought_today_lot_until_next_market_day():
    m, rows = bundle([spec(side="SELL")], state=initial(A=100))
    b = minute_bars(m, rows)
    b["metadata"]["initial_lots"]["lot-A"]["acquired_at"] = ts(0, "09:00:00")
    out = run(m, rows, b)
    assert out["fills"][0]["actual_fill_at"] == ts(1)
    assert "T_PLUS_ONE" in reasons(out["orders"][0])
    assert out["daily_nav"][0]["positions"][0]["quantity"] == 100


def test_partial_buy_across_sessions_only_old_tranche_sellable():
    m, rows = bundle([spec(quantity=200), spec(side="SELL", quantity=200, day=1, available_at=ts(1, "09:31:00"))])
    b = minute_bars(m, rows, capacity=0)
    for v in b["bars"]:
        if v["timestamp"] in (ts(0, "09:31:00"), ts(1), ts(1, "09:32:00"), ts(2)):
            v["capacity"] = 100
    out = run(m, rows, b)
    sells = [f for f in out["fills"] if f["side"] == "SELL"]
    assert [(f["actual_fill_at"], f["executed_quantity"]) for f in sells] == [(ts(1, "09:32:00"), 100), (ts(2), 100)]
    assert out["daily_nav"][1]["positions"][0]["quantity"] == 100
    assert out["daily_nav"][1]["positions"][0]["sellable_quantity"] == 0


def test_limit_down_has_no_same_session_retry_and_preserves_lot():
    m, rows = bundle([spec(side="SELL")], state=initial(A=100))
    b = minute_bars(m, rows)
    for v in b["bars"]:
        if v["timestamp"] == ts(0, "09:31:00"):
            v.update(open=1, close=1)
    out = run(m, rows, b)
    assert out["fills"][0]["actual_fill_at"] == ts(1)
    attempts = [t["at"] for t in out["orders"][0]["transitions"] if t["status"] == "ACTIVE"]
    assert ts(0, "09:32:00") not in attempts
    assert out["daily_nav"][0]["positions"][0]["quantity"] == 100
    assert "LIMIT_DOWN" in reasons(out["orders"][0])


@pytest.mark.parametrize("blocked,reason", [("limit", "LIMIT_UP"), ("suspended", "SUSPENDED"), ("missing", "NO_BAR")])
def test_buy_limit_suspension_and_missing_bars_remain_in_denominator(blocked, reason):
    m, rows = bundle([spec(expires_at=ts(0, "09:34:00"))])
    b = minute_bars(m, rows)
    if blocked == "missing":
        b["bars"] = []
    else:
        for v in b["bars"]:
            if blocked == "limit":
                v.update(open=100, close=100)
            else:
                v["suspended"] = True
    out = run(m, rows, b)
    assert not out["fills"]
    assert out["orders"][0]["status"] == "EXPIRED"
    assert reason in reasons(out["orders"][0])
    assert stats(out)["coverage"]["intent_count"] == 1
    assert stats(out)["coverage"]["original_quantity_denominator"] == 100
    assert stats(out)["coverage"]["quantity_fill_rate"] == 0


def test_cash_shortfall_rejected_or_clipped_in_whole_lots_with_fees():
    m, rows = bundle([spec(quantity=200)], state=initial(2005), fees={"minimum": 5})
    out = run(m, rows, minute_bars(m, rows, price=11))
    assert out["orders"][0]["status"] == "REJECTED"
    assert out["orders"][0]["status_reason"] == "CASH_INSUFFICIENT"
    assert out["orders"][0]["remaining_quantity"] == 100
    assert out["fills"][0]["executed_quantity"] == 100
    assert stats(out)["ending_cash"] == 900
    m, rows = bundle([spec()], state=initial(1005), fees={"minimum": 5})
    out = run(m, rows, minute_bars(m, rows, price=11))
    assert not out["fills"] and out["orders"][0]["status_reason"] == "CASH_INSUFFICIENT"


def test_oversell_actual_failed_buy_is_rejected_without_reference_ledger_reset():
    m, rows = bundle([spec(quantity=200), spec(side="SELL", quantity=200, day=1)], state=initial(2000))
    b = minute_bars(m, rows, price=11)
    out = run(m, rows, b)
    sell = next(o for o in out["orders"] if o["side"] == "SELL")
    assert sell["status"] == "REJECTED" and sell["status_reason"] == "SELLABLE_INSUFFICIENT"
    assert stats(out)["ending_positions"][0]["quantity"] == 100
    assert stats(out)["coverage"]["quantity_fill_rate"] == 0.25


def test_minimum_commission_only_increment_once_across_partial_fills():
    m, rows = bundle([spec(quantity=300)], fees={"buy_rate": 0.002, "minimum": 5})
    out = run(m, rows, minute_bars(m, rows, capacity=100))
    assert [f["fee"] for f in out["fills"]] == [5, 0, 1]
    assert [f["cumulative_fee"] for f in out["fills"]] == [5, 5, 6]
    assert stats(out)["fees"] == 6 and stats(out)["ending_cash"] == 1994
    assert stats(out)["nav_end"] == 4994
    assert stats(out)["net_return"] == pytest.approx(-6 / 5000)
    assert out["fills"][0]["status"] == "PARTIAL"
    assert out["fills"][0]["transitions"][-1]["status"] == "PARTIAL"


def test_expiration_boundary_is_exclusive_and_no_fee_for_unfilled_remainder():
    m, rows = bundle([spec(quantity=200, expires_at=ts(0, "09:32:00"))], fees={"minimum": 5})
    out = run(m, rows, minute_bars(m, rows, capacity=100))
    assert len(out["fills"]) == 1
    assert out["orders"][0]["status"] == "EXPIRED"
    assert out["orders"][0]["remaining_quantity"] == 100
    assert stats(out)["fees"] == 5
    assert stats(out)["ending_positions"][0]["quantity"] == 100


def test_expiry_exit_no_bar_defers_but_ordinary_order_expires():
    for reason, expected in (("EXPIRY_EXIT", "FILLED"), ("ORIGINAL_10_3_SELL", "EXPIRED")):
        m, rows = bundle([spec(side="SELL", expires_at=ts(0, "09:34:00"), reason=reason)], state=initial(A=100))
        b = minute_bars(m, rows)
        b["bars"] = [v for v in b["bars"] if v["timestamp"][:10] != DAYS[0]]
        out = run(m, rows, b)
        assert out["orders"][0]["status"] == expected
        assert out["orders"][0]["expires_at"] == ts(0, "09:34:00")
        if reason == "EXPIRY_EXIT":
            assert out["orders"][0]["deferred_expiry"] is True
            assert out["fills"][0]["actual_fill_at"] == ts(1)
        else:
            assert not out["fills"]


def test_expiry_exit_no_bar_persists_past_window_and_final_mark_is_not_sell():
    m, rows = bundle([spec(side="SELL", expires_at=ts(0, "09:34:00"), reason="EXPIRY_EXIT")], state=initial(A=100))
    b = minute_bars(m, rows)
    b["bars"] = []
    out = run(m, rows, b)
    assert not out["fills"] and out["orders"][0]["status"] == "WAITING"
    assert len(out["daily_nav"]) == 3 and all(d["event"] == "MARK" for d in out["daily_nav"])
    assert stats(out)["ending_positions"][0]["quantity"] == 100
    assert stats(out)["fees"] == 0 and stats(out)["coverage"]["stale_mark_days"] == 3
    assert stats(out)["ending_positions"][0]["last_valuation_at"] == ts(0, "09:29:00")
    assert out["orders"][0]["deferred_beyond_window"] is True
    assert out["orders"][0]["deferred_until"] is None


def test_older_opposite_remainder_cancelled_with_superseded_link():
    m, rows = bundle([spec(quantity=200), spec(side="SELL", quantity=200, day=1)])
    b = minute_bars(m, rows, capacity=0)
    next(v for v in b["bars"] if v["timestamp"] == ts(0, "09:31:00"))["capacity"] = 100
    out = run(m, rows, b)
    buy, sell = out["orders"]
    assert buy["status"] == "CANCELLED" and buy["status_reason"] == "SUPERSEDED"
    assert buy["superseded_by"] == sell["intent_id"]
    assert buy["cumulative_filled_quantity"] == buy["remaining_quantity"] == 100


def test_same_timestamp_sell_first_funds_buy_and_input_order_cannot_change_it():
    m, rows = bundle([spec("A"), spec("Z", "SELL")], state=initial(0, Z=100))
    out = run(m, rows)
    assert [f["side"] for f in out["fills"]] == ["SELL", "BUY"]
    assert all(o["status"] == "FILLED" for o in out["orders"])
    assert stats(out)["ending_cash"] == 0
    assert stats(out)["turnover"] == 1


def test_nav_turnover_drawdown_excess_hand_calculation_with_same_fill_base():
    m, rows = bundle([spec("A", arm="P-BASE"), spec("B", arm="P-CHASE")], state=initial(2000))
    b = minute_bars(m, rows)
    for v in b["bars"]:
        if v["instrument"] == "B" and v["timestamp"][:10] == DAYS[1]:
            v.update(open=12, close=12)
        elif v["instrument"] == "B" and v["timestamp"][:10] == DAYS[2]:
            v.update(open=9, close=9)
    before = deepcopy((m, rows, b))
    out = run(m, rows, b, arm="P-CHASE")
    s = stats(out)
    assert [d["nav"] for d in out["daily_nav"]] == [2000, 2200, 1900]
    assert s["turnover"] == 0.25 and s["two_sided_notional"] == 1000
    assert s["turnover_denominators"] == [2000, 2000, 2200]
    assert s["net_return"] == pytest.approx(-0.05) and s["net_excess"] == pytest.approx(-0.05)
    assert s["max_drawdown"] == pytest.approx(1 - 1900 / 2200)
    assert s["delta_max_drawdown"] == s["max_drawdown"]
    assert [v["difference"] for v in s["daily_net_return_difference"]] == pytest.approx([0, 0.1, -3 / 22])
    assert s["months"]["2026-09"]["net_excess"] == pytest.approx(-0.05)
    assert s["benchmark"]["net_return"] == 0
    assert (m, rows, b) == before


def test_drawdown_includes_first_day_fee_loss_against_initial_nav():
    m, rows = bundle([spec()], fees={"minimum": 5})
    assert stats(run(m, rows))["max_drawdown"] == pytest.approx(5 / 5000)


def action(*, factor=0.5):
    return dict(event_id="split-1", instrument="A", available_at=ts(0, "16:00:00"), effective_at=ts(1, "09:00:00"),
        from_unit="share", to_unit="share", original_quantity=100, factor=factor,
        current_quantity=100 * factor, source_hash="c" * 64, price_domain="none")


def test_quantity_event_scales_pending_sell_and_fractional_held_lot_not_fees():
    m, rows = bundle([spec(side="SELL", quantity=101)], state=initial(A=101), fees={"minimum": 5})
    b = minute_bars(m, rows)
    b["bars"] = [v for v in b["bars"] if v["timestamp"][:10] != DAYS[0]]
    b["corporate_actions"] = [action()]
    for v in b["bars"]:
        v.update(open=20, close=20)
    out = run(m, rows, b)
    o, f = out["orders"][0], out["fills"][0]
    assert o["original_target_quantity"] == 101
    assert o["current_quantity"] == o["cumulative_filled_quantity"] == 50.5
    assert o["remaining_quantity"] == 0 and o["quantity_unit"] == "share"
    assert f["executed_quantity"] == 50.5 and f["fee"] == 5
    assert o["quantity_events"][0]["applied_original_quantity"] == 101
    assert o["quantity_events"][0]["applied_current_quantity"] == 50.5
    assert stats(out)["coverage"]["quantity_fill_rate"] == 1
    assert stats(out)["nav_end"] == 6005


def test_quantity_event_scales_unfilled_buy_and_ref_price_in_both_modes():
    m, rows = bundle([spec(quantity=200)])
    b = minute_bars(m, rows)
    b["bars"] = [v for v in b["bars"] if v["timestamp"][:10] != DAYS[0]]
    b["corporate_actions"] = [action()]
    for v in b["bars"]:
        v.update(open=20, close=20)
    for mode in jr.FILL_MODES:
        out = run(m, rows, b, mode=mode)
        assert out["fills"][0]["executed_quantity"] == 100
        assert out["fills"][0]["price"] == 20
        assert out["orders"][0]["original_target_quantity"] == 200
        assert stats(out)["coverage"]["quantity_fill_rate"] == 1


def test_quantity_event_carries_stale_mark_and_never_fabricates_cash_dividend():
    m, rows = bundle(state=initial(A=101))
    b = minute_bars(m, rows)
    b["bars"] = []
    b["corporate_actions"] = [action()]
    out = run(m, rows, b)
    p = stats(out)["ending_positions"][0]
    assert p["quantity"] == 50.5 and p["mark_price"] == 20 and p["stale"]
    assert stats(out)["ending_cash"] == 5000 and stats(out)["nav_end"] == 6010
    assert p["last_valuation_at"] == ts(0, "09:29:00")


def test_zero_intents_has_null_fill_rates_and_complete_mark_calendar():
    m, rows = bundle()
    out = run(m, rows)
    assert not out["orders"] and not out["fills"]
    assert stats(out)["coverage"]["quantity_fill_rate"] is None
    assert stats(out)["coverage"]["order_fill_rate"] is None
    assert len(out["daily_nav"]) == 3
    assert stats(out)["turnover"] == stats(out)["max_drawdown"] == stats(out)["net_excess"] == 0


@pytest.mark.parametrize("mutate,match", [
    (lambda b: b["metadata"].pop("sessions"), "missing"),
    (lambda b: b["metadata"].pop("session_source"), "missing"),
    (lambda b: b["metadata"].update(bar_label="UNKNOWN"), "label"),
    (lambda b: b["metadata"].update(corporate_actions_complete=False), "SEMANTICS_BLOCKED"),
    (lambda b: b["metadata"].update(price_domain="front"), "SEMANTICS_BLOCKED"),
    (lambda b: b["bars"].append(deepcopy(b["bars"][0])), "duplicate minute"),
    (lambda b: b["bars"][0].update(timestamp=ts(0, "09:34:00")), "outside frozen session"),
    (lambda b: b["bars"][0].update(timestamp="2026-09-07T09:30:00"), "Asia/Shanghai"),
    (lambda b: b["bars"][0].update(execution_symbol="WRONG"), "mapping"),
    (lambda b: b["bars"][0].pop("limit_up"), "missing"),
    (lambda b: b.update(corporate_actions=[{**action(), "factor": 2}]), "conversion mismatch"),
    (lambda b: b.update(corporate_actions=[{**action(), "available_at": ts(2)}]), "PIT"),
    (lambda b: b.update(corporate_actions=[{**action(), "from_unit": "lot"}]), "unit/domain"),
])
def test_minute_inputs_fail_closed(mutate, match):
    m, rows = bundle([spec()])
    b = minute_bars(m, rows)
    mutate(b)
    with pytest.raises(jr.ReplayError, match=match):
        run(m, rows, b)


@pytest.mark.parametrize("mutate,match", [
    (lambda m: m.update(contract_hash="0" * 64), "contract hash"),
    (lambda m: m["metadata"]["implementation_bases"].update(BT=jr.IMPLEMENTATION_BASE_BT), "bases drift"),
    (lambda m: m.update(kind="frozen", status="INPUT_BLOCKED", input_status="INPUT_BLOCKED"), "real inputs"),
    (lambda m: m["metadata"]["strategy"].update(native_stop="r2"), "strategy drift"),
    (lambda m: m["reference_states"][0].update(before_hash="0" * 64), "reference chain"),
    (lambda m: m["arm_intent_hashes"].update(**{"P-BASE": "0" * 64}), "arm hash"),
    (lambda m: m["initial_state"].update(cash=12345), "initial state hash"),
])
def test_mq_identity_and_input_status_fail_closed(mutate, match):
    m, rows = bundle([spec()])
    mutate(m)
    with pytest.raises(jr.ReplayError, match=match):
        run(m, rows)


@pytest.mark.parametrize("raw", [b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":Infinity}', b'\xef\xbb\xbf{}', b'{}\0'])
def test_json_duplicates_nonfinite_bom_nul_rejected(raw):
    with pytest.raises(jr.ReplayError):
        jr.load_json_bytes(raw)


def test_csv_round_trip_preserves_full_typed_intents(tmp_path):
    m, rows = bundle([spec()])
    path = write_bundle(tmp_path, m, rows)
    got_m, got_rows, source = jr.load_bundle(path)
    assert got_rows == rows
    assert all(tuple(r) == jr.INTENT_FIELDS for r in got_rows)
    assert isinstance(got_rows[0]["original_target_quantity"], int)
    assert got_m == m and source["manifest_raw_sha256"]
    raw = path.read_bytes().replace(b'100,', b'200,', 1)
    path.write_bytes(raw + b"\n")
    with pytest.raises(jr.ReplayError, match="raw/content hash"):
        jr.load_bundle(path)


def test_rehashed_intent_tamper_still_fails_identity_and_plan_binding():
    m, rows = bundle([spec()])
    rows[0]["original_target_quantity"] = 200
    with pytest.raises(jr.ReplayError, match="identity drift"):
        jr.validate_intents(rows)
    rows[0]["intent_id"] = jr.content_hash({k: v for k, v in rows[0].items() if k != "intent_id"})
    m["intent_hash"] = jr.content_hash(rows)
    m["arm_intent_hashes"]["P-BASE"] = jr.content_hash([r for r in rows if r["arm_id"] == "P-BASE"])
    with pytest.raises(jr.ReplayError, match="frozen quantity/identity drift"):
        run(m, rows)


def test_cli_all_four_pairs_and_output_hashes_and_immutable_run(tmp_path):
    m, rows = bundle([spec()])
    path = write_bundle(tmp_path, m, rows)
    bars = tmp_path / "bars.json"
    bars.write_bytes(jr.canonical_bytes(minute_bars(m, rows)) + b"\n")
    out = tmp_path / "bt" / m["run_id"]
    cmd = [sys.executable, str(Path(__file__).resolve().parents[1] / "scripts/research/run_joint_return_replay.py"),
           "--intents", str(path), "--bars", str(bars), "--arm", "all", "--fill-mode", "all", "--out", str(out)]
    result = subprocess.run(cmd, text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["status"] == "BT_DATA_FREE_PASS"
    assert {p.name for p in out.iterdir()} == {"orders.csv", "fills.csv", "daily_nav.csv", "summary.json"}
    summary = json.loads((out / "summary.json").read_text())
    assert len(summary["results"]) == 4
    for name, hashes in summary["artifacts"].items():
        assert jr.raw_hash((out / name).read_bytes()) == hashes["raw_sha256"]
        with (out / name).open(newline="", encoding="utf-8") as stream:
            decoded = [{k: json.loads(v) for k, v in row.items()} for row in csv.DictReader(stream)]
        assert jr.content_hash(decoded) == hashes["content_sha256"]
        if name == "orders.csv":
            originals = {r["intent_id"]: r for r in rows}
            assert len(decoded) == 4
            for row in decoded:
                assert {k: row[k] for k in jr.INTENT_FIELDS} == originals[row["intent_id"]]
    again = subprocess.run(cmd, text=True, capture_output=True)
    assert again.returncode == 2 and "OUTPUT_BLOCKED" in again.stdout


def test_cli_missing_manifest_or_invalid_bars_creates_no_success_output(tmp_path, capsys):
    m, rows = bundle([spec()])
    path = write_bundle(tmp_path, m, rows)
    bars = tmp_path / "bars.json"
    bars.write_bytes(b"{}")
    out = tmp_path / "bt" / m["run_id"]
    args = ["--intents", str(path), "--bars", str(bars), "--arm", "P-BASE", "--fill-mode", "M-LAG", "--out", str(out)]
    assert jr.main(args) == 2 and not out.exists()
    assert "INPUT_BLOCKED" in capsys.readouterr().out
    (path.parent / "manifest.json").unlink()
    assert jr.main(args) == 2 and not out.exists()
    assert "manifest.json" in capsys.readouterr().out


def test_replay_has_no_production_or_market_data_imports():
    import ast
    source = Path(jr.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
    assert not any(n and n.startswith(("backtest", "oskh_data", "trade_decision", "qlib", "my_scripts")) for n in imports)
    for path in (Path(jr.__file__), Path(__file__), Path(__file__).resolve().parents[1] / "scripts/research/run_joint_return_replay.py"):
        raw = path.read_bytes()
        assert b"\0" not in raw and not raw.startswith(b"\xef\xbb\xbf")


def test_last_day_post_close_signal_keeps_all_intent_denominator_without_future_fill():
    m, rows = bundle([spec(day=2, available_at=ts(2, "15:03:00"), expires_at="2026-09-10T15:00:00+08:00")])
    out = run(m, rows)
    assert not out["fills"] and out["orders"][0]["status"] == "WAITING"
    assert out["orders"][0]["status_reason"] == "NOT_AVAILABLE"
    assert stats(out)["coverage"]["intent_count"] == 1
    assert stats(out)["coverage"]["quantity_fill_rate"] == 0
    assert stats(out)["coverage"]["open_order_count"] == 1


def test_nonzero_effective_time_and_short_expiry_never_force_an_early_fill():
    m, rows = bundle([spec(effective_at=ts(0, "09:33:30"), expires_at=ts(0, "09:34:00"))])
    out = run(m, rows)
    assert not out["fills"] and out["orders"][0]["status"] == "EXPIRED"
    assert out["orders"][0]["legal_execution_at"] is None


def test_suspended_expiry_day_is_not_the_no_bar_exception():
    m, rows = bundle([spec(side="SELL", reason="EXPIRY_EXIT", expires_at=ts(0, "09:34:00"))], state=initial(A=100))
    b = minute_bars(m, rows)
    for v in b["bars"]:
        if v["timestamp"][:10] == DAYS[0]:
            v["suspended"] = True
    out = run(m, rows, b)
    assert not out["fills"] and out["orders"][0]["status"] == "EXPIRED"
    assert out["orders"][0]["deferred_expiry"] is False


def test_converted_buy_odd_remainder_is_rejected_as_lot_rounding():
    m, rows = bundle([spec()])
    b = minute_bars(m, rows)
    b["bars"] = [v for v in b["bars"] if v["timestamp"][:10] != DAYS[0]]
    b["corporate_actions"] = [action()]
    out = run(m, rows, b)
    assert not out["fills"] and out["orders"][0]["status_reason"] == "LOT_ROUNDING"
    assert out["orders"][0]["current_quantity"] == 50
    assert out["orders"][0]["original_target_quantity"] == 100


def test_partial_fill_unit_conversion_keeps_history_and_cumulative_fee():
    m, rows = bundle([spec(quantity=400)], fees={"minimum": 5})
    b = minute_bars(m, rows, capacity=0)
    b["corporate_actions"] = [action()]
    for v in b["bars"]:
        if v["timestamp"] == ts(0, "09:31:00"):
            v["capacity"] = 200
        if v["timestamp"][:10] != DAYS[0]:
            v.update(open=20, close=20, capacity=100)
    out = run(m, rows, b)
    assert [f["executed_quantity"] for f in out["fills"]] == [200, 100]
    assert [f["fee"] for f in out["fills"]] == [5, 0]
    o = out["orders"][0]
    assert o["current_quantity"] == o["cumulative_filled_quantity"] == 200
    assert o["remaining_quantity"] == 0 and o["original_target_quantity"] == 400
    assert stats(out)["coverage"]["quantity_fill_rate"] == 1
    assert out["daily_nav"][0]["positions"][0]["quantity"] == 200
    assert sum(t["quantity"] for t in out["daily_nav"][0]["positions"][0]["tranches"]) == 200
    assert stats(out)["ending_positions"][0]["quantity"] == 200
    assert stats(out)["nav_end"] == 4995


def test_later_mark_missing_is_flagged_even_if_session_has_other_bars():
    m, rows = bundle(state=initial(A=100))
    b = minute_bars(m, rows)
    b["bars"] = [v for v in b["bars"] if v["timestamp"] != ts(2, "09:33:00")]
    out = run(m, rows, b)
    assert stats(out)["coverage"]["stale_mark_days"] == 1
    assert stats(out)["ending_positions"][0]["last_valuation_at"] == ts(2, "09:33:00")
    assert stats(out)["ending_positions"][0]["stale"] is True


def test_unknown_quantity_event_boundary_and_missing_initial_evidence_block():
    m, rows = bundle(state=initial(A=100))
    b = minute_bars(m, rows)
    b["metadata"]["initial_lots"]["lot-A"].pop("acquired_at")
    with pytest.raises(jr.ReplayError, match="initial lot evidence"):
        run(m, rows, b)
    b = minute_bars(m, rows)
    b["corporate_actions"] = [{**action(), "effective_at": ts(1, "09:31:00")}]
    with pytest.raises(jr.ReplayError, match="intraday quantity event unsupported"):
        run(m, rows, b)


def test_zero_nav_and_bar_content_tampering_block_without_outputs():
    m, rows = bundle(state=initial(0))
    b = minute_bars(m, rows)
    with pytest.raises(jr.ReplayError, match="NAV"):
        run(m, rows, b)
    m, rows = bundle([spec()])
    b = minute_bars(m, rows)
    b["bars"][0]["open"] = 11
    with pytest.raises(jr.ReplayError, match="bars content hash drift"):
        jr.replay(m, rows, b, arm="P-BASE", fill_mode="M-LAG")


def frozen_bundle(*, state=None, reference_price=1):
    """Tiny fixture of the control-only MQ wire format, NOT real 4090 data."""
    m, rows = bundle([spec(arm="P-BASE", reference_price=reference_price)], state=state)
    m.update(kind="frozen", run_id="frozen-fixture", contract_hash=jr.FROZEN_CONTRACT_HASH,
             status="INPUT_BLOCKED", input_status="INPUT_BLOCKED", scores_mode="control_only",
             portfolio_status="PORTFOLIO_CONSTRAINTS_PASS")
    md = m["metadata"]
    md.update(contract_hash=jr.FROZEN_CONTRACT_HASH, scores_mode="control_only", arms=["P-BASE"],
              valuation_version="research-none-mark-v1")
    md.pop("candidate_recorder_id")
    md.pop("sidecar_sha256")
    md["inputs"].pop("pref")
    md["strategy"].update(topk=50, n_drop=5, source="backtest_rule_intents")
    m["pairing"]["arms"] = ["P-BASE"]
    m["reference_states"] = [h for h in m["reference_states"] if h["arm_id"] == "P-BASE"]
    for h in m["reference_states"]:
        plan = h["source_plan"]
        old_hash = jr.content_hash(plan)
        plan["source"] = "backtest_rule_intents"
        for row in rows:
            if row["source_plan_hash"] == old_hash:
                row["source_plan_hash"] = jr.content_hash(plan)
                row["intent_id"] = jr.content_hash({k: v for k, v in row.items() if k != "intent_id"})
    rows = jr.sort_intents(rows)
    m["intent_hash"] = jr.content_hash(rows)
    m["arm_intent_hashes"] = {"P-BASE": jr.content_hash(rows)}
    bars = minute_bars(m, rows, price=11)
    bars["kind"] = "frozen_explicit"
    bars["metadata"].update(contract_hash=jr.FROZEN_CONTRACT_HASH,
                            source="fixture://explicit-prices-not-real-4090")
    return m, rows, seal(bars)


def write_frozen_bundle(tmp_path, m, rows, *, extra_quotes=False):
    path = write_bundle(tmp_path, m, rows)
    pref = {"status": "NOT_RUN", "reason": "control_only: anti/universe/labels deferred", "numeric_scope": []}
    raw = jr.canonical_bytes(pref) + b"\n"
    (path.parent / "pref_check.json").write_bytes(raw)
    m["artifacts"]["pref_check.json"] = dict(raw_sha256=jr.raw_hash(raw), content_sha256=jr.content_hash(pref))
    if extra_quotes:
        # Additional JSON quoting inside CSV quoting, including numeric cells.
        quoted = [{k: json.dumps(v) for k, v in r.items()} for r in rows]
        raw = jr.csv_bytes(quoted, jr.INTENT_FIELDS)
        path.write_bytes(raw)
        m["artifacts"]["intents.csv"]["raw_sha256"] = jr.raw_hash(raw)
    (path.parent / "manifest.json").write_bytes(jr.canonical_bytes(m))
    return path


@pytest.mark.parametrize("entry", ["intents.csv", "manifest.json", "."])
@pytest.mark.parametrize("extra_quotes", [False, True])
def test_frozen_explicit_file_replay_preserves_intents_and_hashes(tmp_path, entry, extra_quotes):
    m, rows, bars = frozen_bundle()
    original = deepcopy(rows)
    path = write_frozen_bundle(tmp_path, m, rows, extra_quotes=extra_quotes)
    prices = tmp_path / "prices.json"
    prices.write_bytes(jr.canonical_bytes(bars))
    out = tmp_path / "bt" / m["run_id"]
    jr.run_replay(path.parent / entry, prices, arm="P-BASE", fill_mode="M-LAG", out=out)
    summary = json.loads((out / "summary.json").read_text())
    assert summary["status"] == "BT_RESEARCH_REPLAY_PASS"
    assert summary["contract_hash"] == jr.FROZEN_CONTRACT_HASH
    assert summary["mq_input_status"] == summary["real_execution_status"] == "INPUT_BLOCKED"
    assert summary["return_status"] == "待实测"
    assert set(p.name for p in out.iterdir()) == {"orders.csv", "fills.csv", "daily_nav.csv", "summary.json"}
    with (out / "fills.csv").open() as stream:
        fills = [{k: json.loads(v) for k, v in row.items()} for row in csv.DictReader(stream)]
    assert fills[0]["price"] == 11  # Never sessions/reference placeholder 1.0.
    assert fills[0]["contract_hash"] == jr.FROZEN_CONTRACT_HASH
    assert {k: fills[0][k] for k in jr.INTENT_FIELDS} == original[0]
    assert rows == original


@pytest.mark.parametrize("mode", ["M-LAG", "M-REF"])
def test_frozen_missing_prices_cli_is_input_blocked(tmp_path, capsys, mode):
    m, rows, _ = frozen_bundle()
    path = write_frozen_bundle(tmp_path, m, rows)
    out = tmp_path / m["run_id"]
    assert jr.main(["--intents", str(path), "--arm", "P-BASE", "--fill-mode", mode, "--out", str(out)]) == 2
    assert "INPUT_BLOCKED" in capsys.readouterr().out
    assert not out.exists()


@pytest.mark.parametrize("arm,mode", [("P-CHASE", "M-LAG"), ("all", "M-LAG"),
                                      ("P-BASE", "M-REF"), ("P-BASE", "all")])
def test_frozen_deferred_arms_and_placeholder_reference_blocked(arm, mode):
    m, rows, bars = frozen_bundle()
    with pytest.raises(jr.ReplayError, match="INPUT_BLOCKED"):
        jr.replay(m, rows, bars, arm=arm, fill_mode=mode)


@pytest.mark.parametrize("target", ["manifest", "metadata", "bars"])
def test_frozen_cannot_mix_synthetic_contract(target):
    m, rows, bars = frozen_bundle()
    obj = {"manifest": m, "metadata": m["metadata"], "bars": bars["metadata"]}[target]
    obj["contract_hash"] = jr.CONTRACT_HASH
    with pytest.raises(jr.ReplayError, match="CONTRACT_MISMATCH.*contract hash"):
        run(m, rows, bars)


def test_frozen_price_coverage_fails_closed_with_counts():
    m, rows, bars = frozen_bundle()
    bars["bars"].pop()
    with pytest.raises(jr.ReplayError, match="INPUT_BLOCKED.*missing_symbol_minutes.*1"):
        run(m, rows, bars)


def test_frozen_prices_need_provenance_hash_and_matching_kind():
    m, rows, bars = frozen_bundle()
    for mutate in (lambda b: b["metadata"].pop("source"), lambda b: b.update(kind="synthetic")):
        bad = deepcopy(bars)
        mutate(bad)
        with pytest.raises(jr.ReplayError):
            run(m, rows, bad)
    bars["bars"][0]["open"] = 12
    with pytest.raises(jr.ReplayError, match="bars content hash drift"):
        jr.replay(m, rows, bars, arm="P-BASE", fill_mode="M-LAG")


def test_frozen_state_supports_fifty_positions():
    m, rows, bars = frozen_bundle(state=initial(**{f"S{i}": 100 for i in range(49)}))
    assert len(stats(run(m, rows, bars))["ending_positions"]) == 50


def frozen_marks(rows):
    return {r["intent_id"]: dict(instrument=r["instrument"], execution_symbol=r["execution_symbol"],
        mark_price=10, mark_at=r["reference_price_at"], price_domain="none", source_kind="lake_bar",
        source="fixture://lake-mark-not-real-data", source_sha256=jr.raw_hash(b"fixture mark source"))
        for r in rows}


def test_frozen_modeb_cli_same_pack_preserves_identity_and_uses_explicit_marks(tmp_path):
    m, rows, bars = frozen_bundle()
    bars["metadata"]["reference_marks"] = frozen_marks(rows)
    original = deepcopy((m, rows, bars))
    pair = run(m, rows, bars, mode="all")
    assert (m, rows, bars) == original
    ref, lag = pair["fills"]
    assert (ref["fill_id"], ref["price"], ref["actual_fill_at"]) == ("M-REF", 10, ts())
    assert (lag["fill_id"], lag["price"], lag["actual_fill_at"]) == ("M-LAG", 11, ts(0, "09:31:00"))
    for fill in (ref, lag):
        assert {k: fill[k] for k in jr.INTENT_FIELDS} == rows[0]
        assert fill["reference_price"] == 1  # Retained identity, never executed.
    assert pair["summary"]["reference_marks"] == frozen_marks(rows)
    assert pair["summary"]["deferred_arms"] == {"P-CHASE": "INPUT_BLOCKED", "weak": "INPUT_BLOCKED"}
    without_marks = deepcopy(bars)
    del without_marks["metadata"]["reference_marks"]
    assert run(m, rows, bars)["fills"] == run(m, rows, without_marks)["fills"]
    path = write_frozen_bundle(tmp_path, m, rows)
    prices = tmp_path / "prices.json"
    prices.write_bytes(jr.canonical_bytes(seal(bars)))
    out = tmp_path / "bt" / m["run_id"]
    assert jr.main(["--intents", str(path), "--bars", str(prices), "--arm", "P-BASE",
                    "--fill-mode", "all", "--out", str(out)]) == 0
    summary = json.loads((out / "summary.json").read_text())
    assert summary["status"] == "BT_RESEARCH_REPLAY_PASS"
    assert summary["reference_marks"] == frozen_marks(rows)
    assert summary["inputs"]["bars_raw_sha256"] == jr.raw_hash(prices.read_bytes())


@pytest.mark.parametrize("change", [
    {"mark_price": 1.0}, {"mark_price": 0}, {"mark_price": -10}, {"mark_price": True},
    {"mark_price": "10"}, {"mark_price": float("nan")},
    {"mark_at": ts()}, {"mark_at": "invalid"}, {"instrument": "B"},
    {"execution_symbol": "B.SYN"}, {"price_domain": "front"},
    {"source_kind": "sessions"}, {"source": ""}, {"source_sha256": "bad"},
])
def test_frozen_mref_invalid_mark_evidence_blocks(change):
    m, rows, bars = frozen_bundle()
    marks = frozen_marks(rows)
    marks[rows[0]["intent_id"]].update(change)
    bars["metadata"]["reference_marks"] = marks
    with pytest.raises(jr.ReplayError, match="INPUT_BLOCKED"):
        run(m, rows, bars, mode="M-REF")


@pytest.mark.parametrize("missing", ["mark_at", "mark_price", "source", "source_sha256"])
def test_frozen_mref_incomplete_evidence_blocks(missing):
    m, rows, bars = frozen_bundle()
    bars["metadata"]["reference_marks"] = frozen_marks(rows)
    del bars["metadata"]["reference_marks"][rows[0]["intent_id"]][missing]
    with pytest.raises(jr.ReplayError, match="INPUT_BLOCKED.*M-REF mark"):
        run(m, rows, bars, mode="M-REF")


@pytest.mark.parametrize("marks", [None, {}, [], {"wrong-intent": {}}])
def test_frozen_mref_missing_or_unbound_marks_cli_blocks_without_outputs(tmp_path, marks):
    m, rows, bars = frozen_bundle()
    bars["metadata"]["reference_marks"] = marks
    path = write_frozen_bundle(tmp_path, m, rows)
    prices = tmp_path / "prices.json"
    prices.write_bytes(jr.canonical_bytes(seal(bars)))
    out = tmp_path / m["run_id"]
    assert jr.main(["--intents", str(path), "--bars", str(prices), "--arm", "P-BASE",
                    "--fill-mode", "M-REF", "--out", str(out)]) == 2
    assert not out.exists()


def test_frozen_marks_do_not_unlock_deferred_arms_or_bypass_hash():
    m, rows, bars = frozen_bundle()
    bars["metadata"]["reference_marks"] = frozen_marks(rows)
    for arm in ("P-CHASE", "weak", "all"):
        with pytest.raises(jr.ReplayError, match="INPUT_BLOCKED"):
            run(m, rows, bars, arm=arm, mode="M-REF")
    with pytest.raises(jr.ReplayError, match="CONTRACT_MISMATCH.*bars content hash"):
        jr.replay(m, rows, bars, arm="P-BASE", fill_mode="M-REF")


def test_frozen_nonplaceholder_intent_and_plan_marks_are_not_source_evidence():
    m, rows, bars = frozen_bundle(reference_price=10)
    with pytest.raises(jr.ReplayError, match="INPUT_BLOCKED.*reference_marks"):
        run(m, rows, bars, mode="M-REF")


def test_frozen_reference_mark_uses_original_quantity_epoch_for_conversion():
    m, rows, bars = frozen_bundle()
    bars["metadata"]["reference_marks"] = frozen_marks(rows)
    # Forward split: deferred 100-share intent becomes 200 shares at mark 5.
    event = action()
    event.update(factor=2, current_quantity=event["original_quantity"] * 2)
    bars["corporate_actions"] = [event]
    for bar in bars["bars"]:
        if bar["timestamp"][:10] == DAYS[0]:
            bar["suspended"] = True
    fill = run(m, rows, bars, mode="M-REF")["fills"][0]
    assert fill["actual_fill_at"] == ts(1)
    assert fill["price"] == 5 and fill["executed_quantity"] == 200
    assert fill["notional"] == 1000 and fill["reference_price"] == 1
