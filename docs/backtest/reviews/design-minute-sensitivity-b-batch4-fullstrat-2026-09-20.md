# 分钟敏感对照 B · 第四批设计（全策略 NAV / DD / 引擎内排名 · 2026-09-20）

**范围**：只读研究路径，用既有全策略 runner 在**扩展窗口**上诚实填补 batch1–3 留下的全策略净收益 / 最大回撤 / 引擎内排名 `DATA_GAP`（能填则填，不能填则空白）。**不**改 production_C（fill / scan / fee / default clock）；**不**在 VM 跑多日湖回测；4090 由 parent 执行。

依据：[计划 SSOT](plan-minute-sensitivity-b-2026-09-20.md)；[batch1](results-minute-sensitivity-b-batch1-2026-09-20.md) / [batch2](results-minute-sensitivity-b-batch2-2026-09-20.md) / [batch3 Mode B](results-minute-sensitivity-b-batch3-modeb-2026-09-20.md)；产物目录 `backtest/research/exports/minute_sensitivity_b_20260920/batch4_fullstrat/`。

BASE tip：`ac1fa97`（Merge #140 / `origin/master`）。

**2026-09-21 Human GO option 2**：批准新增 research-only fullstrat clock/slip hooks；实施基线 `32b78b1`，分支 `research/batch4-fullstrat-clock-slip-hooks`。Human cut A 仍成立：read-only expand，no behavior C；`production_C=frozen`。A（文档）与 B（实现及 data-free pins）分 commit；完成后只开 draft PR，不 merge。发现语义分叉须 PR comment + stop，不能自行裁定。完整人裁已于 #156 确认：**H2 + 未成交卖单到期后次日策略重评**，取代此前 sell pending 桩；B 可继续实施，详见 §9。Q2 已覆盖 Q1；Slice B hooks 与 data-free pins 已落地，能力 `FILLABLE`，数字待合并后 4090。

---

## 1. 能算 vs 必须 DATA_GAP

| 指标 / 轴 | Book（csv_minute_backtest） | v7（csv_minute_backtest_v7） | Mode B（unified_exit_modeb） |
|---|---|---|---|
| **默认时钟 + DEFAULT_SCHEDULE** 全策略 NAV / return / maxDD | **可填**（既有 CLI，`--minute-source qlib_1min`） | **可填**（同上） | **可填**（研究 harness 库调用：入场=同 1min none 聚合日收；分钟=同一 qlib_1min；**禁止** `my_data` day.bin 后复权入场） |
| **引擎内排名** | **可填**（同窗口多卖点书 version1–6,8–10 按 return 排序；不含 topk_*） | N/A（单策略；`within_engine_rank=1` 仅自指） | **可填**（`ranking.csv` / 网格 `StrategyMetrics.total_return`） |
| **全策略 clock 交换**（H2 + Q2） | **FILLABLE** | **FILLABLE** | **FILLABLE** |
| **全策略 slip 轴**（Q2，每边 5/10/20bp） | **FILLABLE** | **FILLABLE** | **FILLABLE** |
| 跨引擎 NAV 优劣比较 | **禁止** | **禁止** | **禁止** |
| 把 batch2/3 局部事件 bp Δ 贴进 NAV 格 | **禁止** | **禁止** | **禁止** |

### 原批为何为 DATA_GAP（历史证据；Slice B 已增加研究 hook）

- Book / v7 / Mode B 生产默认成交时钟与费率写死在引擎路径；CLI **无** research-only「全策略 clock 交换」或「全策略滑点」开关。
- 若为填格而改 `ashare_fill_clock` / 默认 fee / 静默 fork 生产路径 → 触犯 **production_C frozen**。
- batch2/3 的 local-event clock / cost 叠层**仅局部**，不得冒充组合 NAV。本批对这两轴显式留空，并仍交付**默认时钟**基线全策略 NAV（诚实填）。

