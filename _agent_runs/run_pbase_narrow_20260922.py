# -*- coding: utf-8 -*-
"""4090: drop 9+150, rewrite frozen pack, export frozen_explicit bars, P-BASE/M-LAG replay."""
from __future__ import annotations

import csv
import json
import math
import os
import shutil
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

BT = Path(r"D:\PycharmProjects\MyQuant-backtrader")
sys.path.insert(0, str(BT))
from backtest.research.joint_return_replay import (  # noqa: E402
    CONSTRAINT_FIELDS,
    FROZEN_CONTRACT_HASH,
    INTENT_FIELDS,
    SCHEMA_VERSION,
    canonical_bytes,
    content_hash,
    load_bundle,
    raw_hash,
    read_csv,
    validate_bars,
    validate_manifest,
)

PYEXE = Path(r"D:\anaconda3\envs\vanna312\python.exe")
REQUIRED_HEAD = "489fe9d18339766d2bf70c7dedc36f409ad16fc6"
QLIB = Path(os.environ.get("QLIB_1MIN_ROOT", r"C:\Users\wangc\.qlib\qlib_data\my_data_1min"))
QLIB_DAY = Path(os.environ.get("QLIB_DAY_ROOT", r"C:\Users\wangc\.qlib\qlib_data\my_data"))
HANDOFF = Path(r"D:\PycharmProjects\MyQuant\runs\joint_return_4090_20260920_pr95\handoff_bt_20260922")
SRC = HANDOFF / "portfolio_joint-return-control-only-50-5"
WORK = HANDOFF / "narrow_20260922"
PACK = WORK / "portfolio_joint-return-control-only-50-5-narrow"
RUN_ID = "joint-return-control-only-50-5-narrow"
BARS_OUT = Path(r"D:\exports\joint_return_pbase_narrow_20260922\frozen_explicit_bars.json")
REPLAY_OUT = BT / "backtest_output" / "joint-return-v1" / RUN_ID
STATS_CSV = HANDOFF / "QLIB_1MIN_STATS_by_symbol.csv"
RESEARCH_CAP = 1e12


def die(msg: str, code: int = 2) -> None:
    print("INPUT_BLOCKED:", msg, flush=True)
    raise SystemExit(code)


def conf_head() -> str:
    head = subprocess.check_output(["git", "-C", str(BT), "rev-parse", "HEAD"], text=True).strip()
    if head != REQUIRED_HEAD:
        die(f"BT HEAD {head} != {REQUIRED_HEAD}")
    return head


def session_stamps(day: str) -> list[str]:
    out = []
    t = datetime.fromisoformat(f"{day}T09:30:00+08:00")
    end = datetime.fromisoformat(f"{day}T11:30:00+08:00")
    while t <= end:
        out.append(t.isoformat(timespec="seconds"))
        t += timedelta(minutes=1)
    t = datetime.fromisoformat(f"{day}T13:01:00+08:00")
    end = datetime.fromisoformat(f"{day}T15:00:00+08:00")
    while t <= end:
        out.append(t.isoformat(timespec="seconds"))
        t += timedelta(minutes=1)
    if len(out) != 241:
        die(f"grid!=241 {day}: {len(out)}")
    return out


def sessions_map(calendar: list[str]) -> dict:
    return {
        d: [
            [f"{d}T09:30:00+08:00", f"{d}T11:31:00+08:00"],
            [f"{d}T13:01:00+08:00", f"{d}T15:01:00+08:00"],
        ]
        for d in calendar
    }


def load_bin(path: Path, i0: int, i1: int) -> np.ndarray:
    out = np.full(i1 - i0 + 1, np.nan, dtype=np.float64)
    if not path.is_file():
        return out
    raw = np.fromfile(path, dtype="<f4")
    if raw.size < 2:
        return out
    ref = int(round(float(raw[0])))
    vals = raw[1:].astype(np.float64)
    a = max(ref, i0)
    b = min(ref + len(vals) - 1, i1)
    if a > b:
        return out
    out[a - i0 : b - i0 + 1] = vals[a - ref : b - ref + 1]
    return out


def csv_bytes(rows: list[dict], fields: tuple[str, ...]) -> bytes:
    import io

    buf = io.StringIO(newline="")
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(fields)
    for r in rows:
        w.writerow([json.dumps(r[k], ensure_ascii=False, separators=(",", ":")) for k in fields])
    return buf.getvalue().encode("utf-8")


