"""Bounded per-day archive → CSV → SSD parquet → lake pipeline."""
from __future__ import annotations

import json
import queue
import os
import shutil
import stat
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

# Repo-local scripts (no machine-baked D:\PycharmProjects / D:\anaconda3).
_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
from scripts._script_bootstrap import ensure_repo_on_syspath, resolve_oskh_python  # noqa: E402

ensure_repo_on_syspath(__file__)
EXTRACT = _REPO / "scripts" / "misc" / "extract_stock_rar_data.py"
ETL = _REPO / "scripts" / "run" / "run_l2_etl_day.py"

# Host ops defaults for newtest_4090 (override via env). Not scanned by anaconda/E: path gate.
def _env_path(key: str, default: str) -> Path:
    raw = str(os.environ.get(key) or "").strip()
    return Path(raw) if raw else Path(default)

SRC = _env_path("OSKH_STOCK_RAR_SRC", r"J:\stock_data")
CSV_ROOT = _env_path("OSKH_STOCK_CSV_DST", r"E:\l2_csv_scratch")
LAKE = _env_path("OSKH_L2_PARQUET_ROOT", r"J:\l2_lake\l2_parquet")
STAGING = _env_path("OSKH_L2_PARQUET_STAGING_ROOT", str(CSV_ROOT.parent / "l2_parquet_staging"))
ARCHIVES = CSV_ROOT.parent / "l2_archive_scratch"
_AGENT_TOOLS = _env_path("OSKH_L2_AGENT_TOOLS", r"C:\Users\wangc\agent-tools")
SKIP_FILE = _AGENT_TOOLS / "l2_skip_dates.txt"
DATES_FILE = _AGENT_TOOLS / "l2_phase3_dates.txt"
PROGRESS = _AGENT_TOOLS / "l2_batch_progress.md"
LOG_JSONL = _AGENT_TOOLS / "l2_batch_progress.jsonl"
PID_FILE = _AGENT_TOOLS / "l2_phase3_pipeline.pid"
SUMMARY = _AGENT_TOOLS / "l2_batch_summary.json"
SEVEN = _env_path("OSKH_SEVEN_ZIP", r"C:\Program Files\7-Zip\7z.exe")


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S Asia/Shanghai")


def load_dates() -> list[str]:
    return [ln.strip() for ln in DATES_FILE.read_text(encoding="utf-8").splitlines() if ln.strip()]


def manifest_records(root: Path) -> list[dict]:
    path = root / "_manifest.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()] if path.exists() else []


def done_dates() -> set[str]:
    done = set()
    committed = {r["date"] for r in manifest_records(LAKE)}
    if LAKE.is_dir():
        for d in LAKE.iterdir():
            if d.is_dir() and d.name.startswith("date="):
                day = d.name.split("=", 1)[1]
                main = d / "main.parquet"
                order = d / "order.parquet"
                if day in committed and main.is_file() and order.is_file() and main.stat().st_size > 0 and order.stat().st_size > 0:
                    done.add(day)
    return done


_LOG_LOCK = threading.RLock()


def append_progress_md(line: str) -> None:
    with _LOG_LOCK:
        _append_progress_md(line)


def _append_progress_md(line: str) -> None:
    if not PROGRESS.exists():
        PROGRESS.write_text(
            "# L2 batch progress (Asia/Shanghai)\n\n"
            "| time | date | status | extract_s | etl_s | main_gib | order_gib | notes |\n"
            "|---|---|---|---:|---:|---:|---:|---|\n",
            encoding="utf-8",
        )
    with PROGRESS.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def log_rec(rec: dict) -> None:
    with _LOG_LOCK:
        with LOG_JSONL.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def verify_lake(day: str) -> tuple[bool, float, float]:
    d = LAKE / ("date=%s" % day)
    main = d / "main.parquet"
    order = d / "order.parquet"
    if not (main.is_file() and order.is_file()):
        return False, 0.0, 0.0
    mb = main.stat().st_size
    ob = order.stat().st_size
    if mb <= 0 or ob <= 0:
        return False, 0.0, 0.0
    return True, mb / 1024**3, ob / 1024**3


