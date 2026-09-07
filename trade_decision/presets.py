from __future__ import annotations

"""Sell-preset registry and evaluators (version1–version5 + P4 behavioral presets).

**Contract layers**

1. **Registry typing** — ``SellPresetEvaluator`` / ``SellPresetBuyGate`` are aliases of the
   structural Protocols below; ``Dict[str, SellPresetEvaluator]`` registries are typed by
   them (authoritative for registration).
2. **Structural Protocols** — ``SellPresetEvaluatorLike`` / ``PresetBuyGateLike`` in
   ``trade_decision.presets_protocol``, ``@runtime_checkable`` (external injection / static
   annotations). All builtin ``_eval_*`` evaluators and buy gates satisfy them structurally.
3. **Behavioral safety net** — ``tests/test_all_presets_behavior_matrix`` and wiring
   integration tests (see ``docs/architecture/trade-decision-kernel-boundary.md``).

``register_sell_preset`` accepts any ``SellPresetEvaluatorLike`` (aliased as
``SellPresetEvaluator``) — structural typing, no inheritance required. Signature checks stay
Pyright/static — not ``isinstance`` on hot paths (``@runtime_checkable`` only verifies
``__call__`` presence).
"""

import inspect
import threading
from datetime import datetime, time
from typing import Any, Dict, FrozenSet, Mapping, Optional, cast

from common.infra.quant_logger import get_logger
from common.infra.timekeeping import shanghai_now, to_shanghai
from common.infra.trace_context import get_trace_context
from trade_decision.presets_protocol import (
    PresetBuyGateLike as SellPresetBuyGate,
    SellPresetContext,
    SellPresetDecision,
    SellPresetEvaluatorLike as SellPresetEvaluator,
)
from trade_decision.turtle.sell import (
    _eval_prototype_sell,
)

# version5: canonical param key is profit_target_pct; take_profit_pct is a legacy alias (_v5_profit_target_pct).
# Not the same as sell_rules / SELL_BUCKET_RULE_OVERRIDES_JSON take_profit_pct (see docs/operations/csv-live/contract.md).
# SellPresetContext / SellPresetDecision live in presets_protocol (type-flip; turtle.sell depends there).


def _resolve_force_sell_policy(params: Mapping[str, Any]) -> str:
    """Resolve force_sell_policy with legacy force_sell_mode fallback."""
    force_sell_policy = str(params.get("force_sell_policy", "time_only") or "time_only").strip().lower()
    if "force_sell_policy" not in params and "force_sell_mode" in params:
        legacy_mode = str(params.get("force_sell_mode", "or") or "or").strip().lower()
        force_sell_policy = "days_and_time" if legacy_mode == "and" else "days_or_time"
    if force_sell_policy not in {"time_only", "days_or_time", "days_and_time"}:
        raise ValueError(
            f"invalid force_sell_policy: {force_sell_policy!r}; "
            "must be one of time_only/days_or_time/days_and_time"
        )
    return force_sell_policy


_SELL_PRESET_EVALUATORS: Dict[str, SellPresetEvaluator] = {}
_SELL_PRESET_BUY_GATES: Dict[str, SellPresetBuyGate] = {}
_PRESET_REGISTRY_LOCK = threading.RLock()
_PRESET_ALIAS_MAP: Dict[str, str] = {
    "strategy1": "version1",
    "strategy_1": "version1",
    "preset1": "version1",
    "preset_1": "version1",
    "strategy2": "version2",
    "strategy_2": "version2",
    "preset2": "version2",
    "preset_2": "version2",
    "strategy3": "version3",
    "strategy_3": "version3",
    "preset3": "version3",
    "preset_3": "version3",
    "strategy4": "version4",
    "strategy_4": "version4",
    "preset4": "version4",
    "preset_4": "version4",
    "strategy5": "version5",
    "strategy_5": "version5",
    "preset5": "version5",
    "preset_5": "version5",
    # P4 behavioral aliases (canonical registry keys remain version1–version5)
    "trailing_stop": "version1",
    "dynamic_drawdown": "version2",
    "limit_up_profit": "version3",
    "ma_cross": "version4",
    "force_sell": "version5",
}
_HOLD_DAYS_DEPENDENCY_NONE = "none"
_HOLD_DAYS_DEPENDENCY_SOFT = "soft"
_HOLD_DAYS_DEPENDENCY_HARD = "hard"


