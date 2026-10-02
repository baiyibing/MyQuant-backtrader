# 真核大票 · C-New · Codex 残差实施计划（2026-10-02）

| 字段 | 值 |
|---|---|
| 日期 | **2026-10-02 21:53 CST（Asia/Shanghai）** |
| tip 基线 | **`fcf3f6f3`**（master · #313 v6.1 sol MERGED） |
| Human GO | 「Codex 计划+A GO」→ 本 docs **计划清单** + 同票 **A·X7 观察面 draft**（**勿合**） |
| 顾问源 | `/workspace/handoffs/minute_engine_true_core_new_20261002/reviews/CODEX_RESIDUAL_GO.md`（仓外；只读建议） |
| 硬约束 | ≠δ5≠R4；**无**生产写湖；**无** 4090；空 MatchCore/Fees/`simulate`；不 mint 新 contract/backend_id；永 opt-in；永不 BOOKS；绿 R 仍禁 |
| PR | **draft · 勿合**（本刀与 A·X7 同票） |

> **本 note ≠ 全部残差一次实施授权，≠ 生产写湖，≠ host PASS，≠ 4090，≠ 新身份 mint。**  
> 顾问偏序曾推 R1→R4→R5；Human 已逐刀落地 R1（#311）与 R2 staging（#312），并点 **A·X7**。本计划只钉**剩余按序 draft 清单**与本刀范围。

## 1. 已合进度（至 tip `fcf3f6f3`）

| 阶段 | PR | tip / 备注 |
|---|---|---|
| TC1–TC4 | #303–#306 | 合同 / X1 / 消费者 / X8 |
| X6 合成 | #307 | Fixture PASS ≠ lake PASS |
| TC5 docs | #308 | 菜单；H-TC5-NEXT=C 当时已点 |
| X6 真湖边界 / e2e | #309 / #310 | 只读；≠ host PASS |
| **R1 CLI lake** | **#311** MERGED `706a3487` | opt-in `lake`→S4 hybrid；≠ host PASS |
| **R2 写湖 staging** | **#312** MERGED `3f7af6a2` | dry-run + MUST cuts；**≠ 生产写** |
| **v6.1 sol** | **#313** MERGED `fcf3f6f3` | 对照 note + 入口可见性；不改卖点数字 |
| **本刀 A·X7** | **draft** | 新投影入口；观察 ≠ 绿 R；勿合 |

## 2. Codex 残差按序清单（实施计划 · 仍逐刀 GO）

完整偏序建议（顾问原文）：**R1 → R4 → R5 → R3 → R6(X5) → R2**。落地后状态：

| 序 | 轴 | 状态 | 下一动作 |
|---|---|---|---|
| R1 | CLI `--evidence-level=lake` | **已合 #311** | 维护；勿升格 host PASS |
| R2 | 写湖 / Phase4 | **staging 已合 #312** | 生产写须另具名 GO + MUST cuts 齐裁；本仓默认 consume-only |
| R5 / **A·X7** | 观察面 | **本 draft** | 新投影；不塞 `views._FAMILIES`；勿合等人裁 |
| R3 | 4090 / item-4 live | **未开** | 须具名「4090 GO」；结果不得预订 PASS |
| R4 | 暂停消化 | 可选 | 同日多刀后仍可用；≠ 自动收官 C |
| R6 | 仅 X5 同合同批 | **未开** | 须点名；共享现金/新语义 → 新身份 |
| — | X2 / X3 / X4 | **未开** | 必新 contract + backend_id；X3 受 H-TC3 锁 |

**明确不要一次码完**：生产写湖、4090、X2–X5 新合同轴仍物理/合同依赖，须独立 GO。

## 3. 本刀（A·X7）钉死范围

见同票 [note-true-core-ax7-observe-2026-10-02.md](note-true-core-ax7-observe-2026-10-02.md)。

| 交付 | 不做 |
|---|---|
| `observation_id=minute_orders_x7_observe` 新投影入口 | 改 / 追加 `views._FAMILIES` |
| 已获工件 → 红标签 `observation_report.json` | 重算 NAV；产成功 `summary.json` |
| 独立观察根；恒 `observation_only_not_green_r` | 生产写湖；4090；mint 新 contract/backend_id |
| CLI + 合成测例 | 改 MatchCore / Fees / `simulate` / source_loader / backend CLI |

## 4. 后续 draft 建议顺序（人裁后另开）

1. **生产写湖 MUST 齐裁**（若仍要本链写）— 否则停在 #312 staging  
2. **4090 host attestation**（R3）— 独立材料与验收  
3. **X5 同合同批**（若吞吐成瓶颈）— 否则先 R4 消化  
4. **X2/X4**（必新身份草稿）— 未点名不开  
5. **X3** — 默认不推荐（H-TC3）

## 5. 非宣称

本计划 **≠** 授权生产写湖 / 4090 / 改核 / 绿 R / host PASS。A·X7 draft **勿合**。≠δ5 certified ≠R4；回测研究系统 ≠ 交易系统。
