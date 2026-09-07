"""Daily parquet download coverage scan (none/front freshness + placeholder).

Used by:
- ``scripts/data/verify_daily_download_coverage.py`` (post-download gate)
- ``scripts/data/update_adjusted_daily.py`` (refuse complete markers on gaps)
- ``scripts/data/run_daily_adjusted_fast.py`` (``--resume`` must not skip on 3-sample only)

Universe = local Hive partitions under ``period=1d/dividend_type={adjust}``
with canonical A-share codes (``\\d{6}.(SH|SZ|BJ)``). Index/ETF residue
partitions that fail ``is_canonical_symbol`` are ignored.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional, Set

import pandas as pd

from oskh_data.pandas_typing import normalize_timestamp

from oskh_data.downloader import _get_parquet_latest_date, _is_latest_bar_placeholder
from oskh_data.symbol_format import is_canonical_symbol, to_canonical_symbol, to_partition_key

# Local-partition fallback: exclude common ETF/LOF prefixes so residue Hive dirs
# do not false-fail coverage when QMT universe is unavailable.
_ETF_LIKE_PREFIXES = ("15", "16", "18", "50", "51", "56", "58")


def _looks_like_etf_or_fund(canon: str) -> bool:
    code = (canon or "").split(".", 1)[0]
    return len(code) == 6 and code[:2] in _ETF_LIKE_PREFIXES


def _canonical_sector_codes(codes: Optional[list[str]]) -> Optional[list[str]]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in codes or []:
        try:
            canon = to_canonical_symbol(str(raw).strip())
        except Exception:
            continue
        if not is_canonical_symbol(canon) or canon in seen:
            continue
        seen.add(canon)
        out.append(canon)
    if len(out) < 1000:
        return None
    return out


def try_qmt_a_share_universe() -> Optional[list[str]]:
    """Return QMT ``沪深京A股`` canonical codes, or None if unavailable/too small.

    F7（2026-09-03）：xtdata 不可得（daqmt shim 宿主）时回落下载 transport 的
    ``sector_codes``（两后端同契约）。工厂注册由调用方（scripts 层）预导入
    ``oskh_core.daqmt_download_transport`` 完成；未注册/探活失败 → 异常 → None，
    与 xtdata 不可得同语义（调用方各自 fail-fast）。
    """
    try:
        from oskh_data.qmt_xtdata import try_get_xtdata

        xtdata = try_get_xtdata()
    except Exception:
        xtdata = None
    if xtdata is not None:
        try:
            codes = xtdata.get_stock_list_in_sector("沪深京A股")
        except Exception:
            codes = None
        canon = _canonical_sector_codes(codes)
        if canon is not None:
            return canon
    try:
        from oskh_data.download_transport import (
            resolve_download_backend,
            resolve_download_transport,
        )

        if resolve_download_backend() != "xtdata":
            return _canonical_sector_codes(
                resolve_download_transport().sector_codes("沪深京A股")
            )
    except Exception:
        return None
    return None



@dataclass
class CoverageReport:
    """Coverage of one dividend_type tree vs target date."""

    adjust_type: str
    target_date: str  # YYYY-MM-DD
    total: int = 0
    fresh: int = 0
    lag: list[tuple[str, str]] = field(default_factory=list)  # (canonical, latest YYYY-MM-DD|EMPTY|ERR)
    placeholder: list[str] = field(default_factory=list)  # canonical, target bar volume=0
    empty: list[str] = field(default_factory=list)
    excluded_skip: int = 0

    @property
    def lag_count(self) -> int:
        return len(self.lag)

    @property
    def placeholder_count(self) -> int:
        return len(self.placeholder)

    @property
    def ok(self) -> bool:
        """Date-complete and no target-date placeholders among scanned symbols."""
        return self.lag_count == 0 and self.placeholder_count == 0 and self.total > 0

    def summary_line(self) -> str:
        return (
            f"{self.adjust_type}: total={self.total} fresh={self.fresh} "
            f"lag={self.lag_count} placeholder={self.placeholder_count} "
            f"empty={len(self.empty)} skip_excluded={self.excluded_skip} "
            f"ok={self.ok}"
        )


def sanitize_symbol_token(raw: object) -> str:
    """Strip BOM / whitespace from skip-list / coverage tokens.

    Excel / Notepad / PowerShell UTF-8-BOM exports may prefix the first code
    with ``\\ufeff`` (2026-07-24: ``\\ufeff688806.SH`` poisoned skip_list).
    """
    return str(raw).replace("\ufeff", "").strip()


SKIP_LIST_BASENAME = ".update_adjusted_daily_skip"


def skip_list_path(base: Path | str, target_yyyymmdd: str) -> Path:
    """Path to the daily skip-list JSON under a data container root."""
    return Path(base) / f"{SKIP_LIST_BASENAME}_{target_yyyymmdd}.json"


def resolve_skip_list_container_paths(
    *, repo_stock_data: Path | None = None
) -> list[Path]:
    """Ordered skip-list roots: E workspace container, then path-SSOT authority (F).

    When ``OSKH_SOURCE_PARQUET_ROOT`` / ``OSKH_PERIOD_1D_ROOT`` flip parquet to
    another drive, skip JSON may be written there by mistake (``--base-dir F:``).
    Callers must consult **all** roots (lesson 48).
    """
    from common.infra.data_root import resolve_data_root, resolve_source_parquet

    paths: list[Path] = []
    seen: set[str] = set()

    def _add(raw: Path | str) -> None:
        p = Path(raw).resolve()
        key = str(p)
        if key not in seen:
            seen.add(key)
            paths.append(p)

    if repo_stock_data is not None:
        _add(repo_stock_data)
    else:
        _add(resolve_data_root() / "stock_data")

    _add(resolve_source_parquet("adj_factor.parquet").parent)
    return paths


def _read_skip_file(path: Path) -> set[str]:
    import json

    if not path.is_file():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(data, list):
            return set()
        return {sanitize_symbol_token(x) for x in data if sanitize_symbol_token(x)}
    except (OSError, json.JSONDecodeError, TypeError):
        return set()


def load_daily_skip_list(
    target_yyyymmdd: str,
    *,
    repo_stock_data: Path | None = None,
    extra_bases: Iterable[Path | str] | None = None,
    sync_to_container: bool = True,
) -> set[str]:
    """Load skip list from E container, path-SSOT authority, then optional extras.

    Unions all non-empty sources. When ``sync_to_container`` is true and skip
    exists only on authority (F) or extras, mirrors the merged set onto the E
    container JSON (lesson 48: coverage gate anchors E).
    """
    containers = resolve_skip_list_container_paths(repo_stock_data=repo_stock_data)
    container = containers[0]
    bases: list[Path] = list(containers)
    seen_base = {str(p) for p in bases}
    if extra_bases:
        for raw in extra_bases:
            p = Path(raw).resolve()
            key = str(p)
            if key not in seen_base:
                seen_base.add(key)
                bases.append(p)

    merged: set[str] = set()
    for base in bases:
        merged |= _read_skip_file(skip_list_path(base, target_yyyymmdd))

    if sync_to_container and merged:
        dest = skip_list_path(container, target_yyyymmdd)
        container_codes = _read_skip_file(dest)
        if merged != container_codes:
            save_daily_skip_list(
                target_yyyymmdd,
                merged,
                repo_stock_data=repo_stock_data,
            )
    return merged


def save_daily_skip_list(
    target_yyyymmdd: str,
    codes: Iterable[str],
    *,
    repo_stock_data: Path | None = None,
    mirror_bases: Iterable[Path | str] | None = None,
) -> Path:
    """Persist skip list to E workspace container (authoritative for gates).

    Optionally mirror the same JSON to ``mirror_bases`` (e.g. custom ``--base-dir``).
    """
    import json

    containers = resolve_skip_list_container_paths(repo_stock_data=repo_stock_data)
    container = containers[0]
    normalized = sorted(
        {sanitize_symbol_token(c) for c in codes if sanitize_symbol_token(c)}
    )
    path = skip_list_path(container, target_yyyymmdd)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(normalized, ensure_ascii=False, indent=2) + "\n"
    path.write_text(text, encoding="utf-8")

    if mirror_bases:
        for raw in mirror_bases:
            alt = Path(raw).resolve()
            if alt == container.resolve():
                continue
            alt_path = skip_list_path(alt, target_yyyymmdd)
            alt_path.parent.mkdir(parents=True, exist_ok=True)
            alt_path.write_text(text, encoding="utf-8")
    return path


def _normalize_skip_keys(skip_codes: Optional[Iterable[str]]) -> Set[str]:
    """Accept canonical or partition keys; store both forms for membership."""
    out: Set[str] = set()
    if not skip_codes:
        return out
    for raw in skip_codes:
        s = sanitize_symbol_token(raw)
        if not s:
            continue
        out.add(s)
        try:
            canon = to_canonical_symbol(s)
            out.add(canon)
            out.add(to_partition_key(canon))
        except Exception:
            pass
    return out


def scan_dividend_coverage(
    base_dir: Path | str,
    adjust_type: str,
    target_date: pd.Timestamp | str | datetime,
    *,
    skip_codes: Optional[Iterable[str]] = None,
    universe: Optional[Iterable[str]] = None,
    check_placeholder: bool = True,
) -> CoverageReport:
    """Scan ``period=1d/dividend_type={adjust}`` vs ``target_date``.

    Symbols in ``skip_codes`` are excluded from lag/placeholder failure sets
    (still counted in ``excluded_skip``). Placeholders are only meaningful for
    ``none`` (has volume); for front/back, ``check_placeholder`` is ignored.

    When ``universe`` is set (recommended: QMT ``沪深京A股`` list), only those
    symbols are scored — leftover ETF/index Hive partitions are ignored so they
    cannot falsely fail the gate.
    """
    base = Path(base_dir)
    target = normalize_timestamp(pd.Timestamp(target_date))
    target_str = target.strftime("%Y-%m-%d")
    report = CoverageReport(adjust_type=adjust_type, target_date=target_str)
    skip = _normalize_skip_keys(skip_codes)
    from common.infra.data_root import resolve_period_root

    root = resolve_period_root("1d", base=base) / f"dividend_type={adjust_type}"
    if not root.is_dir():
        return report

    do_placeholder = bool(check_placeholder and adjust_type == "none")

    if universe is not None:
        candidates: list[str] = []
        for raw in universe:
            try:
                canon = to_canonical_symbol(str(raw).strip())
            except Exception:
                continue
            if is_canonical_symbol(canon):
                candidates.append(canon)
        # de-dupe preserve order
        seen: set[str] = set()
        ordered: list[str] = []
        for c in candidates:
            if c not in seen:
                seen.add(c)
                ordered.append(c)
        scan_items = ordered
    else:
        scan_items = []
        for sym_dir in root.iterdir():
            if not sym_dir.is_dir() or not sym_dir.name.startswith("symbol="):
                continue
            part = sym_dir.name.replace("symbol=", "", 1)
            try:
                canon = to_canonical_symbol(part)
            except Exception:
                continue
            if not is_canonical_symbol(canon):
                continue
            # Without an explicit universe, ignore ETF/LOF leftover partitions.
            if _looks_like_etf_or_fund(canon):
                continue
            scan_items.append(canon)

    for canon in scan_items:
        part = to_partition_key(canon)
        in_skip = canon in skip or part in skip
        if in_skip:
            report.excluded_skip += 1
            continue

        report.total += 1
        pq_path = root / f"symbol={part}" / "data.parquet"
        if not pq_path.is_file():
            report.empty.append(canon)
            report.lag.append((canon, "MISSING"))
            continue

        latest = _get_parquet_latest_date(pq_path)
        if latest is None:
            # metadata miss → light read
            try:
                df = pd.read_parquet(pq_path, columns=["time"])
                if df.empty:
                    report.empty.append(canon)
                    report.lag.append((canon, "EMPTY"))
                    continue
                latest = normalize_timestamp(pd.to_datetime(int(df["time"].max()), unit="ms"))
            except Exception:
                report.lag.append((canon, "ERR"))
                continue

        latest_n = normalize_timestamp(latest)
        if latest_n < target:
            report.lag.append((canon, latest_n.strftime("%Y-%m-%d")))
            continue

        if do_placeholder and latest_n == target and _is_latest_bar_placeholder(pq_path, target):
            report.placeholder.append(canon)
            continue

        report.fresh += 1

    return report


def coverage_allows_complete_marker(
    base_dir: Path | str,
    target_date: pd.Timestamp | str | datetime,
    *,
    skip_codes: Optional[Iterable[str]] = None,
    universe: Optional[Iterable[str]] = None,
    require_front: bool = True,
) -> tuple[bool, list[CoverageReport]]:
    """Return (ok, reports). ``ok`` requires none (and optionally front) coverage."""
    reports = [
        scan_dividend_coverage(
            base_dir,
            "none",
            target_date,
            skip_codes=skip_codes,
            universe=universe,
            check_placeholder=True,
        )
    ]
    if require_front:
        reports.append(
            scan_dividend_coverage(
                base_dir,
                "front",
                target_date,
                skip_codes=skip_codes,
                universe=universe,
                check_placeholder=False,
            )
        )
    ok = all(r.ok for r in reports)
    return ok, reports


def should_auto_path_b_repair(reports: list[CoverageReport]) -> bool:
    """True when none is fresh but front only has date lag (mirror miss).

    Lesson 49 (2026-09-04 daqmt run): mirror_front can leave ~25% front at T-1
    while none is at target; path-b-repair from disk none fixes without QMT.
    """
    none_r = next((r for r in reports if r.adjust_type == "none"), None)
    front_r = next((r for r in reports if r.adjust_type == "front"), None)
    if none_r is None or front_r is None:
        return False
    return (
        none_r.ok
        and not front_r.ok
        and front_r.lag_count > 0
        and front_r.placeholder_count == 0
    )


__all__ = [
    "CoverageReport",
    "SKIP_LIST_BASENAME",
    "coverage_allows_complete_marker",
    "load_daily_skip_list",
    "resolve_skip_list_container_paths",
    "save_daily_skip_list",
    "scan_dividend_coverage",
    "sanitize_symbol_token",
    "should_auto_path_b_repair",
    "skip_list_path",
    "try_qmt_a_share_universe",
]
