# 事实锚点核查评审（host: zcode-facts）

> 评审对象：[plan-money-modes-v8-pername-2026-09-16.md](../../../../backtest/plan-money-modes-v8-pername-2026-09-16.md) v1.0 · 2026-09-16
> 角色：pattern-evidence / 事实锚点核查 · 结论：**READY-AFTER-FIXES**

## 发现列表

### 🔴 必须修

- **🔴1｜「:313 断言 20→30」改不动：20% 的真源在 ProfitStrategy 预设，不在 strategy8_rules。**
  证据：`backtest/ProfitStrategy.py:760` `"version8": (Strategy8, {"stop_loss_pct": 0.20})`（另 `Strategy8.__init__` 默认值 `:673`）；`tests/test_backtest_profit_strategy.py:308-310` 断言工厂默认 `== 0.20`，`:313-323` 触发测试与 `:362-369` adapter 测试全部经 `StrategyFactory.create("version8")` 取该预设。`strategy8_rules.STOP_PCT` 只流入 CSV 引擎（`csv_strategy_books.py:440`）。因此按 §7 只改 `strategy8_rules.py` 时这些测试**根本不会变红**；要把 :313「更新为 30」必须改 `ProfitStrategy.py`——而它不在 §7 落点表里，改动还会波及 Cerebro 栈（`backtest_main_full.py:221` 菜单、`preset_strategy_adapter.py:188`、`rolling_investment_strategy.py` 多处 v8 分支）。
  修复：plan 须人裁「CSV-only（Cerebro v8 预设留 20%，repo 内出现两套 v8 止损默认并写明）」或「连改 ProfitStrategy.py:760/:673/:221（扩 §7 落点 + 评审范围）」，二选一写死。

- **🔴2｜§7 漏列 `tests/test_csv_daily_backtest_v8.py`，B 切片至少 4 例必红。**
  证据（均经默认 `strategy="version8"` 走 `strategy8_rules.STOP_PCT`）：
  - `test_t1_no_sell_on_entry_day`（:40-56，止损 touch 链条，30% 后永不触发）
  - `test_gap_open_stop_20pct`（:59-75，整个用例围绕 20% 止损线）
  - `test_summarize_v8_params`（:195-207，`:203 assert "止损 20%" in text`）
  - `test_held_name_adds_independent_lot`（:210-235，`add_lots==1`/`skip_held==0` 依赖默认加仓，P2 默认「取消」后双杀；止损 0.30 也单独杀它）
  修复：§5-B 完成定义与 §7 测试落点补此文件及上述用例。

- **🔴3｜§7 漏列 `tests/test_strategy8_rules.py::test_stop_hits_20pct`（:36-39）。**
  证据：`:37-38 stop_hits(7.989, 10.0)` 用函数默认参数 `stop_pct=STOP_PCT`（strategy8_rules.py:46），0.30 后 -20.11% 不再触发，断言失败。
  修复：随 STOP_PCT 同步改断言阈值（如 6.989/7.011 一对）。

### 🟡 应修