Option 2 授权在研究边界内解除「无 hook」限制。§9 的 H2 + Q2 已实现并通过 data-free pins，四个 cell 的能力转为 `FILLABLE`；数值仍等待合并后的 4090 slice D。

---

## 2. 扩展窗口 / 符号提案（相对 batch2：3 日 × 5 标的）

| 项 | batch2（局部事件） | **batch4 提案（全策略）** | 依据 |
|---|---|---|---|
| 日历窗 | `20260916`–`20260918` | **`20260825`–`20260909`** | 仓内 `stock_pool/*.csv` 在该闭区间有 **12** 个交易日文件；`MINUTE_LAKE_END=20260909`；batch2 的 09-16..18 **无** pool CSV，不能支撑 Book/v7 全策略名单驱动 |
| 符号 | 固定 5：`000021.SZ,…` | **窗内 pool 并集**（约 **69** 个六位码；runner 会规范为 `.SH/.SZ`） | 自然扩容；不手工挑「好看」子集 |
| 分钟访问 | `qlib_bin_1min` | **优先** `qlib_bin_1min` → `C:\Users\wangc\.qlib\qlib_data\my_data_1min`；回退同血缘 `E:\stock_data` parquet | 与 batch2/3 一致；`source=parquet_lineage` |
| bar 标签 | START 墙钟 | **START**（`lake_index_is_bar_start_wallclock`） | 同 batch2 |
| Mode B 入场 | 局部：1min 聚合 | **全策略同样**：`daily_entry_source=aggregated_from_1min_none_lineage` | 禁止 qlib day.bin 后复权 |

**缺数规则**：某码/某日在 qlib_1min 无 bar → 该引擎该次 run 的 coverage / `data_gaps.csv` 记 `DATA_GAP`，**不**发明价格；若整窗无法加载 → 对应 NAV 格留空。

**可选收缩**（4090 超时）：同一 fee/clock 基线，把窗缩为 `20260901`–`20260909`（7 日）并在 manifest 注明 `window_contracted=true`；仍须大于 batch2 的 3 日。

---

## 3. 费用基线钉死

| 引擎 | 费用 | 滑点 | 说明 |
|---|---|---|---|
| Book | `DEFAULT_SCHEDULE` = `BILATERAL_10BP`（每边 10bp，min=0） | **0**（无 CLI slip；本批不叠） | `backtest/research/ashare_fees.py` |
| v7 | 同上 `DEFAULT_SCHEDULE` | **0** | `csv_minute_backtest_v7` 默认 `fee=DEFAULT_SCHEDULE` |
| Mode B | `modea.COMMISSION` 双边 10bp 线性 | **0** | 与 batch3 研究叠层一致；不改生产 Mode B 合同 |

**禁止**在本批引入 `REPLACE_COMMISSION_3BP_…` 或 QLIB_PORTANA 作为 NAV 主表费用（那些属 batch1/2 局部/替换情景）。

---

## 4. 单轴矩阵（clock XOR slip；永不同格）

| cell_id | clock | slip | Book NAV/DD/rank | v7 NAV/DD | Mode B NAV/DD/rank |
|---|---|---|---|---|---|
| `baseline_default_clock_fee` | 生产默认 | 0 / DEFAULT_SCHEDULE | **4090 可填** | **4090 可填** | **4090 可填** |
| `clock_next_open_fullstrat` | next-open 研究交换 | 0 | **DATA_GAP** | **DATA_GAP** | **DATA_GAP** |
| `slip_5bp_fullstrat` | 生产默认 | 5bp/边 | **DATA_GAP** | **DATA_GAP** | **DATA_GAP** |
| `slip_10bp_fullstrat` | 生产默认 | 10bp/边 | **DATA_GAP** | **DATA_GAP** | **DATA_GAP** |
| `slip_20bp_fullstrat` | 生产默认 | 20bp/边 | **DATA_GAP** | **DATA_GAP** | **DATA_GAP** |

