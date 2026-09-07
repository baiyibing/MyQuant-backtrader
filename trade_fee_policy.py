# -*- coding: utf-8 -*-
"""
Shared trade fee policy for business modules.

Keep fee/tax semantics consistent across:
- live_trading main loop path
- executor_stream path
- eod_reconcile / backtest (estimate layer; broker statement remains authoritative)

The first component returned by ``calculate_commission_and_stamp_tax`` aggregates
brokerage commission (rate × notional, floored by ``min_commission`` when rate > 0),
optional Shanghai A-share **transfer fee** estimate (see ``transfer_fee_rate_sh``),
and excludes stamp tax. Stamp tax applies on **SELL** for non-exempt symbols only.

**Not modeled** (use broker statements / cash queries for limits): regulatory
bundles, per-broker commission packaging, Shenzhen-specific historical quirks, etc.

``extra_fee_hook`` return values are clamped to a fraction of trade notional (see
``_EXTRA_FEE_MAX_FRACTION_OF_NOTIONAL``) to guard against misconfiguration; log DEBUG when clamped.

Integer-fen entry points (``*_from_notional_fen``) use trade notional in **fen** (1 CNY = 100 fen)
with half-up yuan quantization, for paths that already snap to exchange money units.
"""

from __future__ import annotations

import threading
from decimal import Decimal, ROUND_HALF_UP
from typing import Callable, FrozenSet, Iterable, NamedTuple, Optional, Tuple

_VALID_ACTIONS = frozenset({"BUY", "SELL"})

# Process-local dedupe set: unknown symbols taxed as stock on SELL (see ``STAMP_TAX_UNKNOWN_AS_STOCK``).
# Exposed for tests and ``live_trading._UNKNOWN_TAX_POLICY_STOCKS`` facade alias.
UNKNOWN_TAX_POLICY_STOCKS: set[str] = set()
_TAX_POLICY_LOCK = threading.Lock()

__all__ = (
    "UNKNOWN_TAX_POLICY_STOCKS",
    "build_stamp_tax_exempt_symbol_keys",
    "calculate_commission_and_stamp_tax",
    "calculate_commission_and_stamp_tax_from_notional_fen",
    "calculate_trade_fee",
    "calculate_trade_fee_from_notional_fen",
    "clear_unknown_stamp_tax_policy_dedupe_state",
    "is_stamp_tax_exempt_symbol",
    "maybe_warn_unknown_stamp_tax_treated_as_stock",
)


def clear_unknown_stamp_tax_policy_dedupe_state() -> None:
    """Clear dedupe ledger for unknown-symbol stamp warnings (tests / diagnostics)."""
    with _TAX_POLICY_LOCK:
        UNKNOWN_TAX_POLICY_STOCKS.clear()


def _debug_log_extra_fee_clamped(
    stock: str,
    action: str,
    *,
    raw_extra: float,
    capped_extra: float,
    amount_yuan: float,
    notional_fen: Optional[int] = None,
) -> None:
    """Best-effort DEBUG when ``extra_fee_hook`` return exceeds notional cap."""
    try:
        from common.infra.quant_logger import get_logger

        ctx: dict[str, object] = {
            "stock": str(stock or ""),
            "action": str(action or ""),
            "raw_extra": float(raw_extra),
            "capped_extra": float(capped_extra),
            "amount_yuan": float(amount_yuan),
        }
        if notional_fen is not None:
            ctx["notional_fen"] = int(notional_fen)
        get_logger("TRADE", "fee_policy", trace_id="SYSTEM", signal_id="N/A").debug(
            "extra_fee_hook result clamped to notional fraction cap",
            context=ctx,
        )
    except Exception as e:
        import sys

        print(
            f"[WARNING] trade_fee_policy extra_fee clamped log failed: {e}",
            file=sys.stderr,
            flush=True,
        )


