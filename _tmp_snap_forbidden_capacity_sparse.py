from pathlib import Path
import json, os
root = Path(r"D:\PycharmProjects\MyQuant-backtrader")
phase = root / "backtest_output" / "joint-return-v1-replay-panel-phase"
pack_parent = root / "backtest_output" / "joint-return-v1-dense-panel-bench"
forbidden = []
# prior out leaves under phase
for name in [
    "out-v2-pack-spans-181",
    "out-v2-pack-spans-182",
    "out-v2-pack-spans-marks-accel",
    "out-v2-pack-spans-710687e-cprofile",
    "out-v2-pack-spans-live-universe",
    "out-v2-pack-spans-cheap-bar-decimal",
    "out-v2-pack-spans-4e8fddb-cprofile",
    "out-v2-pack-spans-lifecycle-clock-cache",
    "out-v2-pack",
    "out-v1-json",
]:
    p = phase / name
    if p.exists():
        forbidden.append(p)
        # include immediate children files recursively? #186 used many paths - snapshot all files under these dirs + named files
# phase timings / receipts / pstats
for pat in [
    "phase_timings_B.json",
    "phase_timings_B_182.json",
    "phase_timings_B_4e8fddb_cprofile.json",
    "phase_timings_B_710687e_cprofile.json",
    "phase_timings_B_cheap_bar_decimal.json",
    "phase_timings_B_lifecycle_clock_cache.json",
    "phase_timings_B_live_universe.json",
    "phase_timings_B_marks_accel.json",
    "RECEIPT_REPLAY_LIFECYCLE_CLOCK_CACHE.md",
    "RECEIPT_REPLAY_MARKS_HOTSPOT_CPROFILE_710687e.md",
    "RECEIPT_REPLAY_PANEL_PHASE.md",
    "RECEIPT_REPLAY_PANEL_SPANS_181.md",
    "RECEIPT_REPLAY_PANEL_SPANS_182.md",
    "RECEIPT_REPLAY_PANEL_SPANS_CHEAP_BAR_DECIMAL.md",
    "RECEIPT_REPLAY_PANEL_SPANS_LIVE_UNIVERSE.md",
    "RECEIPT_REPLAY_PANEL_SPANS_MARKS_ACCEL.md",
    "RECEIPT_REPLAY_POST185_CPROFILE_4e8fddb.md",
    "cprofile_B_4e8fddb_post185.pstats",
    "cprofile_B_4e8fddb_post185_dump.txt",
    "cprofile_B_710687e_marks.pstats",
    "cprofile_B_710687e_marks_tops.txt",
]:
    p = phase / pat
    if p.exists():
        forbidden.append(p)

# also look for modeb / cash-1e9 / FULL pack outs
candidates = []
for base in [root / "backtest_output", Path(r"D:\PycharmProjects\MyQuant\runs")]:
    if not base.exists():
        continue
    for p in base.rglob("*"):
        if not p.is_file() and not p.is_dir():
            continue
        s = str(p).lower()
        if any(k in s for k in ["cash-1e9", "modeb", "mode-b", "full-sealed", "clock-patch-614-qlib-bin-full"]):
            # only outs / packs - avoid scanning forever; limit depth via rglob is ok but filter
            if p.is_dir() and any(x in p.name.lower() for x in ["out", "pack", "cash-1e9", "modeb"]):
                candidates.append(p)

# Include sealed pack root as forbidden touch
sealed = root / "backtest_output" / "joint-return-v1-dense-panel-bench" / "packs" / "clock-patch-614-qlib-bin-FULL-sealed"
if sealed.exists():
    forbidden.append(sealed)

# Also #186 specific fills/daily_nav files
for rel in [
    r"out-v2-pack-spans-lifecycle-clock-cache\joint-return-control-only-50-5-narrow-clock-patch-614\fills.csv",
    r"out-v2-pack-spans-lifecycle-clock-cache\joint-return-control-only-50-5-narrow-clock-patch-614\daily_nav.csv",
]:
    p = phase / rel
    if p.exists():
        forbidden.append(p)

# Dedup and expand dirs to themselves + key files (fills/daily_nav under each out leaf)
paths = []
seen = set()
def add(p: Path):
    rp = str(p.resolve()) if p.exists() else str(p)
    if rp in seen:
        return
    seen.add(rp)
    paths.append(p)

for p in forbidden:
    add(p)
    if p.is_dir():
        # add all files one level + recursive fills/daily_nav/orders/summary
        for f in p.rglob("*"):
            if f.is_file() and f.suffix.lower() in {".csv", ".json", ".md", ".pstats", ".txt", ".parquet"}:
                # limit: only under known prior out dirs and sealed pack metadata
                add(f)

# Also search for other modeb outs under backtest_output
bt_out = root / "backtest_output"
for d in bt_out.iterdir() if bt_out.exists() else []:
    n = d.name.lower()
    if d.is_dir() and any(k in n for k in ["modeb", "cash-1e9", "joint-return-v1-dense", "joint-return-control"]):
        add(d)
        for f in d.rglob("fills.csv"):
            add(f)
        for f in d.rglob("daily_nav.csv"):
            add(f)

snap = {}
present = 0
for p in paths:
    if p.exists():
        st = p.stat()
        snap[str(p)] = {"mtime_ns": st.st_mtime_ns, "size": st.st_size, "is_dir": p.is_dir()}
        present += 1

out = phase / "_tmp_forbidden_mtime_snapshot_capacity_sparse.json"
out.write_text(json.dumps({"present_count": present, "paths": snap}, indent=2), encoding="utf-8")
print(f"wrote {out} present={present}")