def _normalize_preset_name(preset: str) -> str:
    return str(preset or "").strip().lower()


def canonical_preset_name(preset: str, *, fallback: str = "") -> str:
    normalized = _normalize_preset_name(preset)
    if normalized in _PRESET_ALIAS_MAP:
        return _PRESET_ALIAS_MAP[normalized]
    if normalized:
        return normalized
    return _normalize_preset_name(fallback)


def _effective_preset_or_raise(preset: str) -> str:
    with _PRESET_REGISTRY_LOCK:
        normalized = canonical_preset_name(preset, fallback="version1") or "version1"
        if normalized not in _SELL_PRESET_EVALUATORS:
            raise ValueError(f"unknown sell preset: {preset!r}")
        return normalized


def _validate_preset_params(preset: str, params: Mapping[str, Any]) -> None:
    key = _effective_preset_or_raise(preset)
    if key == "version2" and "dynamic_drawdown_rules" in params:
        rules = params.get("dynamic_drawdown_rules")
        if not isinstance(rules, Mapping) or not rules:
            raise ValueError("invalid dynamic_drawdown_rules for version2: must be non-empty object")
        normalized: Dict[int, float] = {}
        for k, v in rules.items():
            try:
                day = int(k)
            except (TypeError, ValueError):
                raise ValueError(f"invalid dynamic_drawdown_rules day key: {k!r}") from None
            if day <= 0:
                raise ValueError(f"invalid dynamic_drawdown_rules day key: {k!r}; must be >=1")
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise ValueError(f"invalid dynamic_drawdown_rules threshold for day {day}: {v!r}")
            ratio = float(v)
            if ratio <= 0 or ratio > 1:
                raise ValueError(
                    f"invalid dynamic_drawdown_rules threshold for day {day}: {ratio}; must be within (0,1]"
                )
            normalized[day] = ratio
        prev = 1.0
        for d in sorted(normalized):
            cur = float(normalized[d])
            if cur > prev:
                raise ValueError(
                    f"invalid dynamic_drawdown_rules monotonicity: day {d} threshold {cur} > previous {prev}"
                )
            prev = cur
    if key != "version5":
        return
    force_sell_days = int(params.get("force_sell_days", 0) or 0)
    if force_sell_days < 0:
        raise ValueError("invalid force_sell_days for version5: must be >= 0")


def _non_varkw_params(sig: inspect.Signature) -> list[inspect.Parameter]:
    return [
        p
        for p in sig.parameters.values()
        if p.kind not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
    ]


def _validate_sell_preset_evaluator(evaluator: object) -> None:
    """Registration-time signature check (inspect; not ``isinstance`` Protocol)."""
    if not callable(evaluator):
        raise TypeError("evaluator must be callable")
    try:
        sig = inspect.signature(evaluator)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"evaluator signature not inspectable: {exc}") from exc
    params = _non_varkw_params(sig)
    if len(params) < 2:
        raise TypeError("evaluator must accept at least (params, ctx) parameters")


def _validate_preset_buy_gate(buy_gate: object) -> None:
    if not callable(buy_gate):
        raise TypeError("buy_gate must be callable")
    try:
        sig = inspect.signature(buy_gate)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"buy_gate signature not inspectable: {exc}") from exc
    params = _non_varkw_params(sig)
    if len(params) < 3:
        raise TypeError("buy_gate must accept at least (params, current_price, indicators) parameters")


