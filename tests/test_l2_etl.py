"""Unit tests for l2_analytics.etl_day using synthetic CSV fixtures."""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pytest

from l2_analytics.etl_day import etl_one_day

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


def _row(tran_id: int, time: str, price: float, vol: int, typ: str, soid: int = 1, boid: int = 2) -> tuple:
    return (tran_id, time, price, vol, vol // 2, vol // 2, typ, soid, price, boid, price)


@pytest.fixture()
def synthetic_day(tmp_path: Path) -> Path:
    day = tmp_path / "2026-01-15"
    day.mkdir()
    _write_csv(day, "000001", [
        _row(1, "09:25:00", 10.50, 1000, "B"),
        _row(2, "09:30:01", 10.52, 200, "S"),
        _row(3, "09:30:05", 10.55, 300, "B"),
        _row(4, "14:57:00", 10.60, 500, "B"),
    ])
    _write_csv(day, "510300", [
        _row(1, "09:30:00", 4.20, 5000, "B"),
        _row(2, "10:00:00", 4.21, 3000, "S"),
    ])
    _write_csv(day, "113050", [
        _row(1, "09:30:00", 120.50, 100, "B"),
    ])
    return day


def _read_parquet(path: str) -> list[tuple]:
    con = duckdb.connect(database=":memory:")
    try:
        return con.execute(f"SELECT * FROM read_parquet('{Path(path).as_posix()}')").fetchall()
    finally:
        con.close()


def _query_parquet(path: str, sql: str) -> list[tuple]:
    con = duckdb.connect(database=":memory:")
    try:
        return con.execute(sql.replace("__PQ__", Path(path).as_posix())).fetchall()
    finally:
        con.close()


class TestEtlOneDay:
    def test_basic_etl(self, synthetic_day: Path, tmp_path: Path) -> None:
        out = tmp_path / "out"
        r = etl_one_day(synthetic_day, out_root=out, validate_gap_free=False)
        assert r.rows_main == 7
        assert r.rows_order == 7
        assert not r.skipped
        hive_main = out / f"date={synthetic_day.name}" / "main.parquet"
        hive_order = out / f"date={synthetic_day.name}" / "order.parquet"
        assert hive_main.is_file()
        assert hive_order.is_file()
        assert not list(out.glob(f"{synthetic_day.name}.part-*.main.parquet"))
        assert r.csv_files == 3
        assert r.empty_files == 0
        assert r.profile.get("peak_rss_bytes") is not None
        assert r.profile.get("peak_rss_gb") is not None
        assert r.profile.get("peak_rss_chunk_bytes") is not None
        assert r.profile.get("peak_rss_compact_bytes") is not None
        assert "peak_temp_bytes" in r.profile
        assert r.profile.get("temp_directory")

    def test_instrument_type_injection(self, synthetic_day: Path, tmp_path: Path) -> None:
        out = tmp_path / "out"
        r = etl_one_day(synthetic_day, out_root=out, validate_gap_free=False)
        rows = _query_parquet(
            r.main_parquet,
            "SELECT DISTINCT instrument_type FROM read_parquet('__PQ__') ORDER BY 1",
        )
        types = {row[0] for row in rows}
        assert types == {"stock", "etf", "cvt_bond"}

    def test_canonical_symbol(self, synthetic_day: Path, tmp_path: Path) -> None:
        out = tmp_path / "out"
        r = etl_one_day(synthetic_day, out_root=out, validate_gap_free=False)
        rows = _query_parquet(
            r.main_parquet,
            "SELECT DISTINCT stock_code FROM read_parquet('__PQ__') ORDER BY 1",
        )
        codes = {row[0] for row in rows}
        assert codes == {"000001.SZ", "510300.SH", "113050.SH"}

    def test_session_buckets(self, synthetic_day: Path, tmp_path: Path) -> None:
        out = tmp_path / "out"
        r = etl_one_day(synthetic_day, out_root=out, validate_gap_free=False)
        rows = _query_parquet(
            r.main_parquet,
            "SELECT stock_code, Time, session FROM read_parquet('__PQ__') "
            "WHERE stock_code = '000001.SZ' ORDER BY TranID",
        )
        sessions = {row[1]: row[2] for row in rows}
        assert sessions["09:25:00"] == "pre_open"
        assert sessions["09:30:01"] == "continuous_am"
        assert sessions["09:30:05"] == "continuous_am"
        assert sessions["14:57:00"] == "close_auction"

    def test_idempotent_skip(self, synthetic_day: Path, tmp_path: Path) -> None:
        out = tmp_path / "out"
        etl_one_day(synthetic_day, out_root=out, validate_gap_free=False)
        r2 = etl_one_day(synthetic_day, out_root=out, validate_gap_free=False)
        assert r2.skipped is True
        assert "manifest" in r2.notes

    def test_force_reprocess(self, synthetic_day: Path, tmp_path: Path) -> None:
        out = tmp_path / "out"
        etl_one_day(synthetic_day, out_root=out, validate_gap_free=False)
        r2 = etl_one_day(synthetic_day, out_root=out, validate_gap_free=False, force=True)
        assert r2.skipped is False

    def test_empty_csv_tolerated(self, tmp_path: Path) -> None:
        day = tmp_path / "2026-01-16"
        day.mkdir()
        (day / "000002.csv").write_text(CSV_HEADER + "\n", encoding="utf-8")
        _write_csv(day, "000001", [_row(1, "09:30:00", 10.0, 100, "B")])
        r = etl_one_day(day, out_root=tmp_path / "out", validate_gap_free=False)
        assert r.empty_files == 1
        assert r.rows_main == 1

    def test_empty_day_all_header_only(self, tmp_path: Path) -> None:
        """All CSVs header-only -> 0 rows, no raise, empty manifest parts."""
        day = tmp_path / "2026-01-19"
        day.mkdir()
        (day / "000001.csv").write_text(CSV_HEADER + "\n", encoding="utf-8")
        (day / "000002.csv").write_text(CSV_HEADER + "\n", encoding="utf-8")
        out = tmp_path / "out"
        r = etl_one_day(day, out_root=out, validate_gap_free=False)
        assert r.rows_main == 0
        assert r.rows_order == 0
        assert r.skipped is False
        assert r.empty_files == 2
        assert "empty day" in r.notes
        assert not (out / f"date={day.name}" / "main.parquet").exists()
        assert not list(out.glob(f"{day.name}.part-*.main.parquet"))
        rec = json.loads((out / "_manifest.jsonl").read_text(encoding="utf-8").strip())
        assert rec["rows_main"] == 0
        assert rec["main_parts"] == []
        assert rec["order_parts"] == []

    def test_empty_day_idempotent_skip(self, tmp_path: Path) -> None:
        day = tmp_path / "2026-01-20"
        day.mkdir()
        (day / "000001.csv").write_text(CSV_HEADER + "\n", encoding="utf-8")
        out = tmp_path / "out"
        etl_one_day(day, out_root=out, validate_gap_free=False)
        r2 = etl_one_day(day, out_root=out, validate_gap_free=False)
        assert r2.skipped is True
        assert r2.rows_main == 0
        assert "empty day" in r2.notes

    def test_no_csv_at_all_raises(self, tmp_path: Path) -> None:
        day = tmp_path / "2026-01-21"
        day.mkdir()
        with pytest.raises(FileNotFoundError, match="no .*csv"):
            etl_one_day(day, out_root=tmp_path / "out", validate_gap_free=False)


    def test_gap_free_validation(self, tmp_path: Path) -> None:
        day = tmp_path / "2026-01-17"
        day.mkdir()
        _write_csv(day, "000001", [
            _row(1, "09:30:00", 10.0, 100, "B"),
            _row(3, "09:30:01", 10.1, 100, "S"),
        ])
        r = etl_one_day(day, out_root=tmp_path / "out", validate_gap_free=True, gap_free_sample=0)
        assert r.gap_free_ok is False
        assert len(r.gap_free_failures) > 0

    def test_invalid_dir_name_raises(self, tmp_path: Path) -> None:
        bad = tmp_path / "not-a-date"
        bad.mkdir()
        with pytest.raises(ValueError, match="YYYY-MM-DD"):
            etl_one_day(bad, out_root=tmp_path / "out")

    def test_manifest_written(self, synthetic_day: Path, tmp_path: Path) -> None:
        out = tmp_path / "out"
        r = etl_one_day(synthetic_day, out_root=out, validate_gap_free=False)
        manifest = out / "_manifest.jsonl"
        assert manifest.exists()
        rec = json.loads(manifest.read_text(encoding="utf-8").strip())
        assert rec["date"] == "2026-01-15"
        assert rec["rows_main"] == 7
        assert len(rec["files"]) == 3
        assert rec["main_parts"] == [f"date={synthetic_day.name}/main.parquet"]
        assert rec["order_parts"] == [f"date={synthetic_day.name}/order.parquet"]
        for name in rec["main_parts"] + rec["order_parts"]:
            assert (out / name).exists()

    def test_compress_ratio_positive(self, synthetic_day: Path, tmp_path: Path) -> None:
        out = tmp_path / "out"
        r = etl_one_day(synthetic_day, out_root=out, validate_gap_free=False)
        assert r.compress_ratio > 0
        assert r.source_csv_bytes > 0

    def test_main_order_columns(self, synthetic_day: Path, tmp_path: Path) -> None:
        out = tmp_path / "out"
        r = etl_one_day(synthetic_day, out_root=out, validate_gap_free=False)
        con = duckdb.connect(database=":memory:")
        try:
            main_cols = [
                row[0]
                for row in con.execute(
                    f"SELECT column_name FROM (DESCRIBE SELECT * FROM read_parquet('{Path(r.main_parquet).as_posix()}'))"
                ).fetchall()
            ]
            order_cols = [
                row[0]
                for row in con.execute(
                    f"SELECT column_name FROM (DESCRIBE SELECT * FROM read_parquet('{Path(r.order_parquet).as_posix()}'))"
                ).fetchall()
            ]
        finally:
            con.close()
        assert "stock_code" in main_cols
        assert "session" in main_cols
        assert "instrument_type" in main_cols
        assert "SaleOrderID" in order_cols
        assert "BuyOrderPrice" in order_cols
        assert "SaleOrderID" not in main_cols

    def test_sentinel_price_try_cast(self, tmp_path: Path) -> None:
        """评审 #2: 哨兵/离群 Price (>DECIMAL(10,3) max 9,999,999.999) 经 TRY_CAST → NULL，
        不崩 ETL、行保留（gap-free 不变）、NULL 被 SUM 自然排除。"""
        day = tmp_path / "2026-01-18"
        day.mkdir()
        _write_csv(day, "000001", [
            _row(1, "09:30:00", 10.0, 100, "B"),
            _row(2, "09:30:01", 40_000_000.0, 200, "S"),  # sentinel 4e7 > DECIMAL(10,3)
            _row(3, "09:30:02", 10.1, 100, "B"),
        ])
        r = etl_one_day(day, out_root=tmp_path / "out", validate_gap_free=False)
        assert r.rows_main == 3  # 行保留（TRY_CAST 不丢行，gap-free 不变）
        prices = [
            row[0]
            for row in _query_parquet(
                r.main_parquet, "SELECT Price FROM read_parquet('__PQ__') ORDER BY TranID"
            )
        ]
        assert float(prices[0]) == pytest.approx(10.0)
        assert prices[1] is None  # sentinel → NULL（旧 CAST 会硬崩整 chunk）
        assert float(prices[2]) == pytest.approx(10.1)


class TestManifestContentHash:
    def test_same_size_different_content_hashes_differ(self, tmp_path: Path) -> None:
        from l2_analytics.etl_day import _file_fp

        a = tmp_path / "a.csv"
        b = tmp_path / "b.csv"
        a.write_text("x" * 200, encoding="utf-8")
        b.write_text("y" * 200, encoding="utf-8")
        fa, fb = _file_fp(a), _file_fp(b)
        assert fa["size"] == fb["size"]
        assert fa["content_hash"] != fb["content_hash"]

    def test_content_change_same_size_breaks_idempotent_skip(
        self, synthetic_day: Path, tmp_path: Path
    ) -> None:
        out = tmp_path / "out"
        etl_one_day(synthetic_day, out_root=out, validate_gap_free=False)
        target = synthetic_day / "000001.csv"
        raw = bytearray(target.read_bytes())
        # Flip one ASCII digit somewhere in the body without changing length.
        flipped = False
        for i, b in enumerate(raw):
            if 0x30 <= b <= 0x39:  # '0'-'9'
                raw[i] = 0x31 if b != 0x31 else 0x32
                flipped = True
                break
        assert flipped
        target.write_bytes(bytes(raw))
        r2 = etl_one_day(synthetic_day, out_root=out, validate_gap_free=False)
        assert r2.skipped is False

    def test_manifest_records_content_hash(self, synthetic_day: Path, tmp_path: Path) -> None:
        out = tmp_path / "out"
        etl_one_day(synthetic_day, out_root=out, validate_gap_free=False)
        rec = json.loads((out / "_manifest.jsonl").read_text(encoding="utf-8").strip())
        assert all("content_hash" in f and f["content_hash"] for f in rec["files"])


class TestGapFreeStratified:
    def test_stratified_includes_heaviest(self, tmp_path: Path) -> None:
        from l2_analytics.etl_day import _select_gap_free_targets

        files = []
        sizes: dict[str, int] = {}
        for i, name in enumerate(["000001.csv", "000002.csv", "999999.csv", "600000.csv"]):
            p = tmp_path / name
            payload = ("row\n" * (10 ** (i + 1))).encode("utf-8")
            p.write_bytes(payload)
            files.append(p)
            sizes[str(p)] = len(payload)
        picked = _select_gap_free_targets(files, sample=2, size_by_path=sizes)
        assert len(picked) == 2
        # Heaviest must be included (999999 written with most rows in this loop).
        assert any(p.name == "600000.csv" for p in picked) or any(
            p.name == "999999.csv" for p in picked
        )
        heaviest = max(files, key=lambda p: sizes[str(p)])
        assert heaviest in picked
