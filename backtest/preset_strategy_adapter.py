# -*- coding: utf-8 -*-
"""Backtest sell-side adapter: assemble ``SellPresetContext`` and delegate to ``evaluate_sell_preset``."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Literal, Mapping, Optional, Tuple

from backtest.ProfitStrategy import ProfitStrategy, StrategyFactory
from trade_decision.presets import (
    SellPresetContext,
    evaluate_sell_preset,
)

PriceMode = Literal["raw", "adjusted"]


def resolve_use_preset_sell_adapter(explicit: Optional[bool] = None) -> bool:
    """Env ``BACKTEST_USE_PRESET_SELL_ADAPTER`` overrides when explicit is None."""
    if explicit is not None:
        return bool(explicit)
    raw = os.environ.get("BACKTEST_USE_PRESET_SELL_ADAPTER", "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class SellContextAtoms:
    """Atomic inputs for context assembly parity (same mock values for backtest vs wiring)."""

    stock_code: str
    cost_price: Optional[float]
    current_price: float
    holding_high: float
    hold_days: int
    is_limit_up: bool
    now_local: datetime
    indicators: Optional[Mapping[str, Any]] = None
    reserved_for_limit_up: bool = False
    prev_close: Optional[float] = None
    open_price: Optional[float] = None


def context_from_atoms(atoms: SellContextAtoms) -> SellPresetContext:
    """Canonical ``SellPresetContext`` assembly shared by adapter and parity tests."""
    return SellPresetContext(
        cost_price=atoms.cost_price,
        current_price=float(atoms.current_price),
        holding_high=float(atoms.holding_high),
        hold_days=int(atoms.hold_days),
        is_limit_up=bool(atoms.is_limit_up),
        now_local=atoms.now_local,
        indicators=atoms.indicators,
        reserved_for_limit_up=bool(atoms.reserved_for_limit_up),
        prev_close=atoms.prev_close,
        open_price=atoms.open_price,
        in_topk=None,
        rank_score=None,
        rank_threshold=None,
        rotation_signal=None,
        model_score=None,
        model_threshold=None,
    )


def build_live_wiring_equivalent_context(atoms: SellContextAtoms) -> SellPresetContext:
    """Mirror live wiring base-field assembly (overlay None) for adapter context parity."""
    price_e = float(atoms.current_price)
    prev_high = float(atoms.holding_high)
    holding_high = max(prev_high, price_e) if price_e > 0 else prev_high
    wired_atoms = SellContextAtoms(
        stock_code=atoms.stock_code,
        cost_price=atoms.cost_price,
        current_price=price_e,
        holding_high=holding_high,
        hold_days=atoms.hold_days,
        is_limit_up=atoms.is_limit_up,
        now_local=atoms.now_local,
        indicators=atoms.indicators,
        reserved_for_limit_up=atoms.reserved_for_limit_up,
        prev_close=atoms.prev_close,
        open_price=atoms.open_price,
    )
    return context_from_atoms(wired_atoms)


class PresetSellScratch:
    """Session scratch keyed by stock_code (persists across bars/days until preset clears it)."""

    def __init__(self) -> None:
        self._reserved: Dict[str, bool] = {}

    def get(self, stock_code: str) -> bool:
        return bool(self._reserved.get(stock_code, False))

    def set(self, stock_code: str, reserved: bool) -> None:
        if reserved:
            self._reserved[stock_code] = True
        elif stock_code in self._reserved:
            del self._reserved[stock_code]


def _legacy_reason_from_preset(preset_reason: Optional[str]) -> Optional[str]:
    if not preset_reason:
        return None
    reason = str(preset_reason)
    if ":stop_loss" in reason:
        return f"stop_loss {reason}"
    if "drawdown_take_profit" in reason or "dynamic_drawdown_take_profit" in reason:
        return f"profit_take:drawdown {reason}"
    if ":profit_target" in reason:
        return f"profit_take:target {reason}"
    if ":ma_cross_sell" in reason:
        return f"ma_signal {reason}"
    if "force_sell" in reason:
        return f"force_sell {reason}"
    if "open_board_after_limit_up_reserve" in reason:
        return reason
    return reason


def runtime_atoms_from_backtest(
    *,
    status: Any,
    current_datetime: datetime,
    current_price: float,
    is_limit_up: bool,
    indicators: Optional[Mapping[str, Any]],
    scratch: PresetSellScratch,
    prev_close: Optional[float] = None,
    open_price: Optional[float] = None,
) -> SellContextAtoms:
    stock_code = str(getattr(status, "stock_code", "") or "")
    return SellContextAtoms(
        stock_code=stock_code,
        cost_price=getattr(status, "cost_price", None),
        current_price=float(current_price),
        holding_high=float(getattr(status, "holding_high", current_price) or current_price),
        hold_days=int(getattr(status, "hold_days", 0) or 0),
        is_limit_up=bool(is_limit_up),
        now_local=current_datetime,
        indicators=indicators,
        reserved_for_limit_up=scratch.get(stock_code),
        prev_close=prev_close,
        open_price=open_price,
    )


class PresetStrategyAdapter(ProfitStrategy):
    """Delegates sell/buy gates to ``trade_decision.presets`` (Phase 1 single source)."""

    def __init__(
        self,
        preset_version: str,
        custom_params: Optional[Dict[str, Any]] = None,
        *,
        price_mode: PriceMode = "adjusted",
    ) -> None:
        if preset_version not in StrategyFactory.PRESETS:
            valid = ", ".join(StrategyFactory.PRESETS.keys())
            raise ValueError(f"invalid preset version: {preset_version}; valid: {valid}")
        _cls, default_params = StrategyFactory.PRESETS[preset_version]
        self.preset_version = preset_version
        self.params: Dict[str, Any] = {**default_params, **(custom_params or {})}
        self.price_mode: PriceMode = price_mode
        self._scratch = PresetSellScratch()
        # F1 (P0-1 Phase 1 严格只卖侧)：should_buy 委托 legacy 实例，买侧不切 allow_buy_by_preset
        # （设计稿 §10；评审 v3.1：三家 AI 盲点，主代理核实 backtest rolling:1623/1890 真调 should_buy）。
        self._legacy_strategy = StrategyFactory.create(preset_version, custom_params)
        self._validate_params()

    def _validate_params(self) -> None:
        pass

    def should_sell(
        self,
        status,
        current_datetime,
        current_price: float,
        is_limit_up: bool = False,
        is_limit_down: bool = False,
        indicators=None,
    ) -> Tuple[bool, Optional[str]]:
        del is_limit_down
        # version6 / version8 是回测本地预设：trade_decision.presets 为两仓共享 SSOT
        # （blob 与 1.3 main 一致），不在其中注册；卖侧委托本地 Strategy 实例。
        if self.preset_version in ("version6", "version8"):
            return self._legacy_strategy.should_sell(
                status, current_datetime, current_price, is_limit_up, False, indicators
            )
        atoms = runtime_atoms_from_backtest(
            status=status,
            current_datetime=current_datetime,
            current_price=current_price,
            is_limit_up=is_limit_up,
            indicators=indicators,
            scratch=self._scratch,
        )
        ctx = context_from_atoms(atoms)
        decision = evaluate_sell_preset(self.preset_version, self.params, ctx)
        self._scratch.set(atoms.stock_code, decision.reserved_for_limit_up)
        if not decision.should_sell:
            return False, None
        return True, _legacy_reason_from_preset(decision.reason)

    def should_buy(
        self,
        status,
        current_datetime,
        current_price: float,
        is_limit_up: bool = False,
        is_limit_down: bool = False,
        indicators=None,
    ) -> Tuple[bool, Optional[str]]:
        # F1: 买侧委托 legacy 实例（Phase 1 只卖侧单源）；仅 should_sell 走 evaluate_sell_preset。
        return self._legacy_strategy.should_buy(
            status,
            current_datetime,
            current_price,
            is_limit_up,
            is_limit_down,
            indicators,
        )


def create_preset_strategy_adapter(
    strategy_version: str,
    strategy_params: Optional[Dict[str, Any]] = None,
    *,
    price_mode: PriceMode = "adjusted",
) -> PresetStrategyAdapter:
    return PresetStrategyAdapter(
        strategy_version,
        custom_params=strategy_params,
        price_mode=price_mode,
    )


__all__ = [
    "PresetSellScratch",
    "PresetStrategyAdapter",
    "PriceMode",
    "SellContextAtoms",
    "build_live_wiring_equivalent_context",
    "context_from_atoms",
    "create_preset_strategy_adapter",
    "resolve_use_preset_sell_adapter",
    "runtime_atoms_from_backtest",
]
