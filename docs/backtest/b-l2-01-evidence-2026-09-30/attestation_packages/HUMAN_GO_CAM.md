# Human GO — B-L2 R4 calendar/actions/marks host-fill packs（2026-09-30 Asia/Shanghai）

**人裁原话：**「四格全批，开 packs」

对照 OSkhQuant1.3 #1114 / tip `42d066b81a083be49881f0dd8c5ab53ed4f422f6`
路径 `docs/evidence/b_l2_r4_cam_host_materials_draft_20260930/` 的 `HOST_FILL_FORM_CAM.md` 四格：

| 格 | 决定 |
|---|---|
| §1 日历事实批准 + first_day 确认 | **批准**。日历事实采 CAM 包（SSE 官方休市通知 × PMC/SSE × census 旁证）；`first_day=2025-10-23`（无窗口前 acquire 初始持仓，按 CAM 包建议）；`trading_dates` = PMC 表覆盖 `[first_day, 2025-11-05]` 的子集（须含末次 BUY 下一交易日 2025-11-05）。 |
| §2 覆盖完整性声明 + events=[] 批准 | **批准**。四源互证（ex_date_index 零命中 × cninfo 77 公告零行动 × preClose 链无调整 × adj_factor 恒 1.0）；消费包 `events=[]`、`complete=true`；proof `result.rows=[]`、`complete=true`；覆盖区间 ⊇ `[first_day, end]`。 |
| §3 mark 网格确认 + 行绑定批准 | **批准**。采用 CAM 包候选网格：至少含 **final** `2025-11-04 15:00 → abs row 48681`（close 22.96 raw）+ ≥1 独立抽查点（从包内 9×241 行清单选）；`available_at=event_time`；禁止前值/合成补缺；15:00 独立合法来源 = 湖 parquet pin + 行清单 + census 三点同指。 |
| §4 开 packs 刀授权 | **批准开 packs 刀 only**。写 calendar/actions/marks 消费包 + 三类 proof（complete=true）+ manifest/remap 更新；**`r4_authorized` 不翻**；MatchCore/Fees/SSOT/lake/recipe freeze/4090/R4 均不动；另行具名「开 R4」才授权重跑。 |

范围不变：603196.SH / 20251023–20251104 / basis=cross_source_ratio；production_C=frozen；instruments/status/units 保持 #276 状态。

基线 tip：MyQuant-backtrader master `c69f4bcc487608e8ff75e090526e50d116a4bc0a`（#276）。
上游材料：OSkhQuant1.3 `42d066b81a083be49881f0dd8c5ab53ed4f422f6`（#1114）。
