# 分钟敏感对照 B · 2026-09-20

这是 Human GO B 的独立只读研究产物，BASE 为 `f2fe15124ffbc62d3c0526fc90fed78d014b1bb1`。**仅合成局部价格敏感性，非完整策略重放**。生产湖、名单/因子可得性、真实 bar 标签和生产量均有 DATA_GAP；没有完整策略净收益、回撤或策略排名。Mode B oracle 是事后上界，不能当可执行收益。

- [实验计划](../../../../docs/backtest/reviews/plan-minute-sensitivity-b-2026-09-20.md)
- [第一批结果与逐笔解释](../../../../docs/backtest/reviews/results-minute-sensitivity-b-batch1-2026-09-20.md)
- [研究脚本](../../../../scripts/research/run_minute_sensitivity_b.py)
- [局部证据验证](verify_harness.py)
- [首批 manifest](batch1/manifest.json)

## 复跑

在仓库根目录运行，优先使用已验证的解释器 `/tmp/industry-align-venv/bin/python`；也可显式使用 `/workspace/vanna312/bin/python`（本批未验证其依赖版本）。不要隐式用系统 Python。无需行情湖；脚本只通过 resolver 查询已配置根并记录缺口，不读取或写入市场 bars，不探测磁盘，不下载数据。

```bash
/tmp/industry-align-venv/bin/python scripts/research/run_minute_sensitivity_b.py --output-dir /tmp/minute-sensitivity-b-rerun
/tmp/industry-align-venv/bin/python -m pytest -q backtest/research/exports/minute_sensitivity_b_20260920/verify_harness.py
```

`--output-dir` 必须是**不存在的新目录**，已有目录立即报错，没有覆盖开关。正式首批目录 `batch1/` 已存在，应换复跑目录。脚本会检查 11 个直接研究依赖文件与 BASE 一致，并记录 before/after SHA256；未来修改了这些生产文件时拒绝冒用旧 BASE，需另开版本实验。manifest 同时记录当前 git HEAD、脚本 hash、输入/CSV hash 和解释器版本；提交后复跑 git HEAD 变化是预期元数据变化，CSV 应保持确定性（若环境配置变化，`data_gaps.csv` 也会据实变化）。

## 口径与文件

| 文件 | 用途 |
|---|---|
| `fixtures.json` / `minute_frames.csv` | 26 个时钟事件的参数、真实传入的合成基线 frame 与候选 frame；不是市场采样 |
| `clock_trades.csv` | 逐笔决策/报价/成交时刻、价格、状态、股数、事件现金、净损益差与局部排名 |
| `clock_candidates.csv` | 31 条候选及 `before_submit`、涨跌停、现金拒绝原因；保留第一个可成交候选，不按收益挑选 |
| `clock_summary.csv` | Book/v7 分列的匹配分母；Mode B clock 未运行；完整策略指标空白且标 DATA_GAP |
| `clock_boundaries.csv` | 午休、T+1、收盘竞价排除、卖出跌停、next-open 未完成量、Book 缺报价 pending 的机制探针 |
| `modeb_baseline.csv` | 2 个公开 Q39 入口实例，fast/ref 一致；独立日线 close 入场 |
| `cost_sensitivity.csv` | 144 行，24 个基线成交配对各 4 档滑点＋2 个替换费用情景；逐笔净收益、差额和局部排名 |
| `capacity.csv` / `capacity_shared.csv` | close 的 cap off/on，及同桶买卖共享 350 股预算；与 clock/slippage 分轴 |
| `gap_stop.csv` | 4 行，Book/v7 保护性 gap-open 各 off/on；不改成 chase 的 next-open |
| `fee_granularity.csv` | 两个 100 股 lot：Book 两次卖调用，v7 一次合并调用的最低费差异 |
| `data_gaps.csv` | 6 类证据缺口及 resolver 原始错误 |
| `manifest.json` | 参数、版本、BASE 和数据/源码 hash |

固定终点价格是人工指定的独立局部卖出配对价，日期 2026-09-21；它不是读取市场未来收益或 oracle 挑选的结果。数量固定为原账本成交量，局部 `net_return=(卖出净额−买入含费成本)/买入含费成本`。Book 用 1 万元单次额度；v7 用原 20%×100 万元加仓额度；v7 既有 lot 的盈亏完全不纳入加仓局部收益。Mode B 用自身实例名义金额，不与前两者合并。

Clock 内费用固定双边 10bp/min=0、cap off、slippage=0；替代组冻结订单及基线股数，检查事件现金，现金不足终止该单，不重算仓位/后续信号。允许持单到显式下一 session 是研究假设，可能越过 v7 加仓信号窗口；未重新跑届时 stop/stage/index 变化，不得称可执行策略。实际新成交日用于独立 T+1 检查。

所有 CSV 时刻均为 Asia/Shanghai 墙钟，`hm` 是合成 bar 的 **end**；close 在 end 可得，submit=decision+1ms。09:45 close 后的 09:46 标签 bar 实际 start=09:45，不能供提交后的订单成交；下一可用 open 在 start=09:46、end=09:47。Book fallback 09:43 仅是陈旧报价，基线研究成交时刻仍写 09:45，不能回填 09:43 决策。午休探针不属于 09:45 chase 或 v7 的加仓样本。

匹配定义：`status_match` 为两边是否均成交/均未成交；`matched_fill` 为两边均有正成交量。`matched_fill_rate=共同成交数/基线成交数`，同价率仅在共同成交集合计算。未成交组不填收益、不当 0；均值与 clock 排名只含共同成交集合，存在选择偏差，不能代表全样本。排名限同引擎，同收益保留 12 位小数后取平均名次；名次变化正数表示退后。成本排名使用各引擎的全部基线配对，与 clock 的共同成交排名集合不同。

滑点每边 0/5/10/20bp 未校准，均保留 10bp 佣金代理。费用轴的 `REPLACE_COMMISSION_3BP_MIN5_STAMP_SELL5BP` 是用每次调用万三、最低 5 元、卖出 5bp 印花**假设替换**双边代理，不双重扣 10bp，不包含过户等其他项，也不验证当前法律或账户合同。Mode B 的最低费只存在于研究逐笔算术叠层，生产 Mode B 仍是线性费率。本批不建议生产默认。

本批没有改变生产文件、CLI、默认参数、成交核或 import fence 固定清单；`verify_harness.py` 显式 opt-in，仅验证该研究工具及其证据，不写生产新 pin。13 项研究验证、253 项既有相关测试及 4 项 data-free gate 的结果见结果文档。
