# merge-consensus — plan-industry-align-p3-d2-exdiv-2026-09-19 r1

> 日期：2026-09-19（Asia/Shanghai）  
> 对象：[plan v0.2→v0.2.1](../../../backtest/plan-industry-align-p3-d2-exdiv-2026-09-19.md) @ **working assumption** P3δ2.1–2.5=A/A/A/A/A（用户跳过 cut widget；**pending human GO**，非已录入人裁）  
> `IMPLEMENTATION_BASE=1ad010cca013afe8186f20275cbdcca71e500823`  
> 对抗前置：[codex-adv-r1](../plan-industry-align-p3-d2-exdiv-codex-adv-r1/)（E-d2-01..09 已回填 v0.2）  
> 本轮席位：codex / cursor-kimi-k3-high / cursor-auto / grok（claude=host 空槽）  
> Fan-out：`run_multi_ai_review.py --preset classic --host claude --parallel`；四路 rc=0（codex 138s / kimi 347s / auto 250s / grok 566s）  
> 计票：**证据裁决，不投票**。host 对全部 🔴 亲验。

---

## 四路总裁决

| 席位 | 裁决 | 要点 |
|---|---|---|
| codex | **修后可进** | 🔴 `load_exdiv_rates` 不存在；🟡 B6 stub/入口、B5/v7 股数、pending×除权 |
| cursor-kimi-k3-high | **修 🔴 后可进** | 同 API 名；双路径 resolver；混域脚枪建议人裁认真看；实验复现 E-d2-01/§2.4/Decimal |
| cursor-auto | **修 🔴 后可进 Slice A→B** | 同 API 名 + 双路径；混域建议 A+窄约束；B6/B5/pending；冻结缺域声明文件 |
| grok | **改 R1 后可进** | 同 API 名；**不同意**本刀把 P3δ2.5 改成生产 fail-closed；B6 危险组合 + CLI 红字；`run()` vs `main()` 写盘 |

**主持综合**：方向正确、生产冻结成立、adv-r1 残留（E-d2-01/02）保持 docs pin。唯一硬伤 🔴 为验收链 API 笔误（`load_exdiv_rates`→`load_exdiv_ratios`）。其余 🟡 为 Slice B 合同可执行性与人裁旁注，**不挡**本轮 docs 船，也不授权改生产。人裁五项维持 **A/A/A/A/A 工作假设 / pending human GO**（不写入「已录入 GO」）。

**共识标签：GO-WITH-NITS**（v0.2.1 已合本 PR；docs/tests 船就绪待人裁 GO 后开 Slice A→B→C；生产零行为变更；不重开 P1/P2/P4；δ3/δ4/δ5 停放）。

---

## host 抽验记录（🔴 亲验）

- **MC-1 / 四路 R1 ✅**  
  `plan:66`、`:185` 写 `load_exdiv_rates`。仓内唯一定义 `load_exdiv_ratios`（`exdiv_map.py:220`，`__all__:349`）。`def load_exdiv_rates` / `load_exdiv_factors` 均不存在。adv-r1 errata 原文用 ratios 名，属 v0.2 回填笔误。照抄实现 → `ImportError`。  
  注：codex 正文曾误写 `load_exdiv_factors` 为「实际定义」；auto/kimi/grok 与 host 源码一致为 **`load_exdiv_ratios`**。以源码为准。

- **MC-2 / auto R2 / kimi K-Y1 / grok Y1 ✅**  
  `exdiv_map.py:246-253`：`adj_factor_path` 与 `ex_date_index_path` 各自回落 `resolve_source_parquet`。只传其一 → 已配湖静默读真实 parquet / 未配则解析阶段 fail-loud。B1「绝不走真实 resolver」须钉死双路径显式 tmp。

- **MC-3 / codex R2 / auto Y2 / kimi K-Y3 / grok Y2 ✅**  
  书 `run()` 只 return `SimState`；`write_run_artifacts` 在 `main()`。v7 无 `run()`，入口 `main()`，非空 pool 必调 `load_index_daily`。整 stub `load_limit_context` 或空 codes 不能证明「确实加载 map」。B6 须逐入口列消费模块绑定名。

- **MC-4 / codex R3 / kimi K-Y4 / grok Y6 ✅**  
  `simulate_v7` 无 Position 注入；试仓 `NAME_BUDGET×0.2`，px=10 → ~20k 股。§2.4 小数值 oracle 可达书侧 `simulate`/helper，不可直接当 v7 公开初态。

- **MC-5 / Decimal 半分 ✅**（kimi Exp2/6、grok、host）  
  `limit_prices("600000.SH", 1.65)=(1.82, 1.49)`；`round_fen(1.65*0.9)=1.48`。B4 必须钉主板代码并禁止 float 自算档位。

