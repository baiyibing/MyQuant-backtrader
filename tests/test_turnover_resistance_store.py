# -*- coding: utf-8 -*-
"""Tests for turnover resistance Parquet store + TR Bollinger Bands."""

from __future__ import annotations

from typing import Any, cast

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from oskh_factors.chip.bands import (
    classify_tr_bb_signal,
    compute_tr_bb_columns,
    tr_bollinger_bands,
)
from oskh_data.turnover_resistance_store import (
    SCHEMA_COLUMNS,
    TurnoverResistanceStore,
    merge_parquet_into_canonical,
    normalize_ffi_row,
    resolve_year_staging_path,
)


def _mock_ffi_row(stock_code: str = "000001.SZ", trade_date: str = "20260101") -> dict:
    return {
        "stock_code": stock_code,
        "stock_name": "Test",
        "date": trade_date,
        "close": 10.0,
        "cyqk_T": 0.5,
        "cyqk_T_1": 0.48,
        "profit_chip_diff": 0.02,
        "turnover": 0.03,
        "turnover_resistance": 0.6667,
        "turnover_free": 0.04,
        "turnover_resistance_free": 0.5,
        "circulating_capital": 1e9,
        "freeFloatCapital": 8e8,
        "bb_upper": 11.0,
        "bb_middle": 10.0,
        "bb_lower": 9.0,
        "bb_position": 0.5,
        "bb_width": 0.2,
    }


@pytest.fixture
def store_path(tmp_path: Path) -> Path:
    return tmp_path / "turnover_resistance_daily.parquet"


@pytest.fixture
def store(store_path: Path) -> TurnoverResistanceStore:
    return TurnoverResistanceStore(store_path)


class TestTrBollingerBands:
    def test_matches_manual_rolling(self):
        series = pd.Series([float(i) for i in range(1, 26)])
        result = tr_bollinger_bands(series, period=20, nbdev=2.0, ddof=1)
        roll = series.rolling(window=20, min_periods=20)
        ma = roll.mean().iloc[-1]
        std = roll.std(ddof=1).iloc[-1]
        upper = ma + 2.0 * std
        lower = ma - 2.0 * std
        assert result["tr_bb_middle"] == pytest.approx(round(float(ma), 4))
        assert result["tr_bb_upper"] == pytest.approx(round(float(upper), 4))
        assert result["tr_bb_lower"] == pytest.approx(round(float(lower), 4))

    def test_insufficient_history_returns_nan_bands(self):
        series = pd.Series([1.0, 2.0, 3.0])
        result = tr_bollinger_bands(series, period=20)
        assert np.isnan(result["tr_bb_middle"])
        assert result["tr_bb_position"] == 0.5

    def test_nan_in_window_returns_nan_bands(self):
        values = [float(i) for i in range(1, 19)] + [np.nan, np.nan]
        series = pd.Series(values)
        result = tr_bollinger_bands(series, period=20)
        assert np.isnan(result["tr_bb_middle"])


class TestNormalizeFfiRow:
    def test_maps_all_schema_columns(self):
        row = normalize_ffi_row(_mock_ffi_row(trade_date="20260102"), trade_date="20260102")
        for col in SCHEMA_COLUMNS:
            assert col in row
        assert row["trade_date"] == "20260102"
        assert row["cyqk_t"] == pytest.approx(0.5)
        assert row["free_float_capital"] == pytest.approx(8e8)
        assert np.isnan(row["bands_computed_at"])


