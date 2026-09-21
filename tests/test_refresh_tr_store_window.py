# -*- coding: utf-8 -*-
"""Data-free unit tests for research helper refresh_tr_store_window."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from oskh_data.turnover_resistance_store import TurnoverResistanceStore
from scripts.data.refresh_tr_store_window import refresh_window


def _store_mock(*, with_bands: bool = True) -> MagicMock:
    store = MagicMock(spec=TurnoverResistanceStore)
    store.path = Path("/tmp/turnover_resistance_daily.parquet")
    store.has_trade_date.return_value = False
    store.upsert_daily.return_value = {
        "inserted": 2,
        "replaced": 0,
        "total_after": 2,
    }
    store.compute_and_update_bands.return_value = {
        "updated_rows": 2 if with_bands else 0,
        "trade_dates": 1,
    }

    def _load(_trade_date, *, window=1000, require_bands=False):
        if require_bands and not with_bands:
            return pd.DataFrame()
        if not with_bands and require_bands is False:
            # TR rows exist but bands missing
            return pd.DataFrame({"stock_code": ["000001.SZ"], "trade_date": [_trade_date]})
        return pd.DataFrame({"stock_code": ["000001.SZ"], "trade_date": [_trade_date]})

    store.load_cross_section.side_effect = _load
    return store


def test_refresh_window_upserts_and_bands(tmp_path: Path) -> None:
    store = _store_mock(with_bands=True)
    with patch(
        "scripts.data.refresh_tr_store_window.TurnoverResistanceStore",
        return_value=store,
    ):
        code = refresh_window(
            start="20260825",
            end="20260826",
            store_parquet=tmp_path / "tr.parquet",
            lake_root=tmp_path / "lake",
            dates=["20260825", "20260826"],
            compute_fn=lambda *_a, **_k: [{"stock_code": "000001.SZ"}],
        )
    assert code == 0
    assert store.upsert_daily.call_count == 2
    store.compute_and_update_bands.assert_called_once()
    kwargs = store.compute_and_update_bands.call_args.kwargs
    assert kwargs["trade_dates"] == ["20260825", "20260826"]
    assert kwargs["n_history"] == 60
    assert kwargs["period"] == 20


def test_refresh_window_fail_closed_when_no_bands(tmp_path: Path) -> None:
    store = _store_mock(with_bands=False)
    # empty TR compute -> no rows -> still empty bands
    store.load_cross_section.side_effect = lambda *_a, **_k: pd.DataFrame()
    with patch(
        "scripts.data.refresh_tr_store_window.TurnoverResistanceStore",
        return_value=store,
    ):
        code = refresh_window(
            start="20260825",
            end="20260825",
            store_parquet=tmp_path / "tr.parquet",
            lake_root=tmp_path / "lake",
            dates=["20260825"],
            compute_fn=lambda *_a, **_k: [],
        )
    assert code == 1


def test_bands_only_skips_upsert(tmp_path: Path) -> None:
    store = _store_mock(with_bands=True)
    with patch(
        "scripts.data.refresh_tr_store_window.TurnoverResistanceStore",
        return_value=store,
    ):
        code = refresh_window(
            start="20260825",
            end="20260825",
            store_parquet=tmp_path / "tr.parquet",
            lake_root=tmp_path / "lake",
            dates=["20260825"],
            bands_only=True,
            compute_fn=lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("no compute")),
        )
    assert code == 0
    store.upsert_daily.assert_not_called()
    store.compute_and_update_bands.assert_called_once()


def test_skip_existing_tr(tmp_path: Path) -> None:
    store = _store_mock(with_bands=True)
    store.has_trade_date.return_value = True
    with patch(
        "scripts.data.refresh_tr_store_window.TurnoverResistanceStore",
        return_value=store,
    ):
        code = refresh_window(
            start="20260825",
            end="20260825",
            store_parquet=tmp_path / "tr.parquet",
            lake_root=tmp_path / "lake",
            dates=["20260825"],
            skip_existing_tr=True,
            compute_fn=lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("no compute")),
        )
    assert code == 0
    store.upsert_daily.assert_not_called()
