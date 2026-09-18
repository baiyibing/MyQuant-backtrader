# -*- coding: utf-8 -*-
from backtest.research.ashare_fees import (
    BILATERAL_10BP,
    QLIB_PORTANA,
    trade_commission,
)
from backtest.research.csv_ledger import trade_commission as ledger_trade_commission


def test_bilateral_10bp_has_no_floor():
    assert BILATERAL_10BP.buy_fee(1_000) == 1.0
    assert BILATERAL_10BP.debit_buy(1_000) == 1_001.0
    assert BILATERAL_10BP.credit_sell(1_000) == 999.0


def test_qlib_portana_floors_at_five():
    assert QLIB_PORTANA.buy_fee(1_000) == 5.0
    assert QLIB_PORTANA.buy_fee(1_000_000) == 500.0
    assert QLIB_PORTANA.sell_fee(1_000_000) == 1_500.0


def test_ledger_reexports_same_formula():
    assert ledger_trade_commission(1_000, 0.001) == trade_commission(1_000, 0.001)
    assert trade_commission(0, 0.001) == 0.0
