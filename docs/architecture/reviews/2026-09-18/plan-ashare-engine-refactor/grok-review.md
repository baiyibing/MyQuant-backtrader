# plan-ashare-engine-refactor v1.1（待人裁 GO）— Grok 核评审

> 日期：2026-09-18
> 角色：MyQuant-backtrader Grok 核（只审不合入）
> 对象：本地 docs 包 `plan-ashare-engine-refactor-2026-09-18.md` v1.1 + 交接草稿 + README/AGENTS 入口
> 权威：[engine-positioning-ssot.md](../../../../backtest/engine-positioning-ssot.md) · 1.3 `backtest-architecture-ssot.md` §1 · [workflow-codex-handoff.md](../../../../backtest/workflow-codex-handoff.md)
> 本核 **未 merge**。本结论 **不是** 实施 GO。

---

## 结论

**GO-WITH-NITS**（**docs 包可入库**；nits 不阻断合入，不写撮合 Python，不改 E-R\* / 策略书 / LEBS。本核不 merge）。

施工图把「三仓都有回测」收成可执行边界：本仓只收向量化；MyQuant 停在信号；1.3 拆成 **LEBS 扫参** 与 **真栈验收**。§0.3 与口头裁决同构：LEBS 只在 1.3、LEBS ≠ 真栈、海龟 / 旧 CSV 分轨、策略 7 ≠ turtle、选哪一件四行。R1–R9 与非目标能挡住做重。切片 A–C 合入门、D 宿主、P2–P4 另开 plan，范围收得住。

**人裁 P1–P5 之前仍禁止编码。** 合 docs PR ≠ 实施 GO。#104 未合不得叠分支开工。

---

## 对象

| 项 | 值 |
|----|----|
| plan | `docs/backtest/plan-ashare-engine-refactor-2026-09-18.md` v1.1 |
| 交接草稿 | `handoff-ashare-engine-refactor-codex-impl-2026-09-18.md`（开工闸：未 GO 勿开工） |
| 入口 | `docs/backtest/README.md` SSOT 行 + §1.3 LEBS 段；`AGENTS.md` 一句 |
| 代码 | **零** Python / 引擎 |

---

## 证据表

| 门 | 要求 | 裁决 |
|---|---|---|
| **1 状态 / 禁编码** | ⏳ 待人裁 GO；GO 前禁止写撮合 Python | **PASS** | plan 头部、handoff ⛔、README「勿编码」三处同构 |
| **2 本仓定位** | 只回答日名单怎么成交 | **PASS** | §0.1；对照货币 reason / 可卖 / 涨跌停 |
| **3 LEBS 只在 1.3** | 不复刻事件环；不冒充 `python -m backtest.lebs` | **PASS** | §0.3.1–0.3.3、R1/R2、非目标、handoff §0.1–2、README 1.3 段 |
| **4 LEBS ≠ 真栈** | 扫参 vs 验收；parity 免责；真栈才签字 | **PASS** | §0.3.1 表与口头说明同构 |
| **5 海龟 / 旧 CSV / 本仓 7** | 三份东西 | **PASS** | §0.3.2；R3；非目标 |
| **6 不做重** | 不改 MyQuant 训练/PortAna；不改 1.3 LEBS/真栈/SSOT | **PASS** | §0.2 表 + §4 |
| **7 工作流骨架** | R\* / P\* / 非目标 / 切片 DoD / 验证 / 落点 / 修订 | **PASS** | 七步第 1 步必含节齐全；交接为第 4 步预览 |
| **8 #104 前置** | 不叠未合 `ashare_*` 开工 | **PASS** | plan 头部 + handoff 闸 |

---

## nits（不挡入库）

### nit-1（人裁）P1–P5 仍是建议默认

未写「已裁」不得按 A 偷偷开工。建议人裁时至少钉 P1=A、P2=A 或 C、P3=C、P4=A、P5=A/B。

### nit-2（实施风险）切片 A 删 compact

v7 全市场窗曾 OOM，才改成 DataFrame 按日取。`load_minute_ohlc` 必须保持「不 flatten 全历史」；交接 A 已写，实施若改回 flatten → STOP。

### nit-3（卫生）跨仓相对链接

plan 用 `../../../../MyQuant/...` 与 `../../../../OSkhQuant1.3/...`。本仓克隆体不一定有兄弟目录。不挡；人裁可改成 GitHub blob URL（positioning 对 1.3 SSOT 已有此先例）。

### nit-4（范围）切片 C 围栏 import `trade_fee_policy`

根上 `trade_fee_policy.py` 仍被死 `BarReplayEngine` 引用。围栏应钉 **simulate 热路径**（daily/minute/v7/ledger），不要误伤考古模块——或另开卫生票删死引擎，不塞本船。

---

## 工作流对照

本包 = 第 1 步 plan + 第 2 步本核 + 第 4 步交接**草稿**。第 3 步人裁 GO **未做**。交接未伪标「已 GO（hash）」。

---

## 建议人裁后

1. 回写 P1–P5 + plan hash；刷新 handoff §0。
2. 等 #104 合入再开 `feat/ashare-engine-refactor`。
3. 不要回头把 LEBS 事件环或真栈报单写进本仓。
