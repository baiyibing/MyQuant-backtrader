"""BT injects its data/clock/log policies into the MyQuant factor package."""
from myquant_factors._runtime import configure_host
from common.infra import data_root
from common.infra.quant_logger import get_logger
from pathlib import Path


def _previous_trading_day(value):
    from oskh_data.freshness import get_previous_trading_day
    return get_previous_trading_day(value)


def _reader_factory(*args, **kwargs):
    from oskh_data import StockDataReader
    return StockDataReader(*args, **kwargs)


def _pool_entries(path):
    from backtest.research.csv_pool import parse_pool_csv_entries
    return parse_pool_csv_entries(path)


def _trade_days(**kwargs):
    from common.infra.trading_calendar_pmc import get_trade_days_sse
    return get_trade_days_sse(**kwargs)


def _clock():
    from common.infra.timekeeping import shanghai_now
    return shanghai_now()


def _python():
    from scripts._script_bootstrap import resolve_oskh_python
    return resolve_oskh_python()


def _store(path=None, **kwargs):
    from oskh_data.turnover_resistance_store import TurnoverResistanceStore
    return TurnoverResistanceStore(path, **kwargs)


def _store_path(path=None):
    from oskh_data.turnover_resistance_store import resolve_parquet_path
    return resolve_parquet_path(path)


def _year_path(*args):
    from oskh_data.turnover_resistance_store import resolve_year_staging_path
    return resolve_year_staging_path(*args)


def _store_merge(*args, **kwargs):
    from oskh_data.turnover_resistance_store import merge_parquet_into_canonical
    return merge_parquet_into_canonical(*args, **kwargs)


configure_host(
    source_parquet=lambda name: data_root.resolve_source_parquet(name),
    data_root=lambda **kwargs: data_root.resolve_data_root(**kwargs),
    tr_root=lambda: data_root.resolve_turnover_resist_parquet_root(),
    previous_trading_day=_previous_trading_day,
    logger=get_logger,
    reader_factory=_reader_factory,
    research_root=lambda: Path(__file__).resolve().parents[1],
    period_root=lambda period: data_root.resolve_period_root(period),
    pool_entries=_pool_entries,
    trade_days=_trade_days,
    clock=_clock,
    parquet_root=lambda: data_root.resolve_parquet_container(),
    python=_python,
    store_factory=_store,
    store_path=_store_path,
    year_path=_year_path,
    store_merge=_store_merge,
    tr_backfill_entry=lambda: Path(__file__).resolve().parents[1] / "scripts/tr/backfill_turnover_resistance_bands.py",
)
