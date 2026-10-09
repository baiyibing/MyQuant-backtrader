# bt_corp_actions_20261006 — Wind corporate actions + listing dates (read-only pull)

Generated 2026-10-09 11:31:40 CST on newtest_4090. Source: Kimi Code CLI 2.1.1 headless (`kimi -p`) + kimi-datasource 3.4.0 plugin, data source `wind`. Read-only vendor fetch; no lake/qlib writes, no code/repo changes. No credentials stored here.

## Status / counts
- Universe (universe.txt): **2774** unique codes (Wind form)
- corp_actions.csv: **9096** event rows over 1078 codes; ex_date 2015-01-26..2026-09-30
- Codes with confirmed event coverage: 1083; of these 5 have no event in 2015-01-01..2026-10-06 (work/codes_no_events.txt)
- listing.csv: **2762** rows (2762 with ipo_date, 7 with delist_date)
- FAILURES.csv: 186 failed (code,call) rows over 174 codes; plus pending (not yet fetched) events=1529, listing=0
- Error patterns: {" the current N-day window ends. To continue now, purchase extra usage or upgrade your plan": 162, "no RESULT_JSON entry": 12, "<system>ERROR: Tool execution failed.</system> Request timed out after N seconds.": 9, "Request timed out after N seconds.": 3}

## Universe sources
repo `D:\PycharmProjects\MyQuant-backtrader\stock_pool` (20251023..20260909, 215 files), repo `stock_pool_xls` (156 .xls = GBK TSV), `D:\exports\strategy9_pool_*` (11 dirs), `s10_tr_bb1000_20260825_20260909`, `v11_slice_d_20260921\seed30_export_b\pool`, `topk_s1_cap_cli_host_20261001\signals\pool`. 6-digit -> Wind: 6xxxxx .SH; 0/3xxxxx .SZ; 4/8/9xxxxx .BJ. Per-source counts: work/universe_stats.json.

## Method
- Dividends/bonus: `wind_get_stock_events`, natural-language question, **6 codes per call**: `<codes> 2014年1月1日至2026年10月6日 分红送配 除权除息日 股权登记日 派息日 税前每股派息 送股比例 转增比例 红股上市日`.
  - Asked from 2014-01-01, then filtered locally to ex_date in 2015-01-01..2026-10-06. Reason: a query window starting 2015-01-01 dropped H1-2015 ex-dates of FY2014 payouts (600519 2015-07-17, 000001 2015-04-13 missing in test) — Wind appears to window on report/announcement period.
  - A single response appears capped at 100 rows (a 15-code test returned exactly 100). Batches returning >=100 rows are re-asked in pairs; codes absent from an OK batch are re-asked in triples; anything still failing is asked singly. Wind `API_CALL_ERROR ... 没找到数据` on a follow-up = no events in window.
  - Wind column names carry the window text as prefix (e.g. `2014年1月1日到2026年10月6日分红除权除息日`); normalized by suffix: 除权除息日->ex_date, 股权登记日->record_date, 派息日->pay_date, 税前每股派息->cash_div_per_share (pre-tax CNY/share), 送股比例->bonus_ratio, 转增比例->transfer_ratio, 红股上市日->bonus_list_date.
  - Dedup key (code, ex_date, cash, bonus, transfer); event_id = `<code>_<yyyymmdd>_<seq>`. Raw rows 9250; dropped outside window 61, without ex_date (plans not implemented etc.) 93. 实施进度 of kept rows: {"实施完毕": 9096}.
- Ratio normalization: Wind 送股比例/转增比例 are already per-share (10送3 -> 0.3); kept as returned, NOT divided by 10 (verified on 600519/000001 in the probe). Max ratio seen = 3.0.
- Listing: `wind_get_stock_events` multi-code `<codes> 首发上市日期 摘牌日期` (40 codes/call, one row per code) — far fewer calls than `wind_get_stock_info` (<=3 tickers/call). Codes missing there fall back to `wind_get_stock_info fields=ipo_date`, batches <=3. If 首发上市日期 is empty, 上市日期 is used. delist_date = Wind 摘牌日期 (blank if listed). `source` column names the API.
- Halt/resumption: skipped as instructed.
- Field fill: record_date 9096, pay_date 8918, bonus/transfer>0 1229, bonus_list_date 1228 rows.

## Resume
- `D:\anaconda3\python.exe work\driver.py all 3` — idempotent; skips raw files already present; status in work/status.jsonl. On Kimi quota 403 (5-hour usage limit) it sleeps 20 min and retries (not counted as an attempt). Runs work/assemble.py at the end.
- `D:\anaconda3\python.exe work\assemble.py` — rebuilds the 4 outputs from raw_events/ and raw_listing/ any time. Kimi session logs: work/kimi_logs/.

## Files
corp_actions.csv, listing.csv, FAILURES.csv, universe.txt, raw_events/*.csv (Wind raw), raw_listing/*.csv (Wind raw), work/ (driver, status, logs, summary.json)
