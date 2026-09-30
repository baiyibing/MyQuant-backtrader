# B-L2 R4 calendar/actions/marks 宿主材料包（DRAFT）

生成：2026-09-30（Kimi agent，win11 本机）。承接 MyQuant-backtrader PR #276（instruments host-fill，已合入 tip `c69f4bcc`）之后 freeze 的下一道门：`proof_actions: complete saved result required`（calendar/actions/marks 独立 attestation 缺失）。

## 边界（务必先读）

- 本包是 **DRAFT 宿主材料**，未 pin；与 `attestation_packages/` 无引用关系。
- **未触碰**：`r4_authorized=false`、R3/R4 host 收据、recipe/freeze、MatchCore、生产代码。
- loader 对这三类 proof 的门槛（探索自 tip `c69f4bcc`）：§9.1 六字段封套（issuer/subject/source_refs/filter/result/limitations）+ `complete=true`；actions 额外要求 proof `result.rows == []`、消费包 `events==[]`、覆盖区间 ⊇ [first_day, end]；marks 逐价格映射 pinned 源行、`available_at=event_time`、禁前值/合成补缺。**无** binding/第二 issuer 强制（那是 instruments 独有）。
- recipe（含实际 mark_grid、first_day、run_id）是宿主侧文件，不在任何 git 仓——本包 §3/§1 留了对应【待裁】格。

## 内容

| 路径 | 内容 | 对应合同 |
|---|---|---|
| `calendar/sse_holiday_notices_2025.md` | SSE 官方休市通知两份存档（2024-12-23 年度 + 2025-09-25 国庆专项，均窗口前发布） | §3 表 calendar「独立可核验」 |
| `calendar/pmc_sse_calendar_20250901_20251231.txt` | PMC/SSE 日历 82 交易日（1.3 生产日历 SSOT `common/infra/trading_calendar_pmc.py` 同源，pmc 5.3.2） | 同上 |
| `calendar/calendar_cross_check.md` | 三源交叉核验表（官方通知 × PMC × census 旁证），含下一交易日 2025-11-05 | 同上 |
| `actions/cninfo_603196_announcements_p1..p3.json` | cninfo 原始返回（77 条，2025-06-01..2025-12-31） | §3.2 |
| `actions/cninfo_603196_announcements_analysis.md` | 77 条逐条/关键词分析（行动/停牌/更名零命中）+ 名称连续性更正（日播时尚→璞源材料，⚠️ 非亚士创能）+ 覆盖声明底稿 | §3.2 |
| `actions/ex_date_index_local_check.md` | ex_date_index 本机独立复核：603196 全历史 8 行（2018–2024），2025=0 | §3.2 |
| `actions/preclose_chain_no_ex_adjustment.md` | daqmt preClose 链 9/9 无除权调整（量化旁证） | §3.2 |
| `marks/minute_lake_marks_substrate.md` | 湖 parquet 字节级核验（sha256 与 pin 一致）+ 9 日 × 241 行 abs row 清单 + final mark 候选（11-04 15:00 → row 48681） | §3.3 |
| `HOST_FILL_FORM_CAM.md` | 一页填空表：三 claim 逐格【已备】/【待裁】+ 签字区 | 全部 |

## 三源/四源互证摘要

- **calendar**：SSE 官方通知（权威锚，窗口前发布）× PMC（生产同源）× census（旁证）——9/9 交易日一致。
- **actions**：ex_date_index 零命中 × cninfo 77 公告零行动 × preClose 链无调整 × adj_factor 恒 1.0——区间 events=[]。
- **marks**：湖 parquet 字节核验 + abs row 清单 + 分钟↔日线 close 9/9——任何合法网格均可逐点锚定，不编价。

## 后续流程（比照 instruments）

本人审 → 合入 1.3 `docs/evidence/`（类比 #1112）→ 授权开 MyQuant-backtrader packs 刀（calendar/actions/marks 消费包 + 三 proof complete=true + manifest/remap，r4_authorized 不翻）→ 4090 落包 → 点名「开 R4」重跑。
