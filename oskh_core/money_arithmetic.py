# -*- coding: utf-8 -*-
"""
人民币金额算术：分/元换算、舍入策略、按比例分摊。

纯算术模块 — 无 DB 连接、无 I/O、无副作用（舍入策略配置除外）。
独立于持久化层，供 ``oskh_core``、``trade_decision``、``oskh_db`` 等包直接导入。

原位置 ``oskh_db/money_sqlite.py`` 中的纯算术部分；``oskh_db/money_sqlite.py``
仍保留 ``decode_execution_log_row``（DB 行解码）并 re-export 本模块的全部符号，
保持向后兼容。
"""

from __future__ import annotations

import threading
from decimal import (
    Decimal,
    InvalidOperation,
    ROUND_DOWN,
    ROUND_HALF_EVEN,
    ROUND_HALF_UP,
)
from typing import Any, Optional

from common.infra.constants import EnvVarKeys
from common.infra.runtime_config import get_raw as _runtime_cfg_raw

YUAN_PER_FEN = 100
_FEN_QUANT = Decimal("1")
_YUAN_TO_FEN_FACTOR = Decimal(str(YUAN_PER_FEN))
ROUNDING_STRATEGY_ENV = EnvVarKeys.MONEY_SQLITE_ROUNDING
_ROUNDING_MAP = {
    "HALF_UP": ROUND_HALF_UP,
    "HALF_EVEN": ROUND_HALF_EVEN,
    "DOWN": ROUND_DOWN,
}
_rounding_lock = threading.Lock()
_current_rounding_strategy = "HALF_UP"
_current_rounding_mode = ROUND_HALF_UP


def _normalize_rounding_strategy(raw: Any) -> str:
    s = str(raw or "").strip().upper()
    return s if s else "HALF_UP"


def set_money_rounding_strategy(strategy: str) -> None:
    global _current_rounding_strategy, _current_rounding_mode
    key = _normalize_rounding_strategy(strategy)
    mode = _ROUNDING_MAP.get(key)
    if mode is None:
        raise ValueError(
            f"unsupported money rounding strategy: {strategy!r} "
            f"(allowed: {', '.join(sorted(_ROUNDING_MAP.keys()))})"
        )
    with _rounding_lock:
        _current_rounding_strategy = key
        _current_rounding_mode = mode


def get_money_rounding_strategy() -> str:
    with _rounding_lock:
        return _current_rounding_strategy


def _money_rounding_mode():
    with _rounding_lock:
        return _current_rounding_mode


def _to_decimal(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        d = value
    else:
        try:
            d = Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError) as e:
            raise ValueError(f"invalid money value: {value!r}") from e
    if not d.is_finite():
        raise ValueError(f"non-finite money value: {value!r}")
    return d


def yuan_to_fen(yuan: Any) -> int:
    """Convert yuan amount to fen; accepts float, Decimal, int, str (via ``_to_decimal``)."""
    d = _to_decimal(yuan)
    return int((d * _YUAN_TO_FEN_FACTOR).quantize(_FEN_QUANT, rounding=_money_rounding_mode()))


def fen_to_yuan(fen: Any) -> float:
    # P1-12: NULL 金额禁止隐式回退为 0——金额域内 None ≠ 0 元
    if fen is None:
        raise ValueError(
            "fen_to_yuan: NULL fen is not a valid amount; "
            "use fen_to_yuan_optional if None is expected"
        )
    return int(fen) / YUAN_PER_FEN


def fen_to_yuan_optional(fen: Any) -> Optional[float]:
    if fen is None:
        return None
    return int(fen) / YUAN_PER_FEN


def yuan_snap_fen(yuan: float) -> float:
    """将元金额对齐到「分」再转回元，减少 SQLite REAL 累加漂移。"""
    return fen_to_yuan(yuan_to_fen(yuan))


def yuan_net_after_fee(gross_yuan: float, fee_yuan: float) -> float:
    """卖侧净所得：毛利 − 手续费（各环节按分取整）。"""
    g = yuan_to_fen(gross_yuan)
    f = yuan_to_fen(fee_yuan)
    return fen_to_yuan(max(0, g - f))


def allocate_cost_fen(total_cost_fen: int, part_qty: int, total_qty: int) -> int:
    """
    按数量比例从总成本（分）中切分；卖光整批时取尽剩余分，避免舍入残差。
    """
    total_cost_fen = int(total_cost_fen)
    part_qty = int(part_qty)
    total_qty = int(total_qty)
    if total_qty <= 0 or part_qty <= 0:
        return 0
    if part_qty >= total_qty:
        return total_cost_fen
    if total_cost_fen == 0:
        return 0
    sign = -1 if total_cost_fen < 0 else 1
    abs_cost = abs(total_cost_fen)
    alloc = int(
        (Decimal(abs_cost) * Decimal(part_qty) / Decimal(total_qty)).quantize(
            _FEN_QUANT, rounding=_money_rounding_mode()
        )
    )
    return sign * alloc


# Import-time bootstrap from environment (invalid values fall back to HALF_UP).
try:
    set_money_rounding_strategy(_runtime_cfg_raw(ROUNDING_STRATEGY_ENV) or "HALF_UP")
except ValueError:
    set_money_rounding_strategy("HALF_UP")
