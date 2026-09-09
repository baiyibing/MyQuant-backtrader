# -*- coding: utf-8 -*-
"""Turnover-resistance selector filter (M-004 · RFC-003 M-1).

Pure filter over a pre-loaded ``cross_section`` DataFrame — **no** Store import.
Strategy plugins load ``TurnoverResistanceStore.load_cross_section(...)`` and pass
rows here.
"""

from __future__ import annotations

from typing import Callable, Sequence

import pandas as pd

from common import ConfigurationError, ErrorCode, get_logger
from common.infra.constants import EnvVarKeys
from common.infra.runtime_config import get_raw as _cfg_raw
from oskh_factors.chip.bands import classify_tr_bb_signal
from oskh_factors.chip.constants import CANONICAL_TR_WINDOW, TRWindow
from oskh_factors.chip.window_guard import validate_tr_window_rule, warn_non_canonical_tr_window
from common.infra.strategy_env_parse_defaults_loader import load_env_parse_defaults_dict

_logger = get_logger("strategies.tr_filter")

_VALID_WINDOWS = frozenset({80, 1000})

_RULE_RESIST_TR_BB_1000 = "resist_tr_bb_1000"
_RULE_RESIST_TR_BB_80 = "resist_tr_bb_80"


def _parse_bool(raw: object | None, *, default: bool) -> bool:
    s = str(raw or "").strip().lower()
    if s in {"1", "true", "yes", "on"}:
        return True
    if s in {"0", "false", "no", "off"}:
        return False
    return default


def resolve_selector_tr_filter_enabled() -> bool:
    raw = _cfg_raw(EnvVarKeys.SELECTOR_TR_FILTER_ENABLED)
    default = _parse_bool(
        load_env_parse_defaults_dict().get(EnvVarKeys.SELECTOR_TR_FILTER_ENABLED, "false"),
        default=False,
    )
    return _parse_bool(raw, default=default)


def resolve_selector_tr_fail_closed(*, explicit: bool | None = None) -> bool:
    if explicit is not None:
        return bool(explicit)
    raw = _cfg_raw(EnvVarKeys.SELECTOR_TR_FAIL_CLOSED)
    default = _parse_bool(
        load_env_parse_defaults_dict().get(EnvVarKeys.SELECTOR_TR_FAIL_CLOSED, "true"),
        default=True,
    )
    return _parse_bool(raw, default=default)


def resolve_selector_tr_window(*, explicit: int | None = None) -> int:
    if explicit is not None:
        window = int(explicit)
    else:
        raw = _cfg_raw(EnvVarKeys.SELECTOR_TR_WINDOW)
        default_s = load_env_parse_defaults_dict().get(EnvVarKeys.SELECTOR_TR_WINDOW, "1000")
        window = int(str(raw or default_s).strip())
    if window not in _VALID_WINDOWS:
        raise ValueError(f"SELECTOR_TR_WINDOW must be 80 or 1000, got {window}")
    return window


def _validate_window_rule_pair(window: int, rule: str) -> None:
    validate_tr_window_rule(window, rule)
    if window != CANONICAL_TR_WINDOW and "_80" not in rule and "_tr80" not in rule.lower():
        raise ValueError(
            f"rule {rule!r} must include _80 suffix when window={window} "
            f"!= canonical {CANONICAL_TR_WINDOW}"
        )
    if window != CANONICAL_TR_WINDOW:
        warn_non_canonical_tr_window(window)


def _cell_missing(val: object) -> bool:
    if val is None:
        return True
    try:
        return bool(pd.isna(val))
    except (TypeError, ValueError):
        return False


def _bands_ready(row: pd.Series) -> bool:
    if _cell_missing(row.get("bands_computed_at")) or _cell_missing(row.get("tr_bb_middle")):
        return False
    return True


def _passes_resist_tr_bb(
    row: pd.Series,
    *,
    tr_abs_min: float = 20.0,
    bb_min: float = 0.5,
    tr_bb_min: float = 0.5,
) -> bool:
    if not _bands_ready(row):
        return False
    tr = row.get("turnover_resistance")
    if tr is None or _cell_missing(tr) or abs(float(tr)) <= tr_abs_min:
        return False
    bb_pos = row.get("bb_position")
    if bb_pos is None or _cell_missing(bb_pos) or float(bb_pos) < bb_min:
        return False
    tr_bb_pos = row.get("tr_bb_position")
    if tr_bb_pos is None or _cell_missing(tr_bb_pos) or float(tr_bb_pos) <= tr_bb_min:
        return False
    return True


def _passes_tr_breakout(row: pd.Series) -> bool:
    return classify_tr_bb_signal(row) == "TR_BREAKOUT"


_RULE_HANDLERS: dict[str, Callable[[pd.Series], bool]] = {
    _RULE_RESIST_TR_BB_1000: _passes_resist_tr_bb,
    _RULE_RESIST_TR_BB_80: _passes_resist_tr_bb,
    "tr_breakout": _passes_tr_breakout,
}


def apply_turnover_resistance_filter(
    candidates: Sequence[str],
    cross_section: pd.DataFrame,
    *,
    window: TRWindow = CANONICAL_TR_WINDOW,
    rule: str = _RULE_RESIST_TR_BB_1000,
    fail_closed: bool | None = None,
) -> list[str]:
    """Keep candidates that satisfy the TR rule on *cross_section* rows."""
    if window not in _VALID_WINDOWS:
        raise ValueError(f"window must be 80 or 1000, got {window}")

    _validate_window_rule_pair(int(window), rule)

    handler = _RULE_HANDLERS.get(rule)
    if handler is None:
        raise ValueError(f"unsupported TR filter rule: {rule!r}")

    fc = resolve_selector_tr_fail_closed(explicit=fail_closed)

    if cross_section is None or cross_section.empty:
        if fc:
            raise ConfigurationError(
                "TR filter fail-closed: cross_section is empty",
                error_code=ErrorCode.CFG_VALIDATION_FAILED,
                config_key="cross_section",
            )
        _logger.warning(
            "TR filter skipped: empty cross_section",
            context={"rule": rule, "window": window, "candidate_count": len(candidates)},
        )
        return list(candidates)

    by_code: dict[str, pd.Series] = {}
    for _, row in cross_section.iterrows():
        code = str(row.get("stock_code", "") or "").strip()
        if code:
            by_code[code] = row

    kept: list[str] = []
    for code in candidates:
        norm = str(code or "").strip()
        if not norm:
            continue
        row = by_code.get(norm)
        if row is None:
            if fc:
                raise ConfigurationError(
                    f"TR filter fail-closed: missing cross_section row for {norm!r}",
                    error_code=ErrorCode.CFG_VALIDATION_FAILED,
                    config_key="stock_code",
                )
            _logger.warning(
                "TR filter: candidate missing from cross_section; skipping TR gate for symbol",
                context={"stock_code": norm, "rule": rule},
            )
            kept.append(norm)
            continue
        if handler(row):
            kept.append(norm)

    return kept
