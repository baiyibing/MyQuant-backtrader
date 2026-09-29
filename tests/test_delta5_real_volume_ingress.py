"""Contract §6: N/H are full native comparisons; I rejects before API; L is local.

No real lake, shared cache, shared writer, strategy registration, or engine patch.
"""

from copy import deepcopy
from datetime import date
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

import pandas as pd
import pytest

from backtest.research.ashare_volume_cap import BucketVolume, VolumeCap
from backtest.research.csv_ledger import Position, SimState, _sell, execute_buy
from backtest.research.delta5_volume_ingress import (
    FrozenProvider, IngressError, normalize,
)
from scripts.research import verify_delta5_real_volume_ingress as harness
from tests.fixtures.delta5_ingress import CODE, DAYS, SOURCE_SYMBOL, UNIT, fixture


def passed(f, rate=.1):
    result = harness.compare(f, rate)
    assert result["status"] == "PASS", result["oracle"]
    assert result["differences"] == []
    assert result["native"] == result["harness"]
    assert result["canonical_hash"] == result["coverage"]["canonical_hash"]
    return result


def state(result):
    return result["harness"]["state"]


def used(result):
    return {tuple(k): v for k, v in state(result)["volume_cap"]["used"].get("pairs", [])}


def sells(result):
    return [t for t in state(result)["trades"] if t["side"] == "SELL"]


def test_m1_native_harness_omitted_none_and_zero():
    f = fixture(oracle=[["BUY", 500, 10., 7.5]], cell="M1")
    omitted, explicit = passed(f, harness.OMITTED), passed(f, None)
    assert omitted["native"] == explicit["native"]
    assert state(omitted)["volume_cap"] is None
    assert omitted["harness"]["provider_calls"] == []
    f["oracle"]["fills"] = []
    zero = passed(f, 0)
    assert zero["harness"]["provider_calls"] == [[CODE, DAYS[0], 895]]
    assert used(zero) == {}
    assert state(zero)["trades"][0]["reason"] == "skip_volume_cap:zero_or_exhausted"
    one = passed(fixture(volume=100, oracle=[["BUY", 100, 10., 5.]], cell="M1"), 1)
    assert used(one) == {(CODE, DAYS[0], 895): 100}  # p=1 is still bounded.


def test_m2_native_harness_partial_no_order_and_helper_revisit():
    result = passed(fixture(days=2))
    assert used(result) == {(CODE, DAYS[0], 895): 200}
    assert state(result)["cash"] == 100000 - 2000 - 5
    assert state(result)["positions"][CODE][0]["shares"] == 200
    assert state(result)["stats"]["chase_pending_eod"] == 0
    provider = FrozenProvider(normalize(fixture()["source"]).samples)
    cap = VolumeCap(.1, provider)
    key = CODE, DAYS[0], 895
    assert cap.clamp(key, 895, 500, buy=True) == (200, "")
    cap.consume(key, 200)
    assert cap.clamp(key, 895, 100, buy=True) == (0, "skip_volume_cap:zero_or_exhausted")
    assert cap.clamp(key, 895, 100) == (50, "")
    assert provider.calls == [key]


def test_m3_native_harness_pool_and_independent_step_share_capacity():
    f = fixture(days=3, prices=[10., 11., 12.], signals=(0, 2), volume=3000, budget=2400,
                oracle=[["BUY", 200, 10., 5.], ["BUY", 200, 12., 5.], ["BUY", 100, 12., 5.]], cell="M3")
    result = passed(f)
    assert used(result) == {(CODE, DAYS[0], 895): 200, (CODE, DAYS[2], 895): 300}
    buys = [t for t in state(result)["trades"] if t["side"] == "BUY"]
    assert [t["reason"] for t in buys] == ["pool", "pool", "add:step20"]
    assert buys[1]["position_id"] != buys[2]["position_id"]
    assert result["harness"]["provider_calls"].count([CODE, DAYS[2], 895]) == 1
    # L: a new bucket does not inherit the old 50-share remainder.
    key = CODE, DAYS[0], 895
    cap = VolumeCap(.1, {key: BucketVolume(2500, 895, UNIT),
                         (CODE, DAYS[0], 896): BucketVolume(500, 896, UNIT)})
    cap.consume(key, 200)
    assert cap.clamp((CODE, DAYS[0], 896), 896, 100, buy=True)[0] == 0


