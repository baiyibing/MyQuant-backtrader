"""Unit tests for l2_analytics.templates (loading, injection, execution)."""

from __future__ import annotations

from pathlib import Path

import pytest

from l2_analytics.templates import TEMPLATE_FILES, load_template, run_template

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


def _row(tran_id: int, time: str, price: float, vol: int, typ: str) -> tuple:
    return (tran_id, time, price, vol, vol // 2, vol // 2, typ, 1, price, 2, price)


@pytest.fixture(scope="module")
def l2_con(tmp_path_factory: pytest.TempPathFactory):
    """DuckDB connection with l2_main/l2_order views over synthetic parquet."""
    from l2_analytics.db import connect
    from l2_analytics.etl_day import etl_one_day

    day = tmp_path_factory.mktemp("src") / "2026-01-15"
    day.mkdir()
    _write_csv(day, "000001", [
        _row(1, "09:25:00", 10.50, 1000, "B"),
        _row(2, "09:30:01", 10.52, 200, "S"),
        _row(3, "09:30:05", 10.55, 300, "B"),
        _row(4, "11:00:00", 10.58, 400, "B"),
        _row(5, "13:05:00", 10.60, 500, "S"),
        _row(6, "14:57:00", 10.62, 600, "B"),
    ])
    _write_csv(day, "600000", [
        _row(1, "09:30:00", 8.00, 2000, "B"),
        _row(2, "10:00:00", 8.05, 1500, "S"),
        _row(3, "14:00:00", 8.10, 3000, "B"),
    ])
    out = tmp_path_factory.mktemp("l2_parquet")
    etl_one_day(day, out_root=out, validate_gap_free=False)
    con = connect(parquet_root=out, memory_limit="2GB", threads=2)
    yield con
    con.close()


class TestTemplateLoading:
    def test_all_templates_load(self) -> None:
        for name in TEMPLATE_FILES:
            sql = load_template(name)
            assert "stock_code" in sql, f"{name}: missing stock_code"
            assert "date" in sql, f"{name}: missing date"

    def test_unknown_template_raises(self) -> None:
        with pytest.raises(KeyError, match="unknown template"):
            load_template("nonexistent")

    def test_template_count(self) -> None:
        assert len(TEMPLATE_FILES) == 12
        assert "buy_order_cluster" in TEMPLATE_FILES
        assert "large_order_cluster_agg" in TEMPLATE_FILES
        assert "vwap_adj" in TEMPLATE_FILES
        assert "limit_up_down_true" in TEMPLATE_FILES


class TestTemplateExecution:
    def test_vwap(self, l2_con) -> None:
        rows = run_template(l2_con, "vwap")
        assert len(rows) >= 2
        for row in rows:
            assert row[2] > 0  # vwap positive

    def test_net_inflow(self, l2_con) -> None:
        rows = run_template(l2_con, "net_inflow")
        assert len(rows) >= 2

    def test_tick_speed(self, l2_con) -> None:
        rows = run_template(l2_con, "tick_speed")
        assert len(rows) >= 1

    def test_session_distribution(self, l2_con) -> None:
        rows = run_template(l2_con, "session_distribution")
        assert len(rows) >= 1
        sessions = {row[2] for row in rows}
        assert "continuous_am" in sessions

    def test_limit_up_down(self, l2_con) -> None:
        rows = run_template(l2_con, "limit_up_down")
        assert len(rows) >= 2

    def test_opening_auction(self, l2_con) -> None:
        rows = run_template(l2_con, "opening_auction")
        assert len(rows) >= 2

    def test_price_impact_no_crash(self, l2_con) -> None:
        rows = run_template(l2_con, "price_impact")
        assert isinstance(rows, list)

    def test_large_order_cluster_no_crash(self, l2_con) -> None:
        rows = run_template(l2_con, "large_order_cluster")
        assert isinstance(rows, list)

    def test_buy_order_cluster_no_crash(self, l2_con) -> None:
        rows = run_template(l2_con, "buy_order_cluster")
        assert isinstance(rows, list)
        sql = load_template("buy_order_cluster")
        assert "BuyOrderID" in sql
        assert "GROUP BY o.stock_code, o.date, o.BuyOrderID" in sql

    def test_extra_where_injection(self, l2_con) -> None:
        rows = run_template(l2_con, "vwap", extra_where="stock_code = '000001.SZ'")
        assert len(rows) >= 1
        assert all(r[0] == "000001.SZ" for r in rows)

    def test_limit_injection(self, l2_con) -> None:
        rows = run_template(l2_con, "vwap", limit=1)
        assert len(rows) == 1

    def test_order_by_injection(self, l2_con) -> None:
        rows = run_template(l2_con, "vwap", order_by="vwap DESC")
        if len(rows) >= 2:
            assert rows[0][2] >= rows[1][2]

    def test_params_binding(self, l2_con) -> None:
        rows = run_template(
            l2_con, "vwap", extra_where="stock_code = $code", params={"code": "000001.SZ"}
        )
        assert len(rows) >= 1
        assert all(r[0] == "000001.SZ" for r in rows)

    def test_params_binding_matches_literal(self, l2_con) -> None:
        bound = run_template(
            l2_con, "vwap", extra_where="stock_code = $code", params={"code": "000001.SZ"}
        )
        literal = run_template(l2_con, "vwap", extra_where="stock_code = '000001.SZ'")
        assert bound == literal

    def test_order_by_rejects_injection(self, l2_con) -> None:
        with pytest.raises(ValueError, match="invalid order_by"):
            run_template(l2_con, "vwap", order_by="vwap; DROP TABLE l2_main")

    def test_order_by_rejects_qualified(self, l2_con) -> None:
        with pytest.raises(ValueError, match="invalid order_by"):
            run_template(l2_con, "vwap", order_by="l2_main.vwap")

    def test_order_by_multi_column_ok(self, l2_con) -> None:
        rows = run_template(l2_con, "vwap", order_by="stock_code ASC, vwap DESC")
        assert isinstance(rows, list)


class TestAdjAndTrueLimitTemplates:
    def test_vwap_adj_and_true_limit(self, tmp_path: Path) -> None:
        import duckdb

        from l2_analytics.db import connect
        from l2_analytics.etl_day import etl_one_day

        day = tmp_path / "2026-01-15"
        day.mkdir()
        _write_csv(day, "000001", [
            _row(1, "09:30:00", 11.0, 1000, "B"),  # at +10% of prev 10.0
            _row(2, "10:00:00", 10.5, 500, "S"),
        ])
        out = tmp_path / "l2_parquet"
        etl_one_day(day, out_root=out, validate_gap_free=False)

        adj = tmp_path / "adj_factor.parquet"
        con = duckdb.connect(database=":memory:")
        try:
            con.execute(
                f"""
                COPY (
                  SELECT * FROM (VALUES
                    (DATE '2026-01-14', '000001.SZ', 10.0, 10.0, 1.0, NULL),
                    (DATE '2026-01-15', '000001.SZ', 11.0, 11.0, 1.0, NULL)
                  ) AS t(date, stock_code, close_front, close_none, cumulative_adj_factor, adj_factor_back)
                ) TO '{adj.as_posix()}' (FORMAT PARQUET)
                """
            )
        finally:
            con.close()

        qcon = connect(
            parquet_root=out, memory_limit="2GB", threads=2, adj_factor_path=adj
        )
        try:
            adj_rows = run_template(qcon, "vwap_adj")
            assert len(adj_rows) >= 1
            assert adj_rows[0][3] is not None  # vwap_adj
            true_rows = run_template(qcon, "limit_up_down_true")
            assert any(r[0] == "000001.SZ" and int(r[11]) == 1 for r in true_rows)
        finally:
            qcon.close()

    def test_prev_close_d_domain_on_ex_div(self, tmp_path: Path) -> None:
        """Ex-div: raw LAG(close_none) is wrong; d-domain = prev*cum[D-1]/cum[D]."""
        import duckdb

        from l2_analytics.db import connect

        # Minimal parquet root so connect() succeeds (views only need adj path here).
        root = tmp_path / "l2_parquet"
        day = root / "date=2026-01-15"
        day.mkdir(parents=True)
        # Tiny empty-ish main/order so globs resolve (header-only via duckdb write).
        con = duckdb.connect(database=":memory:")
        try:
            con.execute(
                f"""
                COPY (
                  SELECT
                    CAST('000001.SZ' AS VARCHAR) AS stock_code,
                    DATE '2026-01-15' AS date,
                    1::BIGINT AS TranID,
                    '09:30:00'::VARCHAR AS Time,
                    9.90::DECIMAL(10,3) AS Price,
                    100::BIGINT AS Volume,
                    'B'::VARCHAR AS Type,
                    'stock'::VARCHAR AS instrument_type,
                    'continuous_am'::VARCHAR AS session
                ) TO '{(day / "main.parquet").as_posix()}' (FORMAT PARQUET)
                """
            )
            con.execute(
                f"""
                COPY (
                  SELECT
                    CAST('000001.SZ' AS VARCHAR) AS stock_code,
                    DATE '2026-01-15' AS date,
                    1::BIGINT AS TranID,
                    1::BIGINT AS SaleOrderID,
                    9.90::DECIMAL(18,3) AS SaleOrderPrice,
                    2::BIGINT AS BuyOrderID,
                    9.90::DECIMAL(18,3) AS BuyOrderPrice
                ) TO '{(day / "order.parquet").as_posix()}' (FORMAT PARQUET)
                """
            )
            adj = tmp_path / "adj_factor.parquet"
            # D-1: none=10, cum=1; D ex-div: none=9, front=10 → cum=10/9
            con.execute(
                f"""
                COPY (
                  SELECT * FROM (VALUES
                    (DATE '2026-01-14', '000001.SZ', 10.0, 10.0, 1.0, NULL),
                    (DATE '2026-01-15', '000001.SZ', 10.0, 9.0, 10.0/9.0, NULL)
                  ) AS t(date, stock_code, close_front, close_none, cumulative_adj_factor, adj_factor_back)
                ) TO '{adj.as_posix()}' (FORMAT PARQUET)
                """
            )
        finally:
            con.close()

        qcon = connect(
            parquet_root=root, memory_limit="2GB", threads=2, adj_factor_path=adj
        )
        try:
            row = qcon.execute(
                """
                SELECT prev_close, prev_close_d_domain
                FROM l2_prev_close
                WHERE stock_code = '000001.SZ' AND date = DATE '2026-01-15'
                """
            ).fetchone()
            assert row is not None
            prev_raw, prev_d = float(row[0]), float(row[1])
            assert prev_raw == pytest.approx(10.0)
            assert prev_d == pytest.approx(9.0)
            true_rows = run_template(qcon, "limit_up_down_true")
            # Limit-up of d-domain 9.0 * 1.1 = 9.90 → tick at 9.90 hits.
            hit = [r for r in true_rows if r[0] == "000001.SZ"]
            assert hit and int(hit[0][11]) == 1
            assert float(hit[0][2]) == pytest.approx(9.0)  # prev_close used by template
        finally:
            qcon.close()