def run_extract(day: str) -> tuple[int, float, str]:
    t0 = time.perf_counter()
    cmd = [
        str(resolve_oskh_python()), str(EXTRACT),
        "--src", str(ARCHIVES),
        "--dst", str(CSV_ROOT),
        "--force",
        "--seven-zip", str(SEVEN),
        "--dates", day,
        "--skip-dates-file", str(SKIP_FILE),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    elapsed = time.perf_counter() - t0
    tail = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip().splitlines()[-5:]
    return proc.returncode, elapsed, " | ".join(tail)


def run_etl(day: str) -> tuple[int, float, str, dict]:
    t0 = time.perf_counter()
    env = os.environ.copy()
    env["OSKH_L2_PARQUET_ROOT"] = str(STAGING)
    cmd = [
        str(resolve_oskh_python()), str(ETL),
        "--source", str(CSV_ROOT / day),
        "--out-root", str(STAGING),
        "--gap-free-sample", "50",
    ]
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(ETL.parents[2]),
        env=env,
    )
    elapsed = time.perf_counter() - t0
    out = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()
    parsed = {}
    try:
        start = out.find("{")
        if start >= 0:
            parsed = json.loads(out[start:])
    except Exception:
        parsed = {}
    tail = (out[-500:] + ("\n" + err[-300:] if err else "")).replace("\n", " | ")
    return proc.returncode, elapsed, tail, parsed


def make_writable(path: Path) -> None:
    """Clear Windows read-only while preserving the other permission bits."""
    path.chmod(path.stat().st_mode | stat.S_IWRITE)


def _retry_readonly(func, path, exc_info) -> None:
    # onerror also supports Python versions before rmtree's onexc was added.
    if not isinstance(exc_info[1], PermissionError):
        raise exc_info[1]
    make_writable(Path(path))
    func(path)


def delete_csv(day: str) -> None:
    d = CSV_ROOT / day
    if d.is_dir():
        shutil.rmtree(d, ignore_errors=False, onerror=_retry_readonly)


def csv_ready(day: str) -> bool:
    d = CSV_ROOT / day
    return (d / "_extract_ready").is_file() and any(d.glob("*.csv"))


def stage_ready(day: str) -> bool:
    folder = STAGING / f"date={day}"
    return (folder / "_ready.json").is_file() and all(
        (folder / name).is_file() and (folder / name).stat().st_size > 0
        for name in ("main.parquet", "order.parquet")
    )


def publish_day(day: str) -> tuple[float, float, float]:
    """Copy privately, verify sizes, rename pair, then commit lake manifest.

    Only this pipeline's single publisher writes the lake manifest. An interrupted
    copy is retried from SSD; no partially copied pair appears under date=.
    """
    started = time.perf_counter()
    source = STAGING / f"date={day}"
    pending = LAKE / f".publishing-{day}"
    final = LAKE / f"date={day}"
    if not stage_ready(day):
        raise RuntimeError(f"staging not committed: {day}")
    ready = json.loads((source / "_ready.json").read_text(encoding="utf-8"))
    record = ready["manifest"]
    if final.exists() and verify_lake(day)[0]:
        marker = final / "_pipeline_ready.json"
        if not marker.is_file() or json.loads(marker.read_text(encoding="utf-8")) != record:
            raise RuntimeError(f"existing lake day not owned by this publish: {final}")
        if any((source / name).stat().st_size != (final / name).stat().st_size
               for name in ("main.parquet", "order.parquet")):
            raise RuntimeError(f"existing lake day size mismatch: {day}")
    if not verify_lake(day)[0]:
        if final.exists():
            raise RuntimeError(f"incomplete existing lake day; inspect before retry: {final}")
        if pending.exists():
            shutil.rmtree(pending)
        pending.mkdir(parents=True)
        for name in ("main.parquet", "order.parquet"):
            shutil.copy2(source / name, pending / name)
            if (source / name).stat().st_size != (pending / name).stat().st_size:
                raise RuntimeError(f"publish size mismatch: {day}/{name}")
        (pending / "_pipeline_ready.json").write_text(json.dumps(record), encoding="utf-8")
    # Commit the complete pair first; manifest visibility is the final commit.
    # If interrupted between these operations, SSD readiness survives the retry.
    if not final.exists():
        pending.rename(final)
    manifest = LAKE / "_manifest.jsonl"
    existing = manifest_records(LAKE)
    tmp = LAKE / "._manifest.publish.tmp"
    tmp.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n"
                   for r in existing if r.get("date") != day)
                   + json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, manifest)
    ok, mg, og = verify_lake(day)
    if not ok:
        raise RuntimeError(f"publish verification failed: {day}")
    return time.perf_counter() - started, mg, og


