# -*- coding: utf-8 -*-
"""QLIB 1min lake coverage stats vs joint-return P-BASE handoff. No fabrication, no replay."""
from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

HANDOFF = Path(r"D:\PycharmProjects\MyQuant\runs\joint_return_4090_20260920_pr95\handoff_bt_20260922")
QLIB = Path(r"C:\Users\wangc\.qlib\qlib_data\my_data_1min")
INTENTS = HANDOFF / "portfolio_joint-return-control-only-50-5" / "intents.csv"
FREEZE = HANDOFF / "freeze_metadata.json"
DAY_CAL = Path(r"C:\Users\wangc\.qlib\qlib_data\cn_data\calendars\day.txt")
OUT_MD = HANDOFF / "QLIB_1MIN_STATS.md"
OUT_CSV = HANDOFF / "QLIB_1MIN_STATS_by_symbol.csv"
OUT_DONE = HANDOFF / "QLIB_1MIN_STATS.DONE"
OUT_JSON = Path(r"D:\PycharmProjects\MyQuant-backtrader\_agent_runs\qlib_1min_stats_20260922.json")

WINDOW_START = datetime(2025, 1, 2, 9, 30, 0)
WINDOW_END = datetime(2025, 12, 31, 15, 0, 0)
ABSENT_EXPECTED = [
    "BJ920680", "SH600200", "SH600355", "SH603388",
    "SZ000851", "SZ002231", "SZ300344", "SZ300379", "SZ300391",
]


def parse_field(v: str) -> str:
    v = (v or "").strip()
    if not v:
        return v
    if v[0] in "\"'":
        try:
            return str(json.loads(v)).upper()
        except Exception:
            return v.strip("\"'").upper()
    return v.upper()


def exchange_of(sym: str) -> str:
    s = sym.upper()
    if s.startswith("SH"):
        return "SH"
    if s.startswith("SZ"):
        return "SZ"
    if s.startswith("BJ"):
        return "BJ"
    return "OTHER"


def parse_ts(s: str) -> datetime:
    s = s.strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    raise ValueError(s)


def expected_session_clocks() -> list[str]:
    out = []
    t = datetime(2000, 1, 1, 9, 30, 0)
    end_am = datetime(2000, 1, 1, 11, 30, 0)
    while t <= end_am:
        out.append(t.strftime("%H:%M:%S"))
        t += timedelta(minutes=1)
    t = datetime(2000, 1, 1, 13, 1, 0)
    end_pm = datetime(2000, 1, 1, 15, 0, 0)
    while t <= end_pm:
        out.append(t.strftime("%H:%M:%S"))
        t += timedelta(minutes=1)
    return out


def load_intents() -> list[str]:
    rows = list(csv.DictReader(INTENTS.read_text(encoding="utf-8").splitlines()))
    return sorted({parse_field(r["instrument"]) for r in rows})


def read_bin(path: Path):
    arr = np.fromfile(path, dtype="<f4")
    if arr.size < 2:
        return None, arr
    return int(np.round(float(arr[0]))), arr[1:]


