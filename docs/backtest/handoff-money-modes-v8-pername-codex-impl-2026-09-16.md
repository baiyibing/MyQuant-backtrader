# 交接 · money-modes + v8 每股 100 万 实施（Codex 接手）

> 日期：2026-09-16
> 状态：**plan v1.1 已评审（READY）；待人裁 GO（P1–P4；P5 已裁=前置退场）后本交接生效**。GO 后把 plan §3 人裁表回填，本文件 §0 硬边界即冻结。
> 评审链：[zcode-facts](../architecture/reviews/2026-09-16/plan-money-modes-v8-pername/zcode-facts.md) / [zcode-domain](../architecture/reviews/2026-09-16/plan-money-modes-v8-pername/zcode-domain.md) / [merge-consensus](../architecture/reviews/2026-09-16/plan-money-modes-v8-pername/merge-consensus.md)。
> 权威对象：[plan-money-modes-v8-pername-2026-09-16.md](plan-money-modes-v8-pername-2026-09-16.md)（v1.1）。
> 前置：[plan-cerebro-retire-2026-09-16.md](plan-cerebro-retire-2026-09-16.md) 已合入（否则 B 切片不得开工）。
> 分支：从当时 master 开 `feat/money-modes-v8-pername`；切片 A/B 分 commit。

## 0. 硬边界（人裁已定，勿越）

1. 只实施 plan v1.1 的切片 A–D；M-R\* 现锁一条不破。
2. **禁改** `csv_ledger.py`（含 `_empty_stats`/`_buy_size`/`execute_buy`）、`csv_minute_backtest_v7.py`、成交核 E-R\*、MyQuant 仓、`stock_pool/`、`docs/architecture/reviews/**`。
3. 不加 `--sizing` 全局开关；`equal_risk`/`equity_pct` 连枚举占位都不加（M-R1/M-R7）。
4. 1–6/9/10 默认行为逐字节不变（M-R5）：daily_quota 路径 trades CSV 前后对照是 A 切片验收件。
5. 遇 plan 未覆盖的语义分叉（尤其 skip/chase/force-min 边界）**停下来问人**，不自裁。
6. `tests/fixtures/csv_engine_pre_er1/` 静态锚点**禁重生成**。

## 1. 切片 A · 模式框架

### 代码事实锚点（评审验讫）

- `csv_strategy_books.py:40-54` `CsvStrategyBook` frozen dataclass（现有字段 name/tag/aliases/allow_add/peak_gap_min/help_lock/apply/run_kwargs）；`:89-105` `apply_csv_strategy`（hooks 注入 :92-100，`hooks["allow_add"] = book.allow_add` 在 :92）。
- `csv_simulate_loop.py:135-172` `run_pool_buys_day`：`:145` `per = min(daily_quota, st.cash) / len(planned)`；`:147-149` 已持 skip；`:164-165` 涨涨停排单 `queue_limit_up_chase(..., per, ...)`；`:172` `execute_buy` 返回值被忽略（现状，不改）。
- `run_chase_due_day`（:77-123）：`:91` 到期筛选；`:94-98` 已持分支；`:104` 先 `pending_chase.pop` 再 :123 买入——**per_ch 无需透传改动**（排单日已写入）。
- `csv_ledger.py:24-54` `_empty_stats` 无 skip_cash 键 → 新 stats 一律 `st.stats.setdefault("skip_cash", 0) += 1` 模式；`:202` `daily_quota_used += min(per, notional)`（vestigial）。
- 调用点：日线 `csv_daily_backtest.py:445-457`、分钟 `csv_minute_backtest.py:936`（透传 sizing/name_budget 即可，重置逻辑 :339/:826 不动）。

### 实施

1. `CsvStrategyBook` 加 `sizing: str = "daily_quota"`、`name_budget: float = 1_000_000.0`。
2. `apply_csv_strategy`：hooks 注入 `sizing`/`name_budget`；**`sizing=="per_name"` 时覆写 `hooks["allow_add"] = False`**（单点，M-R3 硬锁）。
3. `run_pool_buys_day` 分支：per_name → `per = min(name_budget, ...)`（每码，不除 n；现金不足在 execute_buy 前置判定 → skip_cash + skip_cash_notional，`setdefault` 计数；不累 `daily_quota_used` 并注释 vestigial）。
4. argparse `--name-budget`（default 1_000_000.0；仅在 per_name 书生效）。
5. stats/record_params 记 `sizing`/`name_budget`；`chase_buy_fail` 拆「cash / shares」两计数。

