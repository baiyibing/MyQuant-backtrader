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
from typing import Callable, FrozenSet, Iterable, Optional, Tuple

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


def _commission_amount(amount: float, commission_rate: float, min_commission: float, max_commission: Optional[float] = None) -> float:
    amt = Decimal(str(float(amount)))
    rate = Decimal(str(float(commission_rate)))
    min_fee = Decimal(str(float(min_commission)))
    if rate <= Decimal("0"):
        return 0.0
    fee = amt * rate
    if fee < min_fee:
        fee = min_fee
    if max_commission is not None:
        max_fee = Decimal(str(float(max_commission)))
        if fee > max_fee:
            fee = max_fee
    return float(fee.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _transfer_fee_sh_amount(
    amount: float,
    stock: str,
    transfer_fee_rate_sh: float,
    min_transfer_fee: float = 1.0,
) -> float:
    if float(transfer_fee_rate_sh) <= 0:
        return 0.0
    if not _shanghai_a_share_transfer_heuristic(stock):
        return 0.0
    raw = Decimal(str(float(amount))) * Decimal(str(float(transfer_fee_rate_sh)))
    fee = raw.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    min_fee = Decimal(str(float(min_transfer_fee)))
    if fee < min_fee:
        fee = min_fee
    return float(fee)


# 费率上限钳制（防止异常配置导致巨额费用）
_MAX_COMMISSION_RATE = 0.1          # 10%
_MAX_STAMP_TAX_RATE = 0.01          # 1%
_MAX_TRANSFER_FEE_RATE = 0.001      # 0.1%
# Upper bound on ``extra_fee_hook`` output as a fraction of trade notional (anti foot-gun).
_EXTRA_FEE_MAX_FRACTION_OF_NOTIONAL = 0.10


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


def _notional_yuan_from_fen(notional_fen: int) -> float:
    return float(
        (Decimal(int(notional_fen)) / Decimal(100)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    )


def _implied_price_yuan_from_notional_fen(notional_fen: int, volume: int) -> float:
    """VWAP-style yuan price from integer fen notional and volume; quantized to 0.01 CNY/share."""
    if int(volume) <= 0:
        return 0.0
    amt = Decimal(int(notional_fen)) / Decimal(100)
    vol = Decimal(int(volume))
    px = (amt / vol).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return float(px)


def _clamp_extra_fee_to_notional(
    extra_fee: float,
    amount_yuan: float,
    *,
    stock: str,
    action: str,
    notional_fen: Optional[int] = None,
) -> float:
    if extra_fee <= 0:
        return 0.0
    amt = float(amount_yuan)
    if amt <= 0:
        return 0.0
    cap = amt * float(_EXTRA_FEE_MAX_FRACTION_OF_NOTIONAL)
    if extra_fee > cap:
        _debug_log_extra_fee_clamped(
            stock,
            action,
            raw_extra=extra_fee,
            capped_extra=cap,
            amount_yuan=amt,
            notional_fen=notional_fen,
        )
        return float(Decimal(str(cap)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    return float(extra_fee)


def _commission_and_stamp_from_amount_yuan(
    action_norm: str,
    stock: str,
    amount: float,
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
    commission = _commission_amount(amount, commission_rate, min_commission)
    transfer_sh = _transfer_fee_sh_amount(amount, stock, transfer_fee_rate_sh)
    commission_total = float(
        (Decimal(str(commission)) + Decimal(str(transfer_sh))).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
    )
    if action_norm != "SELL":
        return commission_total, 0.0
    if is_stamp_tax_exempt_symbol(
        stock,
        stamp_tax_exempt_prefixes,
        stamp_tax_unknown_as_stock,
        exempt_symbol_keys=stamp_tax_exempt_symbol_keys,
        on_unknown_as_stock=on_unknown_stamp_tax_as_stock,
    ):
        return commission_total, 0.0
    stamp_tax = Decimal(str(amount)) * Decimal(str(float(stamp_tax_rate_stock)))
    return commission_total, float(stamp_tax.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


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
    amount = float(Decimal(str(int(volume))) * Decimal(str(float(price))))
    return _commission_and_stamp_from_amount_yuan(
        action_norm,
        stock,
        amount,
        commission_rate=commission_rate,
        min_commission=min_commission,
        stamp_tax_rate_stock=stamp_tax_rate_stock,
        stamp_tax_exempt_prefixes=stamp_tax_exempt_prefixes,
        stamp_tax_unknown_as_stock=stamp_tax_unknown_as_stock,
        stamp_tax_exempt_symbol_keys=stamp_tax_exempt_symbol_keys,
        on_unknown_stamp_tax_as_stock=on_unknown_stamp_tax_as_stock,
        transfer_fee_rate_sh=transfer_fee_rate_sh,
    )


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
    amount = _notional_yuan_from_fen(int(notional_fen))
    return _commission_and_stamp_from_amount_yuan(
        action_norm,
        stock,
        amount,
        commission_rate=commission_rate,
        min_commission=min_commission,
        stamp_tax_rate_stock=stamp_tax_rate_stock,
        stamp_tax_exempt_prefixes=stamp_tax_exempt_prefixes,
        stamp_tax_unknown_as_stock=stamp_tax_unknown_as_stock,
        stamp_tax_exempt_symbol_keys=stamp_tax_exempt_symbol_keys,
        on_unknown_stamp_tax_as_stock=on_unknown_stamp_tax_as_stock,
        transfer_fee_rate_sh=transfer_fee_rate_sh,
    )


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
    com, tax = calculate_commission_and_stamp_tax(
        action,
        stock,
        volume,
        price,
        commission_rate=commission_rate,
        min_commission=min_commission,
        stamp_tax_rate_stock=stamp_tax_rate_stock,
        stamp_tax_exempt_prefixes=stamp_tax_exempt_prefixes,
        stamp_tax_unknown_as_stock=stamp_tax_unknown_as_stock,
        stamp_tax_exempt_symbol_keys=stamp_tax_exempt_symbol_keys,
        on_unknown_stamp_tax_as_stock=on_unknown_stamp_tax_as_stock,
        transfer_fee_rate_sh=transfer_fee_rate_sh,
    )
    extra_fee = 0.0
    if callable(extra_fee_hook):
        amount = float(Decimal(str(int(volume))) * Decimal(str(float(price))))
        try:
            extra_fee = float(
                extra_fee_hook(
                    action=action,
                    stock=stock,
                    volume=volume,
                    price=price,
                    commission=float(com),
                    stamp_tax=float(tax),
                )
            )
        except Exception as e:
            _debug_log_extra_fee_hook_failure(stock, action, e)
            extra_fee = 0.0
        if extra_fee < 0:
            extra_fee = 0.0
        extra_fee = _clamp_extra_fee_to_notional(
            extra_fee, amount, stock=stock, action=str(action)
        )
    return float(com + tax + extra_fee)


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
    com, tax = calculate_commission_and_stamp_tax_from_notional_fen(
        action,
        stock,
        volume,
        notional_fen,
        commission_rate=commission_rate,
        min_commission=min_commission,
        stamp_tax_rate_stock=stamp_tax_rate_stock,
        stamp_tax_exempt_prefixes=stamp_tax_exempt_prefixes,
        stamp_tax_unknown_as_stock=stamp_tax_unknown_as_stock,
        stamp_tax_exempt_symbol_keys=stamp_tax_exempt_symbol_keys,
        on_unknown_stamp_tax_as_stock=on_unknown_stamp_tax_as_stock,
        transfer_fee_rate_sh=transfer_fee_rate_sh,
    )
    amount = _notional_yuan_from_fen(int(notional_fen))
    extra_fee = 0.0
    if callable(extra_fee_hook):
        try:
            px = _implied_price_yuan_from_notional_fen(int(notional_fen), int(volume))
            extra_fee = float(
                extra_fee_hook(
                    action=action,
                    stock=stock,
                    volume=volume,
                    price=float(px),
                    commission=float(com),
                    stamp_tax=float(tax),
                )
            )
        except Exception as e:
            _debug_log_extra_fee_hook_failure(
                stock, action, e, notional_fen=int(notional_fen)
            )
            extra_fee = 0.0
        if extra_fee < 0:
            extra_fee = 0.0
        extra_fee = _clamp_extra_fee_to_notional(
            extra_fee,
            amount,
            stock=stock,
            action=str(action),
            notional_fen=int(notional_fen),
        )
    return float(com + tax + extra_fee)
