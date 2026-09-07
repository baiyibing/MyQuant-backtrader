#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compare legacy E ``tr_staging/`` vs F parquet-container target; optional copy.

Legacy sources (first existing wins for listing; merge for migrate):
  - ``{OSKH_DATA_ROOT or repo}/stock_data/tr_staging``
  - ``E:/data/parquet/tr_staging``

Target (SSOT): ``resolve_tr_staging_dir()`` → typically ``F:/stock_data/tr_staging``.

Usage:
  python scripts/ops/verify_tr_staging_migration.py
  python scripts/ops/verify_tr_staging_migration.py --apply
"""

from __future__ import annotations

import argparse
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from common.infra.data_root import resolve_data_root, resolve_tr_staging_dir


@dataclass(frozen=True)
class FileStat:
    path: Path
    size: int
    mtime: float

    @property
    def mtime_iso(self) -> str:
        return datetime.fromtimestamp(self.mtime).strftime("%Y-%m-%d %H:%M:%S")


def _legacy_staging_dirs() -> List[Path]:
    repo_staging = REPO / "stock_data" / "tr_staging"
    candidates = [
        repo_staging,
        resolve_data_root() / "stock_data" / "tr_staging",
        Path("E:/data/parquet/tr_staging"),
    ]
    out: List[Path] = []
    seen: set[str] = set()
    for p in candidates:
        key = str(p.resolve()) if p.exists() else str(p)
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


def _scan_parquet(dir_path: Path) -> Dict[str, FileStat]:
    if not dir_path.is_dir():
        return {}
    out: Dict[str, FileStat] = {}
    for f in sorted(dir_path.glob("*.parquet")):
        st = f.stat()
        out[f.name] = FileStat(path=f, size=st.st_size, mtime=st.st_mtime)
    return out


def _merge_legacy(legacy_dirs: Iterable[Path]) -> Dict[str, FileStat]:
    merged: Dict[str, FileStat] = {}
    for d in legacy_dirs:
        for name, stat in _scan_parquet(d).items():
            prev = merged.get(name)
            if prev is None or stat.mtime > prev.mtime:
                merged[name] = stat
    return merged


def compare(
    legacy: Dict[str, FileStat], target: Dict[str, FileStat]
) -> Tuple[List[str], List[str], List[str]]:
    only_legacy = sorted(set(legacy) - set(target))
    only_target = sorted(set(target) - set(legacy))
    drift: List[str] = []
    for name in sorted(set(legacy) & set(target)):
        ls, ts = legacy[name], target[name]
        if ls.size != ts.size or abs(ls.mtime - ts.mtime) > 1.0:
            drift.append(name)
    return only_legacy, only_target, drift


def _print_side(label: str, stats: Dict[str, FileStat]) -> None:
    print(f"  {label}: {len(stats)} file(s)")
    if not stats:
        return
    latest = max(stats.values(), key=lambda s: s.mtime)
    print(f"    latest: {latest.path.name}  mtime={latest.mtime_iso}  size={latest.size}")


def run(apply: bool) -> int:
    legacy_dirs = _legacy_staging_dirs()
    target_dir = resolve_tr_staging_dir()
    legacy = _merge_legacy(legacy_dirs)
    target = _scan_parquet(target_dir)

    print("[tr_staging migration check]")
    print(f"  target: {target_dir}")
    for d in legacy_dirs:
        tag = "present" if d.is_dir() else "absent"
        print(f"  legacy: {d} ({tag})")
    print("")
    _print_side("legacy merged", legacy)
    _print_side("target", target)
    print("")

    only_legacy, only_target, drift = compare(legacy, target)
    if only_legacy:
        print(f"  only in legacy ({len(only_legacy)}): {', '.join(only_legacy)}")
    if only_target:
        print(f"  only in target ({len(only_target)}): {', '.join(only_target)}")
    if drift:
        print(f"  size/mtime drift ({len(drift)}): {', '.join(drift)}")

    needs_copy = only_legacy + drift
    if not needs_copy and not only_target:
        print("  verdict: IN SYNC")
        return 0

    if not needs_copy:
        print("  verdict: target has extra files only (ok)")
        return 0

    if not apply:
        print("  verdict: NEEDS MIGRATE (re-run with --apply)")
        return 1

    target_dir.mkdir(parents=True, exist_ok=True)
    for name in needs_copy:
        src = legacy[name].path
        dst = target_dir / name
        print(f"  copy: {src} -> {dst}")
        shutil.copy2(src, dst)

    after = _scan_parquet(target_dir)
    _, _, drift_after = compare(legacy, after)
    if drift_after or set(legacy) - set(after):
        print("  verdict: MIGRATE FAILED (post-copy drift)")
        return 1
    print("  verdict: MIGRATED OK")
    return 0


def main(argv: List[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument(
        "--apply",
        action="store_true",
        help="Copy legacy-only / drift files into resolve_tr_staging_dir()",
    )
    ns = p.parse_args(argv)
    return run(apply=ns.apply)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
