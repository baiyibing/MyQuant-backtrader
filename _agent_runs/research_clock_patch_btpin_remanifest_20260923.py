# -*- coding: utf-8 -*-
"""Patch next-session clocks into old narrow pack (BT-pinned contract) and remanifest."""
from __future__ import annotations

import copy
import csv
import hashlib
import json
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

BT = Path(r"D:\PycharmProjects\MyQuant-backtrader")
sys.path.insert(0, str(BT))
from backtest.research.joint_return_replay import content_hash, raw_hash  # noqa: E402

OLD = Path(r"D:\PycharmProjects\MyQuant\runs\joint_return_4090_20260920_pr95\handoff_bt_20260922\narrow_20260922\portfolio_joint-return-control-only-50-5-narrow")
SESSIONS = Path(r"D:\PycharmProjects\MyQuant\runs\joint_return_4090_20260920_pr95\handoff_bt_20260922\narrow_clock_20260922\sessions.json")
OUT = Path(r"D:\PycharmProjects\MyQuant\runs\joint_return_4090_20260920_pr95\handoff_bt_20260922\narrow_clock_20260922\portfolio_joint-return-control-only-50-5-narrow-clock-patch-btpin")
BARS = Path(r"D:\exports\joint_return_pbase_narrow_20260922\frozen_explicit_bars.json")
REPLAY_OUT = BT / "backtest_output" / "joint-return-v1" / "joint-return-control-only-50-5-narrow-clock-patch"
PY = r"D:\anaconda3\envs\vanna312\python.exe"
OLD_CONTRACT = "9ee8cc3c63c1e7a0910c777c9a58fa4b884a89a853586a65363dc818b54cfe41"


def die(msg: str) -> None:
    raise SystemExit("FATAL: " + msg)


def cell(v):
    if isinstance(v, str):
        try:
            return json.loads(v)
        except Exception:
            return v
    return v


def enc_row(d: dict, fields: list[str]) -> list[str]:
    return [json.dumps(d[k], ensure_ascii=False, separators=(",", ":")) for k in fields]


def main() -> None:
    sessions = {r["date"]: r for r in json.loads(SESSIONS.read_text(encoding="utf-8"))}
    print("load_manifest", flush=True)
    man = json.loads((OLD / "manifest.json").read_text(encoding="utf-8"))
    if man.get("contract_hash") != OLD_CONTRACT:
        die("unexpected old contract " + str(man.get("contract_hash")))

    # patch reference_states source_plan clocks + rebuild plan hash map
    old_to_new_plan_hash = {}
    plan_bug = 0
    plan_ctr = Counter()
    for h in man["reference_states"]:
        p = h["source_plan"]
        day = p["date"]
        s = sessions.get(day)
        if not s:
            die("no session for " + day)
        av0, ex0 = p.get("available_at", ""), p.get("expires_at", "")
        if av0[11:16] == "15:03" and ex0[11:16] == "16:00" and av0[:10] == ex0[:10]:
            plan_bug += 1
        old_h = content_hash(p)
        p = copy.deepcopy(p)
        p["available_at"] = s["available_at"]
        p["effective_at"] = s["effective_at"]
        p["expires_at"] = s["expires_at"]
        # keep decision_at/mark_at
        new_h = content_hash(p)
        old_to_new_plan_hash[(h["arm_id"], old_h)] = new_h
        h["source_plan"] = p
        av, ex = p["available_at"], p["expires_at"]
        plan_ctr[(av[11:16], ex[11:16], av[:10] == ex[:10])] += 1
    print("plans_patched", len(man["reference_states"]), "old_bugish", plan_bug, "patterns", plan_ctr.most_common(), flush=True)

    # patch intents
    fields = None
    rows = []
    with (OLD / "intents.csv").open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        fields = list(reader.fieldnames)
        for raw in reader:
            r = {k: cell(v) for k, v in raw.items()}
            day = r["decision_at"][:10]
            s = sessions[day]
            key = (r["arm_id"], r["source_plan_hash"])
            if key not in old_to_new_plan_hash:
                # try using content of clocks from decision date only
                die("missing plan map for " + str(key))
            r["source_plan_hash"] = old_to_new_plan_hash[key]
            r["available_at"] = s["available_at"]
            r["effective_at"] = s["effective_at"]
            r["expires_at"] = s["expires_at"]
            rows.append(r)
    intent_bug = sum(
        1
        for r in rows
        if r["available_at"][11:16] == "15:03"
        and r["expires_at"][11:16] == "16:00"
        and r["available_at"][:10] == r["expires_at"][:10]
    )
    if intent_bug:
        die("intent bug remains " + str(intent_bug))
    intent_ctr = Counter(
        (r["available_at"][11:16], r["expires_at"][11:16], r["available_at"][:10] == r["expires_at"][:10])
        for r in rows
    )
    print("intents", len(rows), "patterns", intent_ctr.most_common(), flush=True)

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    for p in OLD.iterdir():
        if p.is_file() and p.name not in ("intents.csv", "manifest.json"):
            shutil.copy2(p, OUT / p.name)

    with (OUT / "intents.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(fields)
        for r in rows:
            w.writerow(enc_row(r, fields))

    intents_raw = (OUT / "intents.csv").read_bytes()
    rh = raw_hash(intents_raw)
    ch = content_hash(rows)
    man["intent_hash"] = ch
    for k in list(man.get("arm_intent_hashes", {}) or {}):
        man["arm_intent_hashes"][k] = content_hash([r for r in rows if r["arm_id"] == k])
    arts = man.setdefault("artifacts", {})
    arts.setdefault("intents.csv", {})
    arts["intents.csv"]["raw_sha256"] = rh
    arts["intents.csv"]["content_sha256"] = ch
    # keep contract
    man["contract_hash"] = OLD_CONTRACT
    if "metadata" in man and isinstance(man["metadata"], dict):
        man["metadata"]["contract_hash"] = OLD_CONTRACT

    (OUT / "manifest.json").write_text(json.dumps(man, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("wrote", OUT, "intent_hash", ch, flush=True)

    if REPLAY_OUT.exists():
        shutil.rmtree(REPLAY_OUT)
    cmd = [
        PY, "-u", str(BT / "scripts" / "research" / "run_joint_return_replay.py"),
        "--intents", str(OUT),
        "--bars", str(BARS),
        "--arm", "P-BASE",
        "--fill-mode", "M-LAG",
        "--out", str(REPLAY_OUT),
    ]
    print("RUN", " ".join(cmd), flush=True)
    rc = subprocess.run(cmd, cwd=str(BT)).returncode
    print("rc", rc, flush=True)
    if rc != 0:
        die("replay rc=%s" % rc)
    print((REPLAY_OUT / "summary.json").read_text(encoding="utf-8")[:4000], flush=True)


if __name__ == "__main__":
    main()
