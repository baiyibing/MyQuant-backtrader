# -*- coding: utf-8 -*-
"""Rebuild hash-valid narrow pack from clock-patch portfolio + keep-set intents."""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

BT = Path(r"D:\PycharmProjects\MyQuant-backtrader")
sys.path.insert(0, str(BT))
from backtest.research.joint_return_replay import content_hash, raw_hash  # noqa: E402

FULL = Path(r"D:\PycharmProjects\MyQuant\runs\joint_return_4090_20260920_pr95\handoff_bt_20260922\narrow_clock_20260922\portfolio\joint-return-control-only-50-5-narrow-clock-patch")
NARROW_SRC = Path(r"D:\PycharmProjects\MyQuant\runs\joint_return_4090_20260920_pr95\handoff_bt_20260922\narrow_clock_20260922\portfolio_joint-return-control-only-50-5-narrow-clock-patch")
OUT = Path(r"D:\PycharmProjects\MyQuant\runs\joint_return_4090_20260920_pr95\handoff_bt_20260922\narrow_clock_20260922\portfolio_joint-return-control-only-50-5-narrow-clock-patch-remanifest")


def file_raw_sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    # copy companion files from FULL (manifest base), overwrite intents/constraints from narrow filter
    for name in ("manifest.json", "pref_check.json"):
        shutil.copy2(FULL / name, OUT / name)
    shutil.copy2(NARROW_SRC / "intents.csv", OUT / "intents.csv")
    shutil.copy2(NARROW_SRC / "constraints.csv", OUT / "constraints.csv")

    intents_raw = file_raw_sha(OUT / "intents.csv")
    constraints_raw = file_raw_sha(OUT / "constraints.csv")
    intents_bytes = (OUT / "intents.csv").read_bytes()
    constraints_bytes = (OUT / "constraints.csv").read_bytes()
    # Prefer library raw_hash/content_hash if they match file semantics
    try:
        rh_i = raw_hash(intents_bytes)
        ch_i = content_hash(intents_bytes)
        rh_c = raw_hash(constraints_bytes)
        ch_c = content_hash(constraints_bytes)
        print("lib_hashes", rh_i == intents_raw, rh_c == constraints_raw)
    except Exception as exc:
        print("lib_hash_fallback", exc)
        rh_i, ch_i = intents_raw, intents_raw
        rh_c, ch_c = constraints_raw, constraints_raw

    man = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))
    arts = man.setdefault("artifacts", {})
    arts["intents.csv"] = {
        **(arts.get("intents.csv") or {}),
        "raw_sha256": rh_i,
        "content_sha256": ch_i,
        "uri": str(OUT / "intents.csv"),
    }
    arts["constraints.csv"] = {
        **(arts.get("constraints.csv") or {}),
        "raw_sha256": rh_c,
        "content_sha256": ch_c,
        "uri": str(OUT / "constraints.csv"),
    }
    man["intent_hash"] = ch_i
    # keep arm_intent_hashes if single arm - recompute if possible
    if "arm_intent_hashes" in man and isinstance(man["arm_intent_hashes"], dict):
        if len(man["arm_intent_hashes"]) == 1:
            k = next(iter(man["arm_intent_hashes"]))
            man["arm_intent_hashes"][k] = ch_i
    (OUT / "manifest.json").write_text(json.dumps(man, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("OUT", OUT)
    print("intents_raw", rh_i)
    print("intents_content", ch_i)
    print("n_intent_bytes", len(intents_bytes))


if __name__ == "__main__":
    main()
