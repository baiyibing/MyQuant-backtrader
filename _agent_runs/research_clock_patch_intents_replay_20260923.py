# -*- coding: utf-8 -*-
"""RESEARCH_CLOCK_PATCH intents-only: patch clocks on old narrow pack; remanifest; P-BASE/M-LAG replay."""
from __future__ import annotations

import csv
import hashlib
import json
import shutil
import subprocess
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

BT = Path(r"D:\PycharmProjects\MyQuant-backtrader")
sys.path.insert(0, str(BT))
from backtest.research.joint_return_replay import content_hash, raw_hash  # noqa: E402

OLD_PACK = Path(
    r"D:\PycharmProjects\MyQuant\runs\joint_return_4090_20260920_pr95\handoff_bt_20260922\narrow_20260922\portfolio_joint-return-control-only-50-5-narrow"
)
SESSIONS = Path(
    r"D:\PycharmProjects\MyQuant\runs\joint_return_4090_20260920_pr95\handoff_bt_20260922\narrow_clock_20260922\sessions.json"
)
OUT_PACK = Path(
    r"D:\PycharmProjects\MyQuant\runs\joint_return_4090_20260920_pr95\handoff_bt_20260922\narrow_clock_20260922\portfolio_joint-return-control-only-50-5-narrow-clock-patch-btpin"
)
BARS = Path(r"D:\exports\joint_return_pbase_narrow_20260922\frozen_explicit_bars.json")
OUT_REPLAY = BT / "backtest_output" / "joint-return-v1" / "joint-return-control-only-50-5-narrow-clock-patch"
PY = Path(r"D:\anaconda3\envs\vanna312\python.exe")


def die(msg: str) -> None:
    raise SystemExit("FATAL: " + msg)


def sq(s: str) -> str:
    s = (s or "").strip()
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        return s[1:-1]
    return s