def load_stats():
    rows = list(csv.DictReader(STATS_CSV.open(encoding="utf-8")))
    classes = {r["instrument"]: r["bucket"] for r in rows}
    no_file = {s for s, b in classes.items() if b == "no_file"}
    cow = {s for s, b in classes.items() if b == "contract_over_window_only"}
    full = {s for s, b in classes.items() if b == "full_window"}
    if len(no_file) != 9 or len(cow) != 150 or len(full) != 614:
        die(f"STATS buckets unexpected no_file={len(no_file)} cow={len(cow)} full={len(full)}")
    return classes, no_file | cow, full, {"no_file": sorted(no_file), "cow_n": len(cow), "full_n": len(full)}


def filter_state(state: dict, drop: set) -> dict:
    s = json.loads(json.dumps(state))
    s["positions"] = {k: v for k, v in (s.get("positions") or {}).items() if k not in drop}
    return s


def filter_plan(plan: dict, drop: set) -> dict:
    p = json.loads(json.dumps(plan))
    for k in ("sells", "buy_candidates", "buys"):
        if not isinstance(p.get(k), list):
            continue
        kept = []
        for c in p[k]:
            if isinstance(c, dict):
                if c.get("instrument") not in drop:
                    kept.append(c)
            else:
                if c not in drop:
                    kept.append(c)
        p[k] = kept
    if isinstance(p.get("marks"), dict):
        p["marks"] = {k: v for k, v in p["marks"].items() if k not in drop}
    return p

def rewrite_manifest(m: dict, drop: set, intent_rows: list[dict]):
    m = json.loads(json.dumps(m))
    m["run_id"] = RUN_ID
    m["initial_state"] = filter_state(m["initial_state"], drop)
    cal = m["metadata"]["calendar"]
    arms = ("P-BASE",)
    prior = {a: m["initial_state"] for a in arms}
    old_by = {(h["date"], h["arm_id"]): h for h in m["reference_states"]}
    plan_map: dict[str, str] = {}
    state_map: dict[str, str] = {}
    new_hist = []
    for d in cal:
        for a in arms:
            h = json.loads(json.dumps(old_by[(d, a)]))
            old_before, old_after = h["before_hash"], h["after_hash"]
            old_plan = h["source_plan"]
            old_plan_h = content_hash(old_plan)

            h["before"] = filter_state(h["before"], drop)
            h["after"] = filter_state(h["after"], drop)
            if content_hash(h["before"]) != content_hash(prior[a]):
                h["before"] = json.loads(json.dumps(prior[a]))
            h["before_hash"] = content_hash(h["before"])
            h["after_hash"] = content_hash(h["after"])

            plan = filter_plan(old_plan, drop)
            plan["pre_state_hash"] = h["before_hash"]
            h["source_plan"] = plan
            plan_map[old_plan_h] = content_hash(plan)
            state_map[old_before] = h["before_hash"]
            state_map[old_after] = h["after_hash"]
            new_hist.append(h)
            prior[a] = h["after"]
    m["reference_states"] = new_hist

    new_rows = []
    for r in intent_rows:
        if r["instrument"] in drop:
            continue
        rr = dict(r)
        if rr["source_plan_hash"] not in plan_map:
            die(f"unmapped source_plan_hash {rr.get('intent_id')}")
        if rr["reference_state_hash"] not in state_map:
            die(f"unmapped reference_state_hash {rr.get('intent_id')}")
        rr["source_plan_hash"] = plan_map[rr["source_plan_hash"]]
        rr["reference_state_hash"] = state_map[rr["reference_state_hash"]]
        body = {k: v for k, v in rr.items() if k != "intent_id"}
        rr["intent_id"] = content_hash(body)
        new_rows.append(rr)
    new_rows.sort(key=lambda r: (r["arm_id"], r["decision_at"], r["side"] != "SELL", r["instrument"], r["intent_id"]))
    m["intent_hash"] = content_hash(new_rows)
    m["arm_intent_hashes"] = {"P-BASE": content_hash([r for r in new_rows if r["arm_id"] == "P-BASE"])}
    try:
        m["metadata"]["inputs"]["initial_state"]["content_sha256"] = content_hash(m["initial_state"])
    except Exception:
        pass
    if m.get("contract_hash") != FROZEN_CONTRACT_HASH:
        die("contract_hash drift")
    if m.get("kind") != "frozen":
        die("kind must stay frozen")
    return m, new_rows