- **🟡4｜`tests/test_csv_minute_backtest_v8.py` 有一例受 P2 牵连。** `test_simulate_held_name_adds_lot`（:233 起，`add_lots==1`、`skip_held==0`）在 per_name 已持 skip 落地后翻车；其余用例显式传 `stop_pct=0.20`（:27/:50/:73/:95/:118/:141）或不触止损，止损改 30 不破。修复：P2 通过后同步更新该例；§7 补文件名。
- **🟡5｜`--stop-pct` help 文案过时未列。** `csv_strategy_books.py:136` `"stop-loss fraction override (v6 0.06, v8 0.20, v9 0.08)"`，STOP_PCT→0.30 后需改。另注意 `_run_kwargs_version8`（:454-458）允许 CLI `--stop-pct 0.2` 复现旧止损，属可用回滚路径，可在 plan §8 提一句。
- **🟡6｜共享引擎 HELP_LOCK 对 per_name 失真。** `csv_daily_backtest.py:153`（「常规额度按当日池 CSV 全部名单均分」）、`:166`（「每日 100 万常规额度」）、`csv_minute_backtest.py:109`（「资金…与 csv_daily_backtest 相同」）。v8 切 per_name 后，其 summary.txt 尾部仍随附错误的资金口径说明（help_lock_for 把共享文案拼在书文案前）。修复：共享文案加一句「资金模式见策略书（v8=每股预算）」或在 v8 书文案中显式覆盖说明；§7 相应补两引擎 HELP_LOCK。
- **🟡7｜P1「去 SMALL_ARM 只改一个常量+一处单测」低估。** 若去武装，至少破 `tests/test_strategy8_rules.py` 的 `test_band_floor_boundaries`（:17-21 三条）与 `test_take_profit_small_band_to_plus_2pct`（:54-60）、`tests/test_backtest_profit_strategy.py:334-342`、`test_csv_daily_backtest_v8.py::test_small_band_tp_exits_next_open`（:96-111）及 HELP_LOCK/summarize 文案。默认「保留」没问题，但备选路径的成本描述应更正。
- **🟡8｜skip_cash 计数的实现约束未写明。** `_empty_stats`（`csv_ledger.py:24-54`）无 `skip_cash` 键，而 `csv_ledger.py` 在 §7 禁改名单上；`run_pool_buys_day` 里须用 `st.stats.setdefault("skip_cash", 0) += 1` 模式（现有 `skip_held` 等都靠 `_empty_stats` 预置），否则 KeyError。sizing/name_budget 两个 stats 字段同理只能走 hooks/record_params 注入。
- **🟡9｜§7「`run_chase_due_day` 透传预算」表述错位。** `per_ch` 在排单日由 `run_pool_buys_day` 写入（`csv_simulate_loop.py:145` 算 `per` → `:165 queue_limit_up_chase` 存 `pending_chase`），chase 日只消费（`:93`/`:123`）。per_name 模式下 per=name_budget 后 per_ch 自动等于预算，`run_chase_due_day` 唯一要动的是 P2 相关的已持分支（`:94-98`）。真正改动点全在 `run_pool_buys_day`。
- **🟡10｜`backtest_main_full.py:221` 菜单文案「策略8: 20%止损 + …已持加仓各笔独立」会过时**（与 🔴1 同一裁定点：CSV-only 则两套口径并存，此文案属 Cerebro 口径可不改但应记录；若统一则必改）。

### 🟢 备注

