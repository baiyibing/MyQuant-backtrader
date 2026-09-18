# 交接 · 向量化 A 股撮合核收口（Codex 接手）

> 日期：2026-09-18
> 状态：✅ **已人裁 GO**（2026-09-18 · P1–P5 = A/A/C/A/A · plan v1.3 @ `72178b7`）。**可以开工**：从 master 开 `feat/ashare-engine-refactor`，切片 A→B→C 分 commit；遇 plan 未覆盖语义 → STOP Q40+，不自裁。
> 权威对象：[plan-ashare-engine-refactor-2026-09-18.md](plan-ashare-engine-refactor-2026-09-18.md) **v1.3**（勘误依据 [adversarial-errata.md](../architecture/reviews/2026-09-18/plan-ashare-engine-refactor/adversarial-errata.md) + 多模型共识 [merge-consensus.md](../architecture/reviews/2026-09-18/plan-ashare-engine-refactor-2026-09-18/merge-consensus.md)）。
> 前置：PR [#104](https://github.com/baiyibing/MyQuant-backtrader/pull/104)（`ashare_*`）**已合入 master**（`a61b1ad`）。
> 工作流：[workflow-codex-handoff.md](workflow-codex-handoff.md) 第 4 步定稿；第 3 步人裁已做（2026-09-18）。
> 基线：`origin/master` `a61b1ad`（#104 + #105 已合）；`ashare_*` 符号以 #104 `28c4ce2` 为准，行号漂移以符号名为准。

## ⛔ 开工闸

**两闸均已过（2026-09-18）**：plan 头部 ✅ 已人裁 GO（v1.3 @ `72178b7`，P1–P5 = A/A/C/A/A）；#104 已合（`a61b1ad`）。实施按本文件切片执行；遇 plan 未覆盖语义 → **STOP Q40+**，不自裁。

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
| 1–10 分钟加载 | `csv_minute_backtest.py` → **别名** `load_minute_bars = load_minute_ohlc`（`ashare_bars.py`）；按字面搜 `load_minute_ohlc` 调用点会落空 |
| Mode B 除权只在网格 | `unified_exit_modeb.py`；**勿改** ledger shares |

---

## 1. 切片 A · 一帧分钟 + 禁复制

**步骤**

1. v7 **默认湖路径**改为 `load_minute_ohlc`（DatetimeIndex 书格式）：整载 `(start,end)` 后按日切片；禁逐日调 loader、禁全市场 flatten；**`use_cache=False`**（共享 cache 键仅 `(start,end)`——禁 v7 小名单覆写大名单窗 cache）；缺码路径不得整仓物化（实测 6.6–6.7GB，data-free fixture 验收）。
2. **帧契约三选一写死**：书帧无 `date` 列、`_day_frame_records` 现按 `frame["date"]` 切片，按字面换即 `KeyError`——(a) 复用 1–10 `_slice_day`；(b) `_day_frame_records` 认 `ymd`/DatetimeIndex；(c) 薄适配层。**topk 共用 v7 `_load_cli_bars`**（非独立链）：湖路径跟 v7 适配走，DoD 含 topk 合成窗非空。
3. `load_minute_compact` 降为模块私有；**保留 qlib_1min 源与 `bars_from_pool` 链**（`load_minute_ohlc` 无 source 参数，直接删除断 v7 `--minute-source qlib_1min`）；湖生产调用归零。连带 `load_session_bars` / `bars_from_pool` 处置写明。
4. 新策略不得再写湖/bin 加载、涨跌停、佣金。
5. 回写 `engine-ashare-correctness.md` 模块表。

**测试**：v7 合成窗 reason 计数**与 trades 价格列**对齐改造前（允许漂移必须 STOP）；**非空 bar 计数 > 0**（防空切片假绿）+ topk 合成窗非空；1–10 / Mode B 填价与 reason 不动（cache 写路径允许变）。

**DoD**：pytest 绿；无盘符字面量。

---

## 2. 切片 B · T+1/涨跌停谓词统一（仅 P1=A 且已 GO；双账本保留）

**步骤**

1. T+1 一律 `ashare_session.t1_sellable(buy_date, session)`。
2. 1–10 `entry_idx` 映射为日历日（映射只服务 T+1 谓词与日期打印）；**`n_days` 仍按联合日历下标计数**（禁按个股有 K 日数重建），**不改**卖点公式。
3. 谓词落点=**现有调用点**（simulate 环 / v7 事件环）统一 `t1_sellable` / `skip_buy_at_limit` / `defer_sell_at_limit`；**不改** `execute_buy` / `_sell` / v7 `_buy` / `_sell_lots` 填单契约（现状不含谓词，也不塞进去）；书侧 `limits is None` **先拒**（fail-closed）；`hit_limit_*` 保留给 reserve/open_board/forbid_all/qlib 带内。
4. v7 的 `stage` / `entry_A` / 加仓阶梯留在 v7。

**测试**：日线 + 分钟 + v7 各 1 条 T+1 拒卖、涨停 skip、跌停 defer；**None-limits 卖侧向量两支（无昨收 + 未知板块）记录现状行为**（v7 现状 fail-open 放行，不改，Q40+ 另裁）；日线卖出时点两支（`open_board` 同 bar 当日收 vs 其余 `pending_exit` 次日开）。P1=A 时 golden 指涉物 = tests 合成 golden + 宿主改造前短窗 trades/summary 基线先落盘。`rescale_position` diff 空或仍 shares untouched。

**DoD**：同上；不碰 Mode B `shares/=k`。

---

## 3. 切片 C · 围栏 + 入口文档

**步骤**

1. simulate 热路径 AST：不得 import `qlib` / `trade_fee_policy` / `backtest.lebs`。热路径 = plan §5-C 枚举清单（11 文件 + 传递一层 `csv_daily_loader` / `csv_pool` / `market_layer` / `exdiv_map`），**非 rglob**；测试锚点 `tests/test_ashare_simulate_import_fence.py` + `SIMULATE_HOT_PATH` 常量与清单**字节级一致**。
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

- [x] 人裁 GO 已写回 plan（hash：`72178b7`，2026-09-18 · A/A/C/A/A）
- [x] #104 已合入实施底（`a61b1ad`）
- [ ] A · 一帧分钟
- [ ] B · T+1/涨跌停谓词统一（P1=A；双账本保留）
- [ ] C · 围栏 + 入口
- [ ] D · 宿主对照（host-only；实现 PR 不勾）
