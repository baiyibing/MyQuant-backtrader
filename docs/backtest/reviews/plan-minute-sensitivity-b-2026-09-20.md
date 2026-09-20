# 分钟敏感对照 B：实施计划（2026-09-20）

人裁：Human GO B，#136 合入后；BASE `f2fe15124ffbc62d3c0526fc90fed78d014b1bb1`。依据：[评估 SSOT §C](eval-minute-pitfall-vs-asbuilt-2026-09-20.md#c-收束与人裁选项)。本轮新增独立研究 harness 与产物，不重开 P1/P2/P3/P4 合同，不修改生产 fill、scan、fee、defaults、CLI、仓位或估值，不 monkeypatch，不覆盖基线，不 push 或开 PR。

## 1. 固定项与分列基线

| 对象 | 生产基线锚点 | 本轮实验单位 |
|---|---|---|
| Book chase | `_chase_quotes` → `chase_decision` → `run_chase_due_day` → `execute_buy`，09:45 close 共用决策/成交；缺根取 ≤09:45 最后 close | 单一待追买事件，调用现有函数；持仓/指数门预置通过，固定基线成交股数后改价 |
| v7 add | `in_add_window` + `ladder_decision` + `_buy`，独立阶段/lot 账本 | 单一加仓事件，显式注入已有阶段；分别覆盖四档加仓；不重放之后的阶段迁移 |
| Mode B | `evaluate_exit_modeb`，none 日线 close 入场、Q39 退出 | 独立实例基线；本批仅基线及成本，clock 延后；oracle 明确为事后上界，不计算可执行收益 |
| gap-stop | Book 逐根 open；v7 当日首根 open | 预设止损的独立容量可得性轴，保持 open 价格，不混入 chase/add 的 close 延后 |

固定合成 raw/none 价格，无除权，交易日历显式给出；费用 `BILATERAL_10BP`，每边 10bp、min=0；clock 轴 cap 关闭、slippage=0。基线股数来自原账本；改价组冻结该股数且检查事件现金，避免把重新 sizing 混进价格轴。v7 已有 lot 不并入局部加仓收益。各事件相互独立，无跨事件现金竞争、再投资、后续策略信号或日线估值重放，所有数值只能称**合成局部价格敏感性，非完整策略重放**。

## 2. Clock 轴与时间合同

合成输入显式记录 `bar_start` / `bar_end` / `hm`，Asia/Shanghai；`hm` 是右端完成时刻，不据此推断真实湖标签。close 在 end 可得；研究订单提交为 decision + 1ms（固定、未校准）。仅选择 start ≥ submit 的后续 open；因此 09:45 close 后，close 标签 09:46 的 bar 其 open=09:45，早于提交，被拒绝；最早下一候选是 start=09:46、end=09:47。逐候选保存拒绝原因。这是严格时序假设，不能把“下一行”直接当作下一可成交价。

- Book 即使 fallback 报价来自 09:43，决策仍不得早于计划的 09:45；单列报价年龄。09:45 缺全段报价保留原 pending 语义的基线探针。
- 午休：不造 11:30–13:00 bar；午间边界用通用调度器探针，**不是** Book 09:45/v7 下午信号样本。
- 隔夜：仅走显式合成 session；逐日使用给定 none 昨收重新求涨跌停，保留原订单直到 fixture 结束。这是研究订单存续假设，非生产改造。
- 缺 bar：跳过缺失区间，只用实有候选，记录时间跨度；耗尽则 `UNFILLED`，不补价、不把未成交收益记 0。缺行情不等于停牌。
- 涨跌停：复用 `session_limit_prices` 等价格门。Book 买只测涨停门；v7 买另测跌停门；卖测跌停。被限价门挡住可等下一候选，非排队/流动性保证。拒绝更晚收益选择。
- T+1：复用 `t1_sellable`，按实际买入日期判；独立 same-day/next-session 卖出探针；buy clock 本身不受卖出 T+1 禁令约束。
- 容量：clock 轴关闭，不能解读为真实无限流动性。cap-on 单列，绝不拿当前 open 对应 bar 的未来完成量成交，也不拿前根量代替本桶。
- 收盘竞价：next-open 研究候选只接受连续交易时间（start <14:57）；不声称模拟集合竞价。

## 3. 成本与容量轴（第一批）