def test_m4_native_harness_sell_then_buy_same_bucket():
    f = fixture(days=2, volume=3000, budget=2000, signals=(0, 1),
                overrides={(1, 895): {"price": 9.4, "open": 10.}},
                oracle=[["BUY", 200, 10., 5.], ["SELL", 200, 9.4, 5.], ["BUY", 100, 9.4, 5.]], cell="M4")
    result = passed(f)
    assert used(result)[CODE, DAYS[1], 895] == 300
    assert state(result)["cash"] == 100000 - 2005 + 1875 - 945


@pytest.mark.parametrize("encoding", ["local_wall", "utc_instant", "utc_wall"])
@pytest.mark.parametrize("delay", [0, 1, 60])
def test_m5_native_harness_start_end_and_availability_round_up(encoding, delay):
    oracle = [["BUY", 200, 10., 5.]] if delay == 0 else []
    results = [passed(fixture(label=label, encoding=encoding,
                             overrides={(0, 895): {"delay_seconds": delay}}, oracle=oracle, cell="M5"))
               for label in ("START", "END")]
    assert results[0]["canonical_hash"] == results[1]["canonical_hash"]
    assert results[0]["harness"] == results[1]["harness"]
    if delay:
        assert state(results[0])["trades"][0]["reason"] == "skip_volume_unavailable:available_at"
    for available in (571, 572):
        provider = FrozenProvider({(CODE, DAYS[0], 571): BucketVolume(10**9, available, UNIT)})
        cap = VolumeCap(.1, provider)
        key = CODE, DAYS[0], 571
        assert cap.clamp(key, 570, 500)[1] == "skip_volume_unavailable:bucket_not_completed"
        assert provider.calls == []
        assert cap.clamp(key, 571, 500)[0] == (500 if available == 571 else 0)


@pytest.mark.parametrize("available,filled", [(894, 300), (895, 0)])
def test_m6_native_only_fallback_keeps_actual_quote_key(available, filled):
    # Deliberately invalid ingress. This native tolerance is not a harness PASS.
    f = fixture(volume=3000, oracle=[["BUY", 300, 10., 5.]])
    f["source"]["minute"] = [r for r in f["source"]["minute"] if r["end"][11:16] != "14:55"]
    with pytest.raises(IngressError, match="missing_buckets"):
        normalize(f["source"])
    native = harness.native_inputs(f["native"])
    native.minute[CODE] = native.minute[CODE].loc[native.minute[CODE]["hm"] != 895]
    native.samples[CODE, DAYS[0], 895] = BucketVolume(10**9, 895, UNIT)
    native.samples[CODE, DAYS[0], 894] = BucketVolume(3000, available, UNIT)
    result = harness.invoke(native, harness.options(f["parameters"]), .1)
    assert result["status"] == "PASS"
    assert result["provider_calls"] == [[CODE, DAYS[0], 894]]
    assert [t["shares"] for t in result["state"]["trades"] if t["side"] == "BUY"] == ([filled] if filled else [])


@pytest.mark.parametrize("later_volume", [0, 3000])
def test_m6b_m8_native_harness_latched_partial_exit_prefix(later_volume):
    oracle = [["BUY", 500, 10., 7.5], ["SELL", 200, 9.4, 5.]]
    if later_volume:
        oracle.append(["SELL", 300, 10., 5.])
    f = fixture(days=2, volume=0, overrides={
        (0, 895): {"volume": 5000},
        (1, 571): {"price": 9.4, "open": 10., "volume": 2000},
        (1, 572): {"volume": later_volume},
    }, oracle=oracle, cell="M8")
    result = passed(f)
    assert used(result)[CODE, DAYS[1], 571] == 200
    assert {t["reason"] for t in sells(result)} == {"stop_loss:touch"}
    assert all("t1_deferred" not in t["reason"] for t in sells(result))
    # Explicit prefix equivalence with an independently run opposite tail.
    other = deepcopy(f)
    for r in other["source"]["minute"]:
        if r["end"] == "2026-09-02T09:32:00":
            r.update(volume=3000, volume_state="positive")
    for r in other["native"]["samples"]:
        if r[:3] == [CODE, DAYS[1], 572]:
            r[3][0] = 3000
    other["oracle"]["fills"] = [["BUY", 500, 10., 7.5], ["SELL", 200, 9.4, 5.], ["SELL", 300, 10., 5.]]
    full = passed(other)
    first_exit = next(i for i, t in enumerate(state(result)["trades"]) if t["side"] == "SELL")
    assert state(result)["trades"][:first_exit + 1] == state(full)["trades"][:first_exit + 1]
    assert used(result)[CODE, DAYS[1], 571] == used(full)[CODE, DAYS[1], 571]
    if not later_volume:
        assert state(result)["positions"][CODE][0]["shares"] == 300
        assert state(result)["positions"][CODE][0]["pending_exit"] == "stop_loss:touch"
        assert state(result)["equity_curve"]  # No forced liquidation at window end.


