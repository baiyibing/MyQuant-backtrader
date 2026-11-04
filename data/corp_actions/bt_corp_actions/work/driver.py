# Read-only Wind pull via headless Kimi Code CLI (kimi -p). Resume-safe: status in work/status.jsonl, outputs in raw_*.
import os, sys, json, re, subprocess, time, threading, glob, csv
from concurrent.futures import ThreadPoolExecutor
BASE = r"D:\exports\bt_corp_actions_20261006"
KIMI = r"C:\Users\wangc\.kimi-code\bin\kimi.exe"
KIMI_MODEL = os.environ.get("KIMI_MODEL", "kimi-code/kimi-for-coding")  # 2026-10-09 nok3: Wind needs dynamically_loaded_tools
STATUS = os.path.join(BASE, "work", "status.jsonl")
LOGDIR = os.path.join(BASE, "work", "kimi_logs"); os.makedirs(LOGDIR, exist_ok=True)
lock = threading.Lock()
QUOTA = threading.Event()
class QuotaHit(Exception): pass
# --- 2026-10-08 patch ---
# * Kimi weekly/usage-limit (403 auth_error) and kimi startup failures (credential-store write races:
#   "storage write failed: permission denied" / EPERM rename of credentials) no longer count toward max_attempts.
#   New records get status "quota" / "infra"; legacy "error" records whose session log shows quota/infra are
#   re-classified on the fly from kimi_logs/<session>.txt (status.jsonl itself is not rewritten).
# * On quota hit the runner STOPS (writes work/QUOTA_STOP.txt) instead of sleeping 20 min and retrying.
# * Kimi session starts are staggered (>= START_GAP s apart) to avoid the credentials-file race.
# * listing (40-code) tasks whose codes are already partly covered in raw_listing are left to listing_info.
QUOTA_STOP = os.path.join(BASE, "work", "QUOTA_STOP.txt")
START_GAP = 8
_start_lock = threading.Lock(); _last_start = [0.0]
_kind_cache = {}

def classify_out(out):
    lo = out.lower()
    if ("usage limit" in lo) or ("auth_error" in lo) or ("403" in lo and ("quota" in lo or "7-day" in lo or "weekly" in lo)):
        return "quota"
    if ("failed to run prompt" in lo) and ("result_json" not in lo) and (
            "storage write failed" in lo or "eperm" in lo or "permission denied" in lo or "operation not permitted" in lo):
        return "infra"
    return ""

def session_kind(tag):
    if tag not in _kind_cache:
        try: _kind_cache[tag] = classify_out(open(os.path.join(LOGDIR, f"{tag}.txt"), encoding="utf-8", errors="replace").read())
        except Exception: _kind_cache[tag] = ""
    return _kind_cache[tag]

def is_attempt(r):
    if r.get("status") in ("quota", "infra"): return False
    if r.get("status") == "error" and session_kind(r.get("session") or "") in ("quota", "infra"): return False
    return True

def _gate():
    with _start_lock:
        w = _last_start[0] + START_GAP - time.time()
        if w > 0: time.sleep(w)
        _last_start[0] = time.time()

def load_status():
    st = {}
    if os.path.exists(STATUS):
        for l in open(STATUS, encoding="utf-8"):
            try: r = json.loads(l); st.setdefault(r["id"], []).append(r)
            except: pass
    return st

def log_status(rec):
    with lock:
        with open(STATUS, "a", encoding="utf-8") as f: f.write(json.dumps(rec, ensure_ascii=False) + "\n")

def nrows(p):
    try:
        with open(p, encoding="utf-8-sig") as f: return max(0, sum(1 for _ in f) - 1)
    except: return -1

def call_text(t):
    p = {k: v for k, v in t["params"].items()}
    p["file_path"] = t["file"]
    return f'api_name={t["api"]}，params={json.dumps(p, ensure_ascii=False)}'

