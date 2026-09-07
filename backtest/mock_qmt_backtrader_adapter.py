# -*- coding: utf-8 -*-
"""Minimal Backtrader-to-mock execution adapter (no live QMT integrations)."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Dict, Iterable, List


@dataclass
class BacktestOrderIntent:
    action: str
    stock: str
    volume: int
    price: float
    strategy_name: str = "backtest"
    remark: str = "backtrader_mock_pipeline"


class _MockTrader:
    def __init__(self) -> None:
        self._next_id = 1
        self._orders: List[SimpleNamespace] = []
        self._positions: Dict[str, SimpleNamespace] = {}

    def seed_position(
        self,
        stock_code: str,
        volume: int,
        *,
        can_use_volume: int | None = None,
        avg_price: float = 0.0,
    ) -> None:
        self._positions[str(stock_code)] = SimpleNamespace(
            stock_code=str(stock_code),
            volume=int(volume),
            can_use_volume=int(can_use_volume if can_use_volume is not None else volume),
            avg_price=float(avg_price),
        )

    def order_stock(
        self,
        account: Any,
        stock_code: str,
        order_type: int,
        order_volume: int,
        price_type: int,
        price: float,
        strategy_name: str,
        order_remark: str,
    ) -> int:
        del account, price_type, strategy_name, order_remark
        order_id = self._next_id
        self._next_id += 1
        self._orders.append(
            SimpleNamespace(
                order_id=order_id,
                stock_code=stock_code,
                order_type=order_type,
                order_volume=int(order_volume),
                price=float(price),
                order_status=56,
                traded_volume=int(order_volume),
                traded_price=float(price),
            )
        )
        return order_id

    def query_orders(self, account: Any) -> List[SimpleNamespace]:
        del account
        return list(self._orders)


class _MockManager:
    def __init__(self) -> None:
        self._trader = _MockTrader()

    @classmethod
    def create_isolated_for_unittests(cls) -> "_MockManager":
        return cls()

    @classmethod
    def get_instance(cls) -> "_MockManager":
        return cls()

    def get_connection(self, account_id: str, path: str, session: int) -> tuple[_MockTrader, SimpleNamespace]:
        del path, session
        return self._trader, SimpleNamespace(account_id=str(account_id))


# Backward-compatible name for tests that imported the live mock type.
MockQMTConnectionManager = _MockManager


class BacktestMockQmtPipeline:
    """Execute backtest intents through in-process mock order semantics."""

    def __init__(self, *, account_id: str = "bt_mock_acc", isolated_manager: bool = True) -> None:
        if isolated_manager:
            self._mgr = _MockManager.create_isolated_for_unittests()
        else:
            self._mgr = _MockManager.get_instance()
        self._account_id = str(account_id)
        self._trader, self._account = self._mgr.get_connection(self._account_id, "backtest_mock_path", 1)

    @staticmethod
    def _order_type_from_action(action: str) -> int:
        a = str(action or "").strip().upper()
        if a == "BUY":
            return 0
        if a == "SELL":
            return 1
        raise ValueError(f"unsupported action: {action!r}")

    def submit_intent(self, intent: BacktestOrderIntent) -> Dict[str, Any]:
        order_id = self._trader.order_stock(
            account=self._account,
            stock_code=str(intent.stock),
            order_type=self._order_type_from_action(intent.action),
            order_volume=int(intent.volume),
            price_type=0,
            price=float(intent.price),
            strategy_name=str(intent.strategy_name),
            order_remark=str(intent.remark),
        )
        orders = self._trader.query_orders(self._account)
        order = next((o for o in orders if int(getattr(o, "order_id", -1)) == int(order_id)), None)
        return {
            "order_id": int(order_id),
            "status": int(getattr(order, "order_status", -1) or -1) if order is not None else -1,
            "traded_volume": int(getattr(order, "traded_volume", 0) or 0) if order is not None else 0,
            "traded_price": float(getattr(order, "traded_price", 0.0) or 0.0) if order is not None else 0.0,
        }

    def run_cycle(self, intents: Iterable[BacktestOrderIntent]) -> List[Dict[str, Any]]:
        return [self.submit_intent(intent) for intent in intents]
