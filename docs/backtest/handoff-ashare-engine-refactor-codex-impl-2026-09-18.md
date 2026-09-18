# 交接 · 向量化 A 股撮合核收口（Codex 接手）

> 日期：2026-09-18
> 状态：⏳ **待人裁 GO**。plan 头部未改为「✅ 已人裁 GO（hash）」**禁止开工**。随本 docs PR 先合 master 仍禁止写撮合 Python。
> 权威对象：[plan-ashare-engine-refactor-2026-09-18.md](plan-ashare-engine-refactor-2026-09-18.md) **v1.1**。
> 前置：PR [#104](https://github.com/baiyibing/MyQuant-backtrader/pull/104)（`ashare_*`）。未合则实施底用 #104 merge 后的 master，不叠未合分支。
> 工作流：[workflow-codex-handoff.md](workflow-codex-handoff.md) 第 4 步草稿；第 3 步人裁未做。
> 基线：`origin/master` `4a3e5fe`；`ashare_*` 符号以 #104 `28c4ce2` 为准，行号漂移以符号名为准。

## ⛔ 开工闸

**do not start Codex coding until** plan 头部写明 ✅ 已人裁 GO（commit hash）**并且** #104 已合（或底已含等价 `ashare_session` / `ashare_bars` / `ashare_fees`）。本文件随 docs PR 入库 ≠ 实施许可。

---

## 0. 硬边界（勿越）

复制 plan **R\*** + §0.3：

1. **R1**：四件回测不合成。本仓向量化 / MyQuant 信号厂 / 1.3 LEBS / 1.3 真栈。LEBS **只在 1.3**，且 **LEBS ≠ 真栈**。
2. **R2**：不 import qlib；不复活 Cerebro / PortAna；不复刻 LEBS 事件环 / `matching_env` / Redis / live；不重写 MyQuant 导出或 1.3 拉数；本仓不冒充 `python -m backtest.lebs`。
3. **R3**：只收口本仓已有零件。1–10 / v7 规则数字默认不动。7 不进 BOOKS。topk_app 独立。策略 7 ≠ LEBS turtle ≠ Paper 海龟。
4. **R4**：名单契约不改。
5. **R5**：E-R1–E-R4 不重开。E-R6 shares / 红利未裁 P3 不动。禁止改 `rescale_position` 使 1–6/8 shares/=k。
6. **R6**：默认 `BILATERAL_10BP`。`trade_fee_policy` 不进 simulate 热路径。
7. **R7**：CI data-free；无硬编码盘符。
8. **R8**：不把 `research/` 改名为 `ashare/` 包。
9. **R9**：未覆盖语义 → **STOP Q40+**，不自裁。
10. **P\* 未裁**：合 docs PR ≠ GO。建议默认见 plan §3；未写回「已裁」不得按默认偷偷开工。
11. 完成定义禁止用 PortAna / LEBS / 真栈净值。
12. 新文件 UTF-8 无 BOM、NUL=0；验证用 vanna312 全路径。

**代码事实锚点**（#104 `28c4ce2`；未合时以符号名为准）：

| 符号 | 锚点 |
|------|------|
| `hit_limit_up` / `t1_sellable` / `session_prev_close` | `ashare_session.py:29` / `:39` / `:49` |
| `load_minute_ohlc` / `load_minute_compact` / `bars_from_pool` | `ashare_bars.py:545` / `:202` / `:282` |
| `FeeSchedule` / `DEFAULT_SCHEDULE` / `BILATERAL_10BP` | `ashare_fees.py:35` / `:55` / `:53` |
| 书引擎 `Position.entry_idx` / `rescale_position`（shares untouched） | `csv_ledger.py:66-76` / `:141-150` |
| v7 `Lot.buy_date` / `Position.stage` | `csv_minute_backtest_v7.py:61-77` |
| 1–10 分钟加载 | `csv_minute_backtest.py` → `ashare_bars.load_minute_ohlc` |
| Mode B 除权只在网格 | `unified_exit_modeb.py`；**勿改** ledger shares |

---

## 1. 切片 A · 一帧分钟 + 禁复制

**步骤**

1. v7 加载改为 `load_minute_ohlc`（DatetimeIndex 书格式），按日切片；不要全市场 flatten。
2. `load_minute_compact` 删除或改为模块私有且零生产调用。
3. 新策略不得再写湖/bin 加载、涨跌停、佣金。
4. 回写 `engine-ashare-correctness.md` 模块表。

**测试**：v7 合成窗 reason 计数对齐改造前（允许漂移必须 STOP）；1–10 / Mode B 测不动。

**DoD**：pytest 绿；无盘符字面量。

---

## 2. 切片 B · 唯一 lot 日历（仅 P1=A 且已 GO）

**步骤**

1. T+1 一律 `ashare_session.t1_sellable(buy_date, session)`。
2. 1–10 `entry_idx` 映射为日历日，**不改**卖点公式。
3. `execute_buy` / `_sell` / v7 `_buy` / `_sell_lots` 的涨跌停只调 `skip_buy_at_limit` / `defer_sell_at_limit`。
4. v7 的 `stage` / `entry_A` / 加仓阶梯留在 v7。

**测试**：日线 + 分钟 + v7 各 1 条 T+1 拒卖、涨停 skip、跌停 defer。P1=A 时策略书 golden 字节级。`rescale_position` diff 空或仍 shares untouched。

**DoD**：同上；不碰 Mode B `shares/=k`。

---

## 3. 切片 C · 围栏 + 入口文档

**步骤**

1. simulate 热路径 AST：不得 import `qlib` / `trade_fee_policy` / `backtest.lebs`。
2. README / AGENTS 写清：LEBS 只在 1.3；本仓无 `python -m backtest.lebs`。
3. P5=A：旧 CLI 真身保留；不改 HELP_LOCK。

**DoD**：围栏测绿；docs 与 plan §0.3 同构。

---

## 4. 切片 D · 宿主对照（非合入门）

同窗 1–10 与 v7 短跑，比 **reason 桶**。禁止与 LEBS / PortAna / 真栈比 NAV。实现 PR 不勾选。

---

## 5. 门禁

```bash
D:\anaconda3\envs\vanna312\python.exe -m pytest -q tests/
```

全绿 + CI data-free + fixture 外零真实 symbol。完成后回写 plan 状态与本交接完成标记。

---

## 6. 完成标记（Codex 填；仅 GO 后）

- [ ] 人裁 GO 已写回 plan（hash：____）
- [ ] #104 已合入实施底
- [ ] A · 一帧分钟
- [ ] B · 唯一 lot 日历（P1=A）
- [ ] C · 围栏 + 入口
- [ ] D · 宿主对照（host-only；实现 PR 不勾）