def run_session(tasks, tag):
    lines = "\n".join(f"{i+1}) [{t['id']}] " + call_text(t) for i, t in enumerate(tasks))
    prompt = f"""只读批量取数。只用 kimi-datasource 插件的 wind 数据源（data_source_name="wind"），通过 call_data_source_tool 调用。不要用其他数据源，不要运行 shell 命令，不要读写/创建任何其他文件，不要改代码；结果只通过各调用的 file_path 参数写出。
先调用 get_data_source_desc(name="wind") 一次（只为满足调用流程，不必阅读细节）。然后严格按下面列表逐个调用 call_data_source_tool（data_source_name="wind"），参数原样照抄，不要改写 question，不要合并或拆分，失败也不要重试，继续下一个：
{lines}
全部调用完成后，最后输出一行（不要放在代码块里），格式严格为：
RESULT_JSON: [{{"id":"<方括号里的id>","status":"ok"或"error","rows":<返回行数或null>,"error":"<失败时错误原文前200字，否则空串>"}}, ...]
"""
    t0 = time.time()
    for infra_try in range(3):
      _gate()
      try:
        r = subprocess.run([KIMI, "-m", KIMI_MODEL, "-p", prompt, "--output-format", "text", "--add-dir", BASE],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1800, cwd=os.path.join(BASE, "work"))
        out = (r.stdout or "") + "\n" + (r.stderr or "")
      except subprocess.TimeoutExpired as e:
        out = "SESSION_TIMEOUT"
      kind = classify_out(out)
      if kind != "infra": break
      open(os.path.join(LOGDIR, f"{tag}_infra{infra_try}.txt"), "w", encoding="utf-8").write(out)
      print(f"[{time.strftime('%H:%M:%S')}] {tag}: kimi startup failure (infra), retry {infra_try+1}/3", flush=True)
      time.sleep(15 + 10 * infra_try)
    open(os.path.join(LOGDIR, f"{tag}.txt"), "w", encoding="utf-8").write(out)
    _kind_cache[tag] = kind
    quota = kind == "quota"
    res = {}
    m = re.findall(r"RESULT_JSON:\s*(\[.*?\])\s*$", out, re.S | re.M)
    if m:
        try:
            for x in json.loads(m[-1]): res[x.get("id")] = x
        except Exception: pass
    for t in tasks:
        x = res.get(t["id"], {})
        n = nrows(t["file"])
        if n >= 0 and os.path.getsize(t["file"]) > 0:
            status = "ok"; err = ""
        elif kind in ("quota", "infra"):
            status = kind; err = out.strip()[-200:]  # not an attempt
        else:
            status = "error"; err = (x.get("error") or ("no RESULT_JSON entry" if not x else "no file")).strip()
        log_status(dict(id=t["id"], phase=t["phase"], codes=t["codes"], status=status, rows=n, error=err,
                        reported=x.get("status"), session=tag, ts=time.strftime("%Y-%m-%d %H:%M:%S")))
    if quota: QUOTA.set()
    print(f"[{time.strftime('%H:%M:%S')}] {tag}: {len(tasks)} calls in {time.time()-t0:.0f}s; ok={sum(1 for t in tasks if os.path.exists(t['file']))}", flush=True)

def pending(tasks, max_attempts):
    st = load_status(); todo = []
    for t in tasks:
        if os.path.exists(t["file"]) and os.path.getsize(t["file"]) > 0: continue
        recs = st.get(t["id"], [])
        if any("没找到数据" in (r.get("error") or "") for r in recs): continue
        if sum(1 for r in recs if is_attempt(r)) >= max_attempts: continue
        todo.append(t)
    return todo

def run_phase(tasks, per_session, workers, max_attempts, name):
    for rnd in range(max_attempts):
        todo = pending(tasks, max_attempts)
        print(f"== {name} round {rnd}: {len(todo)} pending of {len(tasks)}", flush=True)
        if not todo: break
        chunks = [todo[i:i+per_session] for i in range(0, len(todo), per_session)]
        QUOTA.clear()
        with ThreadPoolExecutor(workers) as ex:
            futs = []
            for i, c in enumerate(chunks):
                futs.append(ex.submit(lambda c=c, i=i: None if QUOTA.is_set() else run_session(c, f"{name}_r{rnd}_{i:04d}_{int(time.time())}")))
            for f in futs: f.result()
        if QUOTA.is_set(): raise QuotaHit(name)

