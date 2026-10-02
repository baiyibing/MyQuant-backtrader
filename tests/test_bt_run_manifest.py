"""Opt-in research run provenance, independent of market data and fee math."""

import hashlib
import importlib
import inspect
import json
from pathlib import Path

import pytest

from backtest.research import ashare_fees, csv_artifacts
from backtest.research.csv_ledger import SimState
from bt_contract import canonical_json_bytes
from bt_contract.run_manifest import build_bt_run_manifest, write_bt_run_manifest


def _build(**kwargs):
    return build_bt_run_manifest(
        strategy="version6", dividend_type="none", config={}, **kwargs
    )


@pytest.fixture
def state():
    st = SimState()
    st.equity_curve = [("20260925", 1000.0)]
    st.trades = [{"date": "20260925", "side": "BUY", "shares": 100}]
    return st


def test_manifest_records_fee_schedule_and_cap_off_by_default():
    manifest = _build()
    assert manifest["schema"] == "myquant.bt-run/1"
    assert manifest["strategy"] == "version6"
    assert manifest["dividend_type"] == "none"
    assert manifest["fee_schedule"] == "BILATERAL_10BP"
    assert manifest["liquidity_cap"] == "off"
    assert manifest["participation_rate"] is None
    assert manifest["signal_bundle_sha256"] is None


def test_qlib_cost_label_is_QLIB_PORTANA_without_changing_fee_math(monkeypatch):
    assert ashare_fees.trade_commission(1000, 0.001) == 1.0
    assert ashare_fees.BILATERAL_10BP.buy_fee(1000) == 1.0
    assert ashare_fees.QLIB_PORTANA.buy_fee(1000) == 5.0

    def unexpected_fee_call(*args, **kwargs):
        pytest.fail("manifest generation must not calculate a fee")

    with monkeypatch.context() as patch:
        patch.setattr(ashare_fees, "trade_commission", unexpected_fee_call)
        patch.setattr(ashare_fees.FeeSchedule, "buy_fee", unexpected_fee_call)
        assert _build(fee_schedule="QLIB_PORTANA")["fee_schedule"] == "QLIB_PORTANA"
    assert ashare_fees.BILATERAL_10BP.buy_fee(1000) == 1.0


def test_write_run_artifacts_default_does_not_create_manifest(tmp_path, state, monkeypatch):
    def unexpected_manifest_call(*args, **kwargs):
        pytest.fail("default artifact output must not generate a manifest")

    monkeypatch.setattr(
        "bt_contract.run_manifest.write_bt_run_manifest", unexpected_manifest_call
    )
    out = csv_artifacts.write_run_artifacts(tmp_path / "run", state, "报告", "lock\n")
    assert {path.name for path in out.iterdir()} == {
        "summary.txt", "daily_equity.csv", "trades.csv"
    }
    assert (out / "summary.txt").read_bytes() == "报告\nlock\n".encode()


def test_artifact_carries_md5_and_sha256(tmp_path):
    artifact = tmp_path / "trades.csv"
    data = b"side,shares\nBUY,100\n"
    artifact.write_bytes(data)
    manifest = _build(artifacts=[artifact])
    assert manifest["artifacts"] == [{
        "path": artifact.as_posix(),
        "md5": hashlib.md5(data).hexdigest(),
        "sha256": hashlib.sha256(data).hexdigest(),
    }]


def test_bad_fee_schedule_name_raises():
    with pytest.raises(ValueError, match="fee_schedule"):
        _build(fee_schedule="STAMP_DUTY")


def test_summarize_source_unchanged():
    assert "期末净值" in inspect.getsource(csv_artifacts.summarize)