def register_sell_preset(
    preset: str,
    evaluator: SellPresetEvaluator,
    *,
    buy_gate: Optional[SellPresetBuyGate] = None,
) -> None:
    """Register a sell-preset evaluator and optional buy gate.

    Parameter type remains ``SellPresetEvaluator``; see module docstring for
    ``SellPresetEvaluatorLike`` forward-compat note.  Registration validates
    callable signatures via ``inspect`` (not runtime Protocol ``isinstance``).
    """
    _validate_sell_preset_evaluator(evaluator)
    if buy_gate is not None:
        _validate_preset_buy_gate(buy_gate)
    key = canonical_preset_name(preset)
    if not key:
        raise ValueError("preset must not be empty")
    with _PRESET_REGISTRY_LOCK:
        _SELL_PRESET_EVALUATORS[key] = evaluator
        _SELL_PRESET_BUY_GATES[key] = buy_gate or (lambda params, current_price, indicators, ma_comparison_price=None: True)


def get_registered_sell_evaluators() -> Dict[str, SellPresetEvaluator]:
    """Return a snapshot of registered sell evaluators (read-only contract tests / audit)."""
    with _PRESET_REGISTRY_LOCK:
        return dict(_SELL_PRESET_EVALUATORS)


def get_registered_buy_gates() -> Dict[str, SellPresetBuyGate]:
    """Return a snapshot of registered buy gates (read-only contract tests / audit)."""
    with _PRESET_REGISTRY_LOCK:
        return dict(_SELL_PRESET_BUY_GATES)


def registered_sell_evaluator_names() -> FrozenSet[str]:
    """Canonical registry keys currently registered."""
    with _PRESET_REGISTRY_LOCK:
        return frozenset(_SELL_PRESET_EVALUATORS)


def _drawdown_ratio(holding_high: float, current_price: float, cost_price: float) -> float:
    if holding_high <= cost_price:
        return 0.0
    profit_peak = holding_high - cost_price
    if profit_peak <= 0:
        return 0.0
    drawdown = holding_high - current_price
    if drawdown <= 0:
        return 0.0
    return drawdown / profit_peak


_PRESET_RISK_REASON_MARKERS = (
    "stop_loss",
    "profit_target",
    "drawdown",
    "dynamic_drawdown",
    "force_sell",
    "gap_down",
    "dropped_from_topk",
    "rotate_out",
    "below_threshold",
    "ma10_break",
)


def _preset_reason_bypasses_min_hold(reason: Optional[str]) -> bool:
    if not reason:
        return False
    r = str(reason).lower()
    return any(marker in r for marker in _PRESET_RISK_REASON_MARKERS)


def _evaluate_sell_preset_core(
    preset: str,
    params: Mapping[str, Any],
    ctx: SellPresetContext,
) -> SellPresetDecision:
    _validate_preset_params(preset, params)
    with _PRESET_REGISTRY_LOCK:
        p = _effective_preset_or_raise(preset)
        evaluator = _SELL_PRESET_EVALUATORS[p]
    return evaluator(params, ctx)


_PRESETS_WITHOUT_COST_PRICE = frozenset({"version4", "signal_exit"})


def _preset_requires_cost_price(preset: str) -> bool:
    """MA-only and signal-driven presets skip NULL-cost wrapper."""
    name = canonical_preset_name(preset, fallback="version1")
    return name not in _PRESETS_WITHOUT_COST_PRICE