1. 固定生产基线成交价格/数量/配对终点，双边 10bp 下仅变 slippage，每边 0/5/10/20bp；`buy*(1+s)`、`sell*(1-s)`。未校准压力档位，不推荐默认；费用按受冲击名义金额重算。
2. 费用独立轴固定 slippage=0：双边 10bp 佣金代理为基线；另列**替换**代理的万三佣金情景（每次调用最低 5 元）+ 卖出 5bp 印花假设。后者仅为声明的算术情景，不是 live 账单或税法/账户核验；过户等未覆盖，不叠加原 10bp。另设小额两 lot 卖出探针，说明 Book 两次调用与 v7 一次合并调用的最低费差异，Mode B 生产仍是线性费率。
3. Book/v7 cap off/on 独立轴，研究 p=10%（非默认、未校准），显式 `raw_shares_incremental` 与 `available_at`；覆盖足量、限量、缺量、延迟可得、共享桶和 gap-open 未完成量拒绝。生产量及来源证明不足时标 DATA_GAP，合成量只验证局部机制。

## 4. 证据与缺口

首批交付逐笔 decision_px/fill_px/reason/match、报价时间/可得时刻/提交时刻、候选时间/拒绝原因、股数、现金与状态；汇总同时报告状态匹配率、双方成交数/基线成交数、共同成交子集的同价率和价格/净收益差。分母为 0 输出空值。

局部净收益以独立事件的买入含费成本为分母，在固定合成终点卖出扣费后计算；未成交不计算收益。对共同成交事件在**各引擎内部**计算局部收益排名及变化；同时给出全策略净收益、回撤、策略排名 `DATA_GAP`（数值空白）。不把稀疏 marks 当完整 NAV 或最大回撤，不给跨引擎总 NAV。

市场数据只通过 resolver 验证已配置根；未配置/不存在必须记录异常，不探测盘符或猜路径。名单文件日期不能证明盘中可得，抽样检查仓内 CSV 内容及可得时间字段，文件 mtime/commit 时间不用作信号生成时间。真实 bar 标签、名单/因子发布时间、生产量、现金/日线/权益等证据不足均记 gap。即使未来配置了根，本 harness 也不自动声称完整湖回放；应另补数据验收与闭环调度方案。

## 5. 产物与验证

- [独立目录与复跑说明](../../../backtest/research/exports/minute_sensitivity_b_20260920/README.md)：脚本、CSV、输入与运行 manifest；默认拒绝覆盖已存在输出目录。
- [第一批结果](results-minute-sensitivity-b-batch1-2026-09-20.md)：实际运行计数与边界，不写预期数值冒充结果。
- 验证：harness 时间/限价/现金/T+1/容量的有意义断言，原生产相关测试及 data-free gates；检查全 diff 仅新增允许文件、UTF-8 无 BOM/NUL=0、`git diff --check`、复跑 CSV 确定性。
- 持续更新 `/tmp/minute-sensitivity-b-status.md`；完成后本地 `git add`/`git commit`，phase=`CODEX_DONE`。


## 6. 第二批（batch2）指针

真实分钟事件轴：同一 `parquet_lineage`；优先 qlib `my_data_1min` bin，回退 OSKH parquet `E:\stock_data`。结果与 RUNBOOK 见 [results-minute-sensitivity-b-batch2-2026-09-20.md](results-minute-sensitivity-b-batch2-2026-09-20.md)。生产热路径仍冻结。


## 7. 第三批（batch3 / modeb）指针

Mode B clock 轴（`next_tradable_open`）：补齐 batch2 的 `ModeB NOT_RUN`。入场为 **同一 none 1min 帧聚合的日收**（`daily_entry_source=aggregated_from_1min_none_lineage`），**禁止** qlib `my_data` day.bin（后复权）。Q39 基线 `StrategySpec(2,10,5,5)`；oracle 硬标签 `EX_POST_UPPER_BOUND_NOT_EXECUTABLE`，不得并入可执行汇总。产物目录建议：`backtest/research/exports/minute_sensitivity_b_20260920/batch3_modeb/`。结果与 4090 RUNBOOK 见 [results-minute-sensitivity-b-batch3-modeb-2026-09-20.md](results-minute-sensitivity-b-batch3-modeb-2026-09-20.md)。生产 C 仍冻结。
