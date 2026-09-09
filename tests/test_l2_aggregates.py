"""Unit tests for l2_analytics.aggregates (persisted pre-agg build + views)."""

from __future__ import annotations

from pathlib import Path

import pytest

from l2_analytics.aggregates import (
    build_aggregates_for_date,
    build_all_aggregates,
    cluster_agg_path,
    daily_metrics_path,
)
from l2_analytics.db import connect
from l2_analytics.etl_day import etl_one_day
from l2_analytics.templates import run_template

CSV_HEADER = (
    "TranID,Time,Price,Volume,SaleOrderVolume,BuyOrderVolume,"
    "Type,SaleOrderID,SaleOrderPrice,BuyOrderID,BuyOrderPrice"
)


def _write_csv(directory: Path, code: str, rows: list[tuple]) -> Path:
    path = directory / f"{code}.csv"
    lines = [CSV_HEADER]
    for r in rows:
        lines.append(",".join(str(v) for v in r))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _row(tran_id: int, time: str, price: float, vol: int, typ: str, soid: int = 1) -> tuple:
    return (tran_id, time, price, vol, vol // 2, vol // 2, typ, soid, price, 2, price)


@pytest.fixture()
def built_root(tmp_path: Path) -> Path:
    """ETL a synthetic 2-stock day into a parquet root (no aggregates yet)."""
    day = tmp_path / "2026-01-15"
    day.mkdir()
    # Zero-padded HH:MM:SS — required after session buckets use CAST(Time AS TIME).
    _write_csv(day, "000001", [
        _row(i, "09:30:%02d" % (i % 10), 10.50 + i * 0.01, 1000, "B" if i % 2 else "S", soid=100)
        for i in range(1, 9)
    ])
    _write_csv(day, "600000", [
        _row(1, "09:30:00", 8.00, 2000, "B", soid=200),
        _row(2, "10:00:00", 8.05, 1500, "S", soid=200),
        _row(3, "14:00:00", 8.10, 3000, "B", soid=200),
    ])
    out = tmp_path / "l2_parquet"
    etl_one_day(day, out_root=out, validate_gap_free=False)
    return out


class TestBuildAggregates:
    def test_build_creates_files(self, built_root: Path) -> None:
        con = connect(parquet_root=built_root, memory_limit="2GB", threads=2)
        try:
            res = build_aggregates_for_date(con, date="2026-01-15", out_root=built_root)
        finally:
            con.close()
        assert res["skipped"] is False
        assert res["daily_metrics_rows"] >= 1
        assert daily_metrics_path(built_root, "2026-01-15").is_file()
        assert cluster_agg_path(built_root, "2026-01-15").is_file()

    def test_daily_metrics_matches_templates(self, built_root: Path) -> None:
        con = connect(parquet_root=built_root, memory_limit="2GB", threads=2)
        try:
            build_aggregates_for_date(con, date="2026-01-15", out_root=built_root)
        finally:
            con.close()
        # Reconnect so the l2_daily_metrics view is registered.
        con = connect(parquet_root=built_root, memory_limit="2GB", threads=2)
        try:
            vwap_tpl = {
                r[0]: r[2]
                for r in run_template(con, "vwap", extra_where="stock_code = $c", params={"c": "600000.SH"})
            }
            ni_tpl = {
                r[0]: r[2]
                for r in run_template(con, "net_inflow", extra_where="stock_code = $c", params={"c": "600000.SH"})
            }
            agg = con.execute(
                "SELECT stock_code, vwap, net_inflow FROM l2_daily_metrics "
                "WHERE stock_code = '600000.SH'"
            ).fetchall()
        finally:
            con.close()
        assert agg, "expected a daily_metrics row for 600000.SH"
        code, vwap, net_inflow = agg[0]
        assert float(vwap) == pytest.approx(float(vwap_tpl[code]))
        assert float(net_inflow) == pytest.approx(float(ni_tpl[code]))

    def test_cluster_agg_threshold(self, built_root: Path) -> None:
        con = connect(parquet_root=built_root, memory_limit="2GB", threads=2)
        try:
            build_aggregates_for_date(con, date="2026-01-15", out_root=built_root)
        finally:
            con.close()
        con = connect(parquet_root=built_root, memory_limit="2GB", threads=2)
        try:
            rows = con.execute(
                "SELECT fill_count, total_notional FROM l2_cluster_agg"
            ).fetchall()
        finally:
            con.close()
        for fill_count, total_notional in rows:
            assert fill_count >= 5 or float(total_notional) >= 1_000_000

    def test_views_registered_only_when_files_exist(self, built_root: Path) -> None:
        # Before build: agg views absent.
        con = connect(parquet_root=built_root, memory_limit="2GB", threads=2)
        try:
            views = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
            assert "l2_daily_metrics" not in views
            assert "l2_cluster_agg" not in views
        finally:
            con.close()
        # After build + reconnect: agg views present.
        con = connect(parquet_root=built_root, memory_limit="2GB", threads=2)
        try:
            build_aggregates_for_date(con, date="2026-01-15", out_root=built_root)
        finally:
            con.close()
        con = connect(parquet_root=built_root, memory_limit="2GB", threads=2)
        try:
            views = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
            assert "l2_daily_metrics" in views
            assert "l2_cluster_agg" in views
        finally:
            con.close()

    def test_idempotent_skip(self, built_root: Path) -> None:
        con = connect(parquet_root=built_root, memory_limit="2GB", threads=2)
        try:
            build_aggregates_for_date(con, date="2026-01-15", out_root=built_root)
            res2 = build_aggregates_for_date(con, date="2026-01-15", out_root=built_root)
        finally:
            con.close()
        assert res2["skipped"] is True

    def test_force_rebuild(self, built_root: Path) -> None:
        con = connect(parquet_root=built_root, memory_limit="2GB", threads=2)
        try:
            build_aggregates_for_date(con, date="2026-01-15", out_root=built_root)
            res2 = build_aggregates_for_date(
                con, date="2026-01-15", out_root=built_root, force=True
            )
        finally:
            con.close()
        assert res2["skipped"] is False

    def test_empty_date_no_file(self, built_root: Path) -> None:
        con = connect(parquet_root=built_root, memory_limit="2GB", threads=2)
        try:
            res = build_aggregates_for_date(con, date="2099-12-31", out_root=built_root)
        finally:
            con.close()
        assert res["skipped"] is True
        assert res["daily_metrics_rows"] == 0
        assert not daily_metrics_path(built_root, "2099-12-31").is_file()

    def test_build_all_from_manifest(self, built_root: Path) -> None:
        results = build_all_aggregates(built_root, memory_limit="2GB")
        assert len(results) == 1
        assert results[0]["date"] == "2026-01-15"
        assert daily_metrics_path(built_root, "2026-01-15").is_file()

    def test_large_order_cluster_agg_template(self, built_root: Path) -> None:
        con = connect(parquet_root=built_root, memory_limit="2GB", threads=2)
        try:
            build_aggregates_for_date(con, date="2026-01-15", out_root=built_root)
        finally:
            con.close()
        con = connect(parquet_root=built_root, memory_limit="2GB", threads=2)
        try:
            agg_rows = run_template(con, "large_order_cluster_agg")
            raw_rows = run_template(con, "large_order_cluster")
        finally:
            con.close()
        assert isinstance(agg_rows, list)
        # Same HAVING threshold → same cluster cardinality (column order differs).
        assert len(agg_rows) == len(raw_rows)