def write_pack(m, rows, constraints_rows, pref, drop):
    if PACK.exists():
        shutil.rmtree(PACK)
    PACK.mkdir(parents=True)
    crows = [r for r in constraints_rows if r.get("instrument") not in drop]
    intents_raw = csv_bytes(rows, INTENT_FIELDS)
    constraints_raw = csv_bytes(crows, CONSTRAINT_FIELDS)
    pref_raw = canonical_bytes(pref) + b"\n"
    m["artifacts"] = {
        "intents.csv": {"raw_sha256": raw_hash(intents_raw), "content_sha256": content_hash(rows)},
        "constraints.csv": {"raw_sha256": raw_hash(constraints_raw), "content_sha256": content_hash(crows)},
        "pref_check.json": {"raw_sha256": raw_hash(pref_raw), "content_sha256": content_hash(pref)},
    }
    (PACK / "intents.csv").write_bytes(intents_raw)
    (PACK / "constraints.csv").write_bytes(constraints_raw)
    (PACK / "pref_check.json").write_bytes(pref_raw)
    (PACK / "manifest.json").write_bytes(canonical_bytes(m))
    validate_manifest(m, rows)
    load_bundle(PACK)
    print(f"WROTE pack intents={len(rows)} constraints={len(crows)}", flush=True)


def export_bars(m, rows):
    cal = m["metadata"]["calendar"]
    instruments = sorted({r["instrument"] for r in rows} | set((m["initial_state"].get("positions") or {})))
    stamps = []
    for d in cal:
        stamps.extend(session_stamps(d))
    expected = len(stamps) * len(instruments)

    all_cal = [ln.strip() for ln in (QLIB / "calendars" / "1min.txt").read_text(encoding="utf-8").splitlines() if ln.strip()]
    idx = {}
    for i, ln in enumerate(all_cal):
        key = ln.replace(" ", "T")
        if len(key) >= 19:
            key = key[:19] + "+08:00"
        idx[key] = i
    stamp_i = []
    for s in stamps:
        if s not in idx:
            die(f"session minute missing in lake calendar: {s}")
        stamp_i.append(idx[s])
    i_lo, i_hi = min(stamp_i), max(stamp_i)

    day_idx = {}
    if (QLIB_DAY / "calendars" / "day.txt").is_file():
        days = [ln.strip()[:10] for ln in (QLIB_DAY / "calendars" / "day.txt").read_text(encoding="utf-8").splitlines() if ln.strip()]
        day_idx = {d: i for i, d in enumerate(days)}

    bars = []
    missing = []
    observed = 0
    for inst in instruments:
        folder = QLIB / "features" / inst.lower()
        op, cp, vp = folder / "open.1min.bin", folder / "close.1min.bin", folder / "volume.1min.bin"
        if not op.is_file() or not cp.is_file():
            missing.append({"instrument": inst, "reason": "no_bin", "n": len(stamps)})
            continue
        opens = load_bin(op, i_lo, i_hi)
        closes = load_bin(cp, i_lo, i_hi)
        vols = load_bin(vp, i_lo, i_hi) if vp.is_file() else np.full(i_hi - i_lo + 1, np.nan)
        zt, dtmap = {}, {}
        if day_idx:
            dfolder = QLIB_DAY / "features" / inst.lower()
            for name, dest in (("zhangting.day.bin", zt), ("dieting.day.bin", dtmap)):
                p = dfolder / name
                if not p.is_file():
                    continue
                d0, d1 = day_idx.get(cal[0]), day_idx.get(cal[-1])
                if d0 is None or d1 is None:
                    continue
                arr = load_bin(p, d0, d1)
                for day in cal:
                    j = day_idx.get(day)
                    if j is None:
                        continue
                    off = j - d0
                    if 0 <= off < len(arr):
                        v = float(arr[off])
                        if math.isfinite(v) and v > 0:
                            dest[day] = v
        ex = next((r["execution_symbol"] for r in rows if r["instrument"] == inst), inst)
        miss = 0
        for s, li in zip(stamps, stamp_i):
            off = li - i_lo
            o = float(opens[off]) if 0 <= off < len(opens) else float("nan")
            c = float(closes[off]) if 0 <= off < len(closes) else float("nan")
            if not (math.isfinite(o) and math.isfinite(c) and o > 0 and c > 0):
                miss += 1
                continue
            day = s[:10]
            lu = zt.get(day)
            ld = dtmap.get(day)
            if lu is None or not (lu >= max(o, c)):
                lu = max(o, c) * 100.0
            if ld is None or not (ld <= min(o, c)):
                ld = min(o, c) / 100.0
            v = float(vols[off]) if 0 <= off < len(vols) else float("nan")
            cap = float(v) if math.isfinite(v) and v > 0 else RESEARCH_CAP
            bars.append({
                "instrument": inst,
                "execution_symbol": ex,
                "timestamp": s,
                "open": o,
                "close": c,
                "limit_up": float(lu),
                "limit_down": float(ld),
                "suspended": False,
                "capacity": cap,
            })
            observed += 1
        if miss:
            missing.append({"instrument": inst, "reason": "ohlc_gap", "n": miss})

    coverage = {"expected": expected, "observed": observed, "missing": expected - observed,
                "n_instruments": len(instruments), "n_minutes": len(stamps)}
    if coverage["missing"] != 0:
        (WORK / "INPUT_BLOCKED_coverage_breakdown.json").write_text(
            json.dumps({"coverage": coverage, "missing": missing}, ensure_ascii=False, indent=2), encoding="utf-8")
        return None, coverage

    initial_at = f"{cal[0]}T09:29:00+08:00"
    initial_lots = {}
    for inst, p in (m["initial_state"].get("positions") or {}).items():
        lot = p["lot_id"]
        mark = p.get("mark_price") or p.get("price")
        if mark is None:
            die(f"no mark for initial lot {lot}")
        ex = next((r["execution_symbol"] for r in rows if r["instrument"] == inst), inst)
        initial_lots[lot] = {
            "acquired_at": p.get("acquired_at") or initial_at,
            "execution_symbol": ex,
            "mark_price": float(mark),
            "mark_at": p.get("mark_at") or initial_at,
        }
    md = {
        "calendar": list(cal),
        "timezone": "Asia/Shanghai",
        "price_domain": "none",
        "bar_label": "OPEN_TIME",
        "interval_seconds": 60,
        "sessions": sessions_map(cal),
        "session_source": "MQ_manifest_calendar+STATS_grid_241",
        "initial_at": initial_at,
        "initial_lots": initial_lots,
        "corporate_actions_complete": True,
        "source": f"QLIB_1MIN_ROOT={QLIB}; real open/close; capacity=volume|RESEARCH_CAP; limits=day|wide; no fabricated OHLC; contract_hash={FROZEN_CONTRACT_HASH}",
        "contract_hash": FROZEN_CONTRACT_HASH,
    }
    bundle = {
        "schema_version": SCHEMA_VERSION,
        "kind": "frozen_explicit",
        "metadata": md,
        "bars": bars,
        "corporate_actions": [],
    }
    bundle["content_sha256"] = content_hash({k: v for k, v in bundle.items() if k != "content_sha256"})
    validate_bars(bundle, m, rows)
    return bundle, coverage


