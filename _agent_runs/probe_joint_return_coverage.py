"""Probe Qlib 1min coverage for the frozen joint-return universe. No bar fabrication."""
from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np

HANDOFF = Path(r"D:\PycharmProjects\MyQuant\runs\joint_return_4090_20260920_pr95\handoff_bt_20260922")
QLIB = Path(r"C:\Users\wangc\.qlib\qlib_data\my_data_1min")
INTENTS = HANDOFF / "portfolio_joint-return-control-only-50-5" / "intents.csv"
FREEZE = HANDOFF / "freeze_metadata.json"
MANIFEST = HANDOFF / "portfolio_joint-return-control-only-50-5" / "manifest.json"


def main() -> None:
    freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
    calendar_days = freeze["calendar"]
    print("mq_days", len(calendar_days), calendar_days[0], calendar_days[-1])

    lines = (QLIB / "calendars" / "1min.txt").read_text(encoding="utf-8").splitlines()
    by_day: dict[str, list[int]] = {}
    for i, line in enumerate(lines):
        day = line[:10]
        if day in by_day or day >= "2025-01-01":
            by_day.setdefault(day, []).append(i)
    missing_days = [d for d in calendar_days if d not in by_day]
    print("qlib_missing_days", len(missing_days), missing_days[:5])
    counts = {d: len(by_day[d]) for d in calendar_days if d in by_day}
    uniq = sorted(set(counts.values()))
    print("bars_per_day_unique", uniq)
    sample_day = calendar_days[0]
    stamps = [lines[i] for i in by_day[sample_day]]
    print("sample_day_n", len(stamps), "first", stamps[0], "last", stamps[-1])
    clocks = [s[11:] for s in stamps]
    print("has_1130", "11:30:00" in clocks, "has_1300", "13:00:00" in clocks, "has_1301", "13:01:00" in clocks, "has_1500", "15:00:00" in clocks)
    gaps = []
    for a, b in zip(stamps, stamps[1:]):
        # report clock jumps larger than 1 minute
        pass
    from datetime import datetime
    prev = None
    for s in stamps:
        t = datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
        if prev is not None:
            delta = (t - prev).total_seconds()
            if delta != 60:
                gaps.append((prev.strftime("%H:%M:%S"), t.strftime("%H:%M:%S"), int(delta)))
        prev = t
    print("intraday_gaps", gaps)

    rows = list(csv.DictReader(INTENTS.read_text(encoding="utf-8").splitlines()))
    instruments = sorted({json.loads(r["instrument"]) for r in rows})
    print("intent_symbols", len(instruments))

    # initial positions without loading the 663MB manifest fully
    raw = MANIFEST.read_bytes()
    key = b'"initial_state"'
    pos = raw.find(key)
    print("initial_state_at", pos)
    print(raw[pos:pos + 500].decode("utf-8", errors="replace"))

    needed_idx = []
    for d in calendar_days:
        needed_idx.extend(by_day.get(d, []))
    needed = np.asarray(needed_idx, dtype=np.int64)
    print("needed_minutes", int(needed.size), "expected_if_all_symbols", int(needed.size) * len(instruments))

    # instrument listing ranges
    listed = {}
    for line in (QLIB / "instruments" / "all.txt").read_text(encoding="utf-8").splitlines():
        parts = line.split("\t")
        if len(parts) >= 3:
            listed[parts[0].upper()] = (parts[1], parts[2])

    missing_symbol = []
    observed = 0
    missing = 0
    nan_inside = 0
    nonpositive = 0
    no_bin = []
    short_list = []
    per_symbol_missing = []
    for n, inst in enumerate(instruments, 1):
        folder = QLIB / "features" / inst.lower()
        close_path = folder / "close.1min.bin"
        open_path = folder / "open.1min.bin"
        if not close_path.exists() or not open_path.exists():
            no_bin.append(inst)
            missing += int(needed.size)
            per_symbol_missing.append((inst, int(needed.size), "NO_BIN"))
            continue
        close = np.fromfile(close_path, dtype="<f4")
        open_ = np.fromfile(open_path, dtype="<f4")
        if close.size < 2 or open_.size < 2:
            no_bin.append(inst)
            missing += int(needed.size)
            per_symbol_missing.append((inst, int(needed.size), "EMPTY_BIN"))
            continue
        c0 = int(np.round(close[0]))
        o0 = int(np.round(open_[0]))
        cvals = close[1:]
        ovals = open_[1:]
        if c0 != o0 or cvals.size != ovals.size:
            per_symbol_missing.append((inst, -1, f"ALIGN {c0}/{o0} {cvals.size}/{ovals.size}"))
        # map needed index -> local
        local = needed - c0
        in_range = (local >= 0) & (local < cvals.size)
        ok = np.zeros(needed.size, dtype=bool)
        if in_range.any():
            loc = local[in_range]
            cv = cvals[loc]
            ov = ovals[loc]
            finite = np.isfinite(cv) & np.isfinite(ov)
            positive = (cv > 0) & (ov > 0)
            good = finite & positive
            ok[np.flatnonzero(in_range)[good]] = True
            nan_inside += int((in_range.sum()) - int(finite.sum()))
            nonpositive += int(finite.sum() - good.sum())
        got = int(ok.sum())
        miss = int(needed.size - got)
        observed += got
        missing += miss
        if miss:
            meta = listed.get(inst.upper())
            per_symbol_missing.append((inst, miss, str(meta)))
        if n % 100 == 0:
            print(f"progress {n}/{len(instruments)} observed={observed} missing={missing}", flush=True)

    expected = int(needed.size) * len(instruments)
    print("NO_BIN", len(no_bin), no_bin[:20])
    print("EXPECTED", expected)
    print("OBSERVED", observed)
    print("MISSING", missing)
    print("nan_inside_range", nan_inside, "nonpositive", nonpositive)
    print("symbols_with_gaps", len(per_symbol_missing))
    per_symbol_missing.sort(key=lambda x: -x[1] if isinstance(x[1], int) else 0)
    print("worst20")
    for row in per_symbol_missing[:20]:
        print(row)
    out = Path(r"D:\PycharmProjects\MyQuant-backtrader\_agent_runs\coverage_probe.json")
    out.write_text(json.dumps({
        "expected_symbol_minutes": expected,
        "observed_symbol_minutes": observed,
        "missing_symbol_minutes": missing,
        "intent_symbols": len(instruments),
        "needed_minutes": int(needed.size),
        "mq_days": len(calendar_days),
        "qlib_missing_days": missing_days,
        "no_bin": no_bin,
        "symbols_with_gaps": len(per_symbol_missing),
        "nan_inside_range": nan_inside,
        "nonpositive": nonpositive,
        "worst": [{"instrument": a, "missing": b, "note": c} for a, b, c in per_symbol_missing[:50]],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print("wrote", out)


if __name__ == "__main__":
    main()
