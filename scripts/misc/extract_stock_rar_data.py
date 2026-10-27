# -*- coding: utf-8 -*-
"""批量解压 L2 历史日 RAR/7z 数据（每天对应一个归档）。

    {src}/YYYY-MM-DD.rar|.7z  →  {dst}/YYYY-MM-DD/*.csv

扫描布局（--src 可为单一扁平目录，或 stock_data 根）：
- 扁平目录：直接 *.rar / *.7z
- 年目录扁平：YYYY年/*.rar|.7z
- 年/月目录：YYYY年/YYYY.MM/*.rar|.7z
- stock_rar_data：扁平 *.rar|.7z
默认跳过 non_tick、嵌套 stock_data\\stock_data。

- 每天归档解到同名日期目录（扁平布局）。
- 已解压完成（目录存在且非空）视为完成；--force 覆盖重解。
- 解压工具 = 7-Zip（默认 C:\\Program Files\\7-Zip\\7z.exe）。
- 源/目标不写死盘符：--src / --dst 或 env OSKH_STOCK_RAR_SRC / OSKH_STOCK_CSV_DST。

用法：
    python scripts\\misc\\extract_stock_rar_data.py --src J:\\stock_data\\stock_rar_data --dst J:\\l2_work\\stock_csv_data
    python scripts\\misc\\extract_stock_rar_data.py --src J:\\stock_data --dst J:\\l2_work\\stock_csv_data --dry-run
    python scripts\\misc\\extract_stock_rar_data.py --force --dates 2026-07-01 2026-07-02
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import subprocess
import sys
import time
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
_log = logging.getLogger("extract_stock_rar_data")

DEFAULT_7Z = Path(r"C:\Program Files\7-Zip\7z.exe")
_DATE_STEM_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_ARCHIVE_SUFFIXES = {".rar", ".7z"}
_SKIP_DIR_NAMES = {
    "non_tick",
    "_dup_archives",
    "__pycache__",
    ".git",
}


def _resolve_dir(cli: Path | None, env_key: str, flag: str) -> Path:
    if cli is not None and str(cli).strip():
        return Path(cli)
    raw = str(os.environ.get(env_key) or "").strip()
    if raw:
        return Path(raw)
    raise SystemExit(f"FAIL: pass {flag} or set {env_key} (no baked F:/G: path; lesson 58)")


def _is_done(out_dir: Path) -> bool:
    """目录存在且非空 → 视为已解压完成。"""
    return out_dir.is_dir() and any(out_dir.iterdir())


def _flatten_single_subdir(out_dir: Path) -> None:
    """rar 内自带一层同名日期目录时（`<date>/<date>/*.csv`）摊平为顶层。"""
    items = list(out_dir.iterdir())
    if len(items) == 1 and items[0].is_dir():
        inner = items[0]
        for child in inner.iterdir():
            target = out_dir / child.name
            if target.exists():
                raise FileExistsError(f"摊平冲突：目标已存在: {target}")
            child.rename(target)
        inner.rmdir()


def extract_one(seven_zip: Path, rar_path: Path, out_dir: Path) -> bool:
    """解压单个归档到 out_dir（扁平布局）；成功且目录非空返回 True。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.monotonic()
    cmd = [str(seven_zip), "x", str(rar_path), f"-o{out_dir}", "-y", "-bsp1"]
    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    elapsed = time.monotonic() - t0
    if proc.returncode != 0:
        tail = (proc.stdout or "").strip().splitlines()[-3:]
        _log.error(
            "FAIL %s (exit=%s, %.1fs): %s",
            rar_path.name, proc.returncode, elapsed, " | ".join(tail),
        )
        return False
    try:
        _flatten_single_subdir(out_dir)
    except Exception as exc:
        _log.error("FAIL %s: 摊平失败: %s", rar_path.name, exc)
        return False
    if not any(out_dir.iterdir()):
        _log.error("FAIL %s: 7z 成功 但目录为空", rar_path.name)
        return False
    n_files = sum(1 for _ in out_dir.rglob("*") if _.is_file())
    _log.info("OK   %s -> %s (%d files, %.1fs)", rar_path.name, out_dir, n_files, elapsed)
    return True


