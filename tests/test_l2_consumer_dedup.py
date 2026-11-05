"""BT-03 consumer exact-dup collapse: audit helper + deduped persisted aggregates.

Offline fixtures mirror the two vendor patterns that gap-free (#526) already
tolerates in the lake:
  - 600421-style byte-identical close-print double-write (collapse for qty/amt),
  - 688660/688633-style same-TranID distinct rows (STAR after-hours id reuse — keep).
ETL must keep landing both kinds; only consumer aggregation collapses exact dups.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from l2_analytics.aggregates import build_aggregates_for_date
from l2_analytics.consumer_dedup import (
    audit_main_dup_stats,
    exact_deduped_main_sql,
    register_dedup_views,
)
from l2_analytics.db import connect
from l2_analytics.etl_day import etl_one_day

CSV_HEADER = (
    "TranID,Time,Price,Volume,SaleOrderVolume,BuyOrderVolume,"
    "Type,SaleOrderID,SaleOrderPrice,BuyOrderID,BuyOrderPrice"
)

# Exact-dup print (600421-style) placed inside continuous_pm so the persisted
# aggregates (stock + continuous 口径) actually see it. Hand-computed deduped
# expectations: volume 1000 + 20000 = 21000 (close counted ONCE, not 2x),
# ticks 2 (not 3), notional 99000 + 2020000 = 2119000.
_DUP_SOID = 500
_DUP_PRINT = (2, "14:50:00", 101.0, 20000, "B", _DUP_SOID)
_DUP_DAY_MAIN_ROWS = 3  # 1 continuous row + close print written twice

# Same-TranID distinct rows (688660-style) inside continuous_am: the last id
# reused by three distinct prints. Deduped expectations: all 4 rows kept ->
# volume 300 + 100 + 150 + 194 = 744, ticks 4; the multi group holds 3 rows.
_MULTI_SOID = 700
_MULTI_ROWS = [
    (1, "09:30:00", 11.75, 300, "B", _MULTI_SOID),
    (2, "10:31:00", 11.80, 100, "S", _MULTI_SOID),
    (2, "10:45:00", 11.85, 150, "S", _MULTI_SOID),
    (2, "10:50:00", 11.75, 194, "B", _MULTI_SOID),
]


def _write_csv(directory: Path, code: str, rows: list[tuple]) -> Path:
    path = directory / f"{code}.csv"
    lines = [CSV_HEADER]
    for r in rows:
        lines.append(",".join(str(v) for v in r))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _row(
    tran_id: int,
    time: str,
    price: float,
    vol: int,
    typ: str,
    soid: int = 1,
    boid: int = 2,
) -> tuple:
    return (tran_id, time, price, vol, vol // 2, vol // 2, typ, soid, price, boid, price)


def _etl_day(day_rows: dict[str, list[tuple]], tmp_path: Path, date: str) -> Path:
    """ETL a synthetic day with gap-free ON: both dup patterns stay tolerated."""
    day = tmp_path / date
    day.mkdir()
    for code, rows in day_rows.items():
        _write_csv(day, code, [_row(*r) for r in rows])
    out = tmp_path / f"l2_parquet_{date}"
    result = etl_one_day(day, out_root=out, validate_gap_free=True)
    assert result.gap_free_ok, result.gap_free_failures
    return out


def _connect(root: Path):
    return connect(parquet_root=root, memory_limit="2GB", threads=2)


def _build_and_reconnect(root: Path, date: str):
    con = _connect(root)
    try:
        res = build_aggregates_for_date(con, date=date, out_root=root)
        assert res["skipped"] is False
    finally:
        con.close()
    return _connect(root)


@pytest.fixture()
def dup_close_root(tmp_path: Path) -> Path:
    return _etl_day(
        {"600421": [(1, "09:31:00", 99.0, 1000, "S", _DUP_SOID), _DUP_PRINT, _DUP_PRINT]},
        tmp_path,
        "2026-03-02",
    )


@pytest.fixture()
def multi_tran_id_root(tmp_path: Path) -> Path:
    return _etl_day({"688660": _MULTI_ROWS}, tmp_path, "2026-03-03")


@pytest.fixture()
def mixed_root(tmp_path: Path) -> Path:
    return _etl_day(
        {
            "600421": [(1, "09:31:00", 99.0, 1000, "S", _DUP_SOID), _DUP_PRINT, _DUP_PRINT],
            "688660": _MULTI_ROWS,
        },
        tmp_path,
        "2026-03-04",
    )


class TestExactDupDoubleWrite:
    def test_etl_lands_both_rows_audit_flags_surplus(self, dup_close_root: Path) -> None:
        con = _connect(dup_close_root)
        try:
            raw_group = con.execute(
                "SELECT count(*) FROM l2_main WHERE stock_code = '600421.SH' AND TranID = 2"
            ).fetchone()[0]
            stats = audit_main_dup_stats(con)
        finally:
            con.close()
        assert raw_group == _DUP_DAY_MAIN_ROWS - 1  # both dup rows landed in parquet
        assert stats["rows_raw"] == _DUP_DAY_MAIN_ROWS
        assert stats["exact_dup_extra_rows"] == 1
        assert stats["rows_exact_unique"] == (stats["rows_raw"] - stats["exact_dup_extra_rows"])
        assert stats["same_tran_id_groups"] == 0

    def test_daily_metrics_count_close_once(self, dup_close_root: Path) -> None:
        con = _build_and_reconnect(dup_close_root, "2026-03-02")
        try:
            volume, ticks, vwap, net_inflow = con.execute(
                "SELECT volume, ticks, vwap, net_inflow FROM l2_daily_metrics "
                "WHERE stock_code = '600421.SH'"
            ).fetchone()
        finally:
            con.close()
        assert int(volume) == 21000  # deduped: 1000 + 20000 (close once, not 41000)
        assert int(ticks) == 2  # not 3
        assert float(vwap) == pytest.approx(2_119_000 / 21_000)
        assert float(net_inflow) == pytest.approx(-99_000 + 2_020_000)

    def test_cluster_agg_collapses_order_and_main_dups(self, dup_close_root: Path) -> None:
        # Raw join would fan the double-written print out 2x2 (dup order rows x
        # dup main rows): fill_count 3 / volume 41000. Deduped: 2 / 21000.
        con = _build_and_reconnect(dup_close_root, "2026-03-02")
        try:
            rows = con.execute(
                "SELECT SaleOrderID, fill_count, total_volume, total_notional FROM l2_cluster_agg"
            ).fetchall()
        finally:
            con.close()
        assert rows == [(_DUP_SOID, 2, 21000, 2_119_000)]


class TestSameTranIdMultiRows:
    def test_audit_reports_multi_distinct_group(self, multi_tran_id_root: Path) -> None:
        con = _connect(multi_tran_id_root)
        try:
            stats = audit_main_dup_stats(con)
        finally:
            con.close()
        assert stats["rows_raw"] == 4
        assert stats["rows_exact_unique"] == 4  # all distinct-content rows kept
        assert stats["exact_dup_extra_rows"] == 0
        assert stats["same_tran_id_groups"] == 1
        assert stats["same_tran_id_multi_rows"] == 3

    def test_daily_metrics_sum_all_distinct_rows(self, multi_tran_id_root: Path) -> None:
        # Collapsing to one row per TranID would give volume 544 / ticks 3.
        con = _build_and_reconnect(multi_tran_id_root, "2026-03-03")
        try:
            volume, ticks = con.execute(
                "SELECT volume, ticks FROM l2_daily_metrics WHERE stock_code = '688660.SH'"
            ).fetchone()
        finally:
            con.close()
        assert int(volume) == 744  # 300 + 100 + 150 + 194
        assert int(ticks) == 4


class TestMixedDay:
    def test_audit_counters_stable(self, mixed_root: Path) -> None:
        con = _connect(mixed_root)
        try:
            stats = audit_main_dup_stats(con)
            stats_repeat = audit_main_dup_stats(con)
            stats_dated = audit_main_dup_stats(con, date="2026-03-04")
        finally:
            con.close()
        assert stats == stats_repeat  # deterministic across runs
        assert stats_dated == stats  # single-day root: date filter is a no-op
        assert stats == {
            "rows_raw": 7,
            "rows_exact_unique": 6,
            "exact_dup_extra_rows": 1,
            "same_tran_id_groups": 1,
            "same_tran_id_multi_rows": 3,
        }

    def test_mixed_day_aggregates(self, mixed_root: Path) -> None:
        con = _build_and_reconnect(mixed_root, "2026-03-04")
        try:
            rows = con.execute(
                "SELECT stock_code, volume, ticks FROM l2_daily_metrics ORDER BY stock_code"
            ).fetchall()
        finally:
            con.close()
        assert rows == [("600421.SH", 21000, 2), ("688660.SH", 744, 4)]


class TestHelpers:
    def test_register_dedup_views(self, mixed_root: Path) -> None:
        con = _connect(mixed_root)
        try:
            register_dedup_views(con)
            counts = {
                name: con.execute(f"SELECT count(*) FROM {name}").fetchone()[0]
                for name in ("l2_main", "l2_main_exact_dedup", "l2_order", "l2_order_exact_dedup")
            }
        finally:
            con.close()
        # Raw views keep every source row; dedup views drop only the 1 exact dup.
        assert counts == {
            "l2_main": 7,
            "l2_main_exact_dedup": 6,
            "l2_order": 7,
            "l2_order_exact_dedup": 6,
        }

    def test_sql_fragment_alias_and_where(self, mixed_root: Path) -> None:
        con = _connect(mixed_root)
        try:
            n = con.execute(
                f"SELECT count(*) FROM {exact_deduped_main_sql('x')} "
                "WHERE x.stock_code = '688660.SH'"
            ).fetchone()[0]
            # extra_where lives inside the subquery -> unqualified column names.
            n_dated = con.execute(
                f"SELECT count(*) FROM {exact_deduped_main_sql('x', extra_where='date = CAST($d AS DATE)')}",
                {"d": "2026-03-04"},
            ).fetchone()[0]
        finally:
            con.close()
        assert n == 4  # all same-TranID distinct rows survive the exact collapse
        assert n_dated == 6


@pytest.fixture(autouse=True)
def require_optional_infra():
    pytest.importorskip("myquant_infra.l2.ingest")
