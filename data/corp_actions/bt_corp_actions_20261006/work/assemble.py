# Assemble corp_actions.csv / listing.csv / FAILURES.csv / README.md from raw Wind CSVs + status.jsonl. Re-runnable.
import os, csv, glob, json, re, collections, time
BASE = r"D:\exports\bt_corp_actions_20261006"
U = [l.strip() for l in open(os.path.join(BASE, "universe.txt")) if l.strip()]
US = set(U)
def rd(f):
    with open(f, encoding="utf-8-sig", newline="") as fh: return list(csv.reader(fh))
def col(hdr, *keys, exclude=()):
    for i, h in enumerate(hdr):
        if any(h.endswith(k) for k in keys) and not any(x in h for x in exclude): return i
    return None
def num(x):
    x = (x or "").strip()
    if x in ("", "None", "nan", "--"): return ""
    try: v = float(x); return ("%.6f" % v).rstrip("0").rstrip(".")
    except: return x
def dt(x):
    x = (x or "").strip()[:10]
    return x if re.match(r"^\d{4}-\d{2}-\d{2}$", x) else ""
def load_status():
    st = collections.OrderedDict()
    p = os.path.join(BASE, "work", "status.jsonl")
    if os.path.exists(p):
        for l in open(p, encoding="utf-8"):
            try: r = json.loads(l); st.setdefault(r["id"], []).append(r)
            except: pass
    return st
NODATA = "没找到数据"
# ---- events
ev = {}; raw_rows = 0; outwin = 0; noexd = 0; progress = collections.Counter(); raw_ev_codes = set()
for f in sorted(glob.glob(os.path.join(BASE, "raw_events", "*.csv"))):
    rows = rd(f)
    if not rows: continue
    h = rows[0]
    iex = col(h, "除权除息日"); irec = col(h, "股权登记日"); ipay = col(h, "派息日")
    icash = col(h, "税前每股派息"); ibon = col(h, "送股比例"); itr = col(h, "转增比例"); ibl = col(h, "红股上市日")
    ipr = col(h, "实施进度")
    g = lambda r, i: r[i] if (i is not None and i < len(r)) else ""
    for r in rows[1:]:
        if not r or r[0] not in US: continue
        raw_rows += 1; raw_ev_codes.add(r[0])
        exd = dt(g(r, iex))
        if not exd: noexd += 1; continue
        if exd < "2015-01-01" or exd > "2026-10-06": outwin += 1; continue
        progress[g(r, ipr)] += 1
        rec = dict(code=r[0], ex_date=exd, record_date=dt(g(r, irec)), pay_date=dt(g(r, ipay)),
                   cash_div_per_share=num(g(r, icash)), bonus_ratio=num(g(r, ibon)), transfer_ratio=num(g(r, itr)),
                   bonus_list_date=dt(g(r, ibl)))
        k = (rec["code"], rec["ex_date"], rec["cash_div_per_share"], rec["bonus_ratio"], rec["transfer_ratio"])
        old = ev.get(k)
        if old:  # merge: keep non-empty fields
            for kk, vv in rec.items():
                if vv and not old.get(kk): old[kk] = vv
        else: ev[k] = rec
evl = sorted(ev.values(), key=lambda r: (r["code"], r["ex_date"]))
seq = collections.Counter()
with open(os.path.join(BASE, "corp_actions.csv"), "w", encoding="utf-8", newline="") as fh:
    w = csv.writer(fh); w.writerow("code,event_id,ex_date,record_date,pay_date,cash_div_per_share,bonus_ratio,transfer_ratio,bonus_list_date,source".split(","))
    for r in evl:
        seq[(r["code"], r["ex_date"])] += 1
        eid = f'{r["code"]}_{r["ex_date"].replace("-","")}_{seq[(r["code"], r["ex_date"])]}'
        w.writerow([r["code"], eid, r["ex_date"], r["record_date"], r["pay_date"], r["cash_div_per_share"], r["bonus_ratio"], r["transfer_ratio"], r["bonus_list_date"], "wind:wind_get_stock_events"])
# ---- listing
ls = {}
for f in sorted(glob.glob(os.path.join(BASE, "raw_listing", "*.csv"))):
    rows = rd(f)
    if not rows: continue
    h = rows[0]; iipo = col(h, "首发上市日期"); ilst = col(h, "上市日期", exclude=("首发",)); idl = col(h, "摘牌日期")
    src = "wind:wind_get_stock_info" if os.path.basename(f).startswith("info_") else "wind:wind_get_stock_events"
    for r in rows[1:]:
        if not r or r[0] not in US: continue
        ipo = dt(r[iipo]) if iipo is not None and iipo < len(r) else ""
        if not ipo and ilst is not None and ilst < len(r): ipo = dt(r[ilst])
        dl = dt(r[idl]) if idl is not None and idl < len(r) else ""
        old = ls.get(r[0])
        if old and old["ipo_date"] and not ipo: continue
        ls[r[0]] = dict(ipo_date=ipo, delist_date=dl or (old or {}).get("delist_date", ""), source=src)
