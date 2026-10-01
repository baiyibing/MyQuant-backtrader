# -*- coding: utf-8 -*-
"""Load practical-parity board/ST/tick SSOT JSON (leaf; no engine imports).

Canonical on-disk source of truth is ``docs/backtest/ssot/`` (landed by #285).
JSON ``bt_config_binding`` fields that mention ``config/*.json`` are export-era
binding labels; this repo does **not** keep a second divergent copy under
``config/``. Prefer this loader over inventing alternate paths.

Preferred profiles:
- board bands: ``myquant_er2_bt``
- pricetick: ``myquant_fen_half_up``
- ST regimes: single-document cutover (``ST_MAIN_LIMIT_PCT_SWITCH``)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping, Optional

_REPO_ROOT = Path(__file__).resolve().parents[2]
SSOT_DIR = _REPO_ROOT / "docs" / "backtest" / "ssot"

BOARD_LIMIT_BANDS_NAME = "board_limit_bands.json"
ST_LIMIT_REGIMES_NAME = "st_limit_regimes.json"
PRICETICK_LIMIT_ROUNDING_NAME = "pricetick_limit_rounding.json"

PREFERRED_BOARD_PROFILE = "myquant_er2_bt"
PREFERRED_TICK_PROFILE = "myquant_fen_half_up"

PRICE_TICK = Decimal("0.01")


@dataclass(frozen=True)
class PreferredLimitsSsot:
    """Attestation snapshot of preferred practical-parity profiles."""

    board_profile_id: str
    board_bands: tuple[Mapping[str, Any], ...]
    unknown_board_policy: str
    st_cutover_name: str
    st_cutover_date: date
    st_cutover_inclusive: bool
    tick_profile_id: str
    price_tick: Decimal
    rounding_mode: str  # ROUND_HALF_UP
    worked_example_half_up: Mapping[str, Any]


def ssot_dir(root: Optional[Path] = None) -> Path:
    """Return the canonical SSOT directory (docs/backtest/ssot)."""
    if root is None:
        return SSOT_DIR
    return Path(root) / "docs" / "backtest" / "ssot"


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"SSOT JSON missing: {path}")
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"SSOT JSON root must be object: {path}")
    return data


@lru_cache(maxsize=8)
def load_board_limit_bands(root: Optional[str] = None) -> dict[str, Any]:
    base = ssot_dir(None if root is None else Path(root))
    return _load_json(base / BOARD_LIMIT_BANDS_NAME)


@lru_cache(maxsize=8)
def load_st_limit_regimes(root: Optional[str] = None) -> dict[str, Any]:
    base = ssot_dir(None if root is None else Path(root))
    return _load_json(base / ST_LIMIT_REGIMES_NAME)


@lru_cache(maxsize=8)
def load_pricetick_limit_rounding(root: Optional[str] = None) -> dict[str, Any]:
    base = ssot_dir(None if root is None else Path(root))
    return _load_json(base / PRICETICK_LIMIT_ROUNDING_NAME)


def preferred_board_profile(root: Optional[str] = None) -> dict[str, Any]:
    doc = load_board_limit_bands(root)
    prefer = doc.get("preferred_profile") or doc.get("bt_config_binding", {}).get("prefer")
    if prefer != PREFERRED_BOARD_PROFILE:
        raise ValueError(
            f"board SSOT preferred_profile={prefer!r}; expected {PREFERRED_BOARD_PROFILE!r}"
        )
    profiles = doc.get("profiles") or {}
    profile = profiles.get(PREFERRED_BOARD_PROFILE)
    if not isinstance(profile, dict):
        raise KeyError(f"missing board profile {PREFERRED_BOARD_PROFILE!r}")
    return profile


def preferred_tick_profile(root: Optional[str] = None) -> dict[str, Any]:
    doc = load_pricetick_limit_rounding(root)
    prefer = doc.get("preferred_profile") or doc.get("bt_config_binding", {}).get("prefer")
    if prefer != PREFERRED_TICK_PROFILE:
        raise ValueError(
            f"tick SSOT preferred_profile={prefer!r}; expected {PREFERRED_TICK_PROFILE!r}"
        )
    profiles = doc.get("profiles") or {}
    profile = profiles.get(PREFERRED_TICK_PROFILE)
    if not isinstance(profile, dict):
        raise KeyError(f"missing tick profile {PREFERRED_TICK_PROFILE!r}")
    return profile


def _parse_iso_date(value: str) -> date:
    return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()


def load_preferred_limits_ssot(root: Optional[str] = None) -> PreferredLimitsSsot:
    """Load preferred board + ST cutover + fen HALF_UP attestation bundle."""
    board = preferred_board_profile(root)
    regimes = load_st_limit_regimes(root)
    tick = preferred_tick_profile(root)

    cutover = regimes.get("cutover") or {}
    cutover_date = _parse_iso_date(cutover["date"])
    bands = tuple(board.get("bands") or ())
    example = (tick.get("limit_prices") or {}).get("worked_example_half_up") or {}

    price_tick_raw = tick.get("PRICE_TICK", "0.01")
    price_tick = Decimal(str(price_tick_raw))
    rounding = str(tick.get("rounding_mode") or "")
    if rounding != "ROUND_HALF_UP":
        raise ValueError(f"tick rounding_mode={rounding!r}; expected ROUND_HALF_UP")
    if price_tick != PRICE_TICK:
        raise ValueError(f"PRICE_TICK={price_tick!r}; expected {PRICE_TICK!r}")

    return PreferredLimitsSsot(
        board_profile_id=PREFERRED_BOARD_PROFILE,
        board_bands=bands,
        unknown_board_policy=str(board.get("unknown_policy") or ""),
        st_cutover_name=str(cutover.get("name") or "ST_MAIN_LIMIT_PCT_SWITCH"),
        st_cutover_date=cutover_date,
        st_cutover_inclusive=bool(cutover.get("inclusive", True)),
        tick_profile_id=PREFERRED_TICK_PROFILE,
        price_tick=price_tick,
        rounding_mode=rounding,
        worked_example_half_up=example,
    )


def board_pct_from_ssot(code: str, root: Optional[str] = None) -> Optional[float]:
    """Mirror preferred board-band lookup from JSON (attest; not production hot path)."""
    digits = "".join(c for c in str(code) if c.isdigit())
    if not digits:
        return None
    board = preferred_board_profile(root)
    for band in board.get("bands") or []:
        prefixes = tuple(band.get("prefixes") or ())
        if digits.startswith(prefixes):
            return float(band["pct"])
    return None


# Re-export ROUND_HALF_UP so callers can assert identity without importing decimal.
ROUNDING_HALF_UP = ROUND_HALF_UP

__all__ = [
    "BOARD_LIMIT_BANDS_NAME",
    "PREFERRED_BOARD_PROFILE",
    "PREFERRED_TICK_PROFILE",
    "PRICE_TICK",
    "PRICETICK_LIMIT_ROUNDING_NAME",
    "PreferredLimitsSsot",
    "ROUNDING_HALF_UP",
    "SSOT_DIR",
    "ST_LIMIT_REGIMES_NAME",
    "board_pct_from_ssot",
    "load_board_limit_bands",
    "load_preferred_limits_ssot",
    "load_pricetick_limit_rounding",
    "load_st_limit_regimes",
    "preferred_board_profile",
    "preferred_tick_profile",
    "ssot_dir",
]
