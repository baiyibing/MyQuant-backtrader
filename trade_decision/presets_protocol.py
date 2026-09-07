"""Structural typing contracts for ``trade_decision.presets`` evaluators and buy gates.

Owns ``SellPresetContext`` / ``SellPresetDecision`` (protocol layer) so strategy
packages (e.g. ``trade_decision.turtle.sell``) can depend on this module without
importing the registry in ``presets.py`` (avoids presets ↔ turtle cycles).

Orthogonal to ``trade_decision.decision_protocols`` (RSRS / sell-rule callbacks) and
``trade_decision.lt_kernel_protocol`` (live facade surface).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping, Optional, Protocol, runtime_checkable


@dataclass(frozen=True)
class SellPresetContext:
    """Preset evaluation inputs.

    ``now_local`` is normalized to Asia/Shanghai inside time-of-day rules (naive = Shanghai wall;
    see ``common.infra.timekeeping.to_shanghai``).
    """

    cost_price: Optional[float]  # P1-13: None = 成本数据不可用，preset 应返回 False
    current_price: float
    holding_high: float
    hold_days: int
    is_limit_up: bool
    now_local: datetime
    indicators: Optional[Mapping[str, Any]] = None
    reserved_for_limit_up: bool = False
    # P4 optional signal / gap-down fields (default unset → legacy preset behavior unchanged)
    prev_close: Optional[float] = None
    open_price: Optional[float] = None
    rank_score: Optional[float] = None
    rank_threshold: Optional[int] = None
    in_topk: Optional[bool] = None
    rotation_signal: Optional[str] = None
    model_score: Optional[float] = None
    model_threshold: Optional[float] = None
    # Retired turtle layer tag (fast/slow/base). Always None after layer retire; field kept.
    layer_type: Optional[str] = None
    # 卖侧交替止盈已 dispatch 最高档（plan-turtle-sell-protocol-2026-08-06；仅 prototype 消费，
    # wiring per-stock 通道从 position_state 读入）
    sell_band_seq: int = 0
    # P0 (2026-08-03): null_cost_skip 日志定位用——wiring 两处构造点（layered/per-stock）填充；
    # 末尾追加保位置参数构造兼容（tests 位置参数构造）；None=未知，日志不炸
    stock_code: Optional[str] = None
    # P0 (2026-08-04): per-stock 路径 layer 覆埋——区分 skip 来源路径。per-stock 聚合跨层
    # layer_type 恒 None，单看 layer_type 无法区分两条路径（08-04 现场 11 只 layer=null 无法
    # 定位是 per-stock 还是 layered-with-None）。layered 填 "layered"、per-stock 填 "per_stock"；
    # None=未标（test/backtest/v4 合成 ctx 不填）。末尾追加保位置参数构造兼容
    sell_scan_path: Optional[str] = None
    # plan-turtle-strategy-docx-alignment-2026-08-10：加仓次数（满仓=add_count≥2；止损/回撤止盈）
    add_count: int = 0
    # 首仓价（5 日持仓：下一加仓线 = entry×1.04 / ×1.10）；0=未知则跳过时间止损
    entry_price: float = 0.0
    # C：MA10 同域比较价（front last = raw × adj_factor）。None = 未接通/降级，MA10 惰性。
    ma_comparison_price: Optional[float] = None
    # 当前档数（Fix A rebase；满仓 = units>=max_units；5 日规则 units<max_units 才适用）
    units: int = 0


@dataclass(frozen=True)
class SellPresetDecision:
    """``sell_fraction``（Phase D，SDD §6.4.3）：应卖比例，默认 1.0=整仓清；
    透传保留，layer 恒 None（分层已废止）；per-stock 路径忽略（恒整仓语义不变）。"""

    should_sell: bool
    reason: Optional[str]
    reserved_for_limit_up: bool = False
    sell_fraction: float = 1.0


@runtime_checkable
class SellPresetEvaluatorLike(Protocol):
    """Read-only structural contract for a sell-preset evaluator.

    Matches the existing ``SellPresetEvaluator`` callable signature:
    ``(params: Mapping[str, Any], ctx: SellPresetContext) -> SellPresetDecision``.
    No explicit inheritance required — any callable with the same signature
    (including all 8 builtin ``_eval_*`` functions and user-defined evaluators)
    satisfies this contract.

    **Runtime-checkable limitation**: ``@runtime_checkable`` only verifies the
    presence of a ``__call__`` attribute; it does *not* validate argument
    count, keyword-only parameters, or return type.  Signature correctness is
    enforced by Pyright at static-check time, not by ``isinstance`` at
    runtime.  Production hot paths do not call ``isinstance``.
    """

    def __call__(self, params: Mapping[str, Any], ctx: SellPresetContext) -> SellPresetDecision: ...


@runtime_checkable
class PresetBuyGateLike(Protocol):
    """Read-only structural contract for a preset buy gate.

    Matches the existing ``SellPresetBuyGate`` callable signature:
    ``(params: Mapping[str, Any], current_price: float, indicators: Optional[Mapping[str, Any]], ma_comparison_price: Optional[float] = None) -> bool``.
    Covers builtin buy gates (e.g. ``_allow_buy_v4``) and the default
    no-op fallback ``lambda _params, _price, _ind, _ma_cmp=None: True``.

    Runtime-checkable limitation — see :class:`SellPresetEvaluatorLike`.
    """

    def __call__(
        self,
        params: Mapping[str, Any],
        current_price: float,
        indicators: Optional[Mapping[str, Any]],
        ma_comparison_price: Optional[float] = None,
    ) -> bool: ...


__all__ = [
    "PresetBuyGateLike",
    "SellPresetContext",
    "SellPresetDecision",
    "SellPresetEvaluatorLike",
]
