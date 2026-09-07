# -*- coding: utf-8 -*-
"""path-SSOT PR-3 D7: .authority marker + loud fallback (unset is not rollback)."""

from __future__ import annotations

import warnings
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import pytest

from common.infra.data_root import (
    AUTHORITY_MARKER_NAME,
    find_authority_marker,
    reset_authority_fallback_warnings,
    resolve_l2_parquet_root,
    resolve_parquet_container,
    resolve_period_root,
    resolve_source_parquet,
    resolve_tr_staging_dir,
    resolve_turnover_resist_parquet_root,
)


@pytest.fixture(autouse=True)
def _isolate_authority_hint(monkeypatch, tmp_path):
    hint = tmp_path / "authority_hint"
    hint.mkdir()
    monkeypatch.setenv("OSKH_AUTHORITY_HINT_ROOT", str(hint))
    for key in (
        "OSKH_PERIOD_1D_ROOT",
        "OSKH_PERIOD_1M_ROOT",
        "OSKH_SOURCE_PARQUET_ROOT",
        "OSKH_L2_PARQUET_ROOT",
        "TURNOVER_RESIST_DATA_DIR",
        "TURNOVER_RESIST_STAGING_DIR",
    ):
        monkeypatch.delenv(key, raising=False)
    reset_authority_fallback_warnings()
    return hint


def _touch_marker(hint: Path) -> Path:
    marker = hint / AUTHORITY_MARKER_NAME
    marker.write_text("oskh-path-ssot-authority=1\n", encoding="utf-8")
    return marker


def test_find_authority_marker_absent(_isolate_authority_hint):
    assert find_authority_marker() is None


def test_find_authority_marker_present(_isolate_authority_hint):
    marker = _touch_marker(_isolate_authority_hint)
    assert find_authority_marker() == marker


def test_period_default_uses_authority_parent_when_env_unset(
    monkeypatch, _isolate_authority_hint
):
    _touch_marker(_isolate_authority_hint)
    monkeypatch.delenv("OSKH_PERIOD_1D_ROOT", raising=False)
    with pytest.warns(UserWarning, match="OSKH_PERIOD_1D_ROOT is unset"):
        got = resolve_period_root("1d")
    assert got == _isolate_authority_hint / "period=1d"


def test_period_no_warn_when_env_set(monkeypatch, _isolate_authority_hint, tmp_path):
    _touch_marker(_isolate_authority_hint)
    f_root = tmp_path / "f_period"
    monkeypatch.setenv("OSKH_PERIOD_1D_ROOT", str(f_root))
    with _no_user_warning():
        assert resolve_period_root("1d") == f_root


def test_period_no_warn_when_marker_absent(monkeypatch, _isolate_authority_hint):
    monkeypatch.delenv("OSKH_PERIOD_1D_ROOT", raising=False)
    with _no_user_warning():
        resolve_period_root("1d")


def test_period_base_kwarg_skips_authority_warn(
    monkeypatch, _isolate_authority_hint, tmp_path
):
    _touch_marker(_isolate_authority_hint)
    monkeypatch.delenv("OSKH_PERIOD_1D_ROOT", raising=False)
    local = tmp_path / "e_container"
    with _no_user_warning():
        got = resolve_period_root("1d", base=local)
    assert got == local / "period=1d"


def test_period_explicit_root_skips_authority_warn(
    monkeypatch, _isolate_authority_hint, tmp_path
):
    _touch_marker(_isolate_authority_hint)
    monkeypatch.delenv("OSKH_PERIOD_1D_ROOT", raising=False)
    explicit = tmp_path / "explicit_1d"
    with _no_user_warning():
        assert resolve_period_root("1d", explicit_root=str(explicit)) == explicit


def test_source_parquet_uses_authority_parent_when_env_unset(
    monkeypatch, _isolate_authority_hint
):
    _touch_marker(_isolate_authority_hint)
    monkeypatch.delenv("OSKH_SOURCE_PARQUET_ROOT", raising=False)
    with pytest.warns(UserWarning, match="OSKH_SOURCE_PARQUET_ROOT is unset"):
        got = resolve_source_parquet("adj_factor.parquet")
    assert got == _isolate_authority_hint / "adj_factor.parquet"


def test_l2_uses_authority_parent_when_env_unset(monkeypatch, _isolate_authority_hint):
    _touch_marker(_isolate_authority_hint)
    monkeypatch.delenv("OSKH_L2_PARQUET_ROOT", raising=False)
    with pytest.warns(UserWarning, match="OSKH_L2_PARQUET_ROOT is unset"):
        got = resolve_l2_parquet_root()
    assert got == _isolate_authority_hint / "l2_parquet"


def test_parquet_container_uses_authority_parent(
    monkeypatch, _isolate_authority_hint
):
    _touch_marker(_isolate_authority_hint)
    monkeypatch.delenv("OSKH_SOURCE_PARQUET_ROOT", raising=False)
    assert resolve_parquet_container() == _isolate_authority_hint


def test_tr_parquet_root_defaults_to_parquet_container(
    monkeypatch, _isolate_authority_hint
):
    _touch_marker(_isolate_authority_hint)
    monkeypatch.delenv("TURNOVER_RESIST_DATA_DIR", raising=False)
    assert resolve_turnover_resist_parquet_root() == _isolate_authority_hint
    assert resolve_tr_staging_dir() == _isolate_authority_hint / "tr_staging"


def test_tr_parquet_root_env_override(monkeypatch, tmp_path):
    custom = tmp_path / "custom_tr"
    monkeypatch.setenv("TURNOVER_RESIST_DATA_DIR", str(custom))
    assert resolve_turnover_resist_parquet_root() == custom


def test_default_data_dir_uses_parquet_resolver(
    monkeypatch, _isolate_authority_hint
):
    from oskh_factors.bridge.turnover_resist import _default_data_dir

    _touch_marker(_isolate_authority_hint)
    monkeypatch.delenv("TURNOVER_RESIST_DATA_DIR", raising=False)
    assert Path(_default_data_dir()) == _isolate_authority_hint


def test_resolve_staging_dir_uses_f_container(
    monkeypatch, _isolate_authority_hint
):
    from oskh_data.turnover_resistance_store import resolve_staging_dir

    _touch_marker(_isolate_authority_hint)
    monkeypatch.delenv("TURNOVER_RESIST_DATA_DIR", raising=False)
    monkeypatch.delenv("TURNOVER_RESIST_STAGING_DIR", raising=False)
    assert resolve_staging_dir() == _isolate_authority_hint / "tr_staging"


def test_authority_warning_latched_once(monkeypatch, _isolate_authority_hint):
    _touch_marker(_isolate_authority_hint)
    monkeypatch.delenv("OSKH_PERIOD_1D_ROOT", raising=False)
    with pytest.warns(UserWarning, match="OSKH_PERIOD_1D_ROOT is unset"):
        resolve_period_root("1d")
    with _no_user_warning():
        resolve_period_root("1d")


@contextmanager
def _no_user_warning() -> Iterator[None]:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", UserWarning)
        yield
        user = [w for w in caught if issubclass(w.category, UserWarning)]
        assert user == [], [str(w.message) for w in user]