def finalize_ok(
    day: str, ex_s: float, etl_s: float, mg: float, og: float,
    parsed: dict, notes_extra: str, prefetch_wait_s: float = 0.0, publish_s: float = 0.0, archive_s: float = 0.0,
) -> None:
    delete_started = time.perf_counter()
    try:
        delete_csv(day)
        del_note = "csv_deleted"
    except Exception as exc:
        del_note = "csv_delete_fail:%s" % exc
    csv_delete_s = time.perf_counter() - delete_started
    notes = "%s %s" % (del_note, notes_extra)
    if parsed.get("rows_main"):
        notes += " rows_main=%s" % parsed.get("rows_main")
    notes = notes.strip()
    rec = {
        "ts": now(),
        "date": day,
        "status": "ok",
        "extract_s": round(ex_s, 1),
        "etl_s": round(etl_s, 1),
        "publish_s": round(publish_s, 3),
        "archive_s": round(archive_s, 3),
        "prefetch_wait_s": round(prefetch_wait_s, 1),
        "csv_delete_s": round(csv_delete_s, 3),
        "main_gib": round(mg, 3),
        "order_gib": round(og, 3),
        "notes": notes,
        "parsed": {k: parsed.get(k) for k in ("rows_main", "rows_order", "csv_files", "elapsed_s") if k in parsed},
        "profile": parsed.get("profile"),
    }
    log_rec(rec)
    append_progress_md(
        "| %s | %s | ok | %.1f | %.1f | %.3f | %.3f | %s |"
        % (now(), day, ex_s, etl_s, mg, og, notes.replace("|", "/"))
    )
    print("[%s] OK %s main=%.3fGiB order=%.3fGiB ex=%.1fs etl=%.1fs" % (now(), day, mg, og, ex_s, etl_s), flush=True)


def process_pipeline(todo: list[str]) -> dict:
    """One worker per stage; bounded queues provide SSD backpressure, not barriers."""
    from scripts.misc.extract_stock_rar_data import discover_archives

    roots = [path.resolve() for path in (CSV_ROOT, STAGING, ARCHIVES, LAKE)]
    if any(a == b or a in b.parents or b in a.parents
           for i, a in enumerate(roots) for b in roots[i + 1:]):
        raise ValueError("CSV, parquet staging, archive scratch and lake must be separate trees")
    for root in (CSV_ROOT, STAGING, ARCHIVES, LAKE):
        root.mkdir(parents=True, exist_ok=True)
    archives = {p.stem: p for p in discover_archives(SRC)}
    counts = dict.fromkeys(("ok", "skip_lake", "archive_fail", "extract_fail",
                            "extract_empty", "etl_fail", "publish_fail"), 0)
    stop = threading.Event()
    lock = threading.Lock()
    consecutive_fail = 0
    # One queued day per boundary, plus at most one active day per worker.
    links = [queue.Queue(maxsize=1) for _ in range(4)]
    sentinel = object()

    def archive(job):
        day = job["date"]
        if stage_ready(day) or csv_ready(day):
            return
        source = archives[day]
        target = ARCHIVES / source.name
        started = time.perf_counter()
        temporary = target.with_suffix(target.suffix + ".copying")
        if temporary.exists():
            make_writable(temporary)
        shutil.copy2(source, temporary)
        if temporary.stat().st_size != source.stat().st_size:
            raise RuntimeError("archive copy size mismatch")
        if target.exists():
            make_writable(target)
        os.replace(temporary, target)
        job["archive_s"] = time.perf_counter() - started
        job["archive"] = target

    def extract(job):
        day = job["date"]
        if stage_ready(day) or csv_ready(day):
            return
        # --force overlays files; remove any interrupted extraction first.
        delete_csv(day)
        rc, elapsed, tail = run_extract(day)
        job["extract_s"] = elapsed
        if rc:
            raise RuntimeError(tail)
        if not (CSV_ROOT / day).is_dir() or not any((CSV_ROOT / day).glob("*.csv")):
            raise RuntimeError("no csv after extraction")
        (CSV_ROOT / day / "_extract_ready").touch()
        if "archive" in job:
            try:
                make_writable(job["archive"])
                job["archive"].unlink()
            except OSError as exc:
                print(f"archive cleanup deferred {day}: {exc}", flush=True)

    def etl(job):
        day = job["date"]
        if stage_ready(day):
            job.update(json.loads((STAGING / f"date={day}" / "_ready.json").read_text(encoding="utf-8")))
            return
        rc, elapsed, tail, parsed = run_etl(day)
        job.update(etl_s=elapsed, parsed=parsed)
        folder = STAGING / f"date={day}"
        if rc or not all((folder / n).is_file() and (folder / n).stat().st_size > 0
                         for n in ("main.parquet", "order.parquet")):
            raise RuntimeError(tail)
        # Persist timings/profile only after successful subprocess completion.
        job["manifest"] = next(r for r in manifest_records(STAGING) if r["date"] == day)
        tmp = folder / "_ready.tmp"
        tmp.write_text(json.dumps({k: v for k, v in job.items() if k != "archive"}), encoding="utf-8")
        os.replace(tmp, folder / "_ready.json")

    def publish(job):
        day = job["date"]
        elapsed, mg, og = publish_day(day)
        finalize_ok(day, job.get("extract_s", 0), job.get("etl_s", 0), mg, og,
                    job.get("parsed", {}), "ssd_pipeline", publish_s=elapsed,
                    archive_s=job.get("archive_s", 0))
        try:
            shutil.rmtree(STAGING / f"date={day}")
        except OSError as exc:
            print(f"staging cleanup deferred {day}: {exc}", flush=True)

    def worker(index, action, failure):
        nonlocal consecutive_fail
        upstream = links[index]
        downstream = links[index + 1] if index < 3 else None
        while True:
            job = upstream.get()
            if job is sentinel:
                if downstream is not None:
                    downstream.put(sentinel)
                return
            if stop.is_set():
                continue
            try:
                print(f"[{now()}] {action.__name__} start {job['date']}", flush=True)
                action(job)
            except Exception as exc:
                with lock:
                    counts[failure] += 1
                    consecutive_fail += 1
                    print(f"[{now()}] {failure} {job['date']}: {exc}", flush=True)
                    try:
                        log_rec({"ts": now(), "date": job["date"], "status": failure, "notes": str(exc)})
                        append_progress_md(f"| {now()} | {job['date']} | {failure} | | | | | {str(exc)[:300].replace('|', '/')} |")
                        if consecutive_fail >= 3:
                            stop.set()
                            append_progress_md(f"| {now()} | — | batch_stop | | | | | 3 consecutive failures |")
                    except OSError as logging_error:
                        stop.set()
                        print(f"progress write failed: {logging_error}", flush=True)
                continue
            if downstream is not None:
                downstream.put(job)
            else:
                with lock:
                    counts["ok"] += 1
                    consecutive_fail = 0

    workers = [threading.Thread(target=worker, args=(i, action, failure))
               for i, (action, failure) in enumerate(zip(
                   (archive, extract, etl, publish),
                   ("archive_fail", "extract_fail", "etl_fail", "publish_fail")))]
    for thread in workers:
        thread.start()
    completed = done_dates()
    for day in dict.fromkeys(todo):
        if stop.is_set():
            break
        if day in completed:
            counts["skip_lake"] += 1
            continue
        links[0].put({"date": day})
    links[0].put(sentinel)
    for thread in workers:
        thread.join()
    return counts


