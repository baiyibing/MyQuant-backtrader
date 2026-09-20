# 分钟敏感对照 B · 第二批结果（2026-09-20）

**Human GO B 第二批已完成：真实分钟序列只读局部事件敏感性，非完整策略重放。** BASE `f2fe15124ffbc62d3c0526fc90fed78d014b1bb1`（Merge #136）。跑批 git HEAD `38f19d5ad360ab3c5a79321bea8a93622f0e8061`（CRLF fence + lookback + validate lookback + START add-window）。`lake_read_status=READ_OK`，`access=qlib_bin_1min`。全策略净收益、最大回撤、策略排名均为 **DATA_GAP**，数值空白。下述数值仅属于注入状态的独立事件，不推断实盘收益偏差、影响方向或引擎优劣。

依据：[SSOT §C](eval-minute-pitfall-vs-asbuilt-2026-09-20.md#c-收束与人裁选项)；[计划](plan-minute-sensitivity-b-2026-09-20.md)；[第一批](results-minute-sensitivity-b-batch1-2026-09-20.md)；[复跑 README](../../../backtest/research/exports/minute_sensitivity_b_20260920/README.md)；[manifest](../../../backtest/research/exports/minute_sensitivity_b_20260920/batch2/manifest.json)。本轮仅研究脚本/文档与独立 CSV/JSON；生产 fill/scan/fee/defaults/CLI **未改**。

## 0. 数据血缘（同一分钟序列，两层访问）

| 字段 | 取值 |
|---|---|
| `source` / lineage | `parquet_lineage`（none 复权 1m 湖为真相源；qlib bin 为其物化，**不是**对立宇宙） |
| `access`（本批实际） | `qlib_bin_1min` → `C:\Users\wangc\.qlib\qlib_data\my_data_1min` |
| `access`（回退偏好） | `oskh_parquet_1m` → `OSKH_SOURCE_PARQUET_ROOT=E:\stock_data`（同数据集） |
| `lake_read_status` | `READ_OK` |
| 日频 bin | `my_data` / `cn_data` 仅 day.bin — **不用于分钟轴** |
| F: 湖 | **不存在**；禁止声称 |

## 1. Bar 标签语义（相对 batch1 的诚实差异）

| 批次 | 标签 | 含义 |
|---|---|---|
| batch1 合成 | `hm` = bar **END** | 人工构造；close 在 end 可得 |
| batch2 真实 | index / `hm` = bar **START** 墙钟 | `bar_label_semantics=lake_index_is_bar_start_wallclock`；4090 核实 hm585=09:45 START |

batch2：`close_available = bar.start + 1min`，`submit = close_available + 1ms`；候选 open 要求 `bar.start >= submit`。因此 09:45 START bar 的 close 在 09:46 可得后，**09:46 START open 会被 `before_submit` 拒绝**，最早下一 open 为 09:47。候选 CSV 与此一致（例：Book `000021.SZ_20260916_585` 首候选 09:46=`before_submit`，09:47=`FILLED`）。**禁止**把 batch1 END 语义套到本批。

## 2. 样本与可得性

| 项 | 本批核实 | 结论 |
|---|---|---|
| 符号 | `000021.SZ,002025.SZ,600000.SH,600007.SH,600276.SH`（`--symbols`；多标的以便 Book/v7 路径触发） | 已跑 |
| 窗口 | `20260916`–`20260918`（YYYYMMDD） | 已跑 |
| `600000.SH` | Book 三日 chase 均为 `NO_FILL`/`abandon`（相对 prior-open 注入诚实无单）；v7 该标的 36 事件亦全 `NO_FILL` | 诚实缺口，非静默填价 |
| 生产分钟湖可读 | qlib_bin_1min READ_OK；与 E:\stock_data parquet 同血缘 | 局部事件可用 |
| 名单发布时间 | 仓内 `stock_pool/*.csv` 仅代码/名称两列抽样 | DATA_GAP |
| 因子可得性 | 无经核验 generated_at/available_at 链 | DATA_GAP |
| 真实 volume 单位/可得时刻 | reader 丢量或无 attested 增量股数 | DATA_GAP（capacity 轴全行 `volume_status=DATA_GAP`） |
| 官方涨跌停/除权 | 仅用前一自然日 15:00 分钟收盘代理 | DATA_GAP |
| 完整现金路径/日线估值/权益 | 独立注入事件，无策略闭环 | DATA_GAP；不输出 NAV/DD/rank |
| Mode B | `NOT_RUN` | DATA_GAP |

明细：[缺口 CSV](../../../backtest/research/exports/minute_sensitivity_b_20260920/batch2/data_gaps.csv)（含 16 条事件级 `missing_next_calendar_day_1455_exit_mark`）。

## 3. Clock 汇总（来自 `clock_summary.csv`）

Book/v7 均为注入状态局部事件：Book pending 1 万元现金预算；v7 四档独立阶段、100 股 lot、事件现金 100 万元；gates 预通过（除本地规则）。费用双边 10bp/min=0、slippage=0、cap off。数量冻结自基线账本。`local_rank=NOT_RUN`（manifest）。**不是** 1–10 策略书全量回测。

| 独立基线 | 请求/评估事件 | 基线成交 | next 成交 | 共同成交 | 状态匹配率 | 共同成交同价率 | mean Δ价 bp | clock 状态 |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| Book chase | 15 / 15 | 8 | 8 | 8 | 1.0 | 0.125（1/8） | ≈8.998 | LOCAL_EVENTS_COMPLETE |
| v7 add | 180 / 180 | 35 | 35 | 35 | 1.0 | ≈0.0857（3/35） | ≈−1.055 | LOCAL_EVENTS_COMPLETE |
| Mode B | — | — | — | — | — | — | — | NOT_RUN |

状态匹配含“两边都不成交”；同价率仅在共同成交集合。`Δ价bp=(next_px/base_px−1)×10000`。Book 基线成交多为 same-close 代理时刻 09:46，next-open 为 09:47（START 语义）；v7 加仓成交集中在信号日后午盘 open。完整逐笔见 [clock_trades.csv](../../../backtest/research/exports/minute_sensitivity_b_20260920/batch2/clock_trades.csv)、[clock_candidates.csv](../../../backtest/research/exports/minute_sensitivity_b_20260920/batch2/clock_candidates.csv)。

### 局部净收益差与全策略

共同成交中，退出标记可得者为 Book 7 / v7 20（其余 `local_pair_status=DATA_GAP`，缺下一交易日 14:55 exit mark）。有配对者的等权 `local_return_delta_bp` 均值：Book ≈−8.78bp（n=7），v7 ≈−1.97bp（n=20）。局部名次未跑（全空白）。**禁止**把局部均值当成组合收益。

| 对象 | 共同成交局部收益差均值 | 局部事件名次 | 全策略净收益 | 最大回撤 | 策略排名 |
|---|---|---|---|---|---|
| Book | ≈−8.78bp（7 笔有 exit mark；另 1 笔 DATA_GAP） | NOT_RUN | DATA_GAP | DATA_GAP | DATA_GAP |
| v7 | ≈−1.97bp（20 笔有 exit mark；另 15 笔 DATA_GAP） | NOT_RUN | DATA_GAP | DATA_GAP | DATA_GAP |
| Mode B | NOT_RUN | NOT_RUN | DATA_GAP | DATA_GAP | DATA_GAP |

## 4. Mode B

| 项 | 状态 |
|---|---|
| clock / 日线入场 / 实例日历 | `NOT_RUN`（本批发运时；clock 现见 [batch3 Mode B](results-minute-sensitivity-b-batch3-modeb-2026-09-20.md)） |
| `modeb_baseline.csv` | 单行占位：status=`NOT_RUN`，NAV/DD/rank 空白 |
| production_replay | DATA_GAP |

## 5. Fee / slippage（独立轴，`cost_sensitivity.csv`）

仅对有 `PRICE_PAIR_ONLY_NOT_EXECUTED_EXIT` 的基线配对做成本叠层（Book 7、v7 20）；NO_FILL / DATA_GAP 行保留状态、不填零收益。clock 的 next-open 价不混入本轴。以下为各档等权**局部净收益率差均值**（相对同事件 slip=0 / 双边代理）：

| 独立基线 | 每边 0bp | 每边 5bp | 每边 10bp | 每边 20bp | n（有配对） |
|---|---:|---:|---:|---:|---:|
| Book | 0.00bp | ≈−10.18bp | ≈−20.35bp | ≈−40.65bp | 7 |
| v7 | 0.00bp | ≈−10.14bp | ≈−20.27bp | ≈−40.50bp | 20 |
| Mode B | — | — | — | — | NOT_RUN |

费用轴 `REPLACE_COMMISSION_3BP_MIN5_STAMP_SELL5BP`（万三佣金、最低 5 元、卖出 5bp 印花**替换**双边 10bp 代理，不双重扣）相对代理的局部收益差均值：Book ≈+2.36bp（n=7），v7 ≈+9.13bp（n=20）。未验证现实账户合同或税法；不建议生产默认。

## 6. Capacity（独立轴，`capacity.csv`）

| 轴 | 核实 |
|---|---|
| volume 证据 | 全部 390 行 `volume_status=DATA_GAP`（reader 无 attested 增量股数/单位） |
| cap-off | Book 8 FILLED / 7 NO_FILL；v7 35 FILLED / 145 NO_FILL（与 clock 基线一致量级） |
| cap-on p=0.1 | 原可成交事件因 `skip_volume_unavailable:missing_or_untyped` 拒绝（43 行该 reason）；**不虚构量** |
| 生产参与率/排队 | DATA_GAP |

## 7. Manifest 关键字段（已核对）

`batch2/manifest.json`：`source=parquet_lineage`、`access=qlib_bin_1min`、`bar_label_semantics=lake_index_is_bar_start_wallclock`、`production_replay=DATA_GAP`、`base=f2fe15124ffbc62d3c0526fc90fed78d014b1bb1`、`git_head=38f19d5…`、`checked_sources_match_base=true`（before/after 哈希一致）、符号与窗口同上、Python 3.12.13 / pandas 2.3.3 / numpy 2.3.5（4090）。

产物目录：[batch2/](../../../backtest/research/exports/minute_sensitivity_b_20260920/batch2/)（含 `minute_frames.csv`）。

## 8. 边界与后续

本批回答的是「真实 START 标签分钟序列上，注入事件 same-close vs next-open 的局部价差与成本/容量分轴」；**未**回答全策略 NAV/DD/rank。补齐后者仍需名单/因子发布时间、官方限价与除权、完整现金与后续订单闭环，以及 Mode B 自有实例口径。生产成交时钟、费率/滑点接口、容量默认的任何改变仍属 C，需另开计划和人裁。
