# B-L2 R4 calendar/actions/marks 宿主填空表（HOST_FILL_FORM_CAM，一页版）

> 依据：合同 note §3 表 / §3.2 / §3.3 / §9.1；loader `source_loader.py` 校验合同（三类 proof 走 §9.1 六字段封套，无 binding/第二 issuer 强制；actions 额外要求 `rows==[]` + 消费包 `events==[]` + 覆盖区间 ⊇ [first_day, end]）。
> 范围：603196.SH（窗口期简称日播时尚，现名璞源材料）/ 2025-10-23 ~ 2025-11-04。
> 用法：【已备】= 材料已在本包；【待裁】= 必须人裁/宿主提供。

---

## §1 calendar（claim: complete_trading_calendar；pack schema bl2_calendar_v1，仅校验 trading_dates 字段）

【已备】SSE 官方休市通知两份（年度 2024-12-23 上证公告〔2024〕38号 + 国庆专项 2025-09-25 上证公告〔2025〕36号，均窗口前发布）；PMC/SSE 日历输出 82 日（1.3 生产日历 SSOT 同源，pandas_market_calendars 5.3.2）；三源交叉核验表 9/9。
【待裁】① 批准日历事实（trading_dates 建议 = PMC 82 日表中覆盖 [first_day, 2025-11-05] 的子集，须含末次 BUY 的下一交易日 2025-11-05）；② recipe 的 first_day（若无窗口前 acquire 的初始持仓则 = 2025-10-23）——**R4c recipe 在宿主侧，须确认**。

## §2 actions（claim: complete_no_company_actions；pack schema bl2_actions_v1：complete=true、events=[]、覆盖区间 ⊇ [first_day, end]、proofs 引用 subject=actions 的 proof；proof 的 result.rows 必须 == []）

【已备】四源互证「区间无事件」：① ex_date_index 零命中（pin 版本 R3 草稿 + 本机更新版独立复核一致，2025 全年 0）；② cninfo 77 公告零行动/停牌/更名关键词（原始 JSON p1–p3 已存档）；③ daqmt preClose 链 9/9 无除权调整；④ adj_factor 窗口因子恒 1.0（14 交易日切片）。
【待裁】① 覆盖完整性声明签署（源=ex_date_index + cninfo，范围、完整性、筛选结果三要素，§3.2 明文「无行/因子未变/源缺失均不单独证明无事件」——故声明须引用多源）；② proof 的 `result.rows` 填 []、`complete` 翻 true 的批准；③ 消费包 events=[] 的批准。

## §3 marks（claim: raw_contemporaneous_grid；loader：逐价格映射 pinned 源行、时间严格等于 event_time、禁前值/合成补缺；网格 ≥2 点且含 end_at）

【已备】湖 parquet 字节级身份核验（sha256 与 census pin 一致）；9 日 × 241 行清单含全部 abs row；final mark 候选 2025-11-04 15:00 → row 48681（close 22.96，raw）；分钟↔日线 close 9/9 交叉一致。
【待裁】① recipe 实际 mark_grid（时点/mark_id）——**R4c recipe 在宿主侧（4090/exports），须提供或确认采用本包候选**；② 逐点行绑定批准；③ 15:00 mark「独立合法来源」叙述批准（建议：湖 parquet pin + 行清单 + census 审核记录三点同指）。

## §4 packs 刀授权（比照 #276 的边界）

【待裁】材料包人审通过并合入 1.3（类比 #1112）→ 授权开 MyQuant-backtrader packs 刀：写 calendar/actions/marks 消费包 + 三类 proof（complete=true）+ manifest/remap 更新；**`r4_authorized` 不翻、MatchCore 不动、recipe/freeze 仍等点名「开 R4」**。

---

## 签字区

| 项 | 决定/值 | 批准人 | 日期 |
|---|---|---|---|
| §1 日历事实批准 + first_day 确认 | | | |
| §2 覆盖完整性声明 + events=[] 批准 | | | |
| §3 mark 网格确认 + 行绑定批准 | | | |
| §4 开 packs 刀授权 | | | |