def evaluate_sell_preset(
    preset: str,
    params: Mapping[str, Any],
    ctx: SellPresetContext,
    *,
    ma_comparison_price: Optional[float] = None,
) -> SellPresetDecision:
    if _preset_requires_cost_price(preset) and (
        ctx.cost_price is None or float(ctx.cost_price or 0) <= 0
    ):
        # P0 (2026-08-03): reason 区分 null_cost vs non_positive_cost（条件含 None or <=0，
        # 文案别只写 is None）；context 带 stock/layer_type/cost_price 实值定位被 skip 标的
        get_logger("SellRules", "null_cost_skip", trace_id=get_trace_context()).warning(
            "avg_cost_yuan is None or <= 0; preset sell SKIPPED",
            context={
                "reason": "null_cost" if ctx.cost_price is None else "non_positive_cost",
                "preset": str(preset or ""),
                "stock": ctx.stock_code,
                "layer_type": ctx.layer_type,
                "sell_scan_path": ctx.sell_scan_path,
                "cost_price": ctx.cost_price,
            },
        )
        return SellPresetDecision(False, None, ctx.reserved_for_limit_up)
    if float(ctx.current_price or 0) <= 0:
        return SellPresetDecision(False, None, ctx.reserved_for_limit_up)
    if ma_comparison_price is not None and _effective_preset_or_raise(preset) == "version4":
        decision = _eval_v4(params, ctx, ma_comparison_price=ma_comparison_price)
    else:
        decision = _evaluate_sell_preset_core(preset, params, ctx)
    min_hold_days = int(params.get("min_hold_days", 0) or 0)
    if (
        min_hold_days > 0
        and decision.should_sell
        and decision.reason
        and int(ctx.hold_days) < min_hold_days
        and not _preset_reason_bypasses_min_hold(decision.reason)
    ):
        return SellPresetDecision(False, None, decision.reserved_for_limit_up)
    return decision


def allow_buy_by_preset(
    preset: str,
    params: Mapping[str, Any],
    *,
    current_price: float,
    indicators: Optional[Mapping[str, Any]] = None,
    ma_comparison_price: Optional[float] = None,
) -> bool:
    with _PRESET_REGISTRY_LOCK:
        p = _effective_preset_or_raise(preset)
        gate = _SELL_PRESET_BUY_GATES.get(p) or (lambda _params, _price, _ind, _ma_cmp=None: True)
    price = float(current_price)
    if ma_comparison_price is not None:
        return bool(gate(params, price, indicators, ma_comparison_price))
    return bool(gate(params, price, indicators))


def get_sell_preset_hold_days_dependency_level(preset: str, params: Mapping[str, Any]) -> str:
    """
    Return hold-days dependency level for operational reset guards.

    - none: preset does not consume hold_days in sell condition
    - soft: hold_days influences sell behavior but is not a hard gate
    - hard: hold_days is an explicit force-sell gate (e.g. version5.force_sell_days > 0)
    """
    key = _effective_preset_or_raise(preset)
    if key == "version2":
        return _HOLD_DAYS_DEPENDENCY_SOFT
    if key == "version5":
        force_sell_days = int(params.get("force_sell_days", 0) or 0)
        if force_sell_days > 0:
            return _HOLD_DAYS_DEPENDENCY_HARD
        return _HOLD_DAYS_DEPENDENCY_NONE
    return _HOLD_DAYS_DEPENDENCY_NONE


def _allow_buy_v4(
    params: Mapping[str, Any],
    current_price: float,
    indicators: Optional[Mapping[str, Any]],
    ma_comparison_price: Optional[float] = None,
) -> bool:
    ma_buy_period = int(params.get("ma_buy_period", 10))
    cmp_price = float(ma_comparison_price) if ma_comparison_price is not None else float(current_price)
    if cmp_price <= 0:
        return False
    feats = indicators or {}
    # M.1-1: 指标缺失时 fail-closed（不把缺失的 MA 当零值使用）
    if feats.get("data_ok") is False:
        return False
    ma_key = f"ma{ma_buy_period}"
    ma_val = float(feats.get(ma_key, 0) or 0)
    if ma_val <= 0:
        return False
    return cmp_price >= ma_val