def write_narrow_md(counts, coverage, metrics, head, blocker=None):
    text = "\n".join([
        "# NARROW.md — P-BASE narrow replay 2026-09-22",
        "",
        "## BT cartesian coverage fact",
        f"At tip `{REQUIRED_HEAD}`, validate_bars requires len(bars)==len(minutes)*len(instruments).",
        "No per-symbol calendar; lake has no suspension quotes for pre-listing minutes.",
        "Therefore the 150 contract_over_window_only names are **dropped** from this frozen knife.",
        "M-REF INPUT_BLOCKED for frozen; only P-BASE/M-LAG.",
        "",
        "## Universe",
        f"- dropped no_file (9): {counts['no_file']}",
        f"- dropped contract_over_window_only: {counts['cow_n']}",
        f"- kept full_window: {counts['full_n']}",
        "",
        "## Coverage",
        f"- expected: {coverage.get('expected')}",
        f"- observed: {coverage.get('observed')}",
        f"- missing: {coverage.get('missing')}",
        "",
        "## Metrics",
        f"- turnover: {metrics.get('turnover')}",
        f"- drawdown: {metrics.get('drawdown')}",
        f"- net_excess: {metrics.get('net_excess')}",
        f"- status: {metrics.get('status')}",
        "",
        f"## BT HEAD: `{head}`",
        f"## Blocker: {blocker or 'none'}",
        f"- pack: `{PACK}`",
        f"- bars: `{BARS_OUT}`",
        f"- replay: `{REPLAY_OUT}`",
        f"written_at: {datetime.now().astimezone().isoformat(timespec='seconds')}",
        "",
    ])
    WORK.mkdir(parents=True, exist_ok=True)
    (HANDOFF / "NARROW.md").write_text(text, encoding="utf-8")
    (WORK / "NARROW.md").write_text(text, encoding="utf-8")