with open(os.path.join(BASE, "listing.csv"), "w", encoding="utf-8", newline="") as fh:
    w = csv.writer(fh); w.writerow(["code", "ipo_date", "delist_date", "source"])
    for c in U:
        if c in ls: w.writerow([c, ls[c]["ipo_date"], ls[c]["delist_date"], ls[c]["source"]])
# ---- coverage / failures
st = load_status()
ok_any = lambda recs: any(r["status"] == "ok" for r in recs)
nod_any = lambda recs: any(NODATA in (r.get("error") or "") for r in recs)
covered_ev = set(raw_ev_codes); nodata_codes = set()
for tid, recs in st.items():
    if not recs[0]["phase"].startswith("ev"): continue
    if ok_any(recs) and recs[0]["phase"] != "ev": covered_ev |= set(recs[0]["codes"])   # follow-up OK => missing codes have no events
    if nod_any(recs): nodata_codes |= set(recs[0]["codes"]); covered_ev |= set(recs[0]["codes"])
# a code in an OK 6-batch but absent counts as covered only if a follow-up confirmed; else pending
fails = collections.OrderedDict()
for tid, recs in st.items():
    if ok_any(recs) or nod_any(recs): continue
    ph = recs[0]["phase"]
    call = "wind_get_stock_info" if ph == "listing_info" else ("wind_get_stock_events(listing)" if ph == "listing" else "wind_get_stock_events")
    e = (recs[-1].get("error") or "").replace("\n", " ")
    for c in recs[0]["codes"]:
        if call == "wind_get_stock_events" and c in covered_ev: continue
        if call != "wind_get_stock_events" and c in ls: continue
        fails[(c, call)] = (e[:200], len(recs))
# collapse: listing failures resolved by later info call are already filtered by `c in ls`; drop listing(events) failure when info also failed (keep the last)
err_pat = collections.Counter(re.sub(r"\d+", "N", e)[:90] for (c, call), (e, n) in fails.items())
pend_ev = [c for c in U if c not in covered_ev and (c, "wind_get_stock_events") not in fails]
pend_ls = [c for c in U if c not in ls and (c, "wind_get_stock_events(listing)") not in fails and (c, "wind_get_stock_info") not in fails]
with open(os.path.join(BASE, "FAILURES.csv"), "w", encoding="utf-8", newline="") as fh:
    w = csv.writer(fh); w.writerow(["code", "call", "error"])
    for (c, call), (e, n) in fails.items(): w.writerow([c, call, f"{e} (attempts={n})"])
    for c in pend_ev: w.writerow([c, "wind_get_stock_events", "pending: not yet fetched/confirmed (run interrupted)"])
    for c in pend_ls: w.writerow([c, "wind_get_stock_events(listing)", "pending: not yet fetched (run interrupted)"])
ev_codes = {r["code"] for r in evl}
no_ev = sorted(c for c in covered_ev if c not in ev_codes)
ratios = [float(r[k]) for r in evl for k in ("bonus_ratio", "transfer_ratio") if r[k]]
S = dict(generated=time.strftime("%Y-%m-%d %H:%M:%S") + " CST", universe=len(U), event_rows=len(evl), codes_with_events=len(ev_codes),
         codes_covered_events=len(covered_ev), codes_no_events_in_window=len(no_ev), listing_rows=len(ls),
         listing_with_ipo=sum(1 for v in ls.values() if v["ipo_date"]), delisted=sum(1 for v in ls.values() if v["delist_date"]),
         failure_rows=len(fails), failure_codes=len({c for c, _ in fails}), pending_events=len(pend_ev), pending_listing=len(pend_ls),
         raw_event_rows=raw_rows, dropped_outside_window=outwin, dropped_no_exdate=noexd,
         ex_date_min=min((r["ex_date"] for r in evl), default=""), ex_date_max=max((r["ex_date"] for r in evl), default=""),
         ratio_max=max(ratios, default=None), progress=dict(progress), err_patterns=dict(err_pat.most_common(8)),
         rows_with_record_date=sum(1 for r in evl if r["record_date"]), rows_with_pay_date=sum(1 for r in evl if r["pay_date"]),
         rows_with_bonus_list=sum(1 for r in evl if r["bonus_list_date"]),
         rows_with_bonus_or_transfer=sum(1 for r in evl if r["bonus_ratio"] or r["transfer_ratio"]))