def eval_v4_ma_cross_raw(
    *,
    side: str,
    ma_comparison_price: float,
    indicators: Optional[Mapping[str, Any]],
    params: Optional[Mapping[str, Any]] = None,
) -> bool:
    """Pure v4 MA-cross boolean for parity/audit (no min_hold / preset kernel).

    Public wrapper around ``_eval_v4`` / ``_allow_buy_v4`` — live decisions still use
    ``evaluate_sell_preset`` / ``allow_buy_by_preset``.
    """
    p = dict(params or {})
    side_u = str(side or "").strip().upper()
    ma_cmp = float(ma_comparison_price)
    if side_u == "SELL":
        ctx = SellPresetContext(
            cost_price=1.0,
            current_price=ma_cmp,
            holding_high=ma_cmp,
            hold_days=999,
            is_limit_up=False,
            now_local=shanghai_now(),
            indicators=indicators,
            reserved_for_limit_up=False,
        )
        return bool(_eval_v4(p, ctx, ma_comparison_price=ma_cmp).should_sell)
    if side_u == "BUY":
        return bool(
            _allow_buy_v4(
                p,
                float(ma_cmp),
                indicators,
                ma_comparison_price=ma_cmp,
            )
        )
    raise ValueError(f"eval_v4_ma_cross_raw: unsupported side={side!r}")


def _effective_cost_price(ctx: SellPresetContext) -> float:
    """Positive cost; wrapper validates before core eval for cost-dependent presets."""
    return cast(float, ctx.cost_price)


def _maybe_gap_down_sell(
    preset_key: str,
    params: Mapping[str, Any],
    ctx: SellPresetContext,
) -> Optional[SellPresetDecision]:
    gap_down_pct = float(params.get("gap_down_pct", 0) or 0)
    if gap_down_pct <= 0:
        return None
    prev_close = ctx.prev_close
    open_price = ctx.open_price
    if prev_close is None or open_price is None or prev_close <= 0 or open_price <= 0:
        return None
    w_start = time.fromisoformat(str(params.get("gap_down_window_start", "09:30")))
    w_end = time.fromisoformat(str(params.get("gap_down_window_end", "09:45")))
    if not _in_open_reserve_window(ctx.now_local, w_start, w_end):
        return None
    gap = (open_price - prev_close) / prev_close
    if gap <= -gap_down_pct:
        return SellPresetDecision(
            True,
            f"bucket_preset:{preset_key}:gap_down",
            ctx.reserved_for_limit_up,
        )
    return None


def preset_gap_down_enabled(params: Mapping[str, Any]) -> bool:
    return float(params.get("gap_down_pct", 0) or 0) > 0


def preset_gap_down_in_evaluation_window(params: Mapping[str, Any], now_local: datetime) -> bool:
    if not preset_gap_down_enabled(params):
        return False
    w_start = time.fromisoformat(str(params.get("gap_down_window_start", "09:30")))
    w_end = time.fromisoformat(str(params.get("gap_down_window_end", "09:45")))
    return _in_open_reserve_window(now_local, w_start, w_end)


def preset_gap_down_fields_missing(ctx: SellPresetContext) -> bool:
    prev_close = ctx.prev_close
    open_price = ctx.open_price
    return (
        prev_close is None
        or open_price is None
        or float(prev_close or 0) <= 0
        or float(open_price or 0) <= 0
    )


def _eval_v1(params: Mapping[str, Any], ctx: SellPresetContext) -> SellPresetDecision:
    gap_dec = _maybe_gap_down_sell("version1", params, ctx)
    if gap_dec is not None:
        return gap_dec
    stop_loss_pct = float(params.get("stop_loss_pct", 0.02))
    profit_drawdown_pct = float(params.get("profit_drawdown_pct", 0.50))
    if stop_loss_pct <= 0:
        return SellPresetDecision(False, None, ctx.reserved_for_limit_up)
    cost = _effective_cost_price(ctx)
    pnl = (ctx.current_price - cost) / cost
    if pnl <= -stop_loss_pct:
        return SellPresetDecision(True, "bucket_preset:version1:stop_loss", ctx.reserved_for_limit_up)
    if pnl > 0:
        dd = _drawdown_ratio(ctx.holding_high, ctx.current_price, cost)
        if dd >= profit_drawdown_pct:
            return SellPresetDecision(True, "bucket_preset:version1:drawdown_take_profit", ctx.reserved_for_limit_up)
    return SellPresetDecision(False, None, ctx.reserved_for_limit_up)