def file_sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    for p in (OLD_PACK, SESSIONS, BARS):
        if not p.exists():
            die("missing " + str(p))
    sessions = json.loads(SESSIONS.read_text(encoding="utf-8"))
    by_date = {
        r["date"]: {
            "available_at": r["available_at"],
            "effective_at": r["effective_at"],
            "expires_at": r["expires_at"],
        }
        for r in sessions
    }

    if OUT_PACK.exists():
        shutil.rmtree(OUT_PACK)
    OUT_PACK.mkdir(parents=True)
    # copy all companions from old pack
    for p in OLD_PACK.iterdir():
        if p.is_file():
            shutil.copy2(p, OUT_PACK / p.name)

    # patch intents clocks by decision date
    src_rows = list(csv.DictReader((OLD_PACK / "intents.csv").open(encoding="utf-8", newline="")))
    fields = list(src_rows[0].keys())
    out_rows = []
    bug0 = bug1 = 0
    ctr = Counter()
    missing = []
    for r in src_rows:
        decision = sq(r["decision_at"])
        day = decision[:10]
        clocks = by_date.get(day)
        if not clocks:
            missing.append(day)
            continue
        av0, ex0 = sq(r["available_at"]), sq(r["expires_at"])
        if av0[11:16] == "15:03" and ex0[11:16] == "16:00" and av0[:10] == ex0[:10]:
            bug0 += 1
        r = dict(r)
        # preserve CSV quoting style of old pack (values often JSON-encoded strings)
        def enc(v: str) -> str:
            # old pack stores JSON-string cells via json.dumps in writer sometimes;
            # keep same style as source cell if it was quoted json string
            return json.dumps(v, ensure_ascii=False)

        # detect encoding style from original available_at cell
        raw_cell = src_rows[0]["available_at"]
        if raw_cell.startswith('"'):
            r["available_at"] = enc(clocks["available_at"])
            r["effective_at"] = enc(clocks["effective_at"])
            r["expires_at"] = enc(clocks["expires_at"])
        else:
            r["available_at"] = clocks["available_at"]
            r["effective_at"] = clocks["effective_at"]
            r["expires_at"] = clocks["expires_at"]
        av, ex = clocks["available_at"], clocks["expires_at"]
        ctr[(av[11:16], ex[11:16], av[:10] == ex[:10])] += 1
        if av[11:16] == "15:03" and ex[11:16] == "16:00" and av[:10] == ex[:10]:
            bug1 += 1
        out_rows.append(r)
    if missing:
        die("session missing for days: " + str(sorted(set(missing))[:10]))
    if bug1:
        die("patched intents still have same-day 15:03->16:00")
    print("patched", len(out_rows), "old_bug", bug0, "new_bug", bug1, "patterns", ctr.most_common(), flush=True)

    # write intents with same quoting as original (json.dumps per cell like old producer)
    with (OUT_PACK / "intents.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(fields)
        for r in out_rows:
            # if original used json.dumps for every cell, continue that
            sample = src_rows[0]
            if sample["instrument"].startswith('"'):
                w.writerow([r[k] if r[k].startswith('"') else json.dumps(sq(r[k]) if k in ("available_at","effective_at","expires_at","decision_at") else sq(r[k]), ensure_ascii=False) for k in fields])
            else:
                w.writerow([r[k] for k in fields])

    # Actually rewrite cleanly: mirror old producer csv_bytes style (json.dumps each field)
    with (OUT_PACK / "intents.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(fields)
        for r in out_rows:
            row_out = []
            for k in fields:
                val = r[k]
                # values already json-encoded strings for clock fields; others from source
                if k in ("available_at", "effective_at", "expires_at"):
                    # ensure json string cell
                    inner = sq(val)
                    row_out.append(json.dumps(inner, ensure_ascii=False))
                else:
                    # keep original cell text as-is if already encoded
                    row_out.append(val if isinstance(val, str) else json.dumps(val, ensure_ascii=False))
            w.writerow(row_out)

    raw = (OUT_PACK / "intents.csv").read_bytes()
    rh = raw_hash(raw)
    # content hash of parsed rows (as replay does)
    parsed = list(csv.DictReader((OUT_PACK / "intents.csv").open(encoding="utf-8", newline="")))
    # parse json cells
    def parse_row(r):
        out = {}
        for k, v in r.items():
            try:
                out[k] = json.loads(v)
            except Exception:
                out[k] = v
        return out
    parsed_obj = [parse_row(r) for r in parsed]
    ch = content_hash(parsed_obj)
    print("intents_raw", rh, "content", ch, flush=True)

    man = json.loads((OUT_PACK / "manifest.json").read_text(encoding="utf-8"))
    # update artifact hashes — support both key spellings
    arts = man.get("artifacts") or man.get("artifacts")
    if "artifacts" in man:
        arts = man["artifacts"]
        if "intents.csv" in arts:
            arts["intents.csv"]["raw_sha256"] = rh
            arts["intents.csv"]["content_sha256"] = ch
    if "intent_hash" in man:
        man["intent_hash"] = ch
    if "arm_intent_hashes" in man and isinstance(man["arm_intent_hashes"], dict):
        for k in list(man["arm_intent_hashes"]):
            man["arm_intent_hashes"][k] = ch
    (OUT_PACK / "manifest.json").write_text(json.dumps(man, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("pack", OUT_PACK, "contract", man.get("contract_hash"), flush=True)

    if OUT_REPLAY.exists():
        shutil.rmtree(OUT_REPLAY)
    cmd = [
        str(PY), "-u", str(BT / "scripts" / "research" / "run_joint_return_replay.py"),
        "--intents", str(OUT_PACK),
        "--bars", str(BARS),
        "--arm", "P-BASE",
        "--fill-mode", "M-LAG",
        "--out", str(OUT_REPLAY),
    ]
    print("RUN", " ".join(cmd), flush=True)
    rc = subprocess.run(cmd, cwd=str(BT)).returncode
    print("replay_rc", rc, flush=True)
    if rc != 0:
        die("replay failed rc=%s" % rc)
    summary = OUT_REPLAY / "summary.json"
    print("summary", summary.exists(), flush=True)
    if summary.exists():
        print(summary.read_text(encoding="utf-8")[:3000], flush=True)


if __name__ == "__main__":
    main()