### 测试（新增，`tests/test_csv_strategy_books.py`）

- per_name 两码名单：per 均为 name_budget（**不是** quota/n）。
- 现金 1.5M、预算 1M 两码：第一码成交、第二码 skip_cash=1 且 skip_cash_notional≈1M。
- chase 排单 per_ch = name_budget；到期已持 → chase_skip_held。
- force-min：`--name-budget=3000`、px=40 → 100 股、supp=1000（**别按 1M 写**）。
- per_name 同码次日再现 → skip_held+1、add_lots 恒 0（M-R3 锁）。
- 回归：daily_quota 模式 fixture 窗 trades 逐字节对照。

## 2. 切片 B · v8 切换

### 代码事实锚点

- `strategy8_rules.py`：`STOP_PCT=0.20`(:17)、`SMALL_ARM=0.06`(:20)、BANDS(:26-32)、docstring(:3)、HELP_LOCK、`ALLOW_ADD=True`(:14)。
- `csv_strategy_books.py:136` `--stop-pct` help（"v8 0.20" 过时）；`:454-458` `_run_kwargs_version8`（CLI `--stop-pct` 可回滚旧止损）。
- 必红测试：`tests/test_csv_daily_backtest_v8.py`（:40 `test_t1_no_sell_on_entry_day`、:59 `test_gap_open_stop_20pct`、:195 `test_summarize_v8_params` :203 断言「止损 20%」、:210 `test_held_name_adds_independent_lot`）；`tests/test_strategy8_rules.py:36` `test_stop_hits_20pct`（默认参数走 STOP_PCT）；`tests/test_csv_minute_backtest_v8.py:233` `test_simulate_held_name_adds_lot`（随 P2）。
- 共享 HELP_LOCK：`csv_daily_backtest.py:153`（「按当日池 CSV 全部名单均分」）、`:166`（「每日 100 万常规额度」）、`csv_minute_backtest.py:109`。

### 实施

1. v8 注册项：`sizing="per_name"`、`name_budget=1_000_000.0`。
2. `STOP_PCT = 0.30`；docstring/HELP_LOCK/`--stop-pct` help/summarize 同步（HELP_LOCK 写明模式分叉：per_name 无加仓、daily_quota 历史复跑路径）。
3. **P1 待裁**：去武装则删 `SMALL_ARM` + `band_floor` :38 分支 + 相关测试（facts 列了 :17-21/:54-60、`test_csv_daily_backtest_v8.py:96-111`）；保留则仅改 v1.1 所列四处。**先等人裁，勿预改。**
4. 按上方清单更新三个测试文件（校准断言，非放宽）。

## 3. 切片 C · 文档

- `docs/backtest/README.md` v8 例注（每股 100 万/止损 30%/skip_cash 语义一句）。
- 共享 HELP_LOCK 加「资金模式见策略书（v8=每股预算）」。
- M-R8③ 二选一落地：caption sizing 检查（`csv_daily_backtest.py:714` `format_equity_compare`）**或**切片 D 流程锁「先重跑 daily per_name 工件」——实施时定，写回交接。
- 本 plan 状态回写。

## 4. 切片 D · 宿主烟测（非合入门，不阻塞）

1. **先**重跑 `csv_daily --strategy version8 --start 20251023 --end 20260909`（per_name 工件落位），**再**跑分钟对照（防 maybe_compare_daily 误归因）。
2. 对照基线 = 切前 daily_quota 同窗工件（记录其 commit/日期）。
3. 输出短记（落 `docs/backtest/`）：逐日 bought/skip/宽度表、NAV 对照、止损滑出分布（trades 事后算：BUY 成本 × SELL stop_loss\* 成交价）、（若 P1 去武装）有/无武装 A/B。数字不入库。

## 5. 门禁（合并前）

```bash
D:\anaconda3\envs\vanna312\python.exe -m pytest -q tests/test_csv_strategy_books.py tests/test_strategy8_rules.py tests/test_csv_daily_backtest_v8.py tests/test_csv_minute_backtest_v8.py tests/test_csv_daily_backtest.py
grep -rn 'import backtrader' backtest/ tests/   # 前置退场已保证零命中，此处复验
```

- 行为变更断言**更新不放宽**；文本文件 UTF-8 无 BOM、NUL=0。
- 完成后缺陷优先复核 diff，回写 plan 状态与交接完成标记。