def _eval_v2(params: Mapping[str, Any], ctx: SellPresetContext) -> SellPresetDecision:
    gap_dec = _maybe_gap_down_sell("version2", params, ctx)
    if gap_dec is not None:
        return gap_dec
    stop_loss_pct = float(params.get("stop_loss_pct", 0.02))
    dynamic_rules = params.get(
        "dynamic_drawdown_rules",
        {1: 0.50, 2: 0.40, 3: 0.30, 4: 0.20, 5: 0.10},
    )
    if stop_loss_pct <= 0:
        return SellPresetDecision(False, None, ctx.reserved_for_limit_up)
    cost = _effective_cost_price(ctx)
    pnl = (ctx.current_price - cost) / cost
    if pnl <= -stop_loss_pct:
        return SellPresetDecision(True, "bucket_preset:version2:stop_loss", ctx.reserved_for_limit_up)
    if not isinstance(dynamic_rules, Mapping):
        return SellPresetDecision(False, None, ctx.reserved_for_limit_up)
    if int(ctx.hold_days) <= 0:
        return SellPresetDecision(False, None, ctx.reserved_for_limit_up)
    hd = max(1, int(ctx.hold_days))
    keys = []
    for k in dynamic_rules.keys():
        try:
            keys.append(int(k))
        except (TypeError, ValueError):
            continue
    if not keys:
        return SellPresetDecision(False, None, ctx.reserved_for_limit_up)
    threshold = float(dynamic_rules.get(hd, dynamic_rules.get(max(keys), 0.10)))
    dd = _drawdown_ratio(ctx.holding_high, ctx.current_price, cost)
    if dd >= threshold and pnl > 0:
        return SellPresetDecision(True, "bucket_preset:version2:dynamic_drawdown_take_profit", ctx.reserved_for_limit_up)
    return SellPresetDecision(False, None, ctx.reserved_for_limit_up)


def _in_open_reserve_window(now_local: datetime, start: time, end: time) -> bool:
    t = to_shanghai(now_local).time()
    return (t >= start) and (t < end)


def _parse_force_sell_time(raw: Any, default_time: str = "14:50") -> time:
    val = str(raw or default_time).strip()
    try:
        return time.fromisoformat(val)
    except ValueError:
        return time.fromisoformat(default_time)


def _parse_bool(raw: Any, default: bool = False) -> bool:
    if raw is None:
        return bool(default)
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, (int, float)):
        return raw != 0
    val = str(raw).strip().lower()
    if val in {"1", "true", "yes", "y", "on"}:
        return True
    if val in {"0", "false", "no", "n", "off"}:
        return False
    return bool(default)


