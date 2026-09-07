# -*- coding: utf-8 -*-
"""
回测引擎 MVP（第九章 §9.3）：Bar 序列驱动 + 费用/涨跌停钩子占位。

与实盘对齐方向：复用 `strategies.base_strategy.BaseStrategy`，产出可与
`signal_audit` / `execution_log` 字段对照的结构化事件（后续迭代扩展）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional, Protocol, Tuple

from common.infra.trace_context import TraceIdGenerator
from trade_fee_policy import build_stamp_tax_exempt_symbol_keys, calculate_trade_fee


class StrategyLike(Protocol):
    strategy_name: str

    def select_stocks(self, trading_date: str) -> List[str]: ...


@dataclass
class BacktestConfig:
    """回测参数占位；费率口径与 trade_fee_policy 对齐。"""

    commission_rate: float = 0.00005
    tax_rate_sell: float = 0.0005
    min_commission: float = 5.0
    stamp_tax_exempt_prefixes: Tuple[str, ...] = (
        "159",
        "510",
        "511",
        "512",
        "513",
        "515",
        "518",
        "56",
        "58",
    )
    stamp_tax_unknown_as_stock: bool = True
    stamp_tax_exempt_symbols: Tuple[str, ...] = ()
    transfer_fee_rate_sh: float = 0.0
    limit_up_epsilon: float = 0.001  # 相对涨停价容忍


def estimate_backtest_trade_fee(
    cfg: BacktestConfig,
    action: str,
    stock: str,
    volume: int,
    price: float,
) -> float:
    """与实盘相同的费用估算（后续接入撮合时可写入 SimulatedFill.fee）。"""
    keys = build_stamp_tax_exempt_symbol_keys(cfg.stamp_tax_exempt_symbols)
    return calculate_trade_fee(
        action,
        stock,
        volume,
        price,
        commission_rate=cfg.commission_rate,
        min_commission=cfg.min_commission,
        stamp_tax_rate_stock=cfg.tax_rate_sell,
        stamp_tax_exempt_prefixes=cfg.stamp_tax_exempt_prefixes,
        stamp_tax_unknown_as_stock=cfg.stamp_tax_unknown_as_stock,
        stamp_tax_exempt_symbol_keys=keys,
        transfer_fee_rate_sh=cfg.transfer_fee_rate_sh,
    )


@dataclass
class SimulatedFill:
    stock: str
    action: str
    volume: int
    price: float
    fee: float
    trace_id: str
    meta: Dict[str, Any] = field(default_factory=dict)


class BarReplayEngine:
    """
    按交易日顺序调用策略 `select_stocks`，并记录意图事件（非真实撮合）。

    当前不依赖 miniQMT；供后续接入 Tick/Bar 数据与撮合规则。
    """

    def __init__(self, strategy: StrategyLike, config: Optional[BacktestConfig] = None) -> None:
        self._strategy = strategy
        self.config = config or BacktestConfig()
        self.events: List[Dict[str, Any]] = []

    def run_dates(self, dates: List[date], *, trace_prefix: str = "BT") -> List[SimulatedFill]:
        fills: List[SimulatedFill] = []
        for d in dates:
            ds = d.strftime("%Y%m%d")
            tid = TraceIdGenerator.generate("selector", ds)
            picks = self._strategy.select_stocks(ds)
            ev = {
                "type": "selection",
                "trading_date": ds,
                "trace_id": tid,
                "strategy": getattr(self._strategy, "strategy_name", type(self._strategy).__name__),
                "stocks": list(picks),
            }
            self.events.append(ev)
        return fills