def _debug_log_extra_fee_hook_failure(
    stock: str,
    action: str,
    exc: BaseException,
    *,
    notional_fen: Optional[int] = None,
) -> None:
    """Best-effort DEBUG when ``extra_fee_hook`` fails; fee path still returns 0 extra."""
    try:
        from common.infra.quant_logger import get_logger

        ctx: dict[str, object] = {
            "stock": str(stock or ""),
            "action": str(action or ""),
            "error": repr(exc),
        }
        if notional_fen is not None:
            ctx["notional_fen"] = int(notional_fen)
        get_logger("TRADE", "fee_policy", trace_id="SYSTEM", signal_id="N/A").debug(
            "extra_fee_hook failed; extra fee treated as 0",
            context=ctx,
        )
    except Exception as e:
        import sys

        print(
            f"[WARNING] trade_fee_policy extra_fee hook failure log failed: {e}",
            file=sys.stderr,
            flush=True,
        )


def maybe_warn_unknown_stamp_tax_treated_as_stock(code: str) -> None:
    """
    Log once per process when an unmatched symbol is treated as a stock for SELL-side stamp tax
    (``STAMP_TAX_UNKNOWN_AS_STOCK`` true path). Shared by Trading and Executor fee adapters.
    """
    if not code:
        return
    with _TAX_POLICY_LOCK:
        if code in UNKNOWN_TAX_POLICY_STOCKS:
            return
        UNKNOWN_TAX_POLICY_STOCKS.add(code)
    try:
        from common.infra.quant_logger import get_logger

        get_logger("TRADE", "tax_policy", trace_id="SYSTEM", signal_id="N/A").warning(
            "Stock tax policy fallback: unknown symbol treated as stock",
            context={"stock": code, "fallback_to_stock": True},
        )
    except Exception as e:
        import sys

        print(
            f"[WARNING] trade_fee_policy unknown stamp tax log failed: {e}",
            file=sys.stderr,
            flush=True,
        )


def build_stamp_tax_exempt_symbol_keys(symbols: Optional[Iterable[str]]) -> FrozenSet[str]:
    """
    Normalize explicit exempt symbols into a set of comparable keys (full code + suffix-stripped).

    Entries may be like ``510300.SH`` or ``510300``; matching uses the same normalization as ``stock``.
    """
    keys: set[str] = set()
    if not symbols:
        return frozenset(keys)
    for raw in symbols:
        s = str(raw or "").strip().upper()
        if not s:
            continue
        keys.add(s)
        if "." in s:
            keys.add(s.split(".", 1)[0])
    return frozenset(keys)


def _normalized_stock_code(stock: str) -> str:
    code = str(stock or "").strip().upper()
    if not code:
        return ""
    if "." in code:
        code = code.split(".", 1)[0]
    return code


def _stock_match_keys(stock: str) -> FrozenSet[str]:
    full = str(stock or "").strip().upper()
    if not full:
        return frozenset()
    keys = {full}
    if "." in full:
        keys.add(full.split(".", 1)[0])
    return frozenset(keys)


def _shanghai_a_share_transfer_heuristic(stock: str) -> bool:
    """
    True if ``stock`` looks like a Shanghai-listed A-share (6-digit body) for optional transfer fee.

    Heuristic only (not exchange master data): main / STAR boards commonly 600/601/603/605/688/689.
    """
    norm = _normalized_stock_code(stock)
    if len(norm) < 6:
        return False
    head6 = norm[:6]
    if not head6.isdigit():
        return False
    return head6.startswith(("600", "601", "603", "605", "688", "689"))


def is_stamp_tax_exempt_symbol(
    stock: str,
    exempt_prefixes: Iterable[str],
    unknown_as_stock: bool,
    *,
    exempt_symbol_keys: Optional[FrozenSet[str]] = None,
    on_unknown_as_stock: Optional[Callable[[str], None]] = None,
) -> bool:
    """
    Return True if sell-side stamp tax should **not** apply for this symbol.

    Precedence: explicit ``exempt_symbol_keys`` (full list / normalized) > prefix rules >
    ``unknown_as_stock`` fallback (treat unknown as stock => not exempt).
    """
    code = str(stock or "").strip().upper()
    if not code:
        return not unknown_as_stock
    if exempt_symbol_keys and (_stock_match_keys(stock) & exempt_symbol_keys):
        return True
    norm = _normalized_stock_code(stock)
    for prefix in exempt_prefixes:
        p = str(prefix or "").strip().upper()
        if p and norm.startswith(p):
            return True
    if unknown_as_stock:
        if on_unknown_as_stock is not None and norm:
            on_unknown_as_stock(norm)
        return False
    return True


