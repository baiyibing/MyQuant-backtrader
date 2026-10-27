"""Phase 3 pipeline: extract day N+1 while ETL day N (one extract + one ETL).

Continues other years after Phase2 (2026) DONE.
Homed in MyQuant-backtrader (extract + ETL + orchestrator).
Resume-safe via same progress jsonl/md. Asia/Shanghai stamps.
SRC is J:\\stock_data root (year/month + stock_rar_data layouts).
"""
from __future__ import annotations

import json
import os
import shutil
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
PY = str(resolve_oskh_python())

# Host ops defaults for newtest_4090 (override via env). Not scanned by anaconda/E: path gate.
def _env_path(key: str, default: str) -> Path:
    raw = str(os.environ.get(key) or "").strip()
    return Path(raw) if raw else Path(default)

SRC = _env_path("OSKH_STOCK_RAR_SRC", r"J:\stock_data")
CSV_ROOT = _env_path("OSKH_STOCK_CSV_DST", r"J:\l2_work\stock_csv_data")
LAKE = _env_path("OSKH_L2_PARQUET_ROOT", r"J:\l2_lake\l2_parquet")
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


def done_dates() -> set[str]:
    done = set()
    if LOG_JSONL.is_file():
        for ln in LOG_JSONL.read_text(encoding="utf-8").splitlines():
            if not ln.strip():
                continue
            try:
                rec = json.loads(ln)
            except json.JSONDecodeError:
                continue
            if rec.get("status") == "ok":
                done.add(rec["date"])
    if LAKE.is_dir():
        for d in LAKE.iterdir():
            if d.is_dir() and d.name.startswith("date="):
                day = d.name.split("=", 1)[1]
                main = d / "main.parquet"
                order = d / "order.parquet"
                if main.is_file() and order.is_file() and main.stat().st_size > 0 and order.stat().st_size > 0:
                    done.add(day)
    return done