def test_m8_native_harness_same_day_step_t1_keeps_latched_reason():
    f = fixture(days=4, prices=[10., 11., 11., 11.], volume=100000, budget=1200,
                overrides={(2, 895): {"price": 12.}, (2, 900): {"price": 10.4, "open": 12.}},
                oracle=[["BUY", 100, 10., 5.], ["BUY", 100, 12., 5.],
                        ["SELL", 100, 10.4, 5.], ["SELL", 100, 11., 5.]], cell="M8")
    result = passed(f)
    assert [t["date"] for t in sells(result)] == [DAYS[2], DAYS[3]]
    assert [t["reason"] for t in sells(result)] == ["stop_loss:touch", "stop_loss:touch|t1_deferred"]
    assert state(result)["positions"] == {}


def test_m7_native_harness_zero_suspension_and_raw_daily_mark():
    zero = passed(fixture(volume=0, oracle=[], cell="M7"))
    assert used(zero) == {}
    assert len(zero["coverage"]["zero_keys"]) == 240
    f = fixture(days=2, suspended=(1,), cell="M7")
    result = passed(f)
    inputs = normalize(f["source"])
    assert len(inputs.minute[CODE]) == 240
    assert inputs.samples[CODE, DAYS[1], 895] is None
    assert result["coverage"]["suspensions"][0]["absent_buckets"] == 240
    assert state(result)["positions"][CODE][0]["shares"] == 200
    assert len(state(result)["equity_curve"]) == 2
    assert state(result)["equity_curve"][-1][1] == 99995.
    assert any(t["side"] == "EOD_MARK" and t["date"] == DAYS[1] for t in state(result)["trades"])
    assert VolumeCap(.1, {}).clamp((CODE, DAYS[0], 895), 895, 500)[1] == "skip_volume_unavailable:missing_or_untyped"
    f = fixture(volume=0, oracle=[])
    f["source"]["status"][SOURCE_SYMBOL][DAYS[0]] = "suspended"
    assert passed(f)["coverage"]["actual_buckets"] == 240  # Retain recorded zero bars.


def test_m10_native_harness_two_lot_floors_and_cash_exception():
    f = fixture(days=4, prices=[10., 11., 11., 10.], volume=100000, budget=1200,
                overrides={(2, 895): {"price": 12.}},
                oracle=[["BUY", 100, 10., 5.], ["BUY", 100, 12., 5.],
                        ["SELL", 100, 10., 5.], ["SELL", 100, 10., 5.]], cell="M10")
    result = passed(f)
    assert sum(t["commission"] for t in sells(result)) == 10
    assert {t["lot"] for t in sells(result)} == {0, 1}
    assert state(result)["cash"] == 99780.
    f = fixture()
    f["parameters"]["total_cash"] = 2500.
    failed = harness.compare(f, .1)
    assert failed["native"] == failed["harness"]
    assert failed["status"] == "FAIL"
    assert failed["harness"]["exception"]["type"] == "InsufficientCashError"
    assert failed["harness"]["provider_calls"] == []


def test_m10_native_limit_and_l_cash_t1_gates_do_not_read_capacity():
    f = fixture(prices=[11.], oracle=[], cell="M10")
    for key in ("open", "high", "low", "close"):
        f["source"]["daily"][0][key] = 10.
        f["native"]["daily"][CODE][0][key] = 10.
    result = passed(f)
    assert used(result) == {} and result["harness"]["provider_calls"] == []
    assert state(result)["stats"]["skip_limit_up"] == 1
    provider = FrozenProvider({}, forbidden=True)
    st = SimState(cash=1, volume_cap=VolumeCap(.1, provider))
    assert not execute_buy(st, CODE, 10, 5000, 1, date(2026, 9, 2), bucket_id=895)
    new = Position(CODE, 100, 10, 1, 10)
    st.positions[CODE] = [new]
    assert _sell(st, CODE, new, 10, date(2026, 9, 2), "test", bucket_id=895, day_i=1) == 0
    assert provider.calls == [] and st.volume_cap.used == {}


