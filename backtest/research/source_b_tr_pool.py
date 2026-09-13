"""名单源 B：``resist_tr_bb_1000`` → 契约日 CSV（策略 10）。

截面必须是买入日 T 当天、且 ``trade_date<=T``。不写 ``stock_pool/``，
不 import qlib。全市场 Store 实跑是宿主，不是合入门。
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Iterable, Mapping, Sequence

import pandas as pd

from backtest.research.csv_pool import is_repo_stock_pool
from oskh_core.a_share_symbol_normalize import canonical_from_bare_code
from oskh_data.symbol_format import to_canonical_symbol
from strategies.tr_filter import ConfigurationError, apply_turnover_resistance_filter

RULE = "resist_tr_bb_1000"
WINDOW = 1000


def normalize_stock_code(code: str) -> str:
    """Store / lake / CSV dialects → canonical ``XXXXXX.SH|SZ|BJ``."""
    raw = str(code or "").strip()
    if not raw:
        return ""
    if raw.startswith("symbol="):
        raw = raw[len("symbol=") :]
    if "_" in raw and "." not in raw:
        raw = to_canonical_symbol(raw)
    if "." in raw:
        return raw
    digits = "".join(ch for ch in raw if ch.isdigit())
    if len(digits) < 6:
        return ""
    return canonical_from_bare_code(digits[:6]) or ""


def _normalized_frame(cross_section: pd.DataFrame) -> pd.DataFrame:
    frame = pd.DataFrame(cross_section).copy()
    if frame.empty:
        return frame
    if "stock_code" not in frame.columns:
        raise ValueError("cross_section missing stock_code")
    frame["stock_code"] = frame["stock_code"].map(normalize_stock_code)
    frame = frame[frame["stock_code"].astype(bool)]
    return frame


def assert_section_asof(cross_section: pd.DataFrame, ymd: str) -> None:
    """Reject rows whose trade_date is after T (look-ahead)."""
    if cross_section is None or cross_section.empty:
        return
    if "trade_date" not in cross_section.columns:
        return
    dates = cross_section["trade_date"].astype(str).str.replace("-", "", regex=False)
    if (dates > str(ymd)).any():
        raise ValueError(f"cross_section for {ymd} contains trade_date after T")


def filter_day(
    universe: Sequence[str],
    cross_section: pd.DataFrame,
    *,
    fail_closed: bool = True,
) -> list[str]:
    """Keep universe codes that pass ``resist_tr_bb_1000`` on T's section."""
    ymd_codes = [normalize_stock_code(code) for code in universe]
    ymd_codes = [code for code in ymd_codes if code]
    section = _normalized_frame(cross_section)
    return apply_turnover_resistance_filter(
        ymd_codes,
        section,
        window=WINDOW,
        rule=RULE,
        fail_closed=fail_closed,
    )


def unique_preserve(codes: Iterable[str]) -> list[str]:
    """De-dup while keeping first-seen order (filter / lake / file order)."""
    out: list[str] = []
    seen: set[str] = set()
    for raw in codes:
        code = normalize_stock_code(raw)
        if not code or code in seen:
            continue
        seen.add(code)
        out.append(code)
    return out


def scan_tr_days(
    dates: Sequence[str],
    *,
    load_cross_section: Callable[[str], pd.DataFrame],
    universe_for: Callable[[str], Sequence[str]],
    fail_closed: bool = True,
) -> dict[str, list[str]]:
    """``{YYYYMMDD: [canonical codes]}``; empty days omitted.

    ``universe_for(T)`` is required (B-R4). Do not default to store members.
    """
    if universe_for is None:
        raise TypeError("universe_for is required (B-R4 lake or --universe-file)")
    out: dict[str, list[str]] = {}
    for raw in dates:
        ymd = str(raw).replace("-", "")
        section = load_cross_section(ymd)
        if section is None:
            section = pd.DataFrame()
        else:
            section = pd.DataFrame(section)
        assert_section_asof(section, ymd)
        universe = unique_preserve(universe_for(ymd))
        if not universe:
            continue
        if section.empty:
            if fail_closed:
                raise ConfigurationError(
                    f"TR filter fail-closed: empty cross_section for {ymd}",
                    config_key="cross_section",
                )
            continue
        kept = unique_preserve(filter_day(universe, section, fail_closed=fail_closed))
        if kept:
            out[ymd] = kept
    return out


def bares_from_canonical(codes: Sequence[str]) -> list[str]:
    return [str(code).split(".", 1)[0] for code in codes]


def write_tr_pool(
    days: Mapping[str, Sequence[str]],
    out_dir: Path,
    *,
    repo: Path,
) -> list[Path]:
    """Write contract CSVs (bare six-digit, LF, no BOM)."""
    out_root = Path(out_dir)
    if is_repo_stock_pool(out_root, repo=repo):
        raise SystemExit(f"refusing to write into stock_pool/: {out_root}")
    out_root.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for ymd in sorted(days):
        bares = [
            bare
            for bare in bares_from_canonical(days[ymd])
            if bare.isdigit() and len(bare) == 6
        ]
        if not bares:
            continue
        dest = out_root / f"{ymd}.csv"
        dest.write_text(
            "".join(f"{code}\n" for code in bares),
            encoding="utf-8",
            newline="\n",
        )
        written.append(dest)
    return written
