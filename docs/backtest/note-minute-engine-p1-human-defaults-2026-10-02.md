# 分钟引擎 P1 · Human defaults 锁（2026-10-02）

| 字段 | 值 |
|---|---|
| 日期 | 2026-10-02（Asia/Shanghai / CST） |
| tip | `a93b8112e74e99ba2577bc6fe044e848e072acc5`（master · #297 后） |
| Human GO | 采纳提案默认；开 **P1 docs draft**；H6=B → **docs PR 勿合** |
| 方案 | `/workspace/handoffs/minute_engine_industry_plan_20261002/PLAN.md` §3.2 P1-A/B/C；R1_SYNTHESIS + R2_light_docs |
| 仓内落点 | [vendor-bar-alignment-ssot §11](ssot/vendor-bar-alignment-ssot.md)；本 note；轻指针见 industry-state / fill-policy |
| 硬约束 | **docs-only**；不改 MatchCore / Fees / `simulate` / VolumeCap·clamp·完成桶；≠δ5 certified ≠R4；无写湖；无 4090 |

> **本 note ≠ 第二套成交默认表。** 入口默认 / 绿 R·S / 红混比继续只链 [minute-fill-policy-ssot.md](minute-fill-policy-ssot.md)。

## 1. 锁定裁断（H1–H6）

| ID | 锁定 | 含义（执行口径） |
|---|---|---|
| **H1=A** | 湖 END+lots→股 为**推荐**研究路径 | 顶层 PIN：`minute_label=END`、`unit=raw_shares_incremental`（export ×100）；START+sparse 可并存但**强制分列**；禁无声明混比 PnL |
| **H2=A** | sparse A + host lake-accept **松弛须 PIN** | 仅放宽满网断言；禁静默 fill-forward；不改核 |
| **H3=B** | 允许 P2 外壳 fail-closed 预检 | **落点=CLI/adapter/loader**；不改 `simulate` / `participation_rate=None` 旧臂 / VolumeCap·桶；本刀 **只写合同**，码另 GO；≠δ5≠R4 |
| **H4=A** | L2 `minute_orders` **永 opt-in** 对照后端 | 防 P2-C 被读成替换共享 CSV 默认 |
| **H5=A** | G3 科创板申报数量 **延后** | 不进 P1/P2 码；规则表若另开须独立 GO |
| **H6=B** | 批 **docs PR 勿合** | G0≠G1≠「合」；本 PR draft，等待 Human「合」 |

合稿备注（R1）：不论 H1 选项，Phase5 vs START-accept **禁无声明混比**；H7 邻核冻结（VolumeCap/桶/clamp）已写入 PLAN §1.2，本刀遵守。

## 2. 本刀交付范围（P1-A/B/C · docs）

| 刀 | 本 PR | 明确不做 |
|---|---|---|
| P1-A | 增补 vendor-bar SSOT §1/§5/§11；身份五元组勾选 | 不改 simulate；不盲 +1min；不复制 fill-policy 行 |
| P1-B | §5/§11 + [example PIN JSON](ssot/vendor-market-overlay-pin.example.json) 合同 | **不**实现 fail-closed loader 码；不写湖 |
| P1-C | industry-state 索引轻指针（#291 / Phase5 / P1 note）；禁平行状态表 | 不重跑已归档 P3 |

## 3. P2-B 预检合同预告（H3=B · docs only）

产品化目标（码另 GO）：`run_topk_cap_compare` / 共享 `--participation-rate` 在 **CLI 解析后 / loader 出口 / adapter** 做单位与完成桶 fail-closed 预检。

- 省略 `participation_rate=None` = 字节同旧臂。
- 刀文禁写「capacity certified / δ5 / R4」。
- **禁止**把预检塞进 `simulate` / MatchCore；**禁止**改 VolumeCap 公式、clamp、completed-bucket 定义（邻核冻结，升格须 P3 点名刀）。

## 4. 指针

- Bar 身份 SSOT：[vendor-bar-alignment-ssot.md](ssot/vendor-bar-alignment-ssot.md) §10–§11
- 成交假设 SSOT：[minute-fill-policy-ssot.md](minute-fill-policy-ssot.md)（唯一默认总表）
- 状态索引：[industry-state-acceptance-index-2026-09-28.md](industry-state-acceptance-index-2026-09-28.md)
- 行业方案 handoff：`/workspace/handoffs/minute_engine_industry_plan_20261002/`

**≠δ5 certified ≠R4；docs-only；勿合，等待 Human「合」。**