@pytest.mark.parametrize("rate", [-.1, 1.1, float("nan"), float("inf"), True])
def test_invalid_rate_records_both_native_exceptions(rate):
    result = harness.compare(fixture(), rate)
    assert result["status"] == "FAIL"
    assert result["native"] == result["harness"]
    assert result["harness"]["exception"]["type"] == "ValueError"


@pytest.mark.parametrize("quantity", [2500.0, 0.0, 2**53 - 1])
def test_integral_shares_are_explicit_ints(quantity):
    f = fixture(volume=quantity)
    sample = normalize(f["source"]).samples[CODE, DAYS[0], 895]
    assert type(sample.shares) is int
    assert sample.shares == quantity


def corrupt(f, case):
    s = f["source"]
    row = s["minute"][0]
    if case in {"negative", "null", "nan", "bool", "fraction", "inexact_float"}:
        row["volume"] = {"negative": -1, "null": None, "nan": float("nan"),
                         "bool": True, "fraction": 2.5, "inexact_float": float(2**53)}[case]
    elif case == "unproved_float":
        row["volume"], s["float_exact"] = 2500., False
    elif case in {"lots", "cumulative", "unknown_source", "front", "unknown_label", "unknown_time"}:
        key, val = {"lots": ("unit", "lots"), "cumulative": ("incremental", False),
                    "unknown_source": ("kind", "unknown"), "front": ("price_domain", "front"),
                    "unknown_label": ("label", "guess"), "unknown_time": ("time_encoding", "guess")}[case]
        s[key] = val
    elif case == "duplicate":
        s["minute"].insert(1, deepcopy(row))
    elif case == "unordered":
        s["minute"][0], s["minute"][1] = s["minute"][1], s["minute"][0]
    elif case in {"missing_first", "missing_last", "missing_1455"}:
        s["minute"].pop({"missing_first": 0, "missing_last": -1, "missing_1455": 234}[case])
    elif case in {"missing_reference", "missing_mark"}:
        s["daily"].pop(0 if case == "missing_reference" else -1)
    elif case == "missing_volume":
        row.pop("volume")
    elif case == "availability_unknown":
        s["availability_rule"] = "mtime"
    elif case == "backdated":
        row["available_at"] = row["begin"]
    elif case == "cross_session_publication":
        row["available_at"] = "2026-09-01T23:59:59"
    elif case in {"lunch", "after_close", "cross_day", "aggregate", "boundary_seconds", "end_0930"}:
        begin, end = {"lunch": ("11:30", "11:31"), "after_close": ("15:00", "15:01"),
                      "cross_day": ("23:59", "00:00"), "aggregate": ("09:30", "09:32"),
                      "boundary_seconds": ("09:30:01", "09:31:01"), "end_0930": ("09:29", "09:30")}[case]
        row.update(begin=f"2026-09-01T{begin}", end=f"2026-09-01T{end}", timestamp=f"2026-09-01T{begin}")
    elif case == "auction_unknown":
        s["interval_policy"] = "aggregate_auction"
    elif case == "unknown_symbol":
        row["symbol"] = "UNKNOWN"
    elif case == "symbol_collision":
        s["instruments"]["OTHER"] = deepcopy(s["instruments"][SOURCE_SYMBOL])
    elif case == "suspension_positive":
        s["status"][SOURCE_SYMBOL][DAYS[0]] = "suspended"
    elif case == "no_events_missing":
        s["no_events"]["start"] = DAYS[0]
    elif case == "zero_state_missing":
        row["volume_state"] = "unknown"
    elif case == "missing_name":
        s["instruments"][SOURCE_SYMBOL]["name"] = ""
    elif case == "bad_ohlc":
        row["low"] = 11.
    else:
        raise AssertionError(case)