def main() -> None:
    freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
    mq_days = list(freeze["calendar"])
    intents = load_intents()
    min_lines = (QLIB / "calendars" / "1min.txt").read_text(encoding="utf-8").splitlines()
    ashare_2025 = [d for d in DAY_CAL.read_text(encoding="utf-8").splitlines() if d.startswith("2025-")]

    listed: dict[str, tuple[str, str]] = {}
    for line in (QLIB / "instruments" / "all.txt").read_text(encoding="utf-8").splitlines():
        parts = line.split("\t")
        if len(parts) >= 3:
            listed[parts[0].upper()] = (parts[1], parts[2])

    feature_dirs = [p for p in (QLIB / "features").iterdir() if p.is_dir()]
    bin_files = list((QLIB / "features").rglob("*.1min.bin"))
    exch_dirs = Counter(exchange_of(p.name) for p in feature_dirs)
    exch_listed = Counter(exchange_of(k) for k in listed)

    min_days = sorted({ln[:10] for ln in min_lines})
    mq_set, ashare_set, min_day_set = set(mq_days), set(ashare_2025), set(min_days)
    missing_vs_ashare = sorted(ashare_set - mq_set)
    extra_vs_ashare = sorted(mq_set - ashare_set)
    mq_missing_in_1min = sorted(mq_set - min_day_set)

    by_day_idx: dict[str, list[int]] = {}
    for i, ln in enumerate(min_lines):
        by_day_idx.setdefault(ln[:10], []).append(i)

    expect_clocks = expected_session_clocks()
    assert len(expect_clocks) == 241

    day_minute_rows = []
    for d in mq_days:
        idxs = by_day_idx.get(d, [])
        clocks = [min_lines[i][11:] for i in idxs]
        clock_set = set(clocks)
        missing_clocks = [c for c in expect_clocks if c not in clock_set]
        day_minute_rows.append({
            "date": d,
            "n": len(clocks),
            "missing_clocks_n": len(missing_clocks),
            "has_1300": "13:00:00" in clock_set,
        })
    n_perfect = sum(1 for r in day_minute_rows if r["n"] == 241 and r["missing_clocks_n"] == 0)
    n_bad = [r for r in day_minute_rows if not (r["n"] == 241 and r["missing_clocks_n"] == 0)]

    needed_idx: list[int] = []
    for d in mq_days:
        needed_idx.extend(by_day_idx.get(d, []))
    needed = np.asarray(needed_idx, dtype=np.int64)

    per_rows = []
    observed_total = 0
    missing_total = 0
    for n, inst in enumerate(intents, 1):
        folder = QLIB / "features" / inst.lower()
        open_p = folder / "open.1min.bin"
        close_p = folder / "close.1min.bin"
        meta = listed.get(inst)
        row = {
            "instrument": inst,
            "exchange": exchange_of(inst),
            "in_instruments_all": meta is not None,
            "listed_start": meta[0] if meta else "",
            "listed_end": meta[1] if meta else "",
            "has_open_bin": open_p.exists(),
            "has_close_bin": close_p.exists(),
            "bin_start_idx": "",
            "bin_end_idx": "",
            "bin_start_ts": "",
            "bin_end_ts": "",
            "bin_rows": 0,
            "expected_minutes": int(needed.size),
            "observed_minutes": 0,
            "missing_minutes": int(needed.size),
            "bucket": "",
            "note": "",
        }
        if not open_p.exists() or not close_p.exists():
            row["bucket"] = "no_file"
            row["note"] = "missing open/close 1min.bin"
            missing_total += int(needed.size)
            per_rows.append(row)
            continue

        o0, ovals = read_bin(open_p)
        c0, cvals = read_bin(close_p)
        if o0 is None or c0 is None or cvals.size == 0:
            row["bucket"] = "no_file"
            row["note"] = "empty bin"
            missing_total += int(needed.size)
            per_rows.append(row)
            continue

        start = int(c0)
        end_idx = start + len(cvals) - 1
        row["bin_start_idx"] = start
        row["bin_end_idx"] = end_idx
        row["bin_rows"] = int(len(cvals))
        if 0 <= start < len(min_lines):
            row["bin_start_ts"] = min_lines[start]
        if 0 <= end_idx < len(min_lines):
            row["bin_end_ts"] = min_lines[end_idx]
        if c0 != o0 or cvals.size != ovals.size:
            row["note"] = f"align_mismatch close0={c0} open0={o0} csize={cvals.size} osize={ovals.size}"

        local = needed - start
        in_range = (local >= 0) & (local < len(cvals))
        ok = np.zeros(needed.size, dtype=bool)
        if in_range.any():
            loc = local[in_range]
            cv = cvals[loc]
            if o0 == c0 and len(ovals) == len(cvals):
                ov = ovals[loc]
            else:
                ov = np.full(loc.shape, np.nan, dtype=np.float32)
                for j, need_i in enumerate(np.flatnonzero(in_range)):
                    lo = int(needed[need_i] - o0)
                    if 0 <= lo < len(ovals):
                        ov[j] = ovals[lo]
            good = np.isfinite(cv) & np.isfinite(ov) & (cv > 0) & (ov > 0)
            ok[np.flatnonzero(in_range)[good]] = True

        got = int(ok.sum())
        miss = int(needed.size - got)
        row["observed_minutes"] = got
        row["missing_minutes"] = miss
        observed_total += got
        missing_total += miss

        overlap = int(in_range.sum())
        inside_miss = int(overlap - int(ok[in_range].sum())) if overlap else 0
        outside = int((~in_range).sum())
        late = False
        early_end = False
        try:
            if row["bin_start_ts"]:
                late = parse_ts(row["bin_start_ts"]) > WINDOW_START
            if row["bin_end_ts"]:
                early_end = parse_ts(row["bin_end_ts"]) < WINDOW_END
        except Exception as e:
            row["note"] = (row["note"] + f"; ts_parse={e}").strip("; ")

        if got == int(needed.size):
            row["bucket"] = "full_window"
        elif inside_miss > 0:
            row["bucket"] = "intraday_minutes_incomplete"
            row["note"] = (row["note"] + f"; inside_miss={inside_miss}; outside={outside}").strip("; ")
        elif late or early_end:
            # fully good inside overlap; gap is outside bin life
            if outside == miss and inside_miss == 0:
                row["bucket"] = "contract_over_window_only" if (late or early_end) else "file_but_calendar_short"
            else:
                row["bucket"] = "file_but_calendar_short"
            if late:
                row["note"] = (row["note"] + "; late_feature_start").strip("; ")
            if early_end:
                row["note"] = (row["note"] + "; early_feature_end").strip("; ")
        elif outside == miss and got > 0 and inside_miss == 0:
            row["bucket"] = "contract_over_window_only"
        else:
            row["bucket"] = "file_but_calendar_short"

        per_rows.append(row)
        if n % 100 == 0:
            print(f"progress {n}/{len(intents)} obs={observed_total} miss={missing_total}", flush=True)

    bucket_counts = Counter(r["bucket"] for r in per_rows)
    late_rows = []
    for r in per_rows:
        if r["bin_start_ts"]:
            try:
                if parse_ts(r["bin_start_ts"]) > WINDOW_START:
                    late_rows.append(r)
            except Exception:
                pass

    expected_total = int(needed.size) * len(intents)
    n_no = bucket_counts.get("no_file", 0)
    n_short = bucket_counts.get("file_but_calendar_short", 0)
    n_intra = bucket_counts.get("intraday_minutes_incomplete", 0)
    n_over = bucket_counts.get("contract_over_window_only", 0)
    n_full = bucket_counts.get("full_window", 0)

    if n_perfect == len(mq_days) and n_intra == 0 and (n_no + n_short + n_over) > 0:
        conclusion = (
            "更像「湖真缺 / 标的生命周期短于 intent 全窗」：1min 交易日网格相对 A 股日历与 241 分钟契约完整，"
            f"缺口主要来自 {n_no} 只无 bin、以及约 {n_short + n_over} 只特征日历短于 2025 全窗（含晚上市），"
            "而非 expected 日历把交易日算严了。"
        )
    elif n_intra > 0 and n_intra >= max(n_short, 1):
        conclusion = "更像「湖真缺」为主（含日内分钟空洞），不是单纯 expected 日历过严。"
    else:
        conclusion = (
            "混合：交易日网格本身完整，但 intent 全窗对晚上市/无 bin 标的过严；"
            "若收窄宇宙或按标的存活期裁窗，expected 会下降，但仍有真实无 bin / 短历史。"
        )

    fields = list(per_rows[0].keys())
    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(per_rows)

    lines: list[str] = []
    lines.append("# QLIB_1MIN_STATS — my_data_1min coverage vs P-BASE handoff")
    lines.append("")
    lines.append(f"- generated_at: {datetime.now().astimezone().isoformat(timespec='seconds')}")
    lines.append("- host: 4090")
    lines.append(f"- QLIB_1MIN_ROOT: `{QLIB}`")
    lines.append(f"- handoff: `{HANDOFF}`")
    lines.append("- method: read-only probe; no bars fabricated; no replay")
    lines.append("- note: headless Cursor --print stalled twice; stats produced by 4090 local Python probe")
    lines.append("")
    lines.append("## 1) Lake overall")
    lines.append("")
    lines.append("| metric | value |")
    lines.append("|---|---|")
    lines.append(f"| instruments/all.txt rows | {len(listed)} |")
    lines.append(f"| features/ directories | {len(feature_dirs)} |")
    lines.append(f"| total `*.1min.bin` files | {len(bin_files)} |")
    lines.append(f"| 1min calendar stamps | {len(min_lines)} |")
    lines.append(f"| 1min calendar first | {min_lines[0]} |")
    lines.append(f"| 1min calendar last | {min_lines[-1]} |")
    lines.append(f"| distinct days in 1min calendar | {len(min_days)} ({min_days[0]} .. {min_days[-1]}) |")
    lines.append(f"| freeze/MQ trading days (2025 window) | {len(mq_days)} ({mq_days[0]} .. {mq_days[-1]}) |")
    lines.append("")
    lines.append("Exchange distribution (feature dirs / instruments listing):")
    lines.append("")
    lines.append("| exchange | feature dirs | instruments/all |")
    lines.append("|---|---:|---:|")
    for ex in ["SH", "SZ", "BJ", "OTHER"]:
        lines.append(f"| {ex} | {exch_dirs.get(ex, 0)} | {exch_listed.get(ex, 0)} |")
    lines.append("")
    lines.append("## 2) Calendar integrity")
    lines.append("")
    lines.append("Minute window contract (same as RESULT.md): **AM 09:30–11:30** and **PM 13:01–15:00** (no 13:00), **241** stamps/session.")
    lines.append("")
    lines.append(f"- A-share day calendar source: `{DAY_CAL}` (2025 days: {len(ashare_2025)})")
    lines.append(f"- MQ freeze days not in A-share 2025 day list: **{len(extra_vs_ashare)}** {extra_vs_ashare[:10]}")
    lines.append(f"- A-share 2025 days missing from MQ freeze calendar: **{len(missing_vs_ashare)}** {missing_vs_ashare[:20]}")
    lines.append(f"- MQ days missing from 1min.txt: **{len(mq_missing_in_1min)}** {mq_missing_in_1min[:10]}")
    lines.append(f"- MQ sessions with exact 241 contract stamps: **{n_perfect}/{len(mq_days)}**")
    if n_bad:
        lines.append(f"- Sessions not exact 241: {len(n_bad)} (up to 8 shown)")
        for r in n_bad[:8]:
            lines.append(f"  - {r['date']}: n={r['n']} missing_clocks={r['missing_clocks_n']} has_1300={r['has_1300']}")
    else:
        lines.append("- All MQ sessions match the 241-minute contract; no missing intraday clock stamps on those days.")
    uniq_n = sorted({r["n"] for r in day_minute_rows})
    lines.append(f"- Observed minute-count unique values across MQ days: {uniq_n}")
    lines.append("")
    lines.append("## 3) Vs last P-BASE gap (RESULT.md)")
    lines.append("")
    lines.append("| | RESULT.md | this probe |")
    lines.append("|---|---:|---:|")
    lines.append(f"| intent symbols | 773 | {len(intents)} |")
    lines.append(f"| session minutes | 58563 | {int(needed.size)} |")
    lines.append(f"| expected_symbol_minutes | 45269199 | {expected_total} |")
    lines.append(f"| observed_symbol_minutes | 41693339 | {observed_total} |")
    lines.append(f"| missing_symbol_minutes | 3575860 | {missing_total} |")
    lines.append("")
    lines.append("### 9 symbols RESULT called no-bin")
    lines.append("")
    lines.append("| symbol | has bins | in instruments/all | listed start/end | bin start/end | rows | observed/expected | bucket |")
    lines.append("|---|---|---|---|---|---:|---:|---|")
    by_inst = {r["instrument"]: r for r in per_rows}
    for sym in ABSENT_EXPECTED:
        r = by_inst.get(sym)
        if not r:
            lines.append(f"| {sym} | NOT IN INTENTS | | | | | | |")
            continue
        lines.append(
            f"| {sym} | {r['has_open_bin'] and r['has_close_bin']} | {r['in_instruments_all']} | "
            f"{r['listed_start']} .. {r['listed_end']} | {r['bin_start_ts']} .. {r['bin_end_ts']} | "
            f"{r['bin_rows']} | {r['observed_minutes']}/{r['expected_minutes']} | {r['bucket']} |"
        )
    lines.append("")
    lines.append(f"### Symbols with feature start after 2025-01-02 09:30:00: **{len(late_rows)}** (RESULT said 150)")
    lines.append("")
    lines.append("Sample of 15 latest-starting among late set:")
    lines.append("")
    late_sorted = sorted(late_rows, key=lambda r: r["bin_start_ts"], reverse=True)[:15]
    lines.append("| symbol | bin_start | bin_end | rows | missing | bucket |")
    lines.append("|---|---|---|---:|---:|---|")
    for r in late_sorted:
        lines.append(
            f"| {r['instrument']} | {r['bin_start_ts']} | {r['bin_end_ts']} | {r['bin_rows']} | {r['missing_minutes']} | {r['bucket']} |"
        )
    lines.append("")
    lines.append("## 4) Buckets (intent universe)")
    lines.append("")
    lines.append("| bucket | symbols | meaning |")
    lines.append("|---|---:|---|")
    lines.append(f"| full_window | {n_full} | open+close finite >0 on every MQ session minute |")
    lines.append(f"| no_file | {n_no} | missing features/*/open|close.1min.bin |")
    lines.append(f"| file_but_calendar_short | {n_short} | bin exists but date range shorter than intent window |")
    lines.append(f"| intraday_minutes_incomplete | {n_intra} | inside overlap, some minutes not finite/>0 |")
    lines.append(f"| contract_over_window_only | {n_over} | lake full on its life; gap only vs intent window outside bin |")
    lines.append("")
    lines.append(f"Full table: `{OUT_CSV}`")
    lines.append("")
    lines.append("## 5) Conclusion")
    lines.append("")
    lines.append(conclusion)
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("- Observed = finite `open.1min.bin` AND `close.1min.bin` values `> 0` at calendar indices for MQ freeze days.")
    lines.append("- Qlib bin layout: float32, index0 = start calendar index, values follow.")
    lines.append("- No `frozen_explicit_bars` write; no replay CLI.")

    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    OUT_DONE.write_text(datetime.now().astimezone().isoformat(timespec="seconds") + "\n", encoding="utf-8")
    OUT_JSON.write_text(
        json.dumps(
            {
                "expected": expected_total,
                "observed": observed_total,
                "missing": missing_total,
                "bucket_counts": dict(bucket_counts),
                "late_start_n": len(late_rows),
                "n_perfect_sessions": n_perfect,
                "mq_days": len(mq_days),
                "conclusion": conclusion,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print("WROTE", OUT_MD)
    print("WROTE", OUT_CSV)
    print("buckets", dict(bucket_counts))
    print("expected", expected_total, "observed", observed_total, "missing", missing_total)
    print("late", len(late_rows))
    print("conclusion", conclusion)


if __name__ == "__main__":
    main()