json.dump(S, open(os.path.join(BASE, "work", "summary.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
open(os.path.join(BASE, "work", "codes_no_events.txt"), "w").write("\n".join(no_ev) + "\n")
J = lambda o: json.dumps(o, ensure_ascii=False)
md = []
md.append("# bt_corp_actions_20261006 — Wind corporate actions + listing dates (read-only pull)\n")
md.append(f"Generated {S['generated']} on newtest_4090. Source: Kimi Code CLI 2.1.1 headless (`kimi -p`) + kimi-datasource 3.4.0 plugin, data source `wind`. Read-only vendor fetch; no lake/qlib writes, no code/repo changes. No credentials stored here.\n")
md.append("## Status / counts")
md.append(f"- Universe (universe.txt): **{S['universe']}** unique codes (Wind form)")
md.append(f"- corp_actions.csv: **{S['event_rows']}** event rows over {S['codes_with_events']} codes; ex_date {S['ex_date_min']}..{S['ex_date_max']}")
md.append(f"- Codes with confirmed event coverage: {S['codes_covered_events']}; of these {S['codes_no_events_in_window']} have no event in 2015-01-01..2026-10-06 (work/codes_no_events.txt)")
md.append(f"- listing.csv: **{S['listing_rows']}** rows ({S['listing_with_ipo']} with ipo_date, {S['delisted']} with delist_date)")
md.append(f"- FAILURES.csv: {S['failure_rows']} failed (code,call) rows over {S['failure_codes']} codes; plus pending (not yet fetched) events={S['pending_events']}, listing={S['pending_listing']}")
md.append(f"- Error patterns: {J(S['err_patterns'])}\n")
md.append("## Universe sources")
md.append("repo `D:\\PycharmProjects\\MyQuant-backtrader\\stock_pool` (20251023..20260909, 215 files), repo `stock_pool_xls` (156 .xls = GBK TSV), `D:\\exports\\strategy9_pool_*` (11 dirs), `s10_tr_bb1000_20260825_20260909`, `v11_slice_d_20260921\\seed30_export_b\\pool`, `topk_s1_cap_cli_host_20261001\\signals\\pool`. 6-digit -> Wind: 6xxxxx .SH; 0/3xxxxx .SZ; 4/8/9xxxxx .BJ. Per-source counts: work/universe_stats.json.\n")
md.append("## Method")
md.append("- Dividends/bonus: `wind_get_stock_events`, natural-language question, **6 codes per call**: `<codes> 2014年1月1日至2026年10月6日 分红送配 除权除息日 股权登记日 派息日 税前每股派息 送股比例 转增比例 红股上市日`.")
md.append("  - Asked from 2014-01-01, then filtered locally to ex_date in 2015-01-01..2026-10-06. Reason: a query window starting 2015-01-01 dropped H1-2015 ex-dates of FY2014 payouts (600519 2015-07-17, 000001 2015-04-13 missing in test) — Wind appears to window on report/announcement period.")
md.append("  - A single response appears capped at 100 rows (a 15-code test returned exactly 100). Batches returning >=100 rows are re-asked in pairs; codes absent from an OK batch are re-asked in triples; anything still failing is asked singly. Wind `API_CALL_ERROR ... 没找到数据` on a follow-up = no events in window.")
md.append("  - Wind column names carry the window text as prefix (e.g. `2014年1月1日到2026年10月6日分红除权除息日`); normalized by suffix: 除权除息日->ex_date, 股权登记日->record_date, 派息日->pay_date, 税前每股派息->cash_div_per_share (pre-tax CNY/share), 送股比例->bonus_ratio, 转增比例->transfer_ratio, 红股上市日->bonus_list_date.")
md.append(f"  - Dedup key (code, ex_date, cash, bonus, transfer); event_id = `<code>_<yyyymmdd>_<seq>`. Raw rows {S['raw_event_rows']}; dropped outside window {S['dropped_outside_window']}, without ex_date (plans not implemented etc.) {S['dropped_no_exdate']}. 实施进度 of kept rows: {J(S['progress'])}.")
md.append(f"- Ratio normalization: Wind 送股比例/转增比例 are already per-share (10送3 -> 0.3); kept as returned, NOT divided by 10 (verified on 600519/000001 in the probe). Max ratio seen = {S['ratio_max']}.")
md.append("- Listing: `wind_get_stock_events` multi-code `<codes> 首发上市日期 摘牌日期` (40 codes/call, one row per code) — far fewer calls than `wind_get_stock_info` (<=3 tickers/call). Codes missing there fall back to `wind_get_stock_info fields=ipo_date`, batches <=3. If 首发上市日期 is empty, 上市日期 is used. delist_date = Wind 摘牌日期 (blank if listed). `source` column names the API.")
md.append("- Halt/resumption: skipped as instructed.")
md.append(f"- Field fill: record_date {S['rows_with_record_date']}, pay_date {S['rows_with_pay_date']}, bonus/transfer>0 {S['rows_with_bonus_or_transfer']}, bonus_list_date {S['rows_with_bonus_list']} rows.\n")
md.append("## Resume")
md.append("- `D:\\anaconda3\\python.exe work\\driver.py all 3` — idempotent; skips raw files already present; status in work/status.jsonl. On Kimi quota 403 (5-hour usage limit) it sleeps 20 min and retries (not counted as an attempt). Runs work/assemble.py at the end.")
md.append("- `D:\\anaconda3\\python.exe work\\assemble.py` — rebuilds the 4 outputs from raw_events/ and raw_listing/ any time. Kimi session logs: work/kimi_logs/.\n")
md.append("## Files\ncorp_actions.csv, listing.csv, FAILURES.csv, universe.txt, raw_events/*.csv (Wind raw), raw_listing/*.csv (Wind raw), work/ (driver, status, logs, summary.json)")
open(os.path.join(BASE, "README.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")
print(J(S))