@pytest.mark.parametrize("case", [
    "negative", "null", "nan", "bool", "fraction", "inexact_float", "unproved_float",
    "lots", "cumulative", "unknown_source", "front", "unknown_label", "unknown_time",
    "duplicate", "unordered", "missing_first", "missing_last", "missing_1455",
    "missing_reference", "missing_mark", "missing_volume", "availability_unknown",
    "backdated", "cross_session_publication", "lunch", "after_close", "cross_day",
    "aggregate", "boundary_seconds", "end_0930", "auction_unknown", "unknown_symbol",
    "symbol_collision", "suspension_positive", "no_events_missing", "zero_state_missing",
    "missing_name", "bad_ohlc",
])
def test_m5_m6_m7_m11_ingress_rejects_before_api(case, monkeypatch):
    f = fixture()
    corrupt(f, case)
    calls = []

    def forbidden(*args, **kwargs):
        calls.append(1)
        raise AssertionError("preflight failure reached API")

    monkeypatch.setattr(harness.engine, "simulate", forbidden)
    with pytest.raises(IngressError):
        harness.compare(f, .1)
    assert calls == []


def test_provider_unknown_key_propagates_and_freezes():
    key = CODE, DAYS[0], 895
    original = {key: BucketVolume(2500, 895, UNIT)}
    provider = FrozenProvider(original)
    original[key] = BucketVolume(999999, 895, UNIT)
    cap = VolumeCap(.1, provider)
    assert cap.clamp(key, 895, 500, buy=True)[0] == 200
    with pytest.raises(IngressError, match="unregistered key"):
        cap.clamp((CODE, DAYS[1], 895), 895, 500)
    with pytest.raises(TypeError):
        provider.samples[key] = None


@pytest.mark.parametrize("sell_size", [200, 101])
def test_m4_l_reverse_buy_sell_and_odd_shares(sell_size):
    key = CODE, DAYS[1], 895
    st = SimState(cash=100000, buy_cost_rate=.0015, sell_cost_rate=.0015, min_cost=5,
                  volume_cap=VolumeCap(.1, {key: BucketVolume(3000, 895, UNIT)}))
    old = Position(CODE, sell_size, 10, 0, 10)
    st.positions[CODE] = [old]
    assert execute_buy(st, CODE, 10, 1000, 1, date(2026, 9, 2), bucket_id=895)
    assert _sell(st, CODE, old, 10, date(2026, 9, 2), "test", bucket_id=895, day_i=1) == sell_size
    assert st.volume_cap.used[key] == 100 + sell_size


@pytest.mark.parametrize("capacity,child_day,nested,expected", [
    (400, 0, False, 0), (500, 0, False, 500), (500, 1, False, 0), (500, 0, True, 0),
])
def test_m9_l_atomic_ride_group(capacity, child_day, nested, expected):
    key = CODE, DAYS[1], 895
    st = SimState(cash=0, volume_cap=VolumeCap(1, {key: BucketVolume(capacity, 895, UNIT)}))
    parent = Position(CODE, 300, 10, 0, 10, pending_exit="trail")
    child = Position(CODE, 200, 10, child_day, 10, lot_id=1, ride_with=0)
    st.positions[CODE] = [parent, child]
    if nested:
        st.positions[CODE].append(Position(CODE, 100, 10, 0, 10, lot_id=2, ride_with=1))
    _sell(st, CODE, parent, 10, date(2026, 9, 2), "trail", bucket_id=895, day_i=1)
    assert sum(t["shares"] for t in st.trades if t["side"] == "SELL") == expected
    assert st.volume_cap.used == ({key: expected} if expected else {})
    if not expected:
        assert parent.pending_exit == "trail" and child.ride_with == 0
        assert [p.shares for p in st.positions[CODE]][:2] == [300, 200]
    if capacity == 400 or nested:
        assert st.trades[0]["reason"] == (
            "skip_volume_cap:unsupported_ride_tree" if nested else "skip_volume_cap:atomic_exit")


@pytest.fixture
def external():
    # Repository conftest redirects tmp_path into artifacts; the CLI forbids it.
    with tempfile.TemporaryDirectory(prefix="d5-ingress-test-") as directory:
        root = Path(directory)
        (root / "inputs").mkdir()
        yield root


def cli_args(root, f=None, run_id="run"):
    path = root / "inputs" / "fixture.json"
    path.write_text(json.dumps(f or fixture(), ensure_ascii=False), encoding="utf-8")
    go = root / "HUMAN_GO.md"
    go.write_text("Synthetic CLI test authority only; no source certification.\n", encoding="utf-8")
    return ["--fixture", str(path), "--fixture-sha256", hashlib.sha256(path.read_bytes()).hexdigest(),
            "--human-go", str(go), "--external-parent", str(root / "outputs"),
            "--run-id", run_id, "--participation-rate", ".1"]