- **P3δ2.5 混域（auto Y1 / kimi K-Y2 vs grok Y4）→ host 采纳 grok 处置**  
  风险属实：分钟无条件 `load_exdiv_ratios`，`--qlib-day-root` 迫使 `daily_source=qlib_day`（后复权）仍乘 k。但 F-R2/F-R5 冻结「不补 minute/v7 跳过」；本刀不改生产。工作假设维持 A；B6 标危险组合必测 + Slice A CLI/README 红字；真要入口拒绝 → 人裁改 P3δ2.5=B 另案。

---

## 勘误表（已回填 v0.2.1）

| # | 严重度 | 来源 | 裁决 | 勘误 | 回填落点 |
|---|---|---|---|---|---|
| **MC-1** | 🔴 | 四路 R1 | **ACCEPT** | `load_exdiv_rates` → `load_exdiv_ratios`；禁止加兼容别名 | §2.2、B2 |
| **MC-2** | 🟡 | auto R2 / kimi K-Y1 / grok Y1 | **ACCEPT→Slice B** | B1/B2：`load_exdiv_ratios(..., adj_factor_path=..., ex_date_index_path=...)` 两路径皆显式 | B1 |
| **MC-3** | 🟡 | codex R2 / auto Y2 / kimi / grok Y2 | **ACCEPT→Slice B** | B6 逐入口 stub：daily/minute 测 `run`（minute `use_cache=False`）；v7 测 `main` 时 stub bars/index/writer；保留 `load_limit_context` 调用链；非空合成 pool | B6 |
| **MC-4** | 🟡 | codex R3 / kimi / grok Y6 | **ACCEPT→Slice B** | B5：小数值 oracle=书 helper/`simulate`；公开 v7=事件前快照比 Δ | B5、§2.4 旁注 |
| **MC-5** | 🟡 | codex R4 / kimi K-Y5 / grok Y7 | **ACCEPT→Slice B** | B2 增 pending_exit×除权：D−1 pending → D 开盘成交 / 开盘跌停续 defer | B2 |
| **MC-6** | 🟡 | kimi/auto/grok B4 | **ACCEPT→Slice B** | B4 钉 `600000.SH`；期望值只允许来自真实 `session_limit_prices`/`limit_prices`；禁 float 旁路 | B4 |
| **MC-7** | 🟡 | auto Y1 / kimi K-Y2 / grok Y4 | **ACCEPT→docs（不改生产）** | 维持 P3δ2.5=A 工作假设；B6 危险组合 `daily=qlib_day`×仍加载 map；Slice A CLI/README 红字：日线 `--qlib-data-root` 跳过 ≠ 分钟 `--qlib-day-root` | B6、§5 旁注、§6 |
| **MC-8** | ⚪ | auto Y5 / grok / kimi | **DEFER→Slice A** | §9 可选列 `qlib_bin_daily.py`/`qlib_bin_1min.py`；Non-goals 显式排除 cyqk；§8.2 解释器链只留 3.12 路径 | Slice A |
| **MC-9** | ⚪ | kimi K-G1/G2 | **DEFER** | 手工 `k=inf` 穿透 pin；drawdown 夹具 high≤cost 陷阱 | Slice B 实施 handoff |

---

## 对 P* 的立场

| 点 | 四路 | host |
|---|---|---|
| P3δ2.1–2.5 = A/A/A/A/A | 多数维持；auto/kimi 建议 2.5 加窄约束 | **工作假设维持 A**；pending human GO；2.5 风险用 B6/红字消化，不本刀改生产 |
| P1 / P2 / P4 | 一致停放 | **维持停放** |
| δ3 / δ4 / δ5 | 一致停放 | **维持停放** |

---

## 是否可进 Slice A 实现

**可以（GO-WITH-NITS）**，条件：

1. 本 docs PR 合入 v0.2.1 + 本 merge-consensus + 四路评审 md。  
2. **人裁正式录入** P3δ2.*=A/A/A/A/A（或明示改口）后，再开 feat 实施 Slice A→B→C。  
3. 实施仅 docs + data-free tests；§9 十五文件生产 freeze 零 diff。  
4. Slice B 必须落实 MC-2..MC-6 合同文字；合 docs PR ≠ 自动改生产。

---

## 下一步

1. 推本分支 docs PR #122（v0.2.1 errata + r1 consensus + 四路 md）。  
2. **人裁 cut widget** 正式 GO 后开 feat 实施（仍 docs/tests）。  
3. **不必再开 r2 fan-out**（本轮 🔴 为笔误，已回填可验证）。  
4. 不实施 Slice A/B/C；不回复 BT；不嵌套 codex-in-codex；无 cloud。