# 费率上限钳制（防止异常配置导致巨额费用）
_MAX_COMMISSION_RATE = 0.1          # 10%
_MAX_STAMP_TAX_RATE = 0.01          # 1%
_MAX_TRANSFER_FEE_RATE = 0.001      # 0.1%
# Upper bound on ``extra_fee_hook`` output as a fraction of trade notional (anti foot-gun).
_EXTRA_FEE_MAX_FRACTION_OF_NOTIONAL = Decimal("0.10")

_MONEY_QUANT = Decimal("0.01")
_ZERO = Decimal("0")
_FEN_PER_YUAN = Decimal(100)
_MIN_TRANSFER_FEE_SH = Decimal("1.0")


def _validate_fee_rate_inputs(
    *,
    commission_rate: float,
    min_commission: float,
    stamp_tax_rate_stock: float,
    transfer_fee_rate_sh: float,
) -> None:
    if float(commission_rate) < 0:
        raise ValueError(f"Invalid commission_rate={commission_rate!r}; expected >= 0")
    if float(commission_rate) > _MAX_COMMISSION_RATE:
        raise ValueError(
            f"Invalid commission_rate={commission_rate!r}; expected <= {_MAX_COMMISSION_RATE}"
        )
    if float(min_commission) < 0:
        raise ValueError(f"Invalid min_commission={min_commission!r}; expected >= 0")
    if float(stamp_tax_rate_stock) < 0:
        raise ValueError(f"Invalid stamp_tax_rate_stock={stamp_tax_rate_stock!r}; expected >= 0")
    if float(stamp_tax_rate_stock) > _MAX_STAMP_TAX_RATE:
        raise ValueError(
            f"Invalid stamp_tax_rate_stock={stamp_tax_rate_stock!r}; expected <= {_MAX_STAMP_TAX_RATE}"
        )
    if float(transfer_fee_rate_sh) < 0:
        raise ValueError(f"Invalid transfer_fee_rate_sh={transfer_fee_rate_sh!r}; expected >= 0")
    if float(transfer_fee_rate_sh) > _MAX_TRANSFER_FEE_RATE:
        raise ValueError(
            f"Invalid transfer_fee_rate_sh={transfer_fee_rate_sh!r}; expected <= {_MAX_TRANSFER_FEE_RATE}"
        )


def _validate_trade_fee_inputs(
    action: str,
    volume: int,
    price: float,
    *,
    commission_rate: float,
    min_commission: float,
    stamp_tax_rate_stock: float,
    transfer_fee_rate_sh: float,
) -> str:
    act = str(action or "").strip().upper()
    if act not in _VALID_ACTIONS:
        raise ValueError(f"Invalid action={action!r}; expected BUY or SELL")
    if int(volume) <= 0:
        raise ValueError(f"Invalid volume={volume!r}; expected > 0")
    if float(price) <= 0:
        raise ValueError(f"Invalid price={price!r}; expected > 0")
    _validate_fee_rate_inputs(
        commission_rate=commission_rate,
        min_commission=min_commission,
        stamp_tax_rate_stock=stamp_tax_rate_stock,
        transfer_fee_rate_sh=transfer_fee_rate_sh,
    )
    return act


def _validate_trade_fee_inputs_from_notional_fen(
    action: str,
    volume: int,
    notional_fen: int,
    *,
    commission_rate: float,
    min_commission: float,
    stamp_tax_rate_stock: float,
    transfer_fee_rate_sh: float,
) -> str:
    act = str(action or "").strip().upper()
    if act not in _VALID_ACTIONS:
        raise ValueError(f"Invalid action={action!r}; expected BUY or SELL")
    if int(volume) <= 0:
        raise ValueError(f"Invalid volume={volume!r}; expected > 0")
    if int(notional_fen) <= 0:
        raise ValueError(f"Invalid notional_fen={notional_fen!r}; expected > 0")
    _validate_fee_rate_inputs(
        commission_rate=commission_rate,
        min_commission=min_commission,
        stamp_tax_rate_stock=stamp_tax_rate_stock,
        transfer_fee_rate_sh=transfer_fee_rate_sh,
    )
    return act


