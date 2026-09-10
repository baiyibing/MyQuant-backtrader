import importlib


def test_research_engine_import() -> None:
    importlib.import_module("backtest.research.engine")