def _eval_v3(params: Mapping[str, Any], ctx: SellPresetContext) -> SellPresetDecision:
    stop_loss_pct = float(params.get("stop_loss_pct", 0.04))
    profit_target_pct = float(params.get("profit_target_pct", 0.20))
    if stop_loss_pct <= 0 and profit_target_pct <= 0:
        return SellPresetDecision(False, None, ctx.reserved_for_limit_up)
    w_start = time.fromisoformat(str(params.get("limit_up_reserve_start", "09:30")))
    w_end = time.fromisoformat(str(params.get("limit_up_reserve_end", "09:40")))
    cost = _effective_cost_price(ctx)
    pnl = (ctx.current_price - cost) / cost
    if _in_open_reserve_window(ctx.now_local, w_start, w_end) and ctx.is_limit_up:
        return SellPresetDecision(False, None, True)
    if _in_open_reserve_window(ctx.now_local, w_start, w_end) and ctx.reserved_for_limit_up and not ctx.is_limit_up:
        return SellPresetDecision(False, None, False)
    if ctx.reserved_for_limit_up and not ctx.is_limit_up:
        return SellPresetDecision(True, "bucket_preset:version3:open_board_after_limit_up_reserve", False)
    # 强制卖出（2026-07-01：补齐 force_sell，使 v3 成为止损+止盈+强制卖全覆盖版本）
    force_sell_days = int(params.get("force_sell_days", 0) or 0)
    force_sell_time_str = str(params.get("force_sell_time", "14:50") or "14:50").strip()
    force_sell_time = _parse_force_sell_time(force_sell_time_str)
    force_sell_policy = _resolve_force_sell_policy(params)
    days_triggered = force_sell_days > 0 and ctx.hold_days >= force_sell_days
    time_triggered = to_shanghai(ctx.now_local).time() >= force_sell_time
    if force_sell_policy == "days_and_time":
        force_triggered = days_triggered and time_triggered
    elif force_sell_policy == "days_or_time":
        force_triggered = days_triggered or time_triggered
    else:
        force_triggered = time_triggered
    if force_triggered:
        if force_sell_policy == "days_and_time":
            reason = "bucket_preset:version3:force_sell_days_and_time"
        elif force_sell_policy == "time_only":
            reason = "bucket_preset:version3:force_sell_time"
        elif days_triggered:
            reason = "bucket_preset:version3:force_sell_days"
        else:
            reason = "bucket_preset:version3:force_sell_time"
        return SellPresetDecision(True, reason, False)
    if pnl <= -stop_loss_pct:
        return SellPresetDecision(True, "bucket_preset:version3:stop_loss", False)
    if pnl >= profit_target_pct:
        return SellPresetDecision(True, "bucket_preset:version3:profit_target", False)
    return SellPresetDecision(False, None, ctx.reserved_for_limit_up)


def _eval_v4(
    params: Mapping[str, Any],
    ctx: SellPresetContext,
    *,
    ma_comparison_price: Optional[float] = None,
) -> SellPresetDecision:
    ma_sell_period = int(params.get("ma_sell_period", 5))
    indicators = ctx.indicators or {}
    cmp_price = float(ma_comparison_price) if ma_comparison_price is not None else float(ctx.current_price)
    _log = get_logger("trade_decision.presets", "version4_ma_cross", trace_id=get_trace_context())
    # M.1-2: 指标缺失时 fail-closed（不把缺失的 MA 当零值使用）
    if indicators.get("data_ok") is False:
        _log.warning(
            "v4 indicator source unavailable (data_ok=False); fail-closed, position frozen",
            context={"ma_sell_period": ma_sell_period},
        )
        return SellPresetDecision(False, None, ctx.reserved_for_limit_up)
    ma_key = f"ma{ma_sell_period}"
    ma_val = float(indicators.get(ma_key, 0) or 0)
    if ma_val <= 0 or cmp_price <= 0:
        _log.warning(
            "v4 ma value or price invalid; fail-closed, position frozen",
            context={
                "ma_key": ma_key,
                "ma_val": ma_val,
                "current_price": ctx.current_price,
                "ma_comparison_price": ma_comparison_price,
            },
        )
        return SellPresetDecision(False, None, ctx.reserved_for_limit_up)
    if cmp_price < ma_val:
        return SellPresetDecision(True, "bucket_preset:version4:ma_cross_sell", ctx.reserved_for_limit_up)
    return SellPresetDecision(False, None, ctx.reserved_for_limit_up)


def _v5_profit_target_pct(params: Mapping[str, Any]) -> float:
    """Canonical: profit_target_pct; legacy alias: take_profit_pct (domain/YAML historically mixed)."""
    if "profit_target_pct" in params:
        return float(params["profit_target_pct"])
    if "take_profit_pct" in params:
        return float(params["take_profit_pct"])
    return 0.02