def _implied_price_yuan_from_notional_fen(notional_fen: int, volume: int) -> float:
    """VWAP-style yuan price from integer fen notional and volume; quantized to 0.01 CNY/share."""
    if int(volume) <= 0:
        return 0.0
    amt = Decimal(int(notional_fen)) / _FEN_PER_YUAN
    vol = Decimal(int(volume))
    px = (amt / vol).quantize(_MONEY_QUANT, rounding=ROUND_HALF_UP)
    return float(px)


class _FeeKernelResult(NamedTuple):
    commission: Decimal
    stamp_tax: Decimal
    total: Decimal


def _calculate_fee_kernel(
    action_norm: str,
    stock: str,
    amount_yuan: Decimal,
    *,
    commission_rate: Decimal,
    min_commission: Decimal,
    stamp_tax_rate_stock: Decimal,
    stamp_tax_exempt_prefixes: Iterable[str],
    stamp_tax_unknown_as_stock: bool,
    stamp_tax_exempt_symbol_keys: Optional[FrozenSet[str]] = None,
    on_unknown_stamp_tax_as_stock: Optional[Callable[[str], None]] = None,
    transfer_fee_rate_sh: Decimal = _ZERO,
    extra_fee_hook: Optional[Callable[..., float]] = None,
    hook_action: Optional[str] = None,
    hook_volume: Optional[int] = None,
    hook_price: object = None,
    notional_fen: Optional[int] = None,
) -> _FeeKernelResult:
    """Calculate every fee component and total without leaving Decimal money arithmetic."""
    commission = _ZERO
    if commission_rate > _ZERO:
        commission = amount_yuan * commission_rate
        if commission < min_commission:
            commission = min_commission
        commission = commission.quantize(_MONEY_QUANT, rounding=ROUND_HALF_UP)

    transfer_sh = _ZERO
    if (
        transfer_fee_rate_sh > _ZERO
        and _shanghai_a_share_transfer_heuristic(stock)
    ):
        transfer_sh = (amount_yuan * transfer_fee_rate_sh).quantize(
            _MONEY_QUANT, rounding=ROUND_HALF_UP
        )
        if transfer_sh < _MIN_TRANSFER_FEE_SH:
            transfer_sh = _MIN_TRANSFER_FEE_SH

    commission_total = (commission + transfer_sh).quantize(
        _MONEY_QUANT, rounding=ROUND_HALF_UP
    )

    stamp_tax = _ZERO
    if action_norm == "SELL" and not is_stamp_tax_exempt_symbol(
        stock,
        stamp_tax_exempt_prefixes,
        stamp_tax_unknown_as_stock,
        exempt_symbol_keys=stamp_tax_exempt_symbol_keys,
        on_unknown_as_stock=on_unknown_stamp_tax_as_stock,
    ):
        stamp_tax = (amount_yuan * stamp_tax_rate_stock).quantize(
            _MONEY_QUANT, rounding=ROUND_HALF_UP
        )

    extra_fee = _ZERO
    if callable(extra_fee_hook):
        action_for_hook = action_norm if hook_action is None else hook_action
        try:
            raw_extra = float(
                extra_fee_hook(
                    action=action_for_hook,
                    stock=stock,
                    volume=hook_volume,
                    price=hook_price,
                    commission=float(commission_total),
                    stamp_tax=float(stamp_tax),
                )
            )
            extra_fee = Decimal(str(raw_extra))
        except Exception as e:
            _debug_log_extra_fee_hook_failure(
                stock,
                action_for_hook,
                e,
                notional_fen=notional_fen,
            )
            extra_fee = _ZERO

        if extra_fee < _ZERO:
            extra_fee = _ZERO
        cap = amount_yuan * _EXTRA_FEE_MAX_FRACTION_OF_NOTIONAL
        if extra_fee > cap:
            _debug_log_extra_fee_clamped(
                stock,
                action_for_hook,
                raw_extra=float(extra_fee),
                capped_extra=float(cap),
                amount_yuan=float(amount_yuan),
                notional_fen=notional_fen,
            )
            extra_fee = cap.quantize(_MONEY_QUANT, rounding=ROUND_HALF_UP)

    total = (commission_total + stamp_tax + extra_fee).quantize(
        _MONEY_QUANT, rounding=ROUND_HALF_UP
    )
    return _FeeKernelResult(commission_total, stamp_tax, total)