QEV = "{codes} 2014年1月1日至2026年10月6日 分红送配 除权除息日 股权登记日 派息日 税前每股派息 送股比例 转增比例 红股上市日"
QLS = "{codes} 首发上市日期 摘牌日期"
def universe(): return [l.strip() for l in open(os.path.join(BASE, "universe.txt")) if l.strip()]

def mk_events(groups, phase):
    out = []
    for g in groups:
        tid = f"{phase}_" + "_".join(c[:6] for c in g) if len(g) <= 2 else f"{phase}_{g[0][:6]}_{g[-1][:6]}_{len(g)}"
        out.append(dict(id=tid, phase=phase, codes=g, api="wind_get_stock_events",
                        params=dict(question=QEV.format(codes=",".join(g))),
                        file=os.path.join(BASE, "raw_events", tid + ".csv")))
    return out


def ok_codes(prefix_dir, pattern="*.csv"):
    seen = {}
    for f in glob.glob(os.path.join(BASE, prefix_dir, pattern)):
        try:
            for row in csv.reader(open(f, encoding="utf-8-sig")):
                if row and re.match(r"^\d{6}\.(SH|SZ|BJ)$", row[0]): seen.setdefault(row[0], 0); seen[row[0]] += 1
        except Exception: pass
    return seen

def done_or_nodata(tasks):
    st = load_status(); ok = []; nod = []
    for t in tasks:
        if os.path.exists(t["file"]) and os.path.getsize(t["file"]) > 0: ok.append(t)
        elif any("没找到数据" in (r.get("error") or "") for r in st.get(t["id"], [])): nod.append(t)
    return ok, nod

def all_phases(workers):
    U = universe()
    # 1) listing via multi-code events (40/call)
    g = [U[i:i+40] for i in range(0, len(U), 40)]
    L1 = [dict(id=f"ls_{x[0][:6]}_{x[-1][:6]}_{len(x)}", phase="listing", codes=x, api="wind_get_stock_events",
               params=dict(question=QLS.format(codes=",".join(x))), file=os.path.join(BASE, "raw_listing", f"ls_{x[0][:6]}_{x[-1][:6]}_{len(x)}.csv")) for x in g]
    have0 = ok_codes("raw_listing")
    L1 = [t for t in L1 if (os.path.exists(t["file"]) and os.path.getsize(t["file"]) > 0) or not any(c in have0 for c in t["codes"])]
    run_phase(L1, 10, workers, 3, "listing")
    # 1b) listing fallback: wind_get_stock_info fields=ipo_date,delist_date (<=3 tickers)
    have = ok_codes("raw_listing")
    miss = [c for c in U if c not in have]
    L2 = []
    for i in range(0, len(miss), 3):
        x = miss[i:i+3]; tid = "info_" + "_".join(c[:6] for c in x)
        L2.append(dict(id=tid, phase="listing_info", codes=x, api="wind_get_stock_info",
                       params=dict(ticker=",".join(x), fields="ipo_date"), file=os.path.join(BASE, "raw_listing", tid + ".csv")))
    run_phase(L2, 15, workers, 3, "listing_info")
    # 2) events, 6 codes/call
    E1 = mk_events([U[i:i+6] for i in range(0, len(U), 6)], "ev")
    run_phase(E1, 12, workers, 3, "events")
    # 2b) re-query: capped batches (>=100 rows) -> pairs; failed batches -> pairs; missing codes in ok batches -> triples
    ok, nod = done_or_nodata(E1)
    pairs = []; trip = []
    seen = ok_codes("raw_events")
    for t in E1:
        if t in ok and nrows(t["file"]) >= 100: pairs += [t["codes"][i:i+2] for i in range(0, len(t["codes"]), 2)]
        elif t in ok: trip += [c for c in t["codes"] if c not in seen]
        elif t in nod: trip += t["codes"]
        else: pairs += [t["codes"][i:i+2] for i in range(0, len(t["codes"]), 2)]
    E2 = mk_events(pairs, "ev2") + mk_events([trip[i:i+3] for i in range(0, len(trip), 3)], "ev3")
    run_phase(E2, 12, workers, 3, "events2")
    # 2c) singles for anything still not ok (failed pairs/triples)
    ok2, nod2 = done_or_nodata(E2)
    singles = [c for t in E2 if t not in ok2 and t not in nod2 for c in t["codes"]]
    E3 = mk_events([[c] for c in singles], "ev1")
    run_phase(E3, 12, workers, 3, "events1")