def _eval_v5(params: Mapping[str, Any], ctx: SellPresetContext) -> SellPresetDecision:
    profit_target_pct = _v5_profit_target_pct(params)
    force_sell_days = int(params.get("force_sell_days", 0))
    force_sell_time = _parse_force_sell_time(params.get("force_sell_time", "14:50"))
    try:
        force_sell_policy = _resolve_force_sell_policy(params)
    except ValueError as exc:
        get_logger("trade_decision.presets", "version5_policy", trace_id=get_trace_context()).warning(
            "invalid version5 force_sell_policy; fallback removed, rejecting by validation",
        )
        raise
    reserve_enabled = _parse_bool(params.get("limit_up_reserve_enabled", False), default=False)
    w_start = time.fromisoformat(str(params.get("limit_up_reserve_start", "09:30")))
    w_end = time.fromisoformat(str(params.get("limit_up_reserve_end", "09:40")))
    if profit_target_pct <= 0:
        return SellPresetDecision(False, None, ctx.reserved_for_limit_up)
    cost = _effective_cost_price(ctx)
    pnl = (ctx.current_price - cost) / cost
    if reserve_enabled:
        if _in_open_reserve_window(ctx.now_local, w_start, w_end) and ctx.is_limit_up:
            return SellPresetDecision(False, None, True)
        if _in_open_reserve_window(ctx.now_local, w_start, w_end) and ctx.reserved_for_limit_up and not ctx.is_limit_up:
            return SellPresetDecision(False, None, False)
        if ctx.reserved_for_limit_up and not ctx.is_limit_up:
            return SellPresetDecision(True, "bucket_preset:version5:open_board_after_limit_up_reserve", False)
    else:
        if ctx.reserved_for_limit_up:
            return SellPresetDecision(False, None, False)
    # 下行保护：止损（v5 历史无止损，2026-06-05 补齐；默认 0 = 禁用，向后兼容）
    stop_loss_pct = float(params.get("stop_loss_pct", 0) or 0)
    if stop_loss_pct > 0 and pnl <= -stop_loss_pct:
        return SellPresetDecision(True, "bucket_preset:version5:stop_loss", False)
    days_triggered = force_sell_days > 0 and ctx.hold_days >= force_sell_days
    time_triggered = to_shanghai(ctx.now_local).time() >= force_sell_time
    if force_sell_policy == "days_and_time":
        force_triggered = days_triggered and time_triggered
    elif force_sell_policy == "days_or_time":
        force_triggered = days_triggered or time_triggered
    else:
        force_triggered = time_triggered
    if force_triggered:
        if force_sell_policy == "days_and_time":
            reason = "bucket_preset:version5:force_sell_days_and_time"
        elif force_sell_policy == "time_only":
            reason = "bucket_preset:version5:force_sell_time"
        elif days_triggered:
            reason = "bucket_preset:version5:force_sell_days"
        else:
            reason = "bucket_preset:version5:force_sell_time"
        return SellPresetDecision(True, reason, False)
    if pnl >= profit_target_pct:
        return SellPresetDecision(True, "bucket_preset:version5:profit_target", False)
    return SellPresetDecision(False, None, ctx.reserved_for_limit_up)


def _eval_signal_exit(params: Mapping[str, Any], ctx: SellPresetContext) -> SellPresetDecision:
    score = ctx.model_score
    if score is None:
        return SellPresetDecision(False, None, ctx.reserved_for_limit_up)
    threshold = ctx.model_threshold
    if threshold is None:
        threshold = float(params.get("model_threshold", 0) or 0)
    if float(score) < float(threshold):
        return SellPresetDecision(
            True,
            "bucket_preset:signal_exit:below_threshold",
            ctx.reserved_for_limit_up,
        )
    return SellPresetDecision(False, None, ctx.reserved_for_limit_up)


def _register_builtin_presets() -> None:
    with _PRESET_REGISTRY_LOCK:
        _SELL_PRESET_EVALUATORS.clear()
        _SELL_PRESET_BUY_GATES.clear()
        register_sell_preset("version1", _eval_v1)
        register_sell_preset("version2", _eval_v2)
        register_sell_preset("version3", _eval_v3)
        register_sell_preset("version4", _eval_v4, buy_gate=_allow_buy_v4)
        register_sell_preset("version5", _eval_v5)
        register_sell_preset("prototype", _eval_prototype_sell)
        register_sell_preset("signal_exit", _eval_signal_exit)


def reset_sell_preset_registry() -> None:
    _register_builtin_presets()


_register_builtin_presets()