def calculate_commission_and_stamp_tax(
    action: str,
    stock: str,
    volume: int,
    price: float,
    *,
    commission_rate: float,
    min_commission: float,
    stamp_tax_rate_stock: float,
    stamp_tax_exempt_prefixes: Iterable[str],
    stamp_tax_unknown_as_stock: bool,
    stamp_tax_exempt_symbol_keys: Optional[FrozenSet[str]] = None,
    on_unknown_stamp_tax_as_stock: Optional[Callable[[str], None]] = None,
    transfer_fee_rate_sh: float = 0.0,
) -> Tuple[float, float]:
    """
    Return (commission_plus_transfer_sh, stamp_tax) for the trade; stamp_tax is 0 for BUY.

    When ``transfer_fee_rate_sh`` > 0, an additional estimate is added for symbols matching
    the Shanghai A-share heuristic (both BUY and SELL).
    """
    action_norm = _validate_trade_fee_inputs(
        action,
        volume,
        price,
        commission_rate=commission_rate,
        min_commission=min_commission,
        stamp_tax_rate_stock=stamp_tax_rate_stock,
        transfer_fee_rate_sh=transfer_fee_rate_sh,
    )
    amount_yuan = Decimal(int(volume)) * Decimal(str(price))
    result = _calculate_fee_kernel(
        action_norm,
        stock,
        amount_yuan,
        commission_rate=Decimal(str(commission_rate)),
        min_commission=Decimal(str(min_commission)),
        stamp_tax_rate_stock=Decimal(str(stamp_tax_rate_stock)),
        stamp_tax_exempt_prefixes=stamp_tax_exempt_prefixes,
        stamp_tax_unknown_as_stock=stamp_tax_unknown_as_stock,
        stamp_tax_exempt_symbol_keys=stamp_tax_exempt_symbol_keys,
        on_unknown_stamp_tax_as_stock=on_unknown_stamp_tax_as_stock,
        transfer_fee_rate_sh=Decimal(str(transfer_fee_rate_sh)),
    )
    return float(result.commission), float(result.stamp_tax)


def calculate_commission_and_stamp_tax_from_notional_fen(
    action: str,
    stock: str,
    volume: int,
    notional_fen: int,
    *,
    commission_rate: float,
    min_commission: float,
    stamp_tax_rate_stock: float,
    stamp_tax_exempt_prefixes: Iterable[str],
    stamp_tax_unknown_as_stock: bool,
    stamp_tax_exempt_symbol_keys: Optional[FrozenSet[str]] = None,
    on_unknown_stamp_tax_as_stock: Optional[Callable[[str], None]] = None,
    transfer_fee_rate_sh: float = 0.0,
) -> Tuple[float, float]:
    """
    Same semantics as ``calculate_commission_and_stamp_tax``, but trade notional is supplied as
    integer **fen** (1 CNY = 100 fen) to avoid ``volume * price`` float round-trip.

    ``volume`` is still validated (> 0) for call-site consistency and optional extensions.
    """
    action_norm = _validate_trade_fee_inputs_from_notional_fen(
        action,
        volume,
        notional_fen,
        commission_rate=commission_rate,
        min_commission=min_commission,
        stamp_tax_rate_stock=stamp_tax_rate_stock,
        transfer_fee_rate_sh=transfer_fee_rate_sh,
    )
    amount_yuan = Decimal(int(notional_fen)) / _FEN_PER_YUAN
    result = _calculate_fee_kernel(
        action_norm,
        stock,
        amount_yuan,
        commission_rate=Decimal(str(commission_rate)),
        min_commission=Decimal(str(min_commission)),
        stamp_tax_rate_stock=Decimal(str(stamp_tax_rate_stock)),
        stamp_tax_exempt_prefixes=stamp_tax_exempt_prefixes,
        stamp_tax_unknown_as_stock=stamp_tax_unknown_as_stock,
        stamp_tax_exempt_symbol_keys=stamp_tax_exempt_symbol_keys,
        on_unknown_stamp_tax_as_stock=on_unknown_stamp_tax_as_stock,
        transfer_fee_rate_sh=Decimal(str(transfer_fee_rate_sh)),
    )
    return float(result.commission), float(result.stamp_tax)