class TestTurnoverResistanceStore:
    def test_upsert_and_load_series(self, store: TurnoverResistanceStore):
        dates = [f"202601{d:02d}" for d in range(1, 6)]
        for d in dates:
            store.upsert_daily(d, [_mock_ffi_row(trade_date=d)], window=1000)
        df = store.load_series("000001.SZ", end_date="20260105", n=3)
        assert len(df) == 3
        assert list(df["trade_date"]) == ["20260103", "20260104", "20260105"]

    def test_window_conflict_raises(self, store: TurnoverResistanceStore):
        store.upsert_daily("20260101", [_mock_ffi_row()], window=1000)
        with pytest.raises(ValueError, match="window"):
            store.upsert_daily("20260101", [_mock_ffi_row()], window=80)

    def test_strict_mode_rejects_mixed_source(self, store: TurnoverResistanceStore):
        store.upsert_daily(
            "20260101",
            [_mock_ffi_row(trade_date="20260101")],
            window=1000,
            source="canonical_rust",
        )
        store.upsert_daily(
            "20260102",
            [_mock_ffi_row(trade_date="20260102")],
            window=1000,
            source="chip_daily",
        )
        with pytest.raises(ValueError, match="口径不一致"):
            store.load_series("000001.SZ", n=10, strict=True)

    def test_compute_and_update_bands_batch(self, store: TurnoverResistanceStore):
        dates = [f"202601{d:02d}" for d in range(1, 26)]
        tr_values = [float(i) for i in range(1, 26)]
        for i, d in enumerate(dates):
            row = _mock_ffi_row(trade_date=d)
            row["turnover_resistance"] = tr_values[i]
            row["turnover_resistance_free"] = tr_values[i] * 0.5
            store.upsert_daily(d, [row], window=1000)

        stats = store.compute_and_update_bands(trade_dates=["20260125"], n_history=60)
        assert stats["updated_rows"] == 1

        cross = store.load_cross_section("20260125", require_bands=True)
        assert len(cross) == 1
        assert pd.notna(cross.iloc[0]["bands_computed_at"])
        assert pd.notna(cross.iloc[0]["tr_bb_middle"])

        manual = tr_bollinger_bands(pd.Series(tr_values), period=20)
        assert cross.iloc[0]["tr_bb_middle"] == pytest.approx(manual["tr_bb_middle"])

    def test_merge_year_staging_into_canonical(self, tmp_path: Path):
        staging_dir = tmp_path / "tr_staging"
        canonical = tmp_path / "turnover_resistance_daily.parquet"
        y2025 = resolve_year_staging_path(2025, staging_dir)
        y2026 = resolve_year_staging_path(2026, staging_dir)

        store_2025 = TurnoverResistanceStore(y2025)
        store_2025.upsert_daily("20251231", [_mock_ffi_row(trade_date="20251231")], window=1000)

        store_2026 = TurnoverResistanceStore(y2026)
        store_2026.upsert_daily("20260102", [_mock_ffi_row(trade_date="20260102")], window=1000)

        stats = merge_parquet_into_canonical(y2025, y2026, canonical_path=canonical)
        assert stats["source_rows"] == 2
        assert stats["total_after"] == 2

        canonical_store = TurnoverResistanceStore(canonical)
        assert canonical_store.has_trade_date("20251231")
        assert canonical_store.has_trade_date("20260102")

        store_2026.upsert_daily(
            "20260102",
            [_mock_ffi_row(trade_date="20260102", stock_code="000002.SZ")],
            window=1000,
        )
        merge_stats = merge_parquet_into_canonical(y2026, canonical_path=canonical)
        assert merge_stats["total_after"] == 3
        cross = canonical_store.load_cross_section("20260102")
        assert len(cross) == 2

    def test_groupby_batch_matches_manual_sample(self, store: TurnoverResistanceStore):
        codes = [f"600{i:03d}.SH" for i in range(1, 11)]
        dates = [f"202602{d:02d}" for d in range(1, 21)]
        for code in codes:
            suffix = int(code[3:6])
            for j, d in enumerate(dates):
                row = _mock_ffi_row(code, d)
                row["turnover_resistance"] = float(j + 1) + suffix * 0.01
                store.upsert_daily(d, [row], window=1000)

        hist = store.load_recent_history(n_trading_days=20)
        computed = compute_tr_bb_columns(hist, period=20)
        last_day = computed[computed["trade_date"] == "20260220"]
        assert len(last_day) == len(codes)
        for _, row in last_day.iterrows():
            frame = computed[computed["stock_code"] == row["stock_code"]].sort_values(  # pyright: ignore[reportCallIssue]
                by="trade_date"
            )
            series = frame["turnover_resistance"]
            manual = tr_bollinger_bands(cast(Any, series.reset_index(drop=True)), period=20)
            assert row["tr_bb_middle"] == pytest.approx(manual["tr_bb_middle"])


class TestSignals:
    def test_classify_skips_when_bands_missing(self):
        row = pd.Series({"turnover_resistance": 5.0, "tr_bb_upper": 4.0, "tr_bb_lower": 2.0})
        assert classify_tr_bb_signal(row) is None

    def test_classify_breakout(self):
        row = pd.Series(
            {
                "turnover_resistance": 5.0,
                "tr_bb_upper": 4.0,
                "tr_bb_lower": 2.0,
                "tr_bb_middle": 3.0,
                "bands_computed_at": 1.0,
            }
        )
        assert classify_tr_bb_signal(row) == "TR_BREAKOUT"
