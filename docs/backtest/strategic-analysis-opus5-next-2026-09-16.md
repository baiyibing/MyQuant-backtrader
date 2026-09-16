# MyQuant-backtrader 战略分析（tip `5ba97e4`）

- **日期**：2026-09-16
- **分析 tip**：`5ba97e4dc25f8d56653906e207d382a1f2f82643`（`origin/master`；Opus 本跑读自 `.git/refs`，落盘前由执行助手 `git rev-parse HEAD` 复核一致）
- **出处**：local Opus 5 真跑（`/home/box/.local/bin/cursor-agent -p` + `--model claude-opus-5-thinking-high`；`CURSOR_API_KEY` + `unset CURSOR_AUTH_TOKEN`）。**非 CloudAgent**。
- **性质**：**只读战略分析**。未改业务代码、未跑 F 湖回测、未跑 CloudAgent、未跑门禁。本文落盘 commit 会前移 HEAD，但不改变分析基线。
- **必读父本（本跑实际 Read）**：[engine-positioning-ssot.md](engine-positioning-ssot.md) · [brainstorm-overview-2026-09-15.md](brainstorm-overview-2026-09-15.md) · [repo-analysis-opus5-next-2026-09-15.md](repo-analysis-opus5-next-2026-09-15.md) · [perf-4090-context-brief-2026-09-16.md](perf-4090-context-brief-2026-09-16.md) · [engine-ashare-correctness.md](engine-ashare-correctness.md) · [pool-csv-contract.md](pool-csv-contract.md) · [README.md](README.md) · [money-modes-v8-pername-smoke-2026-09-16.md](money-modes-v8-pername-smoke-2026-09-16.md) · [data/daily-adjusted-update-ssot.md](data/daily-adjusted-update-ssot.md)
- **已消费 #57 折扣**（[perf brief §1.2](perf-4090-context-brief-2026-09-16.md)）：G 禁区「物理删除 Cerebro」「改 6/8 卖点」两条**已被人裁取代**（#58 / #61），本文不再把它们当禁区；**WP1(2) compiled scan 在 band-as-data 落地前对在研策略 ROI 为零**，本文不复活它作默认。
- **未发明性能数字**：本文引用的耗时只有 [perf brief §2.2](perf-4090-context-brief-2026-09-16.md) 的 D 烟测（daily 18.7s / minute ~90s）与 [#54 profile](minute-simulate-profile-results-2026-09-15.md)。文中出现的费率算例是**代码常量的算术推演**，不是实测。

---

## 1. Executive verdict

**本仓是**：一台把**中国 A 股撮合语义写死在薄账本里**的向量化研究脸。它的真实资产不是「回测框架」，而是三样东西——
(a) 一组已锁的 A 股正确性契约（E-R1…E-R4：全卖因跌停 defer、Decimal 档位价、未知板块 fail-closed、停牌=丢零量 K）；
(b) 一份把「名单来源」与「成交语义」解耦的日 CSV 契约（[pool-csv-contract.md](pool-csv-contract.md)）；
(c) 一套 50 个测试文件 / 7,933 行的回归网，含 byte-identical golden trades（`tests/test_csv_strategy_books.py:297`）与两条 numba parity。

**本仓不是**：通用回测框架（没有 order/broker 抽象）、因子研究平台（没有 Dataset/Handler 层）、Paper/live parity 工具（[engine-positioning-ssot.md §3.1](engine-positioning-ssot.md)）、也**不是性能受限系统**（D 烟测 daily 18.7s / minute ~90s 全窗）。

**本轮最重要的判断**：本仓的下一个瓶颈**不在性能、不在卫生、不在 GPU**，而在**两个从未被建模的语义槽**：

1. **资金配给（portfolio construction）是隐式的**。D 烟测实测：全期名单名次合计 5,064，实际成交 271；宽度 > 21（现金上限）的交易日 104/215 = 48%（[money-modes …:105](money-modes-v8-pername-smoke-2026-09-16.md)）。也就是说**约 95% 的「信号通过」名次从未拿到资金，而拿到的那 5% 由代码升序决定**——`run_pool_buys_day` 就是按 `planned` 列表顺序先到先得（`backtest/research/csv_simulate_loop.py:159`），现金耗尽即 `skip_cash`（`:185-191`）。这不是 bug，是**一个从未被写成策略的策略**。
2. **不复权链上的除权日未被裁决**。两条引擎全程 `dividend_type=none`（`backtest/research/csv_daily_backtest.py:262`、`csv_minute_backtest.py:355`），而涨跌停价、止损触发、trail 峰值全部建立在**原始 prev_close / 原始 peak** 之上。湖里 `dividend_type=front` 与 `adj_factor.parquet` 就在隔壁（[data/daily-adjusted-update-ssot.md:30-34](data/daily-adjusted-update-ssot.md)），**除权日有多少次假止损 / 假 defer 从未被数过**。

这两条都**改变决策**（它们污染一切 NAV 结论），都**可用现有数据只读测量**，且都**不需要碰 6/8 卖点语义**。

---

## 2. Architecture map vs industry pattern

### 2.1 实际分层（本跑逐文件核对）

```
名单源（仓外：MyQuant / Qlib 导出 · 本仓 TR · 手工）
   ↓  日 CSV 契约（YYYYMMDD.csv，裸六位码 [+名称列]）
csv_pool.py            解析 / 严格校验 / by-day 名称
csv_strategy_books.py  BOOKS dict → hooks（take_profit / sell_gate / buy_gate 皆 callable）
csv_simulate_loop.py   共用骨架：chase / pool buys / equity+EOD mark
csv_daily_backtest.py  日线 simulate + 卖环(内联) + 加载 + CLI + summarize + 落盘
csv_minute_backtest.py 分钟 simulate + scan_held_day + 分钟加载 + bar 缓存 + CLI
csv_ledger.py          Position / SimState / execute_buy / _sell / 追买账
market_layer.py        叶子：limit_pct / Decimal limit_prices / round_fen
```

层次本身**是干净的**：`csv_ledger.py:2-6` 与 `market_layer.py:2-6` 都显式声明「不 import 引擎」，且实际做到了。

### 2.2 与行业范式对照

| 行业层 | Qlib | 事件驱动（Backtrader / vn.py / RQAlpha） | 本仓 |
|---|---|---|---|
| Data / Dataset | `DataHandlerLP` + .bin mmap | Feed | **外包**（只读 F 湖 parquet + 日 CSV） |
| Signal / Model | Model → pred 宽表 | Indicator | **外包**（MyQuant / 本仓 TR 导出器） |
| **Portfolio construction** | `TopkDropoutStrategy`（显式排名+淘汰） | Sizer | **缺失**（见 §5 D1） |
| Execution / Matching | `Exchange`（单价一笔） | Broker + Order 状态机 | `csv_ledger` + 引擎卖环（**本仓的核心资产**） |
| Record / Analysis | `SignalRecord` / `PortAnaRecord` | Analyzer | `write_run_artifacts` 三件套（`csv_daily_backtest.py:660`），**无出处元数据** |

**结论**：本仓在 Execution 层比三家开源都更贴 A 股（档位表、Decimal 分位、全卖因 defer、停牌冻仓），在 **Portfolio 层和 Record 层各缺一格**。这不是「技术落后」，是**当初没必要、现在有证据需要**。

### 2.3 一个结构性倒置（重构优先级 #1）

`csv_minute_backtest.py:33-75` 从 `csv_daily_backtest.py` **import 41 个符号**——包含 `SimState`、`execute_buy`、`_sell`、`summarize`、`write_run_artifacts`、`load_daily_bars`、`add_csv_backtest_common_args`，甚至包含**本来就住在别处的** `build_calendar` / `_pool_names_asof` / `_named_limits`（真身在 `csv_common.py:44,62`）与 `utc_ms_range`（真身在 `market_layer.py:25`）。

即：**一个 CLI 入口模块被当成共享库用，并且还在替另外两个叶子模块做转发**。

`csv_common.py:3-4` 的 docstring 自己写着「Calendar / name-asof live here **so engines avoid coupling through the daily module**」——意图已成文，实际耦合面仍是 41 个符号。后果：
- 分钟引擎的落盘/汇总/参数解析行为**由日线文件定义**，改日线 CLI 会静默改分钟行为；
- 「两套卖环有意分家」这条策略之所以贵，正是因为除卖环外的一切也纠缠在同一个文件里；
- 任何第三条成交时点（例如已被点名的 version11 CSV 移植）都要么继续 import 日线，要么再拷一份。

这是全仓**唯一一条零语义风险、但解锁后续一切的重构**，且有 byte-identical golden 可作验收锁。

---

## 3. A-share correctness posture（强 / 脆）

### 3.1 强（明显强于主流开源）

| 项 | 证据 | 备注 |
|---|---|---|
| 涨跌停档位表 | `market_layer.py:18-22,57-65` | 创科 20%（含 302/689 CDR）/ 北交 30%（920/430/83/87/88）/ 主板 10% / ST 5% |
| **未知前缀 fail-closed** | `market_layer.py:54` → `skip_unknown_board` | 不默认 10%。比「猜一个」更诚实 |
| Decimal 涨跌停价 | `market_layer.py:73-84` | `ROUND_HALF_UP` 到分，显式禁银行家舍入 |
| 涨跌停判定含越界 | `csv_ledger.py:90-97` | `price + EPS >= limit_up`，不是只判相等 |
| T+1 | `csv_daily_backtest.py:359,367`；`csv_minute_backtest.py:551,862` | `n_days = i - entry_idx`，`>= 1` 才可卖 |
| **全卖因跌停 defer**（E-R1） | `csv_daily_backtest.py:362,373,386,413-418` | 含 trail / profit_take / force / ma_signal，不只 stop_loss |
| 整手 100 | `csv_ledger.py:168-178` | `// 100 * 100` |
| 停牌 = 丢零量 K | `csv_daily_backtest.py:225-252`；`csv_minute_backtest.py:165-207` | 复用同一条冻仓路径，不建第二套状态机；净值走 `last_close_mark`（`csv_ledger.py:162`） |
| 名称 as-of（禁后日赢） | `csv_common.py:62-85` | 单调游标 `updates[cursor][0] <= ds`，结构上不可能读到 `ymd > ds` |
| 买入涨停不成交→T+1 追买 | `csv_ledger.py:105-111`；`csv_simulate_loop.py:95` | `day_i > sig` 才评，且只评一次 |

### 3.2 脆（按影响排序）

**(1) 除权除息未建模——最严重。** 链路全程 `dividend_type=none`，而：
- 涨跌停价 = **原始** prev_close × (1±档)（`csv_daily_backtest.py:352-353`）。除权日交易所按**除权参考价**定档，本仓不会；
- 止损触发 = `open <= cost × (1 - stop)`（`:371-372`），`cost` 是**除权前**买价；
- trail 峰值 = `pos.peak = max(peak, high)`（`:393`），峰值是**除权前**高点。

机制推演（**未实测**，这正是 NP3 要数的东西）：一次 10 送 10，次日 open ≈ prev_close/2 → ① 远低于算出的 `limit_down` → `hit_limit_down` 为真 → **所有卖因 defer**；② 同时满足任何 `stop_pct` → 除权正常化后按**未调整的 cost** 记一笔约 -50% 的假止损；③ band 型书（v6/v8/v10）的回撤从未调整 peak 起算 → 立即触发。
湖里 `dividend_type=front`（QMT ground truth）与 `adj_factor.parquet`（含 `cumulative_adj_factor`）**已存在**（[data/daily-adjusted-update-ssot.md:30-34](data/daily-adjusted-update-ssot.md)），所以「哪些 (code, date) 是除权日」是**免费可查**的。

**(2) 成本模型是打包近似，且仓里同时存在一份更准的、没人用的。** 生产链是平的 `COMMISSION = 0.001` 双边（`csv_ledger.py:18`，买 `:198` / 卖 `:231`），无印花税、无最低佣金、无过户费、无滑点。而 `backtest/research/engine.py:34-54` 里躺着一份对齐 `trade_fee_policy` 的正确配置（`commission_rate=0.00005`、`tax_rate_sell=0.0005`、`min_commission=5.0`、ETF 印花豁免前缀）——**它所属的 `BarReplayEngine` 是死代码**（`run_dates` 在 `:106-119` 恒返回空 `fills`），且在 `backtest/legacy/engine.py` 还有第二份。

方向不是单边的（算术推演，非实测）：100 万名义买入，真实 ≈ 50 元（0.005%）vs 模型 1,000 元（0.1%）→ **保守高估约 20×**；但 `_buy_size` 的 force_min 兜到 100 股（`csv_ledger.py:173-177`）时，100 股 × 5 元 = 500 元名义，真实受 `min_commission=5` 约束 ≈ 1.0%，模型 0.5 元 = 0.1% → **乐观低估约 10×**。D 烟测 per_name 1M 下 force_min 未触发（`chase_buy_fail_shares = 0`，[money-modes …:85](money-modes-v8-pername-smoke-2026-09-16.md)），所以这是**窄口径**问题，不是当前结论的污染源——但它和「没有滑点、分钟按触价任意手数成交」叠在一起，意味着**成本侧保守、成交侧乐观，净效应方向不可知**。这一句应该写进 correctness SSOT，而不是留给读者猜。

**(3) 涨跌停档位只建模了「板块 + ST 名」两维。** `market_layer.limit_pct`（`:57-65`）不含新股上市前 5 日无涨跌幅限制、退市整理期、以及「退」字警示。fail-closed 只对**未知前缀**生效，对**已知前缀的特殊 regime** 不生效——一只上市首日的 301xxx 会拿到 20% 而不是无限制。是否重要取决于名单是否含次新股，本文**不臆测频率**。

**(4) ST 名称对长持仓会 stale。** `_pool_names_asof`（`csv_common.py:71-83`）只在票**再次进名单**时推进 `last_seen`。买入后不再入池的持仓，其戴帽/摘帽永远看不到 → `limit_pct` 错档 → 涨跌停判定错 → defer 逻辑错。R10 已记「断档失真」，但记的是名单内断档；**持仓期外失真是同一根因的更长尾巴**。

**(5) 禁前瞻的最后一公里在契约边界上断开。** `pool-csv-contract.md:7-8` 明写「文件名日期就是买入日 T……**不是导出日**」——即契约**不携带出处**。本仓无法区分「T-1 收盘后用 ≤T-1 数据生成的名单」和「事后全历史扫描生成的名单」。唯一的本地 as-of 断言只覆盖源 B（`source_b_tr_pool.py:51-59`，拒 `trade_date > T`），且它**允许 `trade_date == T`**，而日线在 **T 日收盘**买入（`csv_daily_backtest.py:447` 返回 `row["close"]`）——即「用 T 日全日数据选，在 T 日收盘成交」的零延迟假设。这是向量化研究脸的**合法取舍**，但目前**只存在于代码里，没写进契约**。

---

## 4. Gap vs Qlib-like / 向量化最佳实践（语义取舍，非技术差距）

[perf brief §3](perf-4090-context-brief-2026-09-16.md) 已把「Qlib 为什么快」讲透（信号预计算 / 排名淘汰无状态 / 单价成交 / .bin mmap），结论是**砍掉语义谁都快**，本文不重复。补三条它没覆盖的：

1. **Qlib 的 `TopkDropoutStrategy` 不只是快，它是把配给写成了策略。** `topk` + `n_drop` 是显式的、可扫参的、可归因的。本仓的等价物是 `csv_simulate_loop.py:159` 的一个 `for code in planned`——配给规则是**名单文件的行序**。当 48% 的交易日宽度超过现金上限时，这个隐式规则就成了主导变量。**这是本仓从镜子里能学到的最大一件事**，而且学的是**分层**，不是 Qlib 的代码。
2. **Qlib 的 Record 层给出了 run 的出处。** 本仓 `write_run_artifacts`（`csv_daily_backtest.py:660-661`）只出 `summary.txt` / `daily_equity.csv` / `trades.csv`，**不含**代码 SHA、策略参数、湖 root、名单源目录、数据窗口。跨 sizing / 跨窗口对照时要靠人工记「commit/日期与池来源」（[README.md:56](README.md) 的 M-R8③ 就在手工叮嘱这件事）。注意：这**不是**延期中的跨仓 `myquant.run-manifest/1`（那需要产品点头），这是**本仓自己的 run 出处戳**。
3. **zipline / backtesting.py 的教训指向相反方向。** `backtesting.py` 完全没有涨跌停 / T+1 / 整手；zipline 的滑点与佣金模型是美股中心的（`VolumeShareSlippage` / `PerShare`），移植到 A 股要全重写。Backtrader 的事件总线买来的通用性，代价正是本仓已实测的那种逐 bar Python 开销（[#54](minute-simulate-profile-results-2026-09-15.md)：卖环 75.51%）。**本仓选择「纯 Python 状态机 + 批量 parquet 装载 + 薄账本」是曲线上的一个刻意点位**，用通用性换 A 股语义密度。D 烟测 18.7s / ~90s 证明这个点位在当前规模下是对的——**「分钟太慢」的假设已被证伪，不要再拿它当立项理由**。

---

## 5. Debt & risk register（只列改变决策的项）

沿用 #52/#57 的 R 编号空间，新增 D 编号避免撞号。

| ID | 债 / 风险 | 证据 | 为何改变决策 |
|---|---|---|---|
| **D1** | **资金配给隐式且未测量**：宽度超上限时按名单行序（=代码升序）先到先得 | `csv_simulate_loop.py:159,185-191`；[money-modes …:105](money-modes-v8-pername-smoke-2026-09-16.md)（5,064 名次 → 271 成交；104/215 天超上限） | 一切 NAV / 归因结论都含一个未量化的代码序偏好项。不先测它，后续任何策略对照都不可信 |
| **D2** | **除权日语义未裁决**：不复权链上 limit / stop / peak 全用原始价 | `csv_daily_backtest.py:262,352-353,371-372,393`；`csv_minute_backtest.py:355,111-112` | 可能在窗口内制造假止损 / 假 defer。且**修复数据已在湖里**（`adj_factor.parquet`），只差数一次 |
| **D3** | **引擎分层倒置**：分钟从日线 CLI 模块 import 41 个符号，含四个本属叶子模块的转发 | `csv_minute_backtest.py:33-75` vs `csv_common.py:3-4,44,62`、`market_layer.py:25` | 阻塞一切后续结构工作；且 docstring 的成文意图与实际相反 |
| **D4** | **两份死引擎 + 一份没人用的正确费率模型** | `backtest/research/engine.py:34-54,106-119`（`fills` 恒空）；`backtest/legacy/engine.py:49,84`；仅被 `tests/test_research_face_imports.py:33,121` 与 `tests/test_backtest_engine_smoke.py:4` 钉活 | 新人会误以为仓里有第二条成交路径；同时掩盖了「生产链费率是打包近似」这一事实 |
| **D5** | **名单契约无出处字段**，本地 as-of 断言只覆盖源 B 且允许 `trade_date == T` | `pool-csv-contract.md:7-8`；`source_b_tr_pool.py:51-59`；`csv_daily_backtest.py:447` | 上游一旦泄露未来数据，本仓**结构上无法发现** |
| **D6** | **门禁脚本 8 对同名副本，其中 7 对行数已不同**（`scripts/gates/` vs `scripts/research/` vs `backtest/research/`） | 见 §5.1 表 | #57 的 R12 记的是「整份拷贝」；**已分叉意味着两份行为不同**，风险等级上升——cookbook 只钉了权威，未消除歧义入口 |
| **D7** | **pytest 配置引用两个不存在的文件** | `pytest.ini:5`（`tests/test_production_readiness.py`）、`:7`（`scripts/run_csv_contract_release_tests.py`，Glob 命中 0） | CI 的 `-m "not production and not benchmark"` 现在**排除了零个测试**；`csv_contract` / `benchmark` 两个 marker 零使用；`asyncio_mode = auto`（`:13`）是 live 栈退场后的残留 |
| **D8** | **SSOT 级文档仍写「不删 Cerebro」** | `engine-ashare-correctness.md:29`（锁文档，非头脑风暴）；另 `brainstorm-overview-2026-09-15.md:23`、`plan-hygiene-backlog-2026-09-15.md:5,34`、`chip/chip-slowpath-inventory-2026-09-15.md:14`、`repo-analysis-vs-brainstorm-2026-09-15.md:80`（仍列已删入口 `backtest_main_full.py --allow-cerebro-fossil`） | #58 已物理删除。**锁文档与现实矛盾**会让下一个 agent 误判禁区 |
| **D9** | 孤儿日志解析器 | `backtest/tools/parse_log.py:23,31,43` 解析已删的 `rolling_investment_strategy` 日志格式 | 小，但会把人引向已退场的栈 |
| **D10** | `README.md:111` 仍把 `plan-vectorized-hotpath-offload` 标为「★ 进行中」 | 该 plan 自述「v0.1 · 进行中」，其候选 1 未开工、候选 2 已被 #57 折扣判 ROI 弱、GPU 已关闭 | ★ 状态位会让人以为有在途工作 |

**降级/不再单独列**：`daily_quota_used` 在 per_name 下的「保存—调用—还原」手法（`csv_simulate_loop.py:133-135,192-195` + `csv_ledger.py:202`）与 per_name 现金检查对 `execute_buy:199` 的重复（`csv_simulate_loop.py:188`）——真实但局部，随 NP1 顺手收即可。

### 5.1 D6 明细

| 权威（`scripts/gates/`） | 副本 | 行数 |
|---|---|---|
| `verify_single_stock_turnover_resist.py` | `scripts/research/` | 495 / 495（疑整份拷贝） |
| `verify_turnover_resistance_alignment.py` | `scripts/research/` | 173 / 158 |
| `verify_minute_chip.py` | `backtest/research/` | 204 / 194 |
| `verify_adj_minute_chip.py` | `backtest/research/` | 168 / 160 |
| `verify_chip_factor_consistency.py` | `backtest/research/` | 251 / 248 |
| `verify_chip_pool_enhancement.py` | `backtest/research/` | 274 / 270 |
| `verify_mvp_min.py` | `backtest/research/` | 254 / 249 |
| `verify_float_shares_time_dimension_baseline.py` | `backtest/research/` | 226 / 219 |

> 判定依据为行数差与 docstring 差异，**本跑未执行 byte diff**（shell 受限）。权威判定见 [host-lake-gates-cookbook-2026-09-16.md:137-141](host-lake-gates-cookbook-2026-09-16.md)。门禁总数 13、CI 跑 4 的事实经 `.github/workflows/python-tests.yml:40-43` 复核，与 #57 一致。

---

## 6. Prioritized next packages（NP1–NP5）

排序依据：**是否污染现有结论** > **是否解锁后续结构工作** > **成本**。NP1/NP2 是正确性，NP3 是结构，NP4/NP5 是收口。

### NP1 — 资金配给显式化（先测量，后开关）

| | |
|---|---|
| **意图** | 分两步：**(a) 纯记账探针**（data-free，吃现有 `trades.csv` + `--pool-dir`）——按日输出「名单宽度 / 获配名数 / 被配给挤出的名次 / 挤出者在代码序中的位次分布」，把 D1 的 5,064→271 拆成逐日事实；**(b) 显式配给策略参数** `--ration {file_order,seeded_shuffle,...}`，**默认 `file_order` = 现行行为、字节不变**，`seeded_shuffle` 仅供 A/B 量化代码序偏好的幅度 |
| **为何现在** | 48% 的交易日撞现金上限、94.6% 的名次从未获配（[money-modes …:105](money-modes-v8-pername-smoke-2026-09-16.md)）。**在这条被量化之前，任何跨策略 / 跨 sizing 的 NAV 比较都含一个未知大小的系统性偏差**；这也是本仓相对 Qlib 唯一真正缺的那一层 |
| **明确不做** | 改 6/8/9/10 卖点；改默认配给（默认必须 byte-identical）；用 A/B 结果给策略定胜负；把配给做成优化器（不是选股，是配给） |
| **验收** | (a) data-free pytest + 一份合成 fixture；(b) `--ration file_order` 下 `tests/test_csv_strategy_books.py:297` 的 byte-identical golden 仍绿；宿主 A/B 另附短记，**不进 CI**；`pool-csv-contract.md` / `engine-ashare-correctness.md` 各补一行 |
| **风险** | 中。(b) 触及买侧共用路径 `csv_simulate_loop.py:159`。用 golden 锁住默认分支即可控。(a) 零风险，**建议先单独成片** |

### NP2 — 除权日语义裁决（只读探针 → E-R5 锁；**不实现复权**）

| | |
|---|---|
| **意图** | 用 `adj_factor.parquet` 的 `cumulative_adj_factor` 跳变定位除权 (code, date)，在 D 烟测同窗（20251023–20260909）只读统计：① 持仓期内命中的除权日数；② 其中触发 `stop_loss:gap_open` / `defer_sell_limit_down` / band trail 的笔数；③ 对应 `trades.csv` 记录。然后**二选一裁决**：影响可忽略 → 写成 **E-R5「不复权链的已知边界」** 并在两条 HELP_LOCK 里点名；影响显著 → **另开**复权片（因为复权会改写全部历史 NAV 与 fixture，不能顺手做） |
| **为何现在** | 这是**唯一一条既未被任何现有文档覆盖、又直接污染 NAV、还能用手边数据当天数完**的正确性风险。相比之下 §3.2(3)(4) 的频率未知，应等这条的方法学成型后复用 |
| **明确不做** | 本片内改 `dividend_type`；改 `cost` / `peak` 的调整语义；重算历史 fixture；把探针接进 CI（需 F 湖） |
| **验收** | 一份 dated 结果文档（含窗口、口径、命中计数、样例 trade 行）+ `engine-ashare-correctness.md` 的 E-R5 条目或一份新 plan；**只读，无业务代码变更** |
| **风险** | 低（只读）。真正的风险是**裁决被无限期搁置**——所以本片的交付物是「裁决」，不是「调查」 |

### NP3 — 引擎分层倒置修复（纯机械重构）

| | |
|---|---|
| **意图** | 把 `csv_minute_backtest.py:33-75` 那 41 个符号按归属下沉：`build_calendar`/`_pool_names_asof`/`_named_limits`/`utc_ms_range` **直接改指真身**（`csv_common.py` / `market_layer.py`，消除转发）；`summarize`/`write_run_artifacts`/`_progress`/`maybe_compare_daily` 抽出 `csv_artifacts.py`；`load_daily_bars`/`warmup_start`/`warn_stale_period_env` 抽出 `csv_daily_loader.py`；CLI 组装件（`add_csv_backtest_common_args` 等）留在 `csv_strategy_books.py`。两条 `simulate()` 与两套卖环**原地不动** |
| **为何现在** | 零语义风险且有 byte-identical golden 兜底；它是 NP1(b)、未来 version11 移植、以及任何「band-as-data」实验的共同地基。**不做它，每一片后续工作都要先绕过这 41 个符号** |
| **明确不做** | 合并日线↔分钟卖环（G 禁区仍在）；改任何函数体；改 CLI 参数名或落盘路径；顺手做性能优化 |
| **验收** | `tests/test_csv_strategy_books.py:297` byte-identical golden 绿；`tests/test_research_face_imports.py` 绿；全量 pytest 绿；`csv_minute_backtest.py` 对 `csv_daily_backtest` 的 import 数**显著下降**（目标：不再 import 叶子模块的转发）；diff 中零行为变更 |
| **风险** | 低–中。体量中等但全是移动，逐个模块分 commit 可回滚 |

### NP4 — 成本模型诚实化 + 死引擎退场

| | |
|---|---|
| **意图** | (a) 在 `engine-ashare-correctness.md` 补一条**成本口径**：平 0.1% 双边是**打包近似**，写明它相对真实（佣金 + 印花 + 最低佣金 + 过户）在大单方向保守、在 force_min 小单方向乐观，并写明**无滑点 + 分钟触价任意手数成交**这一乐观成交假设；(b) 删除 `backtest/research/engine.py` 与 `backtest/legacy/engine.py` 两份死 `BarReplayEngine`（`fills` 恒空），或若 `trade_fee_policy` 那份配置要保留，就把它降为一个**明确标注「未接入 CSV 链」**的常量模块；相应调整 `tests/test_backtest_engine_smoke.py` 与 `tests/test_research_face_imports.py:33` |
| **为何现在** | 仓里同时存在「生产用的近似费率」和「正确但没人用的费率」，这本身就是误导。且 (b) 的删除把 §3.2(2) 的事实逼到台面上 |
| **明确不做** | 改 `COMMISSION = 0.001` 的数值（那会改写所有 golden 和历史 NAV，须另开片并重跑 fixture）；给 CSV 链加滑点模型；动 `trade_fee_policy` 本身 |
| **验收** | docs 一条 + 删除片；全量 pytest 绿；`engine-ashare-correctness.md` 新条目与 CLI HELP_LOCK 措辞一致 |
| **风险** | 低。唯一注意：`test_research_face_imports.py` 的导入残差用意（防目录拆分后 import 悬空）要保留，别把守卫一起删了 |

### NP5 — 契约/配置收口（D5 + D6 + D7 + D8 + D9 + D10）

| | |
|---|---|
| **意图** | 一次收掉：① `pool-csv-contract.md` 增**可选出处头**（生成时刻 / 数据截止日 / 生成器），加载侧**缺失只 warn 不 fail**（渐进，不破坏现有名单目录），并把「T 日数据选、T 日收盘成交」的零延迟假设写进契约；② D6 的 8 对副本——删副本或改一行 shim，消除歧义入口；③ `pytest.ini` 删两条死引用、清理零使用 marker 与 `asyncio_mode`；④ D8 的 `engine-ashare-correctness.md:29` 等 6 处「不删 Cerebro」改口径；⑤ 删 `parse_log.py` 或标注考古；⑥ `README.md:111` 的 ★ 状态位改为「未开工 / 候选 (2) ROI 弱」 |
| **为何现在** | 这些单独都不值一片，合起来是一次「让下一个 agent 不被误导」的收口。**① 是其中唯一有架构分量的**（禁前瞻的最后一公里），其余是维护 |
| **明确不做** | 把出处头做成硬门（那是 run-manifest，需产品点头）；物理合并门禁脚本的实现（只做删/shim）；改 CI workflow 的湖门禁注释块 |
| **验收** | 单个 PR；`rg` 无死链、无零使用 marker、无「不删 Cerebro」；data-free CI 绿 |
| **风险** | 极低 |

---

## 7. Explicit do-not list

1. **不跑 CloudAgent**。交付路径是本机改 + 评审 + GitHub Actions。
2. **不复活 Cerebro / Rolling**（#58 已物理删除）。ma_chip 默认归档；version11 CSV 移植须另开 dated plan 并重裁成交时点语义。
3. **不把需 F 湖的门禁塞进 CI**。`.github/workflows/python-tests.yml:35-37` 的注释块不动；9 个宿主门禁留在 [cookbook](host-lake-gates-cookbook-2026-09-16.md)。
4. **不重开回测 GPU**。#60 已合入归档、回测 STOP、S2 关闭（[perf brief §2.7](perf-4090-context-brief-2026-09-16.md)）；本文不以任何形式把它设为默认或前置。
5. **不在无产品 GO 时硬接 `myquant.run-manifest/1`**。NP5① 的**本仓出处头**与跨仓 run-manifest 是两件事，不要混为一谈、也不要借前者偷渡后者。
6. **不提合并三仓栈**，不复刻 LEBS / MockQMT / Redis / executor，不在本仓复刻 MyQuant 的 numba 全市场 CYQ feeder。
7. **不拿 Qlib `PortAnaRecord` 当对照基准**，不承诺向量化 NAV 与 LEBS / Paper 对齐（能比的只有名单 / reason / 可卖股 / 涨跌停）。
8. **不 big-bang 合并日线↔分钟卖环**（NP3 明确把两条 `simulate()` 与卖环排除在外）。
9. **不以「分钟太慢」立项**。D 烟测 daily 18.7s / minute ~90s 已证伪该假设；WP1(2) compiled scan 在 band-as-data 落地前对 v6/v8/v9/v10 收益为零（[perf brief §1.2](perf-4090-context-brief-2026-09-16.md)）。微优化需先出痛点证据。
10. **不在 NP4 里顺手改 `COMMISSION` 数值**，不在 NP2 里顺手实现复权——两者都会改写全部 golden 与历史 NAV，必须独立成片。

---

## 8. Recommended default

**建议：不 stop，开下一个 PR——但开的是 NP2 + NP1(a) 这一组「只读、当天可结、改变后续一切判断」的片，不是结构大活。**

理由：
- 上一轮的默认立场「先停在 master」建立在「剩下的只有软卫生」这个前提上。本轮找到了**两条不属于软卫生的东西**（D1 配给隐式、D2 除权未裁决），它们**污染现有 NAV 结论**，而且**都能只读测量**。在它们被数清之前继续做结构或性能工作，是在给一个未校准的秤加零件。
- NP2 与 NP1(a) 都是**零业务代码变更**：前者读 `adj_factor.parquet` + 已有 `trades.csv`，后者读已有 `trades.csv` + `--pool-dir`。两者共用同一套「对着已落盘工件做事后归因」的方法，合成一片成本最低。
- **NP3（分层倒置）是重构优先级第一，但它应该排在这一组之后**：它是地基，而地基要按已校准的需求浇。先知道配给要不要成为一等参数（NP1b），再决定共享层怎么切。
- 若必须二选一只开一片：**开 NP2**。除权是唯一一条「可能正在无声制造假交易记录」的项。

排序：**NP2 + NP1(a)（一片，只读）→ NP1(b) 或 NP3（视 NP1(a) 结论而定）→ NP4 → NP5**。NP5 可在任意空档插入，它不阻塞任何人。

**不建议**的下一步：再开一轮 Hx 式软卫生、任何性能片、任何 GPU 相关、任何跨仓硬接。

---

## 9. 本文的证据边界

- Opus 本跑 **shell 被环境策略拦截**，未执行 `git log` / `rg` / `diff` / `pytest` / 任何门禁；SHA 读自 `.git/refs`。落盘前执行助手复核 tip SHA、D 烟测数字、41 个 import、门禁行数差、死文件引用与 golden 行号；**D6 的「已分叉」判定仍基于行数差与 docstring 差异，未做 byte diff**。
- 引用的全部耗时数字来自 [perf brief §2.2](perf-4090-context-brief-2026-09-16.md)（D 烟测）与 [#54 profile](minute-simulate-profile-results-2026-09-15.md)，**本文未新增任何实测**。
- §3.2(1) 的除权失败机制是**从代码推演**（`csv_daily_backtest.py:352-353,371-372,393`），**未实测频率与幅度**——这正是 NP2 存在的理由，不应被引用为已发生事实。
- §3.2(2) 的费率算例是**代码常量的算术**（`csv_ledger.py:18` vs `backtest/research/engine.py:37-39`），不是回测结果。
- §1 与 §5 D1 的配给数字全部转引 [money-modes-v8-pername-smoke-2026-09-16.md:85,105](money-modes-v8-pername-smoke-2026-09-16.md)，未重算。
