# 交接 · 向量化 A 股撮合核收口（Codex 接手）

> 日期：2026-09-18
> 状态：✅ **已人裁 GO**（2026-09-18 · P1–P5 = A/A/C/A/A · plan v1.3 @ `72178b7`）。**可以开工**：从 master 开 `feat/ashare-engine-refactor`，切片 A→B→C 分 commit；遇 plan 未覆盖语义 → STOP Q40+，不自裁。
> 权威对象：[plan-ashare-engine-refactor-2026-09-18.md](plan-ashare-engine-refactor-2026-09-18.md) **v1.3**（勘误依据 [adversarial-errata.md](../architecture/reviews/2026-09-18/plan-ashare-engine-refactor/adversarial-errata.md) + 多模型共识 [merge-consensus.md](../architecture/reviews/2026-09-18/plan-ashare-engine-refactor-2026-09-18/merge-consensus.md)）。
> 前置：PR [#104](https://github.com/baiyibing/MyQuant-backtrader/pull/104)（`ashare_*`）**已合入 master**（`a61b1ad`）。
> 工作流：[workflow-codex-handoff.md](workflow-codex-handoff.md) 第 4 步定稿；第 3 步人裁已做（2026-09-18）。
> 基线：`origin/master` `a61b1ad`（#104 + #105 已合）；`ashare_*` 符号以 #104 `28c4ce2` 为准，行号漂移以符号名为准。
> **短注**：本轮两处措辞修订关闭 2026-09-18 Opus 5 实施前红旗（R-1 漂移一律 STOP + R-2 numba 调用点锁定），不表示引擎重构已实施。下一行人裁把 R-1 收窄：该 fixture 族七类为预期迁移，七类之外仍 STOP。
> 本轮另两处措辞关闭 2026-09-18 Opus 5 复审红旗 N-1（冻结 `read_lake_minute_ohlc`）与 N-2（切片 A 写死比对物），不表示引擎重构已实施。
> **人裁（2026-09-18 · 切片 A 填价）**：书帧读取器的新成交是**保留结果**，不是缺陷。同一合成 fixture 族（源 parquet SHA 不变、源文件均含 `low`）上，干净窗加①–⑥共七类实测差异是**预期迁移**。**禁止**改 `read_lake_minute_ohlc` 去追回 compact 旧成交。该七类之外的 reason 计数或 trades 价格漂移仍是 **STOP**，须问人。干净窗必须仍一致。读取器现状锁与 numba 内核锁（`can_sell=` 仅 `csv_minute_backtest.py:618`；日线 `n_days >= 1` 仅 `csv_daily_backtest.py:327,334`；两内核字节级不动）不放宽。

## ⛔ 开工闸

**两闸均已过（2026-09-18）**：plan 头部 ✅ 已人裁 GO（v1.3 @ `72178b7`，P1–P5 = A/A/C/A/A）；#104 已合（`a61b1ad`）。实施按本文件切片执行；遇 plan 未覆盖语义 → **STOP Q40+**，不自裁。

---

## 实施前审核 + Codex 启动（宿主环境执行，**非本机**；模型已人裁写死，勿换档）

1. **Cursor opus5 实施前审核**（人裁 2026-09-18：`claude-opus-5`；本机 Cursor CLI 无 claude 系，须宿主环境跑）。prompt 已入库：[opus5-preimpl-prompt.txt](../architecture/reviews/2026-09-18/plan-ashare-engine-refactor-2026-09-18/opus5-preimpl-prompt.txt)，产物写同目录 `opus5-preimpl-review.md`。判据：**无 🔴 才进第 2 步**；有 🔴 → 回写 plan / 本 handoff 后重审，不带病开工。
2. **Codex 无头实施**（工作流第 5 步原文口径）：本 PR 合入 master 后，`git checkout master && git pull && git checkout -b feat/ashare-engine-refactor`，然后：

```bash
codex exec --dangerously-bypass-approvals-and-sandbox \
  -m gpt-5.1-codex-max -c model_reasoning_effort=xhigh \
  "按 docs/backtest/handoff-ashare-engine-refactor-codex-impl-2026-09-18.md 实施切片 A→B→C，分 commit；遇 plan 未覆盖语义 STOP 问人，不自裁"
```

   full-auto 配置（`approval_policy=never` + `sandbox_mode=workspace-write`）见 1.3 `docs/prompts/prompt-codex-config-fullauto.md`；模型 = **最高档**（写死 `gpt-5.1-codex-max`；当日无此档名取可用最高 codex-max 档）。切片 A/B 分 commit；实施后走工作流第 6 步缺陷优先复核、第 7 步回写 plan「✅ 已实施（PR #N）」。

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

**测试**：numba 内核锁不因本切片放宽（`can_sell=` 只在 `csv_minute_backtest.py:618`；日线 `n_days >= 1` 只在 `csv_daily_backtest.py:327,334`；`_scan_held_day_numba_trail` 与 `scan_held_day_python` 字节级不动）。`read_lake_minute_ohlc` 的现状行为（单 `data.parquet`、`low` 为必需列、`_in_session` 过滤、`duplicated(keep="last")` 去重、整日零量丢弃）为**现状锁，字节级不动**。禁止改这只共用读取器来追回 compact 旧成交，也禁止改它来让 ④⑤⑥ 产出非空书帧。

**预期迁移（该 fixture 族，不得另造数字）**：对照物仍是私有化后的 compact 链，或同一 fixture 上落盘的改造前 records；结果侧采用书帧读取器。compact → 书帧：

| 类 | rows | reason | prices |
|---|---|---|---|
| clean | 2→2 | 不变（buy:trial=1, stop:trial_a090=1） | [100, 89] → [100, 89] |
| ① 盘外时间戳 | 3→2 | stop 1→0 | [100, 90] → [100] |
| ② 整日 volume=0 | 2→1 | buy+stop → skip_no_1455 | [100, 89] → null |
| ③ 重复时间戳 | 3→2 | 不变 | [100, 89] → [102, 89]（买价 100→102，因 `duplicated(keep="last")`） |
| ④ 仅多 part | 2→0 | buy+stop → skip_no_1455 | [100, 89] → null |
| ⑤ compact 输出无 `low`（源含 `low`） | 3→1 | buy+stop → skip_no_1455 | [100, 89] → null |
| ⑥ `data.parquet` 另加 part | 2→1 | stop 1→0 | [100, 89] → [100] |

这七行是本 fixture 族的预期迁移，不是待修缺陷。**除此以外**的任何 reason 计数漂移，或任何 trades 价格列漂移，仍是 **STOP**，必须问人，不得自行放行。干净窗必须仍与上表 clean 行一致。实现 PR **不得**以「新测试全绿」代替上述比对；绿测不豁免七类之外的漂移。合成窗必须包含以下六类 fixture 行型，缺一类即不算覆盖：

1. 盘外时间戳（out-of-session timestamps；书帧 `_in_session` 会滤，compact 不过滤）。
2. `volume = 0` 的整日（书帧丢零量日）。
3. 重复时间戳（书帧 `duplicated(keep="last")` 去重，compact 不去重）。
4. 多 part parquet 文件（预期为书帧 `None` 或少行，不是待修缺陷）。
5. compact 的输出帧没有 `low`（`_compact_minute_frame` 的输出不含 `low`），不是源 parquet「缺 `low` 列」；**禁止构造缺 `low` 源文件**。
6. 书帧 vs compact 的文件集差异：书帧只读单个 `data.parquet`，compact 用目录 `glob("*.parquet")`（预期为书帧 `None` 或少行，不是待修缺陷）。

类型 ④⑤⑥ 的预期仍是书帧返回 `None` 或少行（实测即上表，不是待修缺陷）。①–③的 reason/价格差同样是上表已裁定的预期迁移，不得再当成缺陷去改读取器。规整、藏掉上述任一行型的合成窗不得判绿；**非空 bar 计数 > 0**（以及为防空切片假绿而设的非空门）只对干净 symbol 生效，不适用于预期为 `None` 或少行的 ④⑤⑥；topk 合成窗非空仍只针对干净路径。1–10 / Mode B 填价与 reason 相对**同一基线**不动（cache 写路径允许变）。

**DoD**：pytest 绿；无盘符字面量。

---

## 2. 切片 B · T+1/涨跌停谓词统一（仅 P1=A 且已 GO；双账本保留）

**步骤**

1. T+1 一律 `ashare_session.t1_sellable(buy_date, session)`。
2. 1–10 `entry_idx` 映射为日历日（映射只服务 T+1 谓词与日期打印）；**`n_days` 仍按联合日历下标计数**（禁按个股有 K 日数重建），**不改**卖点公式。
3. 谓词落点=**现有调用点**（simulate 环 / v7 事件环）统一 `t1_sellable` / `skip_buy_at_limit` / `defer_sell_at_limit`；**不改** `execute_buy` / `_sell` / v7 `_buy` / `_sell_lots` 填单契约（现状不含谓词，也不塞进去）；书侧 `limits is None` **先拒**（fail-closed）；`hit_limit_*` 保留给 reserve/open_board/forbid_all/qlib 带内。
4. **T+1 谓词只允许加在这两个现有调用/判定点**：`backtest/research/csv_minute_backtest.py:618` 的 `scan_held_day(..., can_sell=(n_days >= 1))` 中 `can_sell=` 实参；`backtest/research/csv_daily_backtest.py:327,334` 的 `pos.pending_exit and n_days >= 1` 与 `if n_days >= 1` 日线判定点。`_scan_held_day_numba_trail` 与 `scan_held_day_python` 两个内核的内部守卫必须字节级不动：前者 `n_days < 1`（`:174`）及 `limit_down > 0.0`（`:183,203`），后者 `n_days < 1`（`:269`）及 `limit_down > 0`（`:278,316`）；禁止把 `date` 对象传进 `@njit`，平价锁为 `tests/test_scan_held_day_numba_parity.py`。
5. v7 的 `stage` / `entry_A` / 加仓阶梯留在 v7。

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
- [x] A · 一帧分钟（帧契约 b；七类迁移断言与原 parquet SHA 对照通过）
- [x] B · T+1/涨跌停谓词统一（P1=A；双账本保留；日历映射/None 两支回归通过）
- [x] C · 围栏 + 入口（固定 11+4 热路径与 plan 字节一致；旧 CLI / HELP_LOCK 保留）
- [ ] D · 宿主对照（host-only；实现 PR 不勾）
