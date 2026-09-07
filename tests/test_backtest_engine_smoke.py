# -*- coding: utf-8 -*-
from datetime import date

from backtest.engine import BarReplayEngine, BacktestConfig


class _S:
    strategy_name = "Stub"

    def select_stocks(self, trading_date: str):
        return ["flat"]


def test_bar_replay_engine_records_events():
    eng = BarReplayEngine(_S(), BacktestConfig())
    eng.run_dates([date(2026, 1, 5)])
    assert len(eng.events) == 1
    assert eng.events[0]["type"] == "selection"
