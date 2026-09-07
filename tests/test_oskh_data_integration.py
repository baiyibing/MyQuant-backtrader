"""oskh_data 集成测试 — smoke tests for core modules."""
from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import duckdb
import pytest

pytestmark = pytest.mark.production


class TestStockDataReader:
    """StockDataReader parquet mode integration."""

    def test_import_and_default_mode(self):
        from oskh_data import StockDataReader

        reader = StockDataReader(mode="parquet")
        assert reader._mode == "parquet"

    def test_read_real_stock_parquet(self):
        """Read a known stock — verify it returns valid OHLCV data."""
        from oskh_data.reader import StockDataReader

        reader = StockDataReader(mode="parquet")
        df = reader.read_stock(
            "000001.SZ",
            start_time="20250101",
            end_time="20250131",
            period="1d",
            adjust_type="none",
        )
        if df is not None:
            assert not df.empty, "DataFrame should not be empty"
            assert "close" in df.columns
            assert "symbol" in df.columns
            assert df["close"].iloc[-1] > 0
        reader.close()

    def test_read_stock_with_as_of_date(self):
        """as_of_date 未实现时应显式报错，避免静默前视偏差。"""
        from oskh_data.reader import StockDataReader

        reader = StockDataReader(mode="parquet")
        with pytest.raises(NotImplementedError, match="as_of_date"):
            reader.read_stock(
                "000001.SZ",
                start_time="20250101",
                end_time="20250110",
                adjust_type="none",
                as_of_date="20250110",
            )
        reader.close()

    def test_context_manager(self):
        """StockDataReader supports 'with' statement."""
        from oskh_data.reader import StockDataReader

        with StockDataReader(mode="parquet") as reader:
            df = reader.read_stock("000001.SZ", start_time="20250101", end_time="20250105")
            if df is not None:
                assert "close" in df.columns
        # Context manager should close connections without error


class TestStockDataReaderDuckDB:
    """DuckDB persistent mode — requires stock_data.duckdb file."""

    @pytest.fixture
    def duckdb_path(self) -> str | None:
        candidates = [
            "stock_data/stock_data.duckdb",
            "stock_data/stock_data_none.duckdb",
            "stock_data/stock_data_front.duckdb",
        ]
        for c in candidates:
            if Path(c).exists():
                return c
        return None

    def test_duckdb_persistent_read(self, duckdb_path):
        if duckdb_path is None:
            pytest.skip("No DuckDB file found")
        from oskh_data.reader import StockDataReader

        reader = StockDataReader(mode="duckdb_persistent", db_path=duckdb_path)
        df = reader.read_stock("000001.SZ", start_time="20250101", end_time="20250110")
        if df is not None:
            assert not df.empty
            assert "close" in df.columns
        reader.close()

    def test_duckdb_persistent_missing_adjust_db_falls_back_to_parquet(self):
        from oskh_data.reader import StockDataReader

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stock_data = root / "stock_data"
            stock_data.mkdir(parents=True, exist_ok=True)
            front_db = root / "stock_data" / "stock_data_front.duckdb"
            con = duckdb.connect(str(front_db))
            con.execute("CREATE TABLE stock_data(symbol VARCHAR, time BIGINT, close DOUBLE)")
            con.close()

            reader = StockDataReader(mode="duckdb_persistent", project_root=str(root))
            # only front DB exists; requesting none must not silently use front DB
            con_none = reader._get_persistent_con("1d", "none")  # pylint: disable=protected-access
            assert con_none is None
            reader.close()


class TestFreshness:
    """Data freshness check."""

    def test_previous_trading_day(self):
        from oskh_data.freshness import get_previous_trading_day

        prev = get_previous_trading_day()
        assert len(prev) == 8
        assert prev.isdigit()

    def test_check_freshness_empty(self, monkeypatch):
        # Empty symbols still runs adj_factor table check (EDPC Phase 1).
        monkeypatch.setattr(
            "oskh_data.freshness._check_adj_factor_table_freshness",
            lambda _e: (True, "20260608"),
        )
        from oskh_data.freshness import check_data_freshness

        result = check_data_freshness([])
        assert result.ok
        assert result.action == "pass"

    def test_check_freshness_no_data(self):
        from oskh_data.freshness import check_data_freshness

        result = check_data_freshness(["999999.SZ"], expected_date="20000101")
        assert not result.ok or result.action in ("warn", "pass")


class TestAudit:
    """Backfill audit module."""

    def test_generate_run_id(self):
        from oskh_data.audit import generate_run_id

        rid = generate_run_id()
        assert rid.startswith("bf_")
        assert len(rid) > 10

    def test_record_cycle(self):
        from oskh_data.audit import (
            generate_run_id,
            get_failed_symbols,
            record_failure,
            record_run_end,
            record_run_start,
        )

        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "test_audit.db")
            rid = generate_run_id()

            record_run_start(rid, "1d", "none", "20200101", "20200131", 10, db_path=db)
            record_failure(rid, "000001.SZ", "silent_failure", "empty data", 1, db_path=db)
            record_failure(rid, "000002.SZ", "timeout", "connection lost", 0, db_path=db)

            ok = record_run_end(rid, 8, 2, db_path=db, min_success_rate=0.70)
            assert ok is True  # 80% > 70%

            failed = get_failed_symbols(rid, db_path=db)
            assert "000001.SZ" in failed
            assert "000002.SZ" in failed

    def test_abort_below_threshold(self):
        from oskh_data.audit import generate_run_id, record_run_end, record_run_start

        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "test_audit.db")
            rid = generate_run_id()
            record_run_start(rid, "1d", "none", "20200101", "20200131", 10, db_path=db)
            ok = record_run_end(rid, 5, 5, db_path=db, min_success_rate=0.70)
            assert ok is False  # 50% < 70%


