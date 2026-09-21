# Handoff：strategy12 金榕元均线减仓书 → Codex 无头实施（2026-09-21）

- **Plan**：[plan-strategy12-jinrongyuan-2026-09-21.md](plan-strategy12-jinrongyuan-2026-09-21.md) **v1.0 已人裁 GO**（master `d75f9c9`）
- **评审链**：对抗层 F1–F8 → 四稿 [consensus S1–S19](../architecture/reviews/2026-09-21/plan-strategy12-jinrongyuan/merge-consensus.md) → 人裁全按建议
- **前置**：**ma_infra 已合入（PR #150）是切片 A 开工门槛**；未合入前只能做切片 B 的引擎重构部分

## §0 硬边界（人裁已定，勿越）

**人裁回填（2026-09-21）：latch = A，只有周期锁。** 同一 MA5 下方周期只减仓一次；成功收复并买回后立即重新武装，同一交易日再次跌破 MA5 允许再次减仓（示例 step 3 可卖）。**不得叠加「每通道每日一次」或任何 once-per-day 日锁**。此裁定覆盖 plan P11 的每日 latch 表述，HELP_LOCK 与测试必须钉死同日收复后可再次减仓。

1. γ 三触点：`execute_buy(..., shares_override=None)`（记账 `per=notional`）；重构 `csv_ledger.py:400-411` 卖出分支（`pos.shares -= shares` 提到条件外、非零余股保留 lot、空 lot 才删）；书侧 exdiv 缩放回调（opt-in）。**不改 BOOKS 注册表既有书、零其它引擎 diff**。
2. **S1 守恒不变量**：部分卖后 `Σ lot.shares` 与 cash 变动守恒（实验证明默认路径现状会静默丢股——修复它就是本刀核心）。
3. 部分卖顺序：**is_step 先卖、中间层 lot_id 升序、lot0 最后且保留 ≥100 股**（P13；保台阶锚 `strategy8_rules.py:61-64`）。
4. 减仓基数 = **t1_sellable** lots 合计 ×50%，floor 100 股；**同一「下方周期」只减一次（cycle latch，人裁 A，2026-09-21）**，成功收复并买回后立即再武装；同日再次跌破可再次减仓，无每日 latch。P11 每日锁措辞已被本裁定覆盖。
5. 双记忆（reduced/stopped 股数）挂 **`st`**（禁模块级 dict）；**按实际成交量**更新；送转按 k 缩放（floor100+残余记 stats）；**新买入（池/chase）清零该码双记忆**（P9④）。
6. 买回 = 第四买因（`run_buybacks_day` 照 `run_step_adds_day` 模板 `csv_simulate_loop.py:322-395`）：上限=该通道记忆股数；`shares_override` 下单；过既有 T+1/涨跌停/费用/容量门；skip_cash 预检在调用点。
7. wiring 四键（P12）：`reserve_limit_up=False`、`defer_limit_up=False`、`daily_same_bar_prefixes=()`、书侧自管止损（不用引擎 STOP_PCT 路径）、MA 通道 `peak_gap_min=0`。
8. reason 前缀复用 **`ma_signal:`**（`csv_ledger.py:394` 已有分支；用 `ma_signal:MA5-derisk` / `ma_signal:MA10-stop` / `ma_signal:MA5-reclaim` / `ma_signal:MA10-reclaim`）。
9. 价域 **front**（P10）：日线 `dividend_type=front`（自动关 E-R6 remap）；分钟 `--daily-source qlib_day` 或新增参数；HELP_LOCK 声明。
10. 台阶改**单调记忆**（S9，独立于存活 is_step lot）；单码单日买向**不加闸**（P6，P11 latch 天然限流，HELP_LOCK 声明理论上限）。
11. `scan_held_day` 5-tuple 不扩（24 个测试调用点）——部分卖信息走 out-param。
12. 禁改 1–10/8.x 书与 Mode A/B；全量 pytest（collect-only=1401）绿不放宽；UTF-8 无 BOM；新文件 ruff 零告警。

## 切片 A：strategy12_rules.py 纯函数（前置：#150 已合入）

**锚点**：`backtest/research/strategy4_rules.py:30-41`（sell_gate/buy_gate 签名先例）；`ma_infra.py`（`sma_asof`/`sma_live`）。
**步骤**：消费 ma_infra；`de_risk_signal(px, closes)`（px < 昨收 MA5 → 触发）、`reclaim_signal(px, closes)`（px ≥ MA5）、`stop_line(ma10)=ma10*0.90`、`exit_plan(code,px,day,closes,lots)->(reason,shares)|None`（含 latch/t1_sellable/is_step 先卖/lot0 保底逻辑的纯函数部分）、`buyback_plan(...)->int`；HELP_LOCK（价域/latch/上限/费用偏差/chase 等值边界/容量不整百声明）；record 函数。
**测试**：`tests/test_strategy12_rules.py` data-free——MA 不足 5/10 根→None、latch A（成功收复后同日第二次减仓允许，无日锁）、50% 取整、lot0 保底、顺序。

## 切片 B：引擎面（可与 A 并行）

**锚点**：`csv_ledger.py:232-248`（execute_buy）、`:400-411`（卖出分支）、`:332/:359`（locked bonus/cap 部分分配）；`csv_simulate_loop.py:322-395`（买因模板）。
**步骤**：① `execute_buy` 加 `shares_override`（`per=notional`）；② 重构卖出分支（S1）；③ `run_buybacks_day` 新买因；④ exdiv 缩放回调 opt-in；⑤ `apply_csv_strategy` hooks 登记（`csv_strategy_books.py:119-136` setdefault 区）。
**测试**：`tests/test_partial_sell.py`——守恒 pin（默认路径+cap 路径）、默认参数下 trades/equity 输出与 HEAD 逐字节等价、实际成交回报（locked bonus/cap）、台阶单调记忆（减仓后同段不重加）。

## 切片 C：状态机 + 注册

**步骤**：记忆挂 `st`（reduced/stopped per code + latch 状态 + 台阶记忆）；双通道买回编排（MA5/MA10 各清各的）；`version12` 注册（别名 `12/v12/version12`、per_name 100 万、`apply()` 必返 `take_profit/record_params`）；AGENTS.md Research entries 增行（含 v7 分工说明）。
**测试**：`tests/test_strategy12_engine.py`——减仓→收复→买回、止损→站回→买回（同日先卖后买）、连续 N 日 MA5 下方只减一次、送转日缩放（exdiv 显式开启）、当日买回当日不可再减、skip_cash、与 chase/pool/step 共存、exdiv 测试**显式开启** `exdiv_economics`。`--strategy 12 --help` 冒烟。

## 切片 D：冒烟 runbook

daily+minute 各 20251023–20260909（front 价域命令写死）；与 v8/8.1/8.2/8.3 五点对比；结果记 reviews（数字不入库）；data_gaps 含价域声明。

## 门禁 + 回写

```powershell
D:\anaconda3\envs\vanna312\python.exe -m pytest -q tests/test_strategy12_rules.py tests/test_partial_sell.py tests/test_strategy12_engine.py tests/test_csv_strategy_books.py
D:\anaconda3\envs\vanna312\python.exe -m pytest -q -m "not production and not benchmark" tests/
D:\anaconda3\envs\vanna312\python.exe -m ruff check <触及文件>
```

完成后：plan 头部回写「✅ 已实施（本 PR）」；遇语义分叉（尤其 latch 边界、exdiv 缩放取整）**停下来在 PR 评论列明，不自裁**。
