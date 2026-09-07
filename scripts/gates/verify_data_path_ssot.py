#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""D4 path-SSOT gate for this slim fork.

Parquet path construction in ``oskh_data/``, ``oskh_factors/``, and ``scripts/``
must go through ``common/infra/data_root.py``. Frozen ``backtest/`` is not scanned.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Dict, List, Pattern, Tuple

_HERE = Path(__file__).resolve()
REPO_ROOT = _HERE.parents[2] if _HERE.parent.name in {"gates", "diagnostics", "data", "ops"} else _HERE.parents[1]

_SCAN_DIRS = ("oskh_data", "oskh_factors", "scripts")

# (tag, expected_hits) — fill after first scan; keep only remaining debt.
_ALLOWLIST: Dict[str, Tuple[str, int]] = {
    "oskh_data/freshness.py": ("LABEL_NONPATH", 1),
    "scripts/backfill_turnover_resistance_bands.py": ("LEGIT_TR", 1),
    "scripts/update_adjusted_daily.py": ("LABEL_NONPATH", 1),
}

_PATTERNS: List[Pattern[str]] = [
    re.compile(r"""["']period=1d["']"""),
    re.compile(r"""["']period=1m["']"""),
    re.compile(r"period=\{"),
    re.compile(
        r"""["'](adj_factor|float_shares|free_float_shares|"""
        r"""turnover_resistance_daily|ex_date_index)\.parquet["']"""
    ),
]
_RESOLVER_MARK = re.compile(
    r"resolve_period_root|resolve_source_parquet|stock_data_path|"
    r"resolve_parquet_container|resolve_turnover_resist_parquet_root|"
    r"resolve_tr_staging_dir"
)

_LOOSE_WRITE_BAN_FILES = (
    "scripts/update_adjusted_daily.py",
)
_EXPLICIT_ROOT_CALL = re.compile(r"resolve_source_parquet\([^\n]*explicit_root\s*=")


def _iter_py_files() -> List[Path]:
    out: List[Path] = []
    for d in _SCAN_DIRS:
        base = REPO_ROOT / d
        if not base.is_dir():
            continue
        out.extend(sorted(base.rglob("*.py")))
    return out


def scan_hits() -> Dict[str, List[Tuple[int, str]]]:
    hits: Dict[str, List[Tuple[int, str]]] = {}
    self_rel = Path(__file__).resolve().relative_to(REPO_ROOT).as_posix()
    for f in _iter_py_files():
        rel = f.relative_to(REPO_ROOT).as_posix()
        if rel == self_rel:
            continue
        try:
            lines = f.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        for i, line in enumerate(lines, start=1):
            stripped = line.strip()
            if stripped.startswith("#") or _RESOLVER_MARK.search(line):
                continue
            if any(p.search(line) for p in _PATTERNS):
                hits.setdefault(rel, []).append((i, stripped))
    return hits


def run(all_files: bool = False) -> Tuple[bool, str]:
    _ = all_files
    hits = scan_hits()
    violations: List[str] = []
    report: List[str] = ["[path-ssot] parquet path SSOT gate (slim fork)", ""]
    total = sum(len(v) for v in hits.values())
    pending_pr1 = 0
    for rel in sorted(set(hits) | set(_ALLOWLIST)):
        actual = len(hits.get(rel, []))
        entry = _ALLOWLIST.get(rel)
        if entry is None:
            violations.append(
                f"NEW_UNWIRED {rel}: {actual} hit(s) not in allowlist"
            )
            report.append(f"  NEW_UNWIRED  {rel}  ({actual})")
            continue
        tag, expected = entry
        if actual > expected:
            violations.append(
                f"DRIFT {rel}: {actual} hits > allowlist {expected} ({tag})"
            )
            report.append(f"  DRIFT        {rel}  {actual} > {expected} ({tag})")
        elif actual < expected:
            violations.append(
                f"STALE {rel}: {actual} hits < allowlist {expected} ({tag})"
            )
            report.append(f"  STALE        {rel}  {actual} < {expected} ({tag})")
        else:
            report.append(f"  OK {tag:<12} {rel}  ({actual}/{expected})")
            if tag == "PR1_PENDING":
                pending_pr1 += actual
    for rel in _LOOSE_WRITE_BAN_FILES:
        f = REPO_ROOT / rel
        if not f.is_file():
            continue
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if _EXPLICIT_ROOT_CALL.search(line):
                violations.append(
                    f"LOOSE_WRITE_BAN {rel}:{i}: do not pass explicit_root"
                )
                report.append(f"  LOOSE_WRITE_BAN {rel}:{i}")
    report.append("")
    report.append(
        f"[path-ssot] hits={total}  PR1_PENDING_remaining={pending_pr1}  "
        f"violations={len(violations)}"
    )
    return (not violations), "\n".join(report + violations)


def main(argv: List[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--all", action="store_true", help="compat flag")
    ns = p.parse_args(argv)
    ok, report = run(all_files=ns.all)
    print(report)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