if __name__ == "__main__":
    cmd = sys.argv[1]; workers = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    if cmd == "pending":
        U = universe(); max_a = 3
        g = [U[i:i+40] for i in range(0, len(U), 40)]
        L1 = [dict(id=f"ls_{x[0][:6]}_{x[-1][:6]}_{len(x)}", codes=x, file=os.path.join(BASE, "raw_listing", f"ls_{x[0][:6]}_{x[-1][:6]}_{len(x)}.csv")) for x in g]
        have = ok_codes("raw_listing")
        L1f = [t for t in L1 if (os.path.exists(t["file"]) and os.path.getsize(t["file"]) > 0) or not any(c in have for c in t["codes"])]
        miss = [c for c in U if c not in have]
        L2 = [dict(id="info_" + "_".join(c[:6] for c in miss[i:i+3]), codes=miss[i:i+3], file=os.path.join(BASE, "raw_listing", "info_" + "_".join(c[:6] for c in miss[i:i+3]) + ".csv")) for i in range(0, len(miss), 3)]
        E1 = mk_events([U[i:i+6] for i in range(0, len(U), 6)], "ev")
        st = load_status()
        def old_pending(ts): return [t for t in ts if not (os.path.exists(t["file"]) and os.path.getsize(t["file"]) > 0)
                                     and not any("没找到数据" in (r.get("error") or "") for r in st.get(t["id"], []))
                                     and len(st.get(t["id"], [])) < max_a]
        res = dict(universe=len(U), covered_codes=len(have), missing_codes=len(miss),
                   listing_total=len(L1), listing_after_cover_filter=len(L1f), listing_pending=len(pending(L1f, max_a)), listing_pending_old_logic=len(old_pending(L1)),
                   listing_info_total=len(L2), listing_info_pending=len(pending(L2, max_a)), listing_info_pending_old_logic=len(old_pending(L2)),
                   listing_info_ok=sum(1 for t in L2 if os.path.exists(t["file"]) and os.path.getsize(t["file"]) > 0),
                   events_total=len(E1), events_pending=len(pending(E1, max_a)))
        print(json.dumps(res, ensure_ascii=False))
    if cmd == "all":
        if os.path.exists(QUOTA_STOP):
            os.rename(QUOTA_STOP, QUOTA_STOP + f".prev_{time.strftime('%Y%m%d_%H%M%S')}")
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] driver start pid={os.getpid()} (2026-10-08 patch: quota/infra not attempts; stop on quota)", flush=True)
        try:
            all_phases(workers); print("ALL PHASES DONE", flush=True)
        except QuotaHit as e:
            U = universe(); have = ok_codes("raw_listing"); miss = [c for c in U if c not in have]
            st = load_status()
            msg = (f"QUOTA_STOP {time.strftime('%Y-%m-%d %H:%M:%S')} CST phase={e}\n"
                   f"listing_missing_codes={len(miss)} of {len(U)}; raw_listing_files={len(glob.glob(os.path.join(BASE, 'raw_listing', '*.csv')))}; "
                   f"raw_events_files={len(glob.glob(os.path.join(BASE, 'raw_events', '*.csv')))}\n"
                   f"Kimi weekly/usage limit (403 auth_error). Runner stopped instead of sleeping; quota hits are not counted as attempts.\n")
            open(QUOTA_STOP, "w", encoding="utf-8").write(msg)
            print(f"[{time.strftime('%H:%M:%S')}] QUOTA HIT in {e}: stopping (see {QUOTA_STOP})", flush=True)
        subprocess.run([sys.executable, os.path.join(BASE, "work", "assemble.py")])
