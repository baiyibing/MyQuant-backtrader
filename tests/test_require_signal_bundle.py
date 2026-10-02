"""Required bundle validation is explicit and precedes market-data loading."""

import hashlib
import importlib
import json

import pytest

from backtest.research.csv_ledger import SimState
from backtest.research.csv_pool import (
    load_signal_bundle_if_present,
    parse_pool_csv,
    require_signal_bundle,
)
from bt_contract import canonical_json_bytes


def _sha256(value):
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _save(root, bundle):
    bundle["bundle_sha256"] = _sha256(
        {key: value for key, value in bundle.items() if key != "bundle_sha256"}
    )
    (root / "signal-bundle.json").write_bytes(canonical_json_bytes(bundle))


@pytest.fixture
def bundle(tmp_path):
    data = b"300190\n"
    (tmp_path / "20260925.csv").write_bytes(data)
    result = {
        "schema": "myquant.signal-bundle/1",
        "signal_asof_policy": "pred_minus_one",
        "availability": "unproven",
        "available_at": None,
        "calendar_id": _sha256(["2026-09-25"]),
        "price_domain": "unspecified",
        "rows": [{
            "signal_asof": "2026-09-24", "target_session": "2026-09-25",
            "pool_file": "20260925.csv", "pool_md5": hashlib.md5(data).hexdigest(),
            "pool_sha256": hashlib.sha256(data).hexdigest(),
        }],
    }
    _save(tmp_path, result)
    return result


def test_missing_sidecar_returns_none_without_flag(tmp_path):
    assert load_signal_bundle_if_present(tmp_path) is None


def test_require_raises_clear_error_when_absent(tmp_path):
    with pytest.raises(FileNotFoundError, match="signal-bundle.json required but missing"):
        require_signal_bundle(tmp_path)


@pytest.mark.parametrize("corruption", ["md5", "sha256", "future_available_at"])
def test_require_rejects_bad_hash_and_future_available_at(tmp_path, bundle, corruption):
    if corruption == "future_available_at":
        bundle.update(availability="declared", available_at="2026-09-26T09:00:00+08:00")
        message = "available_at is after target_session"
    else:
        bundle["rows"][0][f"pool_{corruption}"] = "0" * (32 if corruption == "md5" else 64)
        message = f"pool_{corruption} mismatch"
    _save(tmp_path, bundle)
    with pytest.raises(ValueError, match=message):
        require_signal_bundle(tmp_path)


def test_parse_pool_csv_still_accepts_prefixed_cell(tmp_path):
    path = tmp_path / "20260925.csv"
    path.write_text("SZ300190\n", encoding="utf-8")
    assert parse_pool_csv(path) == ["300190.SZ"]


def test_present_valid_sidecar_returns_verified_bundle(tmp_path, bundle):
    assert load_signal_bundle_if_present(tmp_path) == bundle
    assert require_signal_bundle(tmp_path) == bundle


@pytest.mark.parametrize("engine", ["daily", "minute"])
def test_flag_off_does_not_read_sidecar(tmp_path, monkeypatch, engine):
    module = importlib.import_module(f"backtest.research.csv_{engine}_backtest")
    (tmp_path / "signal-bundle.json").write_text('{"schema":"bad"}', encoding="utf-8")

    class PoolLoadReached(Exception):
        pass

    def pool_loader(*args, **kwargs):
        raise PoolLoadReached

    monkeypatch.setattr(module, "load_pool_day_map", pool_loader)
    with pytest.raises(PoolLoadReached):
        module.main([
            "--strategy", "version6", "--start", "20260925", "--end", "20260925",
            "--pool-dir", str(tmp_path), "--out-dir", str(tmp_path / "out"),
        ])


@pytest.mark.parametrize("engine", ["daily", "minute"])
@pytest.mark.parametrize("corruption", ["missing", "unknown_schema", "pool_hash", "json"])
def test_cli_requires_valid_bundle_before_pool_or_lake_loading(
    tmp_path, bundle, monkeypatch, engine, corruption
):
    module = importlib.import_module(f"backtest.research.csv_{engine}_backtest")
    sidecar = tmp_path / "signal-bundle.json"
    if corruption == "missing":
        sidecar.unlink()
        error, message = FileNotFoundError, "signal-bundle.json required but missing"
    elif corruption == "unknown_schema":
        bundle["schema"] = "myquant.signal-bundle/999"
        _save(tmp_path, bundle)
        error, message = ValueError, "unknown schema"
    elif corruption == "pool_hash":
        (tmp_path / "20260925.csv").write_bytes(b"600000\n")
        error, message = ValueError, "pool_md5 mismatch"
    else:
        sidecar.write_text("{", encoding="utf-8")
        error, message = ValueError, None

    def unexpected_loader(*args, **kwargs):
        pytest.fail("required bundle must be checked before loading pool or market data")

    monkeypatch.setattr(module, "load_pool_day_map", unexpected_loader)
    monkeypatch.setattr(module, "load_daily_ohlc", unexpected_loader)
    with pytest.raises(error, match=message):
        module.main([
            "--strategy", "version6", "--start", "20260925", "--end", "20260925",
            "--pool-dir", str(tmp_path), "--out-dir", str(tmp_path / "out"),
            "--require-signal-bundle",
        ])


@pytest.mark.parametrize("engine", ["daily", "minute"])
def test_cli_required_bundle_hash_links_to_opt_in_manifest(
    tmp_path, bundle, monkeypatch, engine
):
    module = importlib.import_module(f"backtest.research.csv_{engine}_backtest")
    st = SimState()
    st.equity_curve = [("20260925", st.cash)]
    monkeypatch.setattr(module, "load_daily_ohlc", lambda *args, **kwargs: {})
    monkeypatch.setattr(module, "load_exdiv_ratios", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "simulate", lambda *args, **kwargs: st)
    if engine == "minute":
        monkeypatch.setattr(module, "load_minute_bars", lambda *args, **kwargs: {})
        monkeypatch.setattr(module, "maybe_compare_daily", lambda *args, **kwargs: "")
    out = tmp_path / "out"
    assert module.main([
        "--strategy", "version6", "--start", "20260925", "--end", "20260925",
        "--pool-dir", str(tmp_path), "--out-dir", str(out),
        "--require-signal-bundle", "--emit-run-manifest",
    ]) == 0
    manifest = json.loads((out / "run-manifest.json").read_bytes())
    assert st.stats["signal_bundle_sha256"] == bundle["bundle_sha256"]
    assert manifest["signal_bundle_sha256"] == bundle["bundle_sha256"]