def _main() -> int:
    _AGENT_TOOLS.mkdir(parents=True, exist_ok=True)
    LAKE.mkdir(parents=True, exist_ok=True)
    CSV_ROOT.mkdir(parents=True, exist_ok=True)
    try:
        PID_FILE.write_text(str(os.getpid()), encoding="utf-8")
    except Exception:
        pass

    dates = load_dates()
    for day in dates:
        if datetime.strptime(day, "%Y-%m-%d").strftime("%Y-%m-%d") != day:
            raise ValueError(f"invalid date: {day!r}")
    already = done_dates()
    skip_dates_from_file = set()
    if SKIP_FILE.is_file():
        for _ln in SKIP_FILE.read_text(encoding='utf-8').splitlines():
            _s = _ln.strip()
            if _s and not _s.startswith('#'):
                skip_dates_from_file.add(_s)
    already |= skip_dates_from_file
    todo = [d for d in dates if d not in already]
    print(
        "[%s] Phase3 PIPELINE start: total=%d already=%d todo=%d pid=%s SRC=%s"
        % (now(), len(dates), len(already), len(todo), os.getpid(), SRC),
        flush=True,
    )
    append_progress_md(
        "| %s | — | batch_start |  |  |  |  | Phase3 pipeline total=%d already=%d todo=%d pid=%s order=2025..2020 SRC=J:\\\\stock_data |"
        % (now(), len(dates), len(already), len(todo), os.getpid())
    )
    log_rec({
        "ts": now(),
        "date": None,
        "status": "batch_start",
        "notes": "Phase3 pipeline mode order=2025..2020",
        "total": len(dates),
        "already": len(already),
        "todo": len(todo),
        "pid": os.getpid(),
        "src": str(SRC),
    })

    counts = process_pipeline(todo)
    append_progress_md("| %s | — | batch_done |  |  |  |  | Phase3 pipeline counts=%s |" % (now(), counts))
    print("[%s] Phase3 PIPELINE done counts=%s" % (now(), counts), flush=True)
    summary = {"ts": now(), "mode": "pipeline", "phase": 3, "counts": counts, "todo": len(todo)}
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    fails = sum(value for key, value in counts.items() if key.endswith("fail") or key == "extract_empty")
    return 0 if fails == 0 else 1


def main() -> int:
    # OS releases the advisory lock on process exit, including crashes. Keep the
    # file itself: unlinking a locked inode would let a second process bypass it.
    STAGING.mkdir(parents=True, exist_ok=True)
    with (STAGING / ".pipeline.lock").open("a+b") as handle:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return _main()


if __name__ == "__main__":
    raise SystemExit(main())