def test_cli_success_provenance_isolation_and_overwrite(external):
    args = cli_args(external)
    proc = subprocess.run([sys.executable, str(Path(harness.__file__)), *args], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    root = external / "outputs" / "run"
    receipt = json.loads((root / "receipt.json").read_text())
    assert receipt["schema"] == "d5_ingress_v1"
    assert receipt["comparison_status"] == "no_ssot_compare_authorization"
    assert receipt["matrix"]["M2"]["status"] == "PASS"
    assert receipt["matrix"]["M8"]["status"] == "NOT_RUN"
    assert receipt["source"]["before"] == receipt["source"]["after"]
    assert receipt["authority"]["human_go"]["sha256"]
    assert sorted(receipt["output_files"]) == ["comparison.json", "harness/result.json", "native/result.json", "receipt.json"]
    for name, info in receipt["outputs"].items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == info["sha256"]
    assert (root / "native" / "result.json").read_bytes() == (root / "harness" / "result.json").read_bytes()
    before = (root / "receipt.json").read_bytes()
    assert harness.main(args) == 1
    assert (root / "receipt.json").read_bytes() == before


@pytest.mark.parametrize("failure", ["hash", "missing_file", "missing_bucket", "native_delta", "api", "write"])
def test_m11_cli_failure_receipts(external, monkeypatch, failure):
    f = fixture()
    if failure == "missing_bucket":
        f["source"]["minute"].pop()
    if failure == "native_delta":
        f["native"]["minute"][CODE][0]["close"] = 11.
    if failure == "api":
        f["parameters"]["total_cash"] = 1.
    args = cli_args(external, f)
    if failure == "hash":
        (external / "inputs" / "fixture.json").write_text("{}", encoding="utf-8")
    if failure == "missing_file":
        (external / "inputs" / "fixture.json").unlink()
    if failure == "write":
        original = harness.write_json

        def fail_one(path, value):
            if path.name == "result.json":
                raise OSError("test isolated writer failure")
            return original(path, value)

        monkeypatch.setattr(harness, "write_json", fail_one)
    assert harness.main(args) == 1
    receipt = json.loads((external / "outputs" / "run" / "receipt.json").read_text())
    assert receipt["status"] == "FAIL"
    if failure not in ("api",):
        assert receipt["failure"]
    if failure in ("hash", "missing_file", "missing_bucket", "native_delta"):
        assert receipt["output_files"] == ["receipt.json"]


@pytest.mark.parametrize("run_id", ["../escape", "/tmp/escape", "..", "a/b"])
def test_m11_output_escape_rejected(external, run_id):
    assert harness.main(cli_args(external, run_id=run_id)) == 1
    assert not (external / "outputs").exists()


def test_output_overlap_symlink_and_configured_roots_rejected(external, monkeypatch):
    for parent in (harness.REPO_ROOT, external / "inputs", external):
        with pytest.raises(IngressError, match="overlaps"):
            harness.output_root(parent, "run", external / "inputs")
    lake = external / "fake-lake"
    lake.mkdir()
    alias = external / "alias"
    alias.symlink_to(lake, target_is_directory=True)
    monkeypatch.setenv("OSKH_SOURCE_PARQUET_ROOT", str(lake))
    with pytest.raises(IngressError, match="overlaps"):
        harness.output_root(alias / "out", "run", external / "inputs")


def test_m11_identity_drift_during_read(external, monkeypatch):
    args = cli_args(external)
    original = harness.identity
    calls = []

    def changed(path):
        value = original(path)
        calls.append(path)
        if len(calls) > 1:
            value["sha256"] = "drift"
        return value

    monkeypatch.setattr(harness, "identity", changed)
    with pytest.raises(IngressError, match="changed during read"):
        harness.read_fixture(Path(args[1]), args[3])


def test_shared_run_main_and_cache_are_not_used(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("shared IO must not run")

    monkeypatch.setattr(harness.engine, "run", forbidden)
    monkeypatch.setattr(harness.engine, "main", forbidden)
    for name in ("_read_one_minute", "read_minute_cache", "write_minute_cache", "minute_cache_path"):
        monkeypatch.setattr(harness.engine, name, forbidden)
    monkeypatch.setattr(pd, "read_parquet", forbidden)
    monkeypatch.setattr(pd.DataFrame, "to_parquet", forbidden)
    passed(fixture())