def run_replay():
    if REPLAY_OUT.exists():
        die(f"replay out exists: {REPLAY_OUT}")
    cmd = [str(PYEXE), str(BT / "scripts" / "research" / "run_joint_return_replay.py"),
           "--intents", str(PACK), "--bars", str(BARS_OUT),
           "--arm", "P-BASE", "--fill-mode", "M-LAG", "--out", str(REPLAY_OUT)]
    print("RUN", " ".join(cmd), flush=True)
    env = os.environ.copy()
    env["PYTHONPATH"] = str(BT) + os.pathsep + env.get("PYTHONPATH", "")
    p = subprocess.run(cmd, cwd=str(BT), env=env, capture_output=True, text=True)
    print(p.stdout)
    print(p.stderr, file=sys.stderr)
    if p.returncode != 0:
        return {"status": f"EXIT_{p.returncode}", "turnover": None, "drawdown": None, "net_excess": None,
                "stdout": (p.stdout or "")[-2000:], "stderr": (p.stderr or "")[-2000:]}
    summary = json.loads((REPLAY_OUT / "summary.json").read_text(encoding="utf-8"))
    return {
        "status": summary.get("status"),
        "turnover": summary.get("turnover") or (summary.get("metrics") or {}).get("turnover"),
        "drawdown": summary.get("drawdown") or summary.get("max_drawdown") or (summary.get("metrics") or {}).get("drawdown"),
        "net_excess": summary.get("net_excess") or (summary.get("metrics") or {}).get("net_excess"),
    }


def main():
    WORK.mkdir(parents=True, exist_ok=True)
    BARS_OUT.parent.mkdir(parents=True, exist_ok=True)
    head = conf_head()
    print("BT_HEAD", head, flush=True)
    classes, drop, keep, counts = load_stats()
    print("DROP", len(drop), "KEEP", len(keep), flush=True)

    intent_rows = read_csv((SRC / "intents.csv").read_bytes(), INTENT_FIELDS, frozen=True)
    constraints_rows = read_csv((SRC / "constraints.csv").read_bytes(), CONSTRAINT_FIELDS, frozen=True)
    pref = dict(json.loads((SRC / "pref_check.json").read_text(encoding="utf-8")))
    pref["status"] = "NOT_RUN"

    print("Loading manifest...", flush=True)
    m = json.loads((SRC / "manifest.json").read_text(encoding="utf-8"))
    m2, rows2 = rewrite_manifest(m, drop, intent_rows)
    print(f"intents {len(intent_rows)} -> {len(rows2)}", flush=True)
    write_pack(m2, rows2, constraints_rows, pref, drop)

    by = {r["instrument"]: r for r in csv.DictReader(STATS_CSV.open(encoding="utf-8"))}
    with (WORK / "clipped_window_coverage_150.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["instrument", "bucket", "bin_start_ts", "bin_end_ts", "note"])
        for s, b in classes.items():
            if b == "contract_over_window_only":
                r = by[s]
                w.writerow([s, b, r["bin_start_ts"], r["bin_end_ts"], "excluded_from_frozen_knife_cartesian"])

    print("Exporting bars...", flush=True)
    bundle, coverage = export_bars(m2, rows2)
    write_narrow_md(counts, coverage, {"turnover": "NOT_RUN", "drawdown": "NOT_RUN", "net_excess": "NOT_RUN", "status": "PENDING"}, head,
                    None if coverage["missing"] == 0 else f"missing={coverage['missing']}")
    if bundle is None:
        die(f"coverage missing={coverage['missing']}")

    BARS_OUT.write_bytes(canonical_bytes(bundle))
    print(f"WROTE bars n={len(bundle['bars'])}", flush=True)

    metrics = run_replay()
    write_narrow_md(counts, coverage, metrics, head, None if metrics.get("status") == "BT_RESEARCH_REPLAY_PASS" else str(metrics))
    print("DONE", json.dumps({"counts": counts, "coverage": coverage, "metrics": metrics}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
