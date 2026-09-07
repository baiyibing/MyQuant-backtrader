# -*- coding: utf-8 -*-
"""TurtleTrading sell-preset evaluators (moved from ``trade_decision.presets``).

Owns prototype sell evaluator. Registry stays in
``trade_decision.presets`` (presets → turtle.sell one-way). Types come from
``presets_protocol`` only (no import of ``presets`` — cycle guard).
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

from trade_decision.presets_protocol import SellPresetContext, SellPresetDecision
from trade_decision.turtle.buy import TURTLE_ADD_BANDS


def _maybe_log_missing_warmup_feature(indicators: Mapping[str, Any], *, feature: str) -> None:
    try:
        from oskh_core.warmup_declarative_gate import warmup_feature_missing_visible

        if not warmup_feature_missing_visible():
            return
        from common.infra.quant_logger import get_logger

        get_logger("trade_decision", "turtle_sell").warning(
            "turtle sell feature missing (warmup visibility W2b)",
            context={"feature": feature, "keys": sorted(str(k) for k in indicators.keys())},
        )
    except Exception:
        # 观测钩子刻意 fail-open：warning 打不出绝不影响卖决策主路径
        return


def _turtle_ten_day_low_hit(indicators: Mapping[str, Any]) -> bool:
    """SDD §6.4.5 原版海龟离场：low(today) <= MIN(low, past 10 days)。
    缺 ``low``/``low10_prior`` 指标（数据源未供）→ 不适用（False），不 fail-closed。"""
    try:
        low = float(indicators.get("low", 0) or 0)
        low10_prior = float(indicators.get("low10_prior", 0) or 0)
    except (TypeError, ValueError):
        _maybe_log_missing_warmup_feature(indicators, feature="low/low10_prior")
        return False
    if low <= 0 or low10_prior <= 0:
        _maybe_log_missing_warmup_feature(indicators, feature="low/low10_prior")
        return False
    return low <= low10_prior


def _eval_prototype_sell(params: Mapping[str, Any], ctx: SellPresetContext) -> SellPresetDecision:
    """prototype 卖侧（plan-turtle-sell-protocol + docx 对齐 2026-08-10）。

    交替止盈：档位 = 加权成本×[1.3, 1.5, 1.8, 2.0]（xlsx H5-H8），卖**剩余持仓**
    30/20/30/20%（xlsx J5-J8；J8 原公式两处笔误，以 I 列比例序列为权威修正）。
    ``ctx.sell_band_seq`` = 已 dispatch 最高档；同 tick 多档穿越级联合并。
    满仓（units≥max_units）后另评利润回撤止盈（全清）；5 日持仓时间止损（未到下一加仓线）。
    风控增强（涨停锁/炸板/十日低点）仅 ``TURTLE_RISK_ENHANCEMENTS_ENABLED`` 时生效。
    MA10 全清（``TURTLE_RISK_MA10_EXIT_ENABLED``）正交，默认关；涨停日不发 ma10_break。
    止损不在本层——wiring tier stop（docx：试错-4% / 7成+1% / 9成+2%）。
    """
    from trade_decision.turtle.runtime_flags import (
        is_turtle_risk_enhancements_enabled,
        is_turtle_risk_ma10_exit_enabled,
    )

    risk_on = bool(params.get("risk_enhancements_enabled")) or is_turtle_risk_enhancements_enabled()
    if risk_on and ctx.is_limit_up:
        return SellPresetDecision(False, None, True)
    indicators = ctx.indicators or {}
    high = float(ctx.holding_high or 0.0)
    price = float(ctx.current_price or 0.0)
    if risk_on:
        board_break_pct = float(params.get("board_break_pct", 0.03) or 0.03)
        was_limit_up = bool(
            indicators.get("was_limit_up")
            or indicators.get("opened_from_limit_up")
            or params.get("was_limit_up")
            or ctx.reserved_for_limit_up
        )
        if was_limit_up and high > 0 and price > 0:
            board_dd = (high - price) / high
            if board_dd >= board_break_pct:
                return SellPresetDecision(True, "bucket_preset:prototype:board_break", False)
        if _turtle_ten_day_low_hit(indicators):
            return SellPresetDecision(
                True, "bucket_preset:prototype:ten_day_low", ctx.reserved_for_limit_up
            )
    ma10_on = bool(params.get("ma10_exit_enabled")) or is_turtle_risk_ma10_exit_enabled()
    if ma10_on and not ctx.is_limit_up:
        ma10 = 0.0
        try:
            ma10 = float(indicators.get("ma10", 0) or 0)
        except (TypeError, ValueError):
            ma10 = 0.0
        data_ok = indicators.get("data_ok", True)
        cmp_raw = getattr(ctx, "ma_comparison_price", None)
        try:
            cmp = float(cmp_raw) if cmp_raw is not None else 0.0
        except (TypeError, ValueError):
            cmp = 0.0
        if (
            data_ok is not False
            and ma10 > 0
            and cmp > 0
            and cmp < ma10
        ):
            return SellPresetDecision(
                True,
                "bucket_preset:prototype:ma10_break",
                ctx.reserved_for_limit_up,
                1.0,
            )
    cost = float(ctx.cost_price) if ctx.cost_price is not None else None
    if cost is None or cost <= 0 or price <= 0:
        return SellPresetDecision(False, None, ctx.reserved_for_limit_up)

    units = max(0, int(getattr(ctx, "units", 0) or 0))
    max_units = int(params.get("max_units", 3) or 3)
    # 5 日持仓（逐档计时）：未满仓且未触及下一加仓线 → 全清（无论盈亏）
    hold_days = int(getattr(ctx, "hold_days", 0) or 0)
    entry = float(getattr(ctx, "entry_price", 0.0) or 0.0)
    if hold_days >= 5 and units < max_units and entry > 0:
        # 下一加仓线单源 TURTLE_ADD_BANDS（buy.py）：units<=1 → 首档 ×1.04，
        # units>=2 → 第二档 ×1.10；档数变化时 clamp 索引保持语义。
        _band_idx = min(max(units - 1, 0), len(TURTLE_ADD_BANDS) - 1)
        next_mult = 1.0 + TURTLE_ADD_BANDS[_band_idx][0]
        if price < entry * next_mult:
            return SellPresetDecision(
                True, "bucket_preset:prototype:hold_days_5", ctx.reserved_for_limit_up, 1.0
            )

    # 满仓后利润回撤止盈：基准 (high−price)/(high−cost)；档位按峰值涨幅 (high−cost)/cost
    if units >= max_units and high > cost and price > 0:
        peak_gain = (high - cost) / cost
        profit_dd = (high - price) / (high - cost)
        if peak_gain <= 0.20:
            thr = 0.50
        elif peak_gain <= 0.50:
            thr = 0.40
        else:
            thr = 0.20  # docx 第三档笔误 ">20%" → ">50%"
        if profit_dd >= thr:
            return SellPresetDecision(
                True,
                "bucket_preset:prototype:profit_drawdown",
                ctx.reserved_for_limit_up,
                1.0,
            )

    bands = (1.3, 1.5, 1.8, 2.0)  # 档 1-4（1-based 编号）
    ratios = (0.30, 0.20, 0.30, 0.20)
    # sell_band_seq：已 dispatch 最高档编号（1-based；0 = 未触发任何档）。
    # 触发条件严格小于（seq < 档编号）——已 dispatch 档不重复触发。
    seq = max(0, int(getattr(ctx, "sell_band_seq", 0) or 0))
    target: Optional[int] = None
    for i in range(len(bands)):
        if seq < i + 1 and price >= cost * bands[i]:
            target = i
    if target is None:
        return SellPresetDecision(False, None, ctx.reserved_for_limit_up)
    # 应卖合并档 = (seq, target]（seq 作 ratios 索引起点：档 N 的 ratios 索引 N-1，
    # 已发档 seq 之后下一档 ratios 索引恰为 seq）。frac = 1 − Π(1 − ratios[idx])。
    frac = 1.0
    for idx in range(seq, target + 1):
        frac *= 1.0 - ratios[idx]
    frac = round(1.0 - frac, 4)
    return SellPresetDecision(
        True,
        f"bucket_preset:prototype:band:{target + 1}",
        ctx.reserved_for_limit_up,
        sell_fraction=frac,
    )


__all__ = [
    "_eval_prototype_sell",
    "_turtle_ten_day_low_hit",
]
