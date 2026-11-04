"""Pin the host-owned S20 freshness policy without market-data dependencies."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pandas as pd
import pytest

from common.infra import data_root
from oskh_data import freshness

EXPECTED_DATE = "20261104"
STALE_DATE = "20261030"
SYMBOL = "000001.SZ"
MISSING_SYMBOL = "000002.SZ"


@pytest.fixture(
    params=[(True, "block", False), (False, "warn", True)],
    ids=["in-session", "out-of-session"],
)
def session_policy(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> tuple[str, bool]:
    in_session, failure_action, failure_ok = request.param
    monkeypatch.setattr(freshness, "_is_trading_session", lambda: in_session)
    monkeypatch.setattr(
        freshness, "_check_adj_factor_table_freshness", lambda _date: (True, EXPECTED_DATE)
    )
    monkeypatch.setattr(freshness, "_trading_days_count", lambda _since, _until: 0)
    monkeypatch.setattr(freshness, "get_previous_trading_day", lambda _date=None: "20261103")

    # Freshness only needs this resolver; avoid reader's import-time config lookup.
    reader = ModuleType("oskh_data.reader")
    monkeypatch.setattr(reader, "_resolve_data_root", lambda: tmp_path, raising=False)
    monkeypatch.setitem(sys.modules, reader.__name__, reader)
    monkeypatch.setattr(data_root, "resolve_period_root", lambda _period: tmp_path)
    return failure_action, failure_ok


def _write_daily_bar(root: Path, date: str) -> None:
    path = root / "dividend_type=none" / "symbol=000001_SZ" / "data.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    time_ms = pd.Timestamp(date, tz="UTC").value // 1_000_000
    pd.DataFrame({"time": [time_ms]}).to_parquet(path, index=False, engine="pyarrow")


@pytest.mark.parametrize("symbols", [[SYMBOL], []], ids=["nonempty", "empty"])
def test_adj_factor_failure(
    monkeypatch: pytest.MonkeyPatch, session_policy: tuple[str, bool], symbols: list[str]
) -> None:
    action, ok = session_policy
    monkeypatch.setattr(
        freshness, "_check_adj_factor_table_freshness", lambda _date: (False, STALE_DATE)
    )

    result = freshness.check_data_freshness(symbols, expected_date=EXPECTED_DATE)

    assert result == freshness.FreshnessResult(
        ok=ok,
        coverage_ratio=0.0,
        expected_count=len(symbols),
        loaded_count=0,
        missing_symbols=["adj_factor.parquet"],
        last_data_date=STALE_DATE,
        expected_date=EXPECTED_DATE,
        action=action,
    )


@pytest.mark.parametrize("min_coverage_ratio", [0.95, 0.5], ids=["below", "at-threshold"])
def test_coverage_policy(
    tmp_path: Path, session_policy: tuple[str, bool], min_coverage_ratio: float
) -> None:
    failure_action, failure_ok = session_policy
    _write_daily_bar(tmp_path, EXPECTED_DATE)

    result = freshness.check_data_freshness(
        [SYMBOL, MISSING_SYMBOL],
        expected_date=EXPECTED_DATE,
        min_coverage_ratio=min_coverage_ratio,
        max_staleness_days=2,
    )

    below_threshold = min_coverage_ratio == 0.95
    assert result == freshness.FreshnessResult(
        ok=failure_ok if below_threshold else True,
        coverage_ratio=0.5,
        expected_count=2,
        loaded_count=1,
        missing_symbols=[MISSING_SYMBOL],
        last_data_date=EXPECTED_DATE,
        expected_date=EXPECTED_DATE,
        action=failure_action if below_threshold else "pass",
    )


@pytest.mark.parametrize("max_staleness_days", [2, 3], ids=["over", "at-threshold"])
def test_staleness_policy(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    session_policy: tuple[str, bool],
    max_staleness_days: int,
) -> None:
    failure_action, failure_ok = session_policy
    _write_daily_bar(tmp_path, STALE_DATE)
    monkeypatch.setattr(freshness, "_trading_days_count", lambda _since, _until: 3)

    result = freshness.check_data_freshness(
        [SYMBOL],
        expected_date=EXPECTED_DATE,
        min_coverage_ratio=0.95,
        max_staleness_days=max_staleness_days,
    )

    over_threshold = max_staleness_days == 2
    assert result == freshness.FreshnessResult(
        ok=failure_ok if over_threshold else True,
        coverage_ratio=1.0,
        expected_count=1,
        loaded_count=1,
        missing_symbols=[],
        last_data_date=STALE_DATE,
        expected_date=EXPECTED_DATE,
        action=failure_action if over_threshold else "pass",
    )


@pytest.mark.parametrize("symbols", [[SYMBOL], []], ids=["full-coverage", "empty"])
def test_fresh_data_passes(
    tmp_path: Path, session_policy: tuple[str, bool], symbols: list[str]
) -> None:
    _write_daily_bar(tmp_path, EXPECTED_DATE)

    result = freshness.check_data_freshness(symbols, expected_date=EXPECTED_DATE)

    assert result == freshness.FreshnessResult(
        ok=True,
        coverage_ratio=1.0,
        expected_count=len(symbols),
        loaded_count=len(symbols),
        missing_symbols=[],
        last_data_date=EXPECTED_DATE,
        expected_date=EXPECTED_DATE,
        action="pass",
    )


def test_default_thresholds_without_env_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OSKH_DATA_MIN_COVERAGE_RATIO", raising=False)
    monkeypatch.delenv("OSKH_DATA_MAX_STALENESS_DAYS", raising=False)
    # Load a private copy to preserve the original module and existing imports.
    spec = importlib.util.spec_from_file_location(
        "oskh_data._freshness_session_policy_defaults", freshness.__file__
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)

    assert module.DEFAULT_MIN_COVERAGE_RATIO == 0.95
    assert module.DEFAULT_MAX_STALENESS_DAYS == 2


@pytest.mark.parametrize(
    ("wall_time", "in_session"),
    [("09:14:59", False), ("09:15:00", True), ("15:00:00", True), ("15:00:01", False)],
)
def test_trading_session_boundaries(
    monkeypatch: pytest.MonkeyPatch, wall_time: str, in_session: bool
) -> None:
    now = pd.Timestamp(f"2026-11-04 {wall_time}")
    # Replace only freshness's clock reference, leaving pandas itself intact.
    clock = SimpleNamespace(Timestamp=SimpleNamespace(now=lambda: now))
    monkeypatch.setattr(freshness, "pd", clock)

    assert freshness._is_trading_session() is in_session