- 🟢 **§2 锚点逐项核验通过**：`csv_ledger.py:17`（21_000_000.0）、`:168 _buy_size`（force-min :174-177）、`:181 execute_buy`（佣金 :198、现金拒单 :199）；`csv_simulate_loop.py:145` 均分公式原文一致；`csv_daily_backtest.py:135/:339/:445`、`csv_minute_backtest.py:826/:936` 全对；`csv_strategy_books.py:40`（CsvStrategyBook dataclass）；`strategy8_rules.py` 全部常量（STOP_PCT 0.20 :17、PROFIT_BASE 0.15 :18、SMALL_FLOOR 0.02 :19、SMALL_ARM 0.06 :20、PEAK_DD_PCT/ARM :21-22、BANDS :26-32 与 docx 阶梯一致、ALLOW_ADD=True :14）；`csv_minute_backtest_v7.py:48`（NAME_BUDGET=1M）、`:191-192` skip_cash。
- 🟢 **ALLOW_ADD=True 与「各 lot 独立」属实**：lot 独立记账在 `csv_ledger.py:205-207`（lot_id 递增、独立 cost/peak），行为由 `test_csv_daily_backtest_v8.py:210` 验证；chase × allow_add 交互点在 `csv_simulate_loop.py:94-98`（chase 日已持且 not allow_add → skip_held+chase_skip_held）与 `:147-149`（池买已持）。M-R3「daily_quota 模式下保留加仓」在 M-R1（无 --sizing CLI）下实际成为测试专用不可达路径，P2 通过后建议在书注册处一并降 flag 或注明。
- 🟢 **M-R5「trades 逐字节不变」可行**：tests 无 trades/summary/stats 全量快照断言（`tests/test_csv_daily_backtest.py:1043-1048` 的 pre_er1 快照只断言文件存在不回放；`test_strategy1/3/5_rules` 的 `st.stats == {...}` 用 `SimpleNamespace(stats={})` 空字典，与 `_empty_stats` 无关）；`tests/test_presets_cross_repo_snapshot.py` 与 `tests/fixtures/presets_cross_repo_baseline.json` 均无 v8/version8 命中。但注意 `tests/fixtures/csv_engine_pre_er1/version8_trades.csv` 是旧行为静态锚点，v8 切换后**不要**重跑 `generate_snapshot.py` 覆盖它（plan 未提示）。
- 🟢 **分钟引擎 :936 附近无其他 sizing 路径**：买侧 sizing 全部经 `run_pool_buys_day`/`run_chase_due_day`（pending_exit/force_sell 均在卖侧 `scan_held_day`，与 sizing 无关）；v8 因提供 take_profit callable 恒走 Python 扫描（`csv_minute_backtest.py:638-645`），numba 快路径无 stop 常量需要同步。
- 🟢 **v7 对照准确且 plan 已正确区分差异**：v7 `_buy` 无 force-min（`csv_minute_backtest_v7.py:189-192`，整百后 shares<=0 直接 skip_cash），M-R2 的 force-min 是 docx「资金池补齐」口径而非 v7 口径，plan 措辞未混同。另 v7 判定含 `shares <= 0 or cost > cash` 两种都记 skip_cash，per_name 实现时 force-min 保留了 shares>0，仅现金不足才 skip_cash——语义比 v7 窄，符合 M-R2。
- 🟢 `strategy8_rules.py` 模块 docstring（:3「止损 20 个点」）需随 HELP_LOCK 一并改；§6 命令用 vanna312 全路径 python 合规；`scripts/research/bench_minute_simulate_hotpath.py`（:96/:150，strategy="version8"）经 kwargs 透传 monkeypatch，签名兼容不破，仅语义随 per_name 静默变化。
- 🟢 plan 引用的 `handoff-…codex-impl….md` 与 `docs/architecture/reviews/2026-09-16/` 尚不存在——均声明为 GO 后/评审中产物，非锚点错误。

## 锚点勘误表

| Plan 锚点 | 实际情况 |
|---|---|
| §2「`apply_csv_strategy` hooks 注入 :82」（csv_strategy_books.py） | 函数定义在 **:89**，hooks 注入（allow_add/book/name 等）在 :92-100；:82 是 `normalize_csv_strategy` 的 `return aliases[raw]` |
| §1/§5-B「改 STOP_PCT 并更新 `test_v8_stop_loss_triggers_at_20pct_not_19pct`（:313）」 | 该测试及其 :308/:362 邻例的 0.20 来自 **`ProfitStrategy.py:760` PRESETS + :673 构造默认**，与 `strategy8_rules.STOP_PCT` 无关；仅改 strategy8_rules 这些测试不变红、也改不成 30 |
| §7 测试落点仅列 `test_csv_strategy_books.py` / `test_backtest_profit_strategy.py` | 还需：`tests/test_csv_daily_backtest_v8.py`（4 例必红）、`tests/test_strategy8_rules.py`（1 例必红）、`tests/test_csv_minute_backtest_v8.py`（1 例随 P2 红） |
| §2「v7 … :189–193」 | 基本准确（`_buy` 全体 :186-203，skip_cash 判定/事件在 :191-192）；建议精确到 :188-193 |
| §7「`run_chase_due_day` 透传预算」 | per_ch 在排单日由 `run_pool_buys_day`（csv_simulate_loop.py:145→:165）写入 pending_chase；`run_chase_due_day` 仅消费（:93/:123），无需「透传」改动（除 :94 已持分支） |

---

核心结论：plan 的现状锚点与双模式设计事实基础扎实（§2 表 8 项仅 1 处行号错位），但 §5-B/§7 的「测试更新清单」与「v8 止损常量真源」两处与代码不符，直接按 plan 实施会在 B 切片撞墙（3 个测试文件未列 + ProfitStrategy 预设未裁），须按 🔴1–🔴3 修订后再裁 GO。