def calculate_trade_fee(
    action: str,
    stock: str,
    volume: int,
    price: float,
    *,
    commission_rate: float,
    min_commission: float,
    stamp_tax_rate_stock: float,
    stamp_tax_exempt_prefixes: Iterable[str],
    stamp_tax_unknown_as_stock: bool,
    stamp_tax_exempt_symbol_keys: Optional[FrozenSet[str]] = None,
    on_unknown_stamp_tax_as_stock: Optional[Callable[[str], None]] = None,
    extra_fee_hook: Optional[Callable[..., float]] = None,
    transfer_fee_rate_sh: float = 0.0,
) -> float:
    action_norm = _validate_trade_fee_inputs(
        action,
        volume,
        price,
        commission_rate=commission_rate,
        min_commission=min_commission,
        stamp_tax_rate_stock=stamp_tax_rate_stock,
        transfer_fee_rate_sh=transfer_fee_rate_sh,
    )
    amount_yuan = Decimal(int(volume)) * Decimal(str(price))
    result = _calculate_fee_kernel(
        action_norm,
        stock,
        amount_yuan,
        commission_rate=Decimal(str(commission_rate)),
        min_commission=Decimal(str(min_commission)),
        stamp_tax_rate_stock=Decimal(str(stamp_tax_rate_stock)),
        stamp_tax_exempt_prefixes=stamp_tax_exempt_prefixes,
        stamp_tax_unknown_as_stock=stamp_tax_unknown_as_stock,
        stamp_tax_exempt_symbol_keys=stamp_tax_exempt_symbol_keys,
        on_unknown_stamp_tax_as_stock=on_unknown_stamp_tax_as_stock,
        transfer_fee_rate_sh=Decimal(str(transfer_fee_rate_sh)),
        extra_fee_hook=extra_fee_hook,
        hook_action=action,
        hook_volume=volume,
        hook_price=price,
    )
    return float(result.total)


def calculate_trade_fee_from_notional_fen(
    action: str,
    stock: str,
    volume: int,
    notional_fen: int,
    *,
    commission_rate: float,
    min_commission: float,
    stamp_tax_rate_stock: float,
    stamp_tax_exempt_prefixes: Iterable[str],
    stamp_tax_unknown_as_stock: bool,
    stamp_tax_exempt_symbol_keys: Optional[FrozenSet[str]] = None,
    on_unknown_stamp_tax_as_stock: Optional[Callable[[str], None]] = None,
    extra_fee_hook: Optional[Callable[..., float]] = None,
    transfer_fee_rate_sh: float = 0.0,
) -> float:
    action_norm = _validate_trade_fee_inputs_from_notional_fen(
        action,
        volume,
        notional_fen,
        commission_rate=commission_rate,
        min_commission=min_commission,
        stamp_tax_rate_stock=stamp_tax_rate_stock,
        transfer_fee_rate_sh=transfer_fee_rate_sh,
    )
    notional_fen_int = int(notional_fen)
    amount_yuan = Decimal(notional_fen_int) / _FEN_PER_YUAN
    hook_price = (
        _implied_price_yuan_from_notional_fen(notional_fen_int, int(volume))
        if callable(extra_fee_hook)
        else None
    )
    result = _calculate_fee_kernel(
        action_norm,
        stock,
        amount_yuan,
        commission_rate=Decimal(str(commission_rate)),
        min_commission=Decimal(str(min_commission)),
        stamp_tax_rate_stock=Decimal(str(stamp_tax_rate_stock)),
        stamp_tax_exempt_prefixes=stamp_tax_exempt_prefixes,
        stamp_tax_unknown_as_stock=stamp_tax_unknown_as_stock,
        stamp_tax_exempt_symbol_keys=stamp_tax_exempt_symbol_keys,
        on_unknown_stamp_tax_as_stock=on_unknown_stamp_tax_as_stock,
        transfer_fee_rate_sh=Decimal(str(transfer_fee_rate_sh)),
        extra_fee_hook=extra_fee_hook,
        hook_action=action,
        hook_volume=volume,
        hook_price=hook_price,
        notional_fen=notional_fen_int,
    )
    return float(result.total)