def append_progress_md(line: str) -> None:
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
        PY, str(EXTRACT),
        "--src", str(SRC),
        "--dst", str(CSV_ROOT),
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
    env["OSKH_L2_PARQUET_ROOT"] = str(LAKE)
    cmd = [
        PY, str(ETL),
        "--source", str(CSV_ROOT / day),
        "--out-root", str(LAKE),
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


def delete_csv(day: str) -> None:
    d = CSV_ROOT / day
    if d.is_dir():
        shutil.rmtree(d, ignore_errors=False)


def csv_ready(day: str) -> bool:
    d = CSV_ROOT / day
    return d.is_dir() and any(d.glob("*.csv"))


class Prefetch:
    """Background extract for one day; only one at a time."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.day: str | None = None
        self.thread: threading.Thread | None = None
        self.result: tuple[int, float, str] | None = None
        self.error: str | None = None

    def start(self, day: str) -> None:
        with self._lock:
            if self.thread is not None and self.thread.is_alive():
                raise RuntimeError("prefetch already running for %s" % self.day)
            self.day = day
            self.result = None
            self.error = None
            self.thread = threading.Thread(target=self._run, args=(day,), name="extract-%s" % day, daemon=True)
            self.thread.start()
            print("[%s] PREFETCH extract start %s" % (now(), day), flush=True)

    def _run(self, day: str) -> None:
        try:
            self.result = run_extract(day)
        except Exception as exc:
            self.error = str(exc)
            self.result = (1, 0.0, "prefetch_exc:%s" % exc)

    def wait(self) -> tuple[str, int, float, str]:
        with self._lock:
            day = self.day
            th = self.thread
        if day is None or th is None:
            raise RuntimeError("no prefetch")
        th.join()
        rc, elapsed, tail = self.result if self.result is not None else (1, 0.0, self.error or "no result")
        print("[%s] PREFETCH extract done %s rc=%s %.1fs" % (now(), day, rc, elapsed), flush=True)
        with self._lock:
            self.thread = None
            self.day = None
        return day, rc, elapsed, tail

    def busy(self) -> bool:
        with self._lock:
            return self.thread is not None and self.thread.is_alive()


def ensure_extracted(day: str, prefetch: Prefetch | None, extract_cache: dict) -> tuple[int, float, str]:
    """Return (rc, extract_s, tail). Use prefetch/cache if available."""
    if day in extract_cache:
        return extract_cache.pop(day)
    if prefetch is not None and prefetch.day == day:
        d, rc, ex_s, tail = prefetch.wait()
        return rc, ex_s, tail
    if csv_ready(day):
        return 0, 0.0, "csv_already_present"
    return run_extract(day)


def finalize_ok(
    day: str, ex_s: float, etl_s: float, mg: float, og: float,
    parsed: dict, notes_extra: str, prefetch_wait_s: float = 0.0,
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
    counts = {"ok": 0, "skip_lake": 0, "extract_fail": 0, "extract_empty": 0, "etl_fail": 0}
    consecutive_fail = 0
    prefetch = Prefetch()
    extract_cache: dict[str, tuple[int, float, str]] = {}

    for i, day in enumerate(todo):
        print("[%s] (%d/%d) pipeline %s" % (now(), i + 1, len(todo), day), flush=True)

        ok, mg, og = verify_lake(day)
        if ok:
            if day in extract_cache:
                extract_cache.pop(day)
            if prefetch.day == day:
                prefetch.wait()
            rec = {
                "ts": now(), "date": day, "status": "ok", "extract_s": 0, "etl_s": 0,
                "prefetch_wait_s": 0.0, "csv_delete_s": 0.0,
                "main_gib": round(mg, 3), "order_gib": round(og, 3), "notes": "already_in_lake",
            }
            log_rec(rec)
            append_progress_md(
                "| %s | %s | skip_lake | 0 | 0 | %.3f | %.3f | already_in_lake |" % (now(), day, mg, og)
            )
            counts["skip_lake"] += 1
            consecutive_fail = 0
            nxt = todo[i + 1] if i + 1 < len(todo) else None
            if nxt and nxt not in extract_cache and not verify_lake(nxt)[0] and not csv_ready(nxt) and not prefetch.busy():
                prefetch.start(nxt)
            continue

        rc, ex_s, ex_tail = ensure_extracted(day, prefetch, extract_cache)
        if rc != 0:
            rec = {
                "ts": now(), "date": day, "status": "extract_fail",
                "extract_s": round(ex_s, 1), "etl_s": 0, "notes": ex_tail,
            }
            log_rec(rec)
            append_progress_md(
                "| %s | %s | extract_fail | %.1f | 0 |  |  | %s |"
                % (now(), day, ex_s, ex_tail[:120].replace("|", "/"))
            )
            counts["extract_fail"] += 1
            consecutive_fail += 1
            if consecutive_fail >= 3:
                append_progress_md(
                    "| %s | — | batch_stop |  |  |  |  | STOP after 3 consecutive failures counts=%s |"
                    % (now(), counts)
                )
                return counts
            continue

        if not csv_ready(day):
            rec = {
                "ts": now(), "date": day, "status": "extract_empty",
                "extract_s": round(ex_s, 1), "notes": "no csv",
            }
            log_rec(rec)
            append_progress_md(
                "| %s | %s | extract_empty | %.1f | 0 |  |  | no csv |" % (now(), day, ex_s)
            )
            counts["extract_empty"] += 1
            consecutive_fail += 1
            if consecutive_fail >= 3:
                append_progress_md(
                    "| %s | — | batch_stop |  |  |  |  | STOP after 3 consecutive failures counts=%s |"
                    % (now(), counts)
                )
                return counts
            continue

        nxt = todo[i + 1] if i + 1 < len(todo) else None
        prefetch_started = False
        if nxt and not verify_lake(nxt)[0] and not csv_ready(nxt) and not prefetch.busy():
            prefetch.start(nxt)
            prefetch_started = True
            print("[%s] OVERLAP extract_prefetch %s || ETL %s" % (now(), nxt, day), flush=True)

        rc, etl_s, etl_tail, parsed = run_etl(day)
        ok, mg, og = verify_lake(day)
        if rc != 0 or not ok:
            if prefetch_started and prefetch.thread is not None:
                d2, rc2, ex2, tail2 = prefetch.wait()
                extract_cache[d2] = (rc2, ex2, tail2)
            rec = {
                "ts": now(), "date": day, "status": "etl_fail",
                "extract_s": round(ex_s, 1), "etl_s": round(etl_s, 1),
                "notes": etl_tail[:500], "etl_rc": rc,
            }
            log_rec(rec)
            append_progress_md(
                "| %s | %s | etl_fail | %.1f | %.1f |  |  | rc=%s |"
                % (now(), day, ex_s, etl_s, rc)
            )
            counts["etl_fail"] += 1
            consecutive_fail += 1
            if consecutive_fail >= 3:
                if prefetch.busy():
                    d2, rc2, ex2, tail2 = prefetch.wait()
                    extract_cache[d2] = (rc2, ex2, tail2)
                append_progress_md(
                    "| %s | — | batch_stop |  |  |  |  | STOP after 3 consecutive failures counts=%s |"
                    % (now(), counts)
                )
                return counts
            continue

        note_pipe = "pipeline+extract_prefetch" if prefetch_started else "pipeline"
        prefetch_wait_s = 0.0
        if prefetch_started and prefetch.thread is not None:
            wait_started = time.perf_counter()
            d2, rc2, ex2, tail2 = prefetch.wait()
            prefetch_wait_s = time.perf_counter() - wait_started
            extract_cache[d2] = (rc2, ex2, tail2)

        finalize_ok(day, ex_s, etl_s, mg, og, parsed, note_pipe, prefetch_wait_s=prefetch_wait_s)
        counts["ok"] += 1
        consecutive_fail = 0

    if prefetch.busy() or prefetch.day is not None:
        try:
            if prefetch.thread is not None:
                d2, rc2, ex2, tail2 = prefetch.wait()
                extract_cache[d2] = (rc2, ex2, tail2)
        except Exception:
            pass

    return counts


def main() -> int:
    LAKE.mkdir(parents=True, exist_ok=True)
    CSV_ROOT.mkdir(parents=True, exist_ok=True)
    try:
        PID_FILE.write_text(str(os.getpid()), encoding="utf-8")
    except Exception:
        pass

    dates = load_dates()
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
    fails = counts.get("extract_fail", 0) + counts.get("etl_fail", 0) + counts.get("extract_empty", 0)
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