class TestETFLimits:
    """ETF price limit rules."""

    def test_science_innovation_board(self):
        from oskh_data.etf_limits import get_etf_limit_pct

        assert get_etf_limit_pct("588000.SH") == 20.0

    def test_cross_border_no_limit(self):
        from oskh_data.etf_limits import get_etf_limit_pct

        assert get_etf_limit_pct("513100.SH") is None

    def test_default_10_pct(self):
        from oskh_data.etf_limits import get_etf_limit_pct

        assert get_etf_limit_pct("510050.SH") == 10.0

    def test_is_price_at_limit(self):
        from oskh_data.etf_limits import is_price_at_limit

        assert is_price_at_limit(11.0, 10.0, "510050.SH")  # 10% limit
        assert not is_price_at_limit(10.9, 10.0, "510050.SH")
        assert not is_price_at_limit(999.0, 10.0, "513100.SH")  # no limit

    def test_export_rules(self):
        from oskh_data.etf_limits import export_limit_rules

        rules = export_limit_rules()
        assert isinstance(rules, dict)
        assert "588" in rules
        assert "513" in rules


class TestDuckDBDailyBarsProxy:
    """DuckDBDailyBarsProxy routing logic."""

    def test_proxy_t_plus_0_routes_to_delegate(self):
        from common.integrations.duckdb_daily_bars_adapter import DuckDBDailyBarsProxy

        delegate = MagicMock()
        delegate.stock_daily_bars.return_value = {"ok": True, "source": "qmt"}
        proxy = DuckDBDailyBarsProxy(delegate)

        import datetime

        today = datetime.date.today().strftime("%Y%m%d")
        result = proxy.stock_daily_bars(
            symbol="000001.SZ", start_date=today, end_date=today,
            adjust="none", trace_id="test",
        )
        assert result["source"] == "qmt"
        delegate.stock_daily_bars.assert_called_once()

    def test_proxy_passthrough(self):
        from common.integrations.duckdb_daily_bars_adapter import DuckDBDailyBarsProxy

        delegate = MagicMock()
        delegate.full_tick.return_value = {"ok": True}
        proxy = DuckDBDailyBarsProxy(delegate)

        result = proxy.full_tick(symbols=["000001.SZ"], trace_id="test")
        assert result["ok"]
        delegate.full_tick.assert_called_once()

    def test_proxy_cfg_only_routes_to_duckdb(self):
        from common.integrations.duckdb_daily_bars_adapter import DuckDBDailyBarsProxy

        delegate = MagicMock()
        delegate.stock_daily_bars_cfg_only.return_value = {"ok": True, "source": "qmt"}
        proxy = DuckDBDailyBarsProxy(delegate)

        # T-1 date → tries DuckDB first, falls back to delegate if miss
        result = proxy.stock_daily_bars_cfg_only(
            symbol="000001.SZ", start_date="20200101", end_date="20200101",
            adjust="none", trace_id="test",
        )
        assert result["ok"]


class TestPeriodSchema:
    """Local period helpers (no QMT download)."""

    def test_import(self):
        from oskh_data import StockDataManager

        assert StockDataManager.validate_period("1d") is True
        assert StockDataManager.is_minute_period("1d") is False
        assert StockDataManager.is_minute_period("1m") is True

    def test_period_data_manager_validate(self):
        from oskh_data.period_schema import PeriodDataManager

        ok, msg = PeriodDataManager.validate_time_range("1d", "20200101", "20201231")
        assert ok
        assert "有效" in msg

        ok2, _ = PeriodDataManager.validate_time_range("1d", "20201231", "20200101")
        assert not ok2


class TestCachePort:
    """Redis cache port — fail-open when Redis unavailable."""

    def test_cache_graceful_degradation(self):
        from oskh_data.cache_port import (
            get_current_run_id,
            get_daily_bars_cached,
            invalidate_current_run_id,
            set_current_run_id,
        )

        # These methods should not raise — they return None/False when Redis unavailable
        # or work correctly when Redis is available (fail-open design)
        run_id = get_current_run_id("1d")
        assert run_id is None or isinstance(run_id, str)

        df = get_daily_bars_cached("test", "20200101", "20200131")
        assert df is None or hasattr(df, "columns")

        result = set_current_run_id("1d", "test_integration_run")
        assert result in (True, False)  # True if Redis available, False if not

        inv = invalidate_current_run_id("1d")
        assert inv in (True, False)


class TestBacktestNoDownloadContract:
    def test_verify_oskh_data_contract_includes_backtest_scan(self):
        import subprocess
        import sys

        proc = subprocess.run(
            [sys.executable, "scripts/gates/verify_oskh_data_contract.py"],
            cwd=str(Path(__file__).resolve().parents[1]),
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0, proc.stdout + proc.stderr
