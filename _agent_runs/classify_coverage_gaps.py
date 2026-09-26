"""Classify why frozen-universe symbols miss Qlib 1min bars. No fabrication."""
from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

HANDOFF = Path(r"D:\PycharmProjects\MyQuant\runs\joint_return_4090_20260920_pr95\handoff_bt_20260922")
QLIB = Path(r"C:\Users\wangc\.qlib\qlib_data\my_data_1min")
INTENTS = HANDOFF / "portfolio_joint-return-control-only-50-5" / "intents.csv"
FREEZE = HANDOFF / "freeze_metadata.json"
WINDOW_START = datetime(2025, 1, 2, 9, 30, 0)
WINDOW_END = datetime(2025, 12, 31, 15, 0, 0)


def parse_stamp(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")


def main() -> None:
    freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
    days = set(freeze["calendar"])
    lines = (QLIB / "calendars" / "1min.txt").read_text(encoding="utf-8").splitlines()
    needed = [i for i, line in enumerate(lines) if line[:10] in days]
    print("needed", len(needed))

    listed = {}
    for line in (QLIB / "instruments" / "all.txt").read_text(encoding="utf-8").splitlines():
        parts = line.split("\t")
        if len(parts) >= 3:
            listed[parts[0].upper()] = (parts[1], parts[2])

    rows = list(csv.DictReader(INTENTS.read_text(encoding="utf-8").splitlines()))
    instruments = sorted({json.loads(r["instrument"]) for r in rows})
    buckets = {
        "no_feature_bin": [],
        "not_in_instruments_file": [],
        "starts_after_window": [],
        "ends_before_window": [],
        "both_edges": [],
        "listed_covers_window": [],
    }
    for inst in instruments:
        close_path = QLIB / "features" / inst.lower() / "close.1min.bin"
        meta = listed.get(inst.upper())
        if not close_path.exists():
            buckets["no_feature_bin"].append({"instrument": inst, "instruments_row": meta})
            continue
        if meta is None:
            buckets["not_in_instruments_file"].append(inst)
            continue
        start, end = parse_stamp(meta[0]), parse_stamp(meta[1])
        late = start > WINDOW_START
        early = end < WINDOW_END
        row = {"instrument": inst, "listed_start": meta[0], "listed_end": meta[1]}
        if late and early:
            buckets["both_edges"].append(row)
        elif late:
            buckets["starts_after_window"].append(row)
        elif early:
            buckets["ends_before_window"].append(row)
        else:
            buckets["listed_covers_window"].append(row)

    summary = {k: len(v) for k, v in buckets.items()}
    print(json.dumps(summary, ensure_ascii=False))
    out = Path(r"D:\PycharmProjects\MyQuant-backtrader\_agent_runs\coverage_gap_classes.json")
    out.write_text(json.dumps({"summary": summary, "buckets": buckets}, ensure_ascii=False, indent=2), encoding="utf-8")
    print("wrote", out)
    for key in ("no_feature_bin", "not_in_instruments_file", "ends_before_window", "both_edges"):
        print(key, json.dumps(buckets[key], ensure_ascii=False)[:2000])


if __name__ == "__main__":
    main()