同一 `cell_id` 内不得同时改 clock 与 slip。局部事件 Δbp **不得**写入上表数值列。

---

## 5. Book / v7 / Mode B 分列报告规则

1. **分文件、分表**：`book_nav.csv` / `v7_nav.csv` / `modeb_nav.csv`（及各自 rank）；禁止合成「三引擎总排名」或「谁更优」表。
2. **引擎内排名**：Book 仅在 Book 书之间；Mode B 仅在 Mode B 网格标签之间；v7 无跨书对比。
3. **口径声明**：每行带 `engine`、`cell_id`、`fee_schedule`、`clock`、`access`、`window`、`daily_entry_source`（Mode B）。
4. **oracle**（若 Mode B 报告含）：继续标 `EX_POST_UPPER_BOUND_NOT_EXECUTABLE`，不入可执行 NAV/rank。

---

## 6. 既有表面（不重造）

| 用途 | 入口 |
|---|---|
| Book 全策略 | `backtest/research/csv_minute_backtest.py --strategy versionN --minute-source qlib_1min --qlib-1min-root …` |
| v7 全策略 | `backtest/research/csv_minute_backtest_v7.py --qlib-1min-root …` |
| Mode B 网格 | `scripts/research/run_unified_exit_modeb.py`（湖默认）**或** batch4 harness 库路径注入 1min 聚合入场 |
| 局部事件（勿混入 NAV） | `scripts/research/run_minute_sensitivity_b.py` + batch1/2/3 导出 |
| 1min 读 + 日收聚合 | `backtest/research/qlib_bin_1min.py`（`load_qlib_bin_1min_bars` / `daily_closes_from_minutes`） |

---

## 7. 4090 命令配方（路径占位）

```powershell
$env:OSKH_SOURCE_PARQUET_ROOT='E:\stock_data'
$env:QLIB_1MIN_ROOT='C:\Users\wangc\.qlib\qlib_data\my_data_1min'
cd D:\PycharmProjects\MyQuant-backtrader
git fetch origin
git checkout research/minute-sensitivity-b-batch4-fullstrat-2026-09-20
git pull origin research/minute-sensitivity-b-batch4-fullstrat-2026-09-20

# 薄封装：解析已有 runner 产物 → batch4_fullstrat CSV/JSON（勿覆盖已填目录则换 stamp）
D:\anaconda3\envs\vanna312\python.exe scripts\research\run_minute_sensitivity_b_batch4_fullstrat.py `
  --execute `
  --start 20260825 --end 20260909 `
  --qlib-1min-root C:\Users\wangc\.qlib\qlib_data\my_data_1min `
  --pool-dir stock_pool `
  --output-dir backtest\research\exports\minute_sensitivity_b_20260920\batch4_fullstrat

# 或逐步手工 Book 一例（version1）：
D:\anaconda3\envs\vanna312\python.exe backtest\research\csv_minute_backtest.py `
  --strategy version1 --start 20260825 --end 20260909 `
  --minute-source qlib_1min `
  --qlib-1min-root C:\Users\wangc\.qlib\qlib_data\my_data_1min `
  --pool-dir stock_pool `
  --out-dir backtest_output\batch4_book_v1_20260825_20260909

# v7：
D:\anaconda3\envs\vanna312\python.exe backtest\research\csv_minute_backtest_v7.py `
  --start 20260825 --end 20260909 `
  --pool-dir stock_pool `
  --minute-source qlib_1min `
  --qlib-1min-root C:\Users\wangc\.qlib\qlib_data\my_data_1min `
  --output-dir backtest_output\batch4_v7_20260825_20260909