def test_write_manifest_roundtrip_records_config_hash_and_explicit_inputs(tmp_path):
    config = {"pool_dir": tmp_path / "pool", "nested": [{"root": tmp_path}]}
    normalized = {
        "pool_dir": (tmp_path / "pool").as_posix(),
        "nested": [{"root": tmp_path.as_posix()}],
    }
    path = tmp_path / "run-manifest.json"
    manifest = write_bt_run_manifest(
        path,
        strategy="version6",
        dividend_type="front",
        config=config,
        git_commit="a" * 40,
        participation_rate=0.1,
        signal_bundle_sha256="b" * 64,
    )
    assert json.loads(path.read_bytes()) == manifest
    assert path.read_bytes() == canonical_json_bytes(manifest)
    assert manifest["config_sha256"] == hashlib.sha256(
        canonical_json_bytes(normalized)
    ).hexdigest()
    assert manifest["git_commit"] == "a" * 40
    assert manifest["liquidity_cap"] == "on"
    assert manifest["participation_rate"] == 0.1
    assert manifest["signal_bundle_sha256"] == "b" * 64
    assert config["pool_dir"] == tmp_path / "pool"


def test_artifact_manifest_opt_in_preserves_existing_artifact_bytes(tmp_path, state):
    before = csv_artifacts.write_run_artifacts(tmp_path / "off", state, "报告", "lock")
    after = csv_artifacts.write_run_artifacts(
        tmp_path / "on", state, "报告", "lock", emit_run_manifest=True,
        manifest_config={
            "strategy": "version6", "dividend_type": "none", "qlib_cost": True,
            "participation_rate": 0.2,
        },
        signal_bundle_sha256="c" * 64,
    )
    for name in ("summary.txt", "daily_equity.csv", "trades.csv"):
        assert (before / name).read_bytes() == (after / name).read_bytes()
    manifest = json.loads((after / "run-manifest.json").read_bytes())
    assert manifest["fee_schedule"] == "QLIB_PORTANA"
    assert manifest["liquidity_cap"] == "on"
    assert manifest["participation_rate"] == 0.2
    assert manifest["signal_bundle_sha256"] == "c" * 64
    assert len(manifest["artifacts"]) == 3
    for artifact in manifest["artifacts"]:
        data = Path(artifact["path"]).read_bytes()
        assert artifact["md5"] == hashlib.md5(data).hexdigest()
        assert artifact["sha256"] == hashlib.sha256(data).hexdigest()


@pytest.mark.parametrize("engine", ["daily", "minute"])
@pytest.mark.parametrize("emit", [False, True])
def test_cli_manifest_is_opt_in_and_labels_existing_qlib_cost(
    tmp_path, state, monkeypatch, engine, emit
):
    module = importlib.import_module(f"backtest.research.csv_{engine}_backtest")
    calls = []

    def fake_run(*args, **kwargs):
        calls.append(kwargs)
        return state

    monkeypatch.setattr(module, "run", fake_run)
    monkeypatch.setattr(module, "summarize", lambda *args, **kwargs: "报告")
    if engine == "minute":
        monkeypatch.setattr(module, "maybe_compare_daily", lambda *args, **kwargs: "")
    out = tmp_path / "out"
    pool = tmp_path / "pool"
    pool.mkdir()
    argv = [
        "--strategy", "version6", "--start", "20260925", "--end", "20260925",
        "--pool-dir", str(pool), "--out-dir", str(out), "--qlib-cost",
    ]
    if emit:
        argv.append("--emit-run-manifest")
    assert module.main(argv) == 0
    assert len(calls) == 1
    assert calls[0]["buy_cost_rate"] == ashare_fees.QLIB_OPEN_COST
    assert calls[0]["sell_cost_rate"] == ashare_fees.QLIB_CLOSE_COST
    assert calls[0]["min_cost"] == ashare_fees.QLIB_MIN_COST
    path = out / "run-manifest.json"
    assert path.exists() is emit
    if emit:
        manifest = json.loads(path.read_bytes())
        assert manifest["strategy"] == "version6"
        assert manifest["dividend_type"] == "none"
        assert manifest["fee_schedule"] == "QLIB_PORTANA"
        assert manifest["liquidity_cap"] == "off"