def _is_archive(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in _ARCHIVE_SUFFIXES and _DATE_STEM_RE.match(path.stem)


def _should_skip_dir(path: Path, src_root: Path) -> bool:
    name = path.name
    if name in _SKIP_DIR_NAMES:
        return True
    # nested lake fragment: stock_data\stock_data\...
    try:
        rel = path.relative_to(src_root)
    except ValueError:
        return False
    parts = rel.parts
    if len(parts) >= 2 and parts[0] == "stock_data" and parts[1] == "stock_data":
        return True
    if name == "stock_data" and path.parent.resolve() == src_root.resolve():
        # top-level nested fragment folder under stock_data root
        return True
    return False


def discover_archives(src: Path) -> list[Path]:
    """发现日期归档：扁平 src，或年目录 / 年月目录 / stock_rar_data。"""
    found: dict[str, Path] = {}

    def add(p: Path) -> None:
        if not _is_archive(p):
            return
        # prefer .7z over .rar if both present for same day (post-dedup convention)
        prev = found.get(p.stem)
        if prev is None:
            found[p.stem] = p
            return
        if prev.suffix.lower() == ".rar" and p.suffix.lower() == ".7z":
            found[p.stem] = p

    # 1) flat files directly under src
    for p in src.iterdir():
        if p.is_file():
            add(p)

    # 2) named children: stock_rar_data + year dirs (YYYY年 / YYYY)
    for child in sorted(src.iterdir()):
        if not child.is_dir():
            continue
        if _should_skip_dir(child, src):
            _log.info("SKIP dir %s", child)
            continue
        # flat files in child (stock_rar_data or flat year)
        for p in child.iterdir():
            if p.is_file():
                add(p)
            elif p.is_dir() and not _should_skip_dir(p, src):
                # month subdir YYYY.MM or similar
                for q in p.iterdir():
                    if q.is_file():
                        add(q)

    return [found[k] for k in sorted(found)]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", type=Path, default=None, help="归档源目录（或 stock_data 根；env OSKH_STOCK_RAR_SRC）")
    ap.add_argument("--dst", type=Path, default=None, help="解压目标父目录（env OSKH_STOCK_CSV_DST）")
    ap.add_argument("--seven-zip", type=Path, default=DEFAULT_7Z, help=f"7z.exe 路径（默认 {DEFAULT_7Z}）")
    ap.add_argument("--dates", nargs="*", default=None, help="只处理指定日期，如 2026-07-01；默认全部")
    ap.add_argument("--month", default=None, help="只处理指定月份，如 2026-07；默认全部")
    ap.add_argument("--force", action="store_true", help="忽略已完成标记，强制重解")
    ap.add_argument("--dry-run", action="store_true", help="只打印计划，不实际解压")
    ap.add_argument(
        "--skip-dates-file",
        type=Path,
        default=None,
        help="每行一个 YYYY-MM-DD，跳过这些日期（不含 --force 时）",
    )
    args = ap.parse_args(argv)
    args.src = _resolve_dir(args.src, "OSKH_STOCK_RAR_SRC", "--src")
    args.dst = _resolve_dir(args.dst, "OSKH_STOCK_CSV_DST", "--dst")

    if not args.src.is_dir():
        _log.error("源目录不存在: %s", args.src)
        return 2
    if not args.seven_zip.is_file():
        _log.error("7z.exe 不存在: %s；请用 --seven-zip 指定。", args.seven_zip)
        return 2

    archives = discover_archives(args.src)
    if args.month:
        archives = [r for r in archives if r.stem.startswith(args.month)]
    if args.dates:
        wanted = {d.strip() for d in args.dates}
        archives = [r for r in archives if r.stem in wanted]

    skip_set: set[str] = set()
    if args.skip_dates_file is not None:
        if not args.skip_dates_file.is_file():
            _log.error("skip-dates-file 不存在: %s", args.skip_dates_file)
            return 2
        for line in args.skip_dates_file.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            skip_set.add(s.split()[0])

    if skip_set and not args.force:
        before = len(archives)
        archives = [r for r in archives if r.stem not in skip_set]
        _log.info("skip-dates-file 过滤 %d -> %d", before, len(archives))

    if not archives:
        _log.warning("无匹配归档文件（src=%s, dates=%s, month=%s）", args.src, args.dates, args.month)
        return 1

    _log.info("共 %d 个归档（dst=%s force=%s dry_run=%s）", len(archives), args.dst, args.force, args.dry_run)

    n_ok = n_skip = n_fail = 0
    failed: list[str] = []
    for i, rar in enumerate(archives, 1):
        out_dir = args.dst / rar.stem
        if not args.force and _is_done(out_dir):
            _log.info("SKIP %s（%s 已存在且非空）[%d/%d]", rar.name, out_dir, i, len(archives))
            n_skip += 1
            continue
        if args.dry_run:
            _log.info("PLAN %s -> %s [%d/%d]", rar.name, out_dir, i, len(archives))
            continue
        _log.info("EXTRACT %s [%d/%d]", rar.name, i, len(archives))
        if extract_one(args.seven_zip, rar, out_dir):
            n_ok += 1
        else:
            n_fail += 1
            failed.append(rar.name)

    _log.info("完成：成功 %d，跳过 %d，失败 %d，共 %d", n_ok, n_skip, n_fail, len(archives))
    if failed:
        _log.error("失败清单: %s", ", ".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