```

VM 无湖：`--dry-run` / `--emit-stubs` / `--help` 即可；不要求本地 qlib。

---

## 8. 产物清单

| 路径 | 说明 |
|---|---|
| 本设计 | `docs/backtest/reviews/design-minute-sensitivity-b-batch4-fullstrat-2026-09-20.md` |
| 结果桩 | `docs/backtest/reviews/results-minute-sensitivity-b-batch4-fullstrat-2026-09-20.md` |
| harness | `scripts/research/run_minute_sensitivity_b_batch4_fullstrat.py` |
| 导出 | `backtest/research/exports/minute_sensitivity_b_20260920/batch4_fullstrat/`（matrix / stubs / manifest） |

生产 Python **零行为变更**；仅 docs + research harness + 导出桩。

---

## 9. research-only fullstrat clock/slip hooks

### 已授权边界与 API 合同

- 新 helper：`backtest/research/fullstrat_research_hooks.py`；batch4 harness 的 `run_book` / `run_v7` / `run_modeb_library` 显式传 `clock_mode="production_default"`、`slip_bp_per_side=0`。不增加生产 CLI 开关，不使用隐式环境开关或全局默认替换。
- `clock_mode ∈ {production_default, next_tradable_open_research}`；`slip_bp_per_side ∈ {0,5,10,20}`。非默认 clock 与非零 slip 同时出现必须拒绝，运行前校验整个矩阵。
- harness 可提供 `--cells <comma-separated cell_id>` 选择固定矩阵子集；每个 cell 的 kwargs 来自矩阵，不允许任意组合。既有 Book/v7 CLI 默认及 ModeB 默认库调用保留原路径；`production_default + 0` 的 trades/equity 须逐字节等价。
- clock 研究交换复用 `next_tradable_open` 的可得时刻、`decision_at + 1ms`、连续竞价、涨跌停、现金与实际买日 T+1 门。**替换全部买卖成交，严格同日到期；未成交卖单到期清除，次交易日由策略重新评估。**
- slip：`s = slip_bp_per_side / 10000`，买价 `buy * (1+s)`、卖价 `sell * (1-s)`；按受冲击名义金额重算每边费用。真实成交、现金、持仓及逐日估值重放后生成组合 NAV；未卖持仓的 market mark 不伪装成受冲击卖出。不把 local-event Δbp 贴入 NAV。
- 不修改 `ashare_fill_clock` 的默认语义或 `DEFAULT_SCHEDULE` 常量；Book/v7 仍以 `BILATERAL_10BP` 为费用基线，ModeB 仍用原双边 10bp 合同。优先隔离到新研究 helper；不编辑 #151/#152 的 `strategy11*`、`strategy12*`、`csv_ledger.py` 买卖实现。
- 各 cell 使用独立 artifact 目录及参数来源记录，避免基线缓存被当作实验结果。Book / v7 / ModeB 分文件，排名仅在同引擎同 cell 内；ModeB oracle 不进入可执行 NAV/rank。

| cell_id | clock_mode | slip_bp_per_side | hook 落地后的 Book / v7 / ModeB 能力状态 |
|---|---|---:|---|
| `baseline_default_clock_fee` | `production_default` | 0 | `FILLABLE`（基线路径不变） |
| `clock_next_open_fullstrat` | `next_tradable_open_research` | 0 | `FILLABLE`（H2 + Q2 pins 通过） |
| `slip_5bp_fullstrat` | `production_default` | 5 | `FILLABLE`（Q2 pins 通过） |
| `slip_10bp_fullstrat` | `production_default` | 10 | `FILLABLE`（Q2 pins 通过） |
| `slip_20bp_fullstrat` | `production_default` | 20 | `FILLABLE`（Q2 pins 通过） |

`FILLABLE` 仅代表研究 runner 有能力运行，不等于 `FILLED`。所有新增数值仍留空；slice D 为合并后 4090 执行，超出本 PR。实际缺行情、缺名单或运行失败仍保留带证据的 `DATA_GAP`。

### 完整人裁（绑定）：H2 + 卖单到期次日策略重评

代码证据（`32b78b1`）：

1. `scripts/research/run_minute_sensitivity_b.py::LakeBar` 使用 START 标签；`next_open` 要求 `bar.start >= decision_at + 1ms`，只接收上午 `[09:30,11:30)`、下午 `[13:00,14:57)`。`lake_event` / `MODEB_NEXT_OPEN_RULE` 的真实湖探针只给当日候选，订单当日到期；batch1 合成隔夜 fixture 另有显式跨日 session，不是 batch2/3 的湖合同。
2. `csv_minute_backtest.py::simulate` 的 pool 买入取 `BUY_HM=14:55` close；v7 `simulate_v7` 在 `hm==895` 用 close 开 trial。若该报价为 START 14:55，则 close 于 14:56 可得、14:56:00.001 提交。14:56 open 早于提交，14:57 及之后被连续竞价门拒绝。Book 精确 14:55 pool 买入与 v7 trial 在严格同日规则下均无候选；Book 更早 fallback 报价须另按其可得时刻处理，不能以此证明正常入场可成交。
3. ModeB `assemble_instances` 用同一 none 1min 聚合的日收作为入场价；batch3 只交换 **退出**，没有定义把日收入场改到哪个后续 session。把 clock 扩到入场且保持同日到期，将没有入场候选。
4. v7 `_buy` 成功后，调用方立即推进 `position.stage`；Book 当日卖出扫描先于 chase/pool 买入。仅替换未来成交价或 fee 对象不能实现延迟到下一 session 的资金、lot、stage、T+1 和日终 NAV。ModeB 局部 `UNFILLED` 也没有说明全策略剩余窗口内如何恢复退出评估。

data-free 复核：提取现有 `stamp` / `Bar` / `LakeBar` / `next_open` AST 原定义执行（不改源文件、不读湖）；Book/v7 14:56 决策，候选 14:56–15:00，实际返回 `UNFILLED`，拒绝序列为 `before_submit`、随后四个 `outside_continuous_session`。ModeB 日收后无候选返回 `UNFILLED/no_candidate`。

**FULL HUMAN CUT（2026-09-21，绑定，取代此前“sell pending”部分裁定）：**

1. 替换 **全部** fill 为 research `next_tradable_open`，覆盖全组合全部买卖路径；不局限于原局部探针。
2. 买单与卖单都 **严格同日到期**；不把任何未成交订单带入下一 session。
3. 接受 `UNFILLED`、未开仓乃至全现金 NAV；**不静默保留 baseline 入场**。START 14:55 close 入场无同日 eligible open 时必须未成交。
4. **未成交卖单到期清除**；保留实际持仓，**下一交易日正常执行策略评估，重新决定是否卖出**；不保留 exit intent 等待未来成交。下一日不再满足卖出条件时继续持仓，若重新触发则创建新的当日订单。

时钟仍复用 START 可得时间、`decision_at + 1ms`、连续竞价、限价、现金和实际买日 T+1 门。只有实际成交才改变现金、份额、lot 与阶段；不能提前记账未来价格。信号未成交不等于数据缺口，持仓继续按原市场 mark 估值；全现金结果合法。

Slice B pins：晚 14:55 START 入场 UNFILLED（无 baseline 回退）；买卖同日到期；卖单过期清除且次日正常策略重评（不 sticky）；clock XOR slip；5/10/20bp 每边冲击及 post-impact fees；默认参数 trades/equity 等价；矩阵仅能力 `FILLABLE`，新增数字保持空白，等待合并后 4090。

先提交本完整裁定文档，再实施代码。发现**新的**语义分叉仍须 PR comment + stop；本裁定已解决的晚入场 / 同日到期 / 卖单次日重评不再作为停点。`production_C=frozen`，不动 #151/#152 contested files，不 merge。

### Q2 成交价重定量（2026-09-21 最新绑定人裁）

**Q2 覆盖 `40afca4` / `dde7a6f` 的 Q1 固定股数及停点叙述。** 信号价只计算暂定股数；到 next-open / slip 实际成交价，按本次订单预算重新执行引擎整手 sizer（类似 `execute_buy` → `_buy_size`），再检查当时现金和受冲击名义金额费用。允许缩股后成交；不把信号股数冻结后以 `cash_reject_terminal` 拒单作为适配器合同。原 batch1–3 局部固定股数实验保留历史口径，不控制本次 fullstrat。

Q2 pin：预算 10,000、现金 10,050、信号价 10 → 暂定 1,000 股；next-open 10.1 → 重定量 900 股，费用 9.09，支出 9,099.09，现金 950.91。固定 1,000 股会因支出 10,110.10 拒单，是必须对照排除的 Q1 反例。slip 5/10/20bp 同样按实际成交价重定量。重定量后仍无足够现金可未成交；不隐式透支或改预算。

H2 全部成交交换、严格同日到期、UNFILLED / 全现金合法、卖单到期清除并次日策略重评继续绑定。clock 轴按日内事件排序，现金、持仓与阶段只在实际 eligible open 更新，未来卖出不得资助更早买单。slip 轴保留引擎默认决策/处理顺序，仅重算成交价、整手股数和含费账本。新语义分叉仍 PR comment + stop；Q2 已有明确人裁，无需重问。

### Slice B 实现与隔离

- `fullstrat_research_hooks.py`：显式配置、当日事件队列、START 可得时刻与 +1ms、连续竞价/限价/T+1；Q2 由回调在实际成交价调用引擎 sizer。
- `fullstrat_research_book.py` / `fullstrat_research_v7.py`：单独研究重放循环，复用原策略 hooks/scanner/账本 primitives；Book pool/chase/step 与全部卖出、v7 trial/add/stop/timer 均覆盖。未成交卖单清除，实际持仓和已观测峰值留下。
- `fullstrat_research_modeb.py`：日收入场同日无更晚 open 即未开仓，合法全现金；slip 在受冲击入场成本上重新评估退出，按受冲击卖价重算费用。入场日及后续缺分钟时，持仓按无冲击市场 close 估值并应用原 E-R6，不能把受冲击 fill price 当作 market mark。退出到期后以保留的行情历史重新评估后续 session，不续旧意图。oracle 不进入研究可执行矩阵。
- `fullstrat_research_runners.py`：显式加载边界（沿用原 resolver / lake / qlib 读路径）；没有 module-global 替换/monkeypatch，没有生产入口反向依赖研究代码。受 #152 争用的 `csv_minute_backtest.py` / `csv_ledger.py` / `csv_simulate_loop.py` 均未改。
- batch4 harness `--cells` 从固定矩阵选轴；默认仅 baseline。每个 cell 独立 `runner_artifacts/<cell_id>/`，记录 Q2/H2、参数与 git tip；实验目录已有产物即拒绝复用，`--force` 也不能将旧基线当实验。各引擎、各 cell 分别排名。
- `production_default + 0` 直接调用原引擎；Book/v7 trades/equity bytes 及 ModeB ranking 对照通过。实验容量开关拒绝混入，capacity 仍为另轴。

Data-free pins：`tests/test_fullstrat_research_hooks.py`。矩阵 `FILLABLE` 是实现能力；历史导出不重写，新增数值继续空白。


研究循环额外对照：绕过默认委托，直接以零冲击调用 Book/v7 实验循环，经济 trades/equity 对齐原引擎；ModeB 实验零冲击全 ranking 对齐原引擎。两名单实例 pin 验证 ModeB 买日不卖（原 `_instance_path` 从 `buy_i+1` 开始）、T+1 卖出现金用于次日日收新入场；拒绝凭空加入 T+0 出场。每日 pool 预算保持一次分配，Q2 只在成交价重算整手股数，不重新分配该预算。
