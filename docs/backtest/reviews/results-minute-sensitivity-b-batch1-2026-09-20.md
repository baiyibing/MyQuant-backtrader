# 分钟敏感对照 B · 第一批结果（2026-09-20）

**Human GO B 首批已完成，范围是合成局部价格敏感性，非完整策略重放。** BASE `f2fe15124ffbc62d3c0526fc90fed78d014b1bb1`（Merge #136）。未配置生产分钟湖，Book/v7/Mode B 的全策略净收益、最大回撤、策略排名均为 **DATA_GAP**，数值空白。下述数值仅属于人工构造的独立事件，不推断实盘收益偏差、影响方向或引擎优劣。

依据：[SSOT §C](eval-minute-pitfall-vs-asbuilt-2026-09-20.md#c-收束与人裁选项)；[本轮计划](plan-minute-sensitivity-b-2026-09-20.md)；[复跑 README](../../../backtest/research/exports/minute_sensitivity_b_20260920/README.md)；[manifest](../../../backtest/research/exports/minute_sensitivity_b_20260920/batch1/manifest.json)。本轮仅新增研究脚本、验证工具、文档和独立 CSV/JSON；不修改生产成交/扫描/费用/仓位/估值/默认参数/CLI，不 monkeypatch，不覆盖基线，不开 PR、不 push。

## 1. 样本与可得性

26 个 Book/v7 时钟事件，31 条候选记录；另外 2 个 Mode B Q39 独立实例、7 个调度/缺报价探针、16 行 close 容量开关、8 行共享容量、4 行 gap-stop、4 行最低费粒度、144 行成本情景。输入由 harness 显式生成，**没有把 handoff fixture 当生产行情样本**。

| 证据项 | 本轮核实 | 结论 |
|---|---|---|
| 生产 `period=1m` 湖 | `OSKH_SOURCE_PARQUET_ROOT`、`OSKH_AUTHORITY_HINT_ROOT`、`OSKH_PERIOD_1M_ROOT` 均未设；resolver 抛 `UnconfiguredDataRootError`，原文在 `data_gaps.csv` | DATA_GAP；未猜路径或静默返回空行情 |
| 名单发布时间 | 抽样 `stock_pool/20260909.csv`，首行只有代码/名称两列；不拿文件名日期或 mtime 充当盘中可得时刻 | DATA_GAP；不是完整上游审计 |
| 因子可得性 | 无经核验的 generated_at/available_at 生成链 | DATA_GAP |
| 真实分钟起止标签 | 仅源码的时钟表示说明，不足以核实实际湖 bar 区间及延迟 | DATA_GAP；本批标签为人工声明 |
| 真实 volume 单位/可得时刻 | 只有人工 `raw_shares_incremental` / `available_at` | DATA_GAP；不推断生产容量 |
| 完整现金、日线估值、权益及后续信号 | 未做全样本闭环重放 | DATA_GAP；不输出策略 NAV/回撤/排名 |

明细：[缺口 CSV](../../../backtest/research/exports/minute_sensitivity_b_20260920/batch1/data_gaps.csv)。未来即使配置了根，本脚本也不会自动变成完整策略回放器。

## 2. Clock：固定项与匹配结果

Book 基线直接调用 `_chase_quotes`、`chase_decision`、`run_chase_due_day` 和原账本。v7 基线使用显式独立阶段快照、`ladder_decision` 和原 `_buy`；四档价格/股数另与公开 `simulate_v7` 的连续加仓序列核对一致。Book 持仓/指数/买门预设通过；v7 保持 add-window、止损前置存活及买侧价格门。它们不是 1–10 策略书全量回测。

两组均固定双边 10bp/min=0、slippage=0、cap off；next-open 冻结基线订单数量，检查当前事件现金。Book 额度 1 万元，例中成交 900 股；v7 沿用每次 20%×100 万元目标额度，19200/18500/17800/17200 股。v7 已有 lot 盈亏不混入加仓局部收益。各事件没有现金竞争或再投资。

| 独立基线 | 事件数 | 基线成交 | next-open 成交/共同成交 | 状态匹配率 | 共同成交/基线成交 | 共同成交中的同价率 |
|---|---:|---:|---:|---:|---:|---:|
| Book chase | 12 | 10 | 7 | 9/12 = 75.00% | 7/10 = 70.00% | 1/7 = 14.29% |
| v7 add | 14 | 12 | 10 | 12/14 = 85.71% | 10/12 = 83.33% | 1/10 = 10.00% |
| Mode B Q39 | 2 个基线实例 | 2 个退出 | clock 本批未做 | 不适用 | 不适用 | 不适用 |

状态匹配包括“两边都不成交”的控制事件，因此不能当成成交匹配率。表中比例是人为边界覆盖比例，**不是市场匹配率估计**。没有合并三引擎分母。

### 时间边界

本批统一声明 Asia/Shanghai 墙钟；合成 `hm` 为 bar end，close 在 end 可得，订单提交在 decision+1ms。09:45 close 后，标签 09:46 的 bar 实际 start=09:45，早于提交；该候选被记为 `before_submit`。最早通过严格时序的是 start=09:46、end=09:47 的 open。此 1ms 是未校准的研究假设，既不是生产行为，也不证明现实可按该 open 成交。

- Book fallback：09:43 报价年龄 120 秒，计划决策和基线成交代理时刻仍为 09:45；不回填更早决策。
- 缺 bar：只遍历实有候选；无候选不补价。Book 缺全段报价的原调度探针保留 pending，到下个显式 session 报价成功仍写 `chase:T+1`。
- 午休：11:30 后候选 open=13:00；该行属于调度器机制探针，未混进 09:45 chase/v7 下午加仓样本。
- 隔夜：允许冻结订单延续到 fixture 中下一 session，按该日给定昨收重新算涨跌停；不等同生产新增跨日 pending。v7 可能越过信号窗口，未重跑届时 stop/stage/index，故只能作局部对照。
- 限价：Book 买仅测涨停；v7 买另挡跌停；卖出挡跌停。按时间找首个通过者，不挑收益最好的后续价，也不模拟盘口排队。
- T+1：独立卖出探针显示当日 lot 锁定、下一 session 可卖。局部固定卖出终点为 2026-09-21，晚于所有合成新买入日。
- 现金不足终止该冻结订单，不等更低价重试，不改股数。连续交易候选 start≥14:57 被排除，不模拟收盘集合竞价。
- clock 轴 cap 关闭。独立 cap-on open 探针拒绝本桶未来完成量，未改用前根量或日成交量。

证据：[候选逐条 CSV](../../../backtest/research/exports/minute_sensitivity_b_20260920/batch1/clock_candidates.csv)、[边界 CSV](../../../backtest/research/exports/minute_sensitivity_b_20260920/batch1/clock_boundaries.csv)、[完整输入 frame](../../../backtest/research/exports/minute_sensitivity_b_20260920/batch1/minute_frames.csv)。

### 逐笔价差与局部净收益差

`Δ价bp=(next_px/base_px−1)×10000`；`Δ净收益bp` 是固定终点下两个**买入含费成本收益率**之差，不是股价 bp 或组合收益。费用在新价格下重算。下表四舍五入，CSV 保留原数值；“—”为空值，未成交不按零收益计算。

| Book 事件 | 基线价 | next 价 | Δ价 bp | Δ局部净收益 bp | next 结果 |
|---|---:|---:|---:|---:|---|
| up | 10.20 | 10.60 | +392.16 | -395.07 | 首个合格 open |
| down | 10.20 | 9.90 | -294.12 | +311.32 | 首个合格 open |
| unchanged_price | 10.20 | 10.20 | 0.00 | 0.00 | 同价控制 |
| fallback_0943 | 10.20 | 10.30 | +98.04 | -101.64 | 陈旧报价决策后成交 |
| missing_bar | 10.20 | 10.40 | +196.08 | -201.33 | 跳过缺根 |
| limit_release | 10.20 | 10.50 | +294.12 | -299.12 | 先挡 11.00 涨停 |
| limit_exhausted | 10.20 | — | — | — | 所有候选涨停 |
| overnight | 10.20 | 10.40 | +196.08 | -201.33 | 下一 session |
| cash_reject | 10.20 | — | — | — | 现金不足，终止 |
| no_next_bar | 10.20 | — | — | — | 无候选 |
| abandon | — | — | — | — | 两边均无订单 |
| decision_limit | — | — | — | — | 基线决策涨停，均无订单 |

| v7 事件 | 基线价 | next 价 | Δ价 bp | Δ局部净收益 bp | next 结果 |
|---|---:|---:|---:|---:|---|
| trial_add | 10.40 | 10.60 | +192.31 | -197.36 | 首档加仓 |
| four_add | 10.80 | 11.00 | +185.19 | -189.86 | 第二档，独立昨收 10.80 |
| six_add | 11.20 | 11.40 | +178.57 | -182.90 | 第三档，独立昨收 11.20 |
| eight_add | 11.60 | 11.80 | +172.41 | -176.44 | 第四档，独立昨收 11.60 |
| down | 10.40 | 10.10 | -288.46 | +307.84 | 后续 open 更低 |
| unchanged_price | 10.40 | 10.40 | 0.00 | 0.00 | 同价控制 |
| missing_bar | 10.40 | 10.50 | +96.15 | -97.79 | 跳过缺根 |
| overnight | 10.40 | 10.60 | +192.31 | -193.73 | 下一 session |
| limit_release | 10.40 | 10.50 | +96.15 | -97.79 | 先挡涨停 |
| limit_down_release | 10.40 | 10.30 | -96.15 | +99.69 | 先挡跌停 |
| limit_exhausted | 10.40 | — | — | — | 候选涨停 |
| no_next_bar | 10.40 | — | — | — | 无候选 |
| no_signal | — | — | — | — | 未达到阶梯条件 |
| outside_add_window | — | — | — | — | 14:44 不在加仓窗 |

完整的基线/next 金额净损益、收益率、股数、事件剩余现金和 reason 在 [clock_trades.csv](../../../backtest/research/exports/minute_sensitivity_b_20260920/batch1/clock_trades.csv)。例如 Book up 的局部净收益率 4.6924%→0.7417%，Book down 为 2.7355%→5.8487%；方向由构造的后续 open 决定，不能据此声称生产分钟收益必然虚高。

### 净收益、回撤与排名的可报告范围

| 对象 | 共同成交事件的局部收益差均值 | 局部事件名次变化 | 全策略净收益 | 最大回撤 | 策略排名变化 |
|---|---:|---|---|---|---|
| Book | -126.74bp（7 笔等权算术平均） | 7/7；up 3.5→7，down 7→1 | DATA_GAP | DATA_GAP | DATA_GAP |
| v7 | -72.83bp（10 笔等权算术平均） | 10/10；trial_add 1→4，down 5→1 | DATA_GAP | DATA_GAP | DATA_GAP |
| Mode B | clock 未运行 | clock 未运行 | DATA_GAP | DATA_GAP | DATA_GAP |

局部名次仅在同引擎、两组共同成交集合中排序；收益先保留 12 位小数再对并列取平均名次。某事件自身同价时，其名次仍可因其他事件移动而改变。未成交剔除带来选择偏差；上述均值不是组合收益。没有把稀疏 marks 计算成伪精确回撤。

## 3. Mode B 独立基线

调用 `evaluate_exit_modeb`，`StrategySpec(rule=2,n=10,x=5,y=5)`；每个实例入场为 none 日线 close=10.00、100000 股，日历 2026-09-17/18。fast/ref 结果相同。

| 合成实例 | 退出价 | reason | 独立实例净损益 | 独立实例净收益率 |
|---|---:|---|---:|---:|
| close_take_profit | 10.60 | take_profit | +57940.00 | +5.7882% |
| gap_stop | 9.40 | stop_loss | -61940.00 | -6.1878% |

这些数值仅复核 Q39 与双边 10bp 的实例算术，未并入 Book/v7 NAV。Mode B clock 延后为后续工作，生产无 volume-cap 接口。本批未计算 Q38 oracle；任何后续 oracle 只能标事后上界，**oracle ≠ 可执行收益**。原始数据：[modeb_baseline.csv](../../../backtest/research/exports/minute_sensitivity_b_20260920/batch1/modeb_baseline.csv)。

## 4. Fee / slippage：独立轴

24 个基线成交配对（Book 10、v7 12、Mode B 2）各跑 6 行，合计 144 行。基线交易钟、价格和股数固定，clock 的 next-open 价格不混入成本轴。即使 clock 替代组不成交，成本轴仍可使用该事件原基线配对，所以其样本集合大于 clock 共同成交集合。

滑点保持 `BILATERAL_10BP`，每边仅变 0/5/10/20bp，buy×(1+s)、sell×(1−s)，费用在受冲击的名义金额上重算。以下为各自配对等权的**局部净收益率差均值**，不是组合收益，也不是校准后的成本建议：

| 独立基线 | 每边 0bp | 每边 5bp | 每边 10bp | 每边 20bp | 本批局部名次变化 |
|---|---:|---:|---:|---:|---|
| Book | 0.00bp | -10.44bp | -20.88bp | -41.72bp | 各档 0/10 |
| v7 | 0.00bp | -10.33bp | -20.64bp | -41.24bp | 各档 0/12 |
| Mode B | 0.00bp | -9.98bp | -19.94bp | -39.84bp | 各档 0/2 |

固定比例滑点在本批线性费率配对中保持了名次，不构成真实策略排名稳健性结论。未重跑现金不足、数量、限价或后续策略，故成本叠层仍为局部算术；也不把冲击后价格当作已经通过真实流动性验收。

费用轴固定 slippage=0，比较双边 10bp/min=0 佣金代理与 **REPLACE_COMMISSION_3BP_MIN5_STAMP_SELL5BP**：用每次调用万三佣金、最低 5 元，外加卖出 5bp 印花假设**替换**原 10bp。该行不再扣双边代理，过户及其他项未覆盖；不导入 live 费用模块，不确认现实账户合同、当前税法或历史所有时期适用性。Mode B 的最低费仅在研究算术叠层出现，生产仍保持线性费用合同。

该替换情景相对代理的局部收益差均值：Book +4.54bp、v7 +9.30bp、Mode B +8.98bp；各自事件排名变化均为 0。数值受名义金额和最低费影响，不能用于比较引擎费用高低或选择新默认。

最低费粒度另用同价卖出两个 100 股 lot，每个 1000 元名义金额作原账本探针：

| 独立账本 | 卖调用次数 | 双边代理下卖佣金 | 替换情景卖佣金 | 独立印花假设 |
|---|---:|---:|---:|---:|
| Book `_sell` 两次 | 2 | 2.00 | 10.00 | 1.00 |
| v7 `_sell_lots` 合并 | 1 | 2.00 | 5.00 | 1.00 |

明细：[cost_sensitivity.csv](../../../backtest/research/exports/minute_sensitivity_b_20260920/batch1/cost_sensitivity.csv)、[fee_granularity.csv](../../../backtest/research/exports/minute_sensitivity_b_20260920/batch1/fee_granularity.csv)。

## 5. Capacity 与 gap-stop 分轴

close 容量轴使用原调用接口，研究 p=10%（非默认、未校准）；raw 增量股数由 fixture 声明，量在对应 `hm` 可得。足量桶不改变 Book 900/v7 19200 股；3500 股桶的 350 股预算经买入整百约束，二者均只买 300 股；缺量和 `available_at=hm+1` 均不成交。cap-off 只说明关闭了模型容量门，不证明真实无限流动性。

同桶买卖共享探针中，买入先消耗 300 股，旧 lot 卖出只能再用 50 股，总消耗 350；v7 当日新增 lot 不可卖。原始结果见 [capacity.csv](../../../backtest/research/exports/minute_sensitivity_b_20260920/batch1/capacity.csv) 与 [capacity_shared.csv](../../../backtest/research/exports/minute_sensitivity_b_20260920/batch1/capacity_shared.csv)。

gap-stop 使用预先存在的止损线 9.50、第一根 open=9.40、昨收=10.00；Book 原扫描返回 `stop_loss:gap_open`，v7 使用独立 four 阶段原 stop/lot 卖出函数。两者 1000 股旧 lot 在 cap-off 成交，卖出净额 9390.60；cap-on 时各拒绝 1 次，原因均为 `skip_volume_unavailable:bucket_not_completed`（bucket=571，at=570，available_at=571）。**不把保护性 gap-open 改成 chase 的 next-open。** 本 probe 的 T+1 条件先通过，拒绝归因是未完成量，而不是不可卖 lot。

明细：[gap_stop.csv](../../../backtest/research/exports/minute_sensitivity_b_20260920/batch1/gap_stop.csv)。真实参与率、排队、成交量单位或交易日分布仍是 DATA_GAP，不能由这 4 行推算生产拒绝率或收益影响。

## 6. 验证与后续边界

实际解释器 `/tmp/industry-align-venv/bin/python`：Python 3.12.13、pandas 3.0.6、numpy 2.5.3。

- 研究 `verify_harness.py`：**13 passed**。覆盖严格提交时序、未来 close 不影响 open 选择、fallback、首个合格价、现金不择价重试、逐日限价、T+1、午休、容量/gap、成本不重复计费、原 v7 公开加仓序列、Mode B 算术、拒绝覆盖及两次输出逐字节一致。
- 原相关测试：**253 passed**。包括分钟书/v7、strategy7、fees/fee_wiring、volume_cap、fill_clock、固定 import fence、Mode B exit/vector、presets 跨仓快照。仅 2 条既有 pandas `copy` 参数弃用 warning；未运行全仓测试或湖回测。
- 4 项 data-free gate：`verify_oskh_data_contract.py`、`verify_data_path_ssot.py`、`verify_no_hardcoded_machine_paths.py`、`verify_tr_bridge_import_ssot.py` 均通过。
- 正式运行检查 11 个直接依赖源码与 BASE 相同、before/after SHA256 相同；生产 diff 为空。产物 UTF-8 无 BOM、NUL=0，内部文件引用及 CSV/JSON hashes 已检查；`git diff --check` 通过。

下一批若要回答策略净收益/回撤/排名，需要先补真实名单/因子可得性、bar 时间语义、完整分钟/日线/权益及原始量，再用隔离研究执行状态完成现金与后续订单闭环；Mode B clock 应在自己的实例口径内另外做。生产成交时钟、费率/滑点接口、容量默认的任何改变仍属于 C，需另开计划和人裁。本轮 B 没有给生产变更授权。
