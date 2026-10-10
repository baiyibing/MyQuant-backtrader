# 计划：盘后结果分析（2026-10-10）

> **状态：P1、P2、P3 已落地。P3 是切窗，不是 bootstrap。**
> Q1–Q8 与 M1–M10 的结论在第 9 节。
> 性能优化已停。本计划不改成交、不改默认净值、不开新策略版本、不复活 Cerebro。

## 0. 评审怎么用

评审人只回答文末 **Q1–Q8**，并指出口径冲突。不要在评审里改 `simulate`、补性能开关，或把 vendor 引擎接进来。

草案立场写在每题后面，供推翻。推翻某一题只改那一题的口径，不把整份计划打回「再调研 vendor」。

## 1. 已锁定

这些在 2026-10-10 的讨论里已经定过，评审不再重开方向：

1. 下一步是结果分析，不是再做一轮性能。
2. 分析读已经落盘的 `summary.txt`、`daily_equity.csv`、`trades.csv`。入口仍是 `scripts/research/export_csv_human_analysis.py`。不重跑回测。
3. 成交规则、账本、默认净值保持不动。`trades.csv` 与 `daily_equity.csv` 的字节不因本计划改变。
4. 不抄 vendor 的成交引擎。对照过的只是报表字段：RQAlpha `sys_analyser`、Qlib `analysis_position/report.py` 与 `contrib/evaluate.py`、vectorbt `portfolio/trades.py`、backtrader `analyzers/tradeanalyzer.py`、Pybroker 的 walkforward / bootstrap。vn.py、cfquant、qmt、xtquant、nautilus、LEAN 经纪商层、Zipline Pipeline 不进入实现。
5. 年化用复利，一年 252 个交易日。不采用 Qlib `risk_analysis(..., mode="sum")` 的「日均收益 × 238」。Qlib 文档写明那不是复利年化。
6. 已平仓胜率与含期末浮盈的胜率继续分开。vectorbt 把未平仓混进胜率的做法不采用。
7. 第一份要做的是净值页加交易盈亏比。个股集中度、切窗或 bootstrap 靠后，且单独批准。

## 2. 现在已经有的

| 已有 | 位置 | 本计划怎么用 |
|---|---|---|
| 盘后包 | `backtest/research/csv_analysis_export.py`，字段说明 `docs/backtest/csv-analysis-fields.txt`，提示词 `docs/backtest/prompt-csv-human-analysis.md` | 往现有目录加文件，不另起一套导出 |
| 回撤、胜率、按卖因 | `drawdown_and_win_rates` | 函数和字段都不改。平均盈亏和获利因子只进 `trade_payoff.json` |
| 回合与个股盈亏 | `round_trips.csv`、`pnl_by_stock.csv` | P1 读回合；P2 才改个股表 |
| 可选风险包 | `backtest/research/metrics_pack.py`，CLI `scripts/research/rb13_metrics_pack.py` | 不改它的 JSON 形状。口径相同的夏普继续调用它；新字段放到新文件，避免现有 rb13 测试变红 |
| 净值列 | `daily_equity.csv` 为 `date,equity` | 分析只读这两列，加列算在导出目录里 |

`metrics_pack` 在调用方传入基准 CSV 时能算超额、beta、跟踪误差。默认导出不带基准，所以盘后包里现在看不到指数。

## 3. 分期

### P1（评审通过并批准实施后的唯一开工范围）

在 `<run-dir>/analysis/` 增加两个文件，并在 `human_analysis.txt` 里各引一行。缺基准时交易页仍要写出。

`account_curve.json`

- 区间复利收益、复利年化（252）、年化波动、夏普（无风险利率草案为 0，见 Q8）
- 最大回撤、谷底日、峰值日、交易日长度、自然日长度（见 Q4）
- 有基准时：期末几何超额、期末算术超额、超额最大回撤及其峰值日/谷底日/两种长度、信息比率、超额夏普
- 月度表：当月收益；有基准且该月两端都能对齐时再写当月几何超额
- 换手（见 Q5）、费用拖累
- 佣金加回后的期末权益。只加 `trades.csv` 里已经有的佣金列。没有单独印花税列就不估计

`trade_payoff.json`

只统计 `round_trips.csv` 里 `status=closed` 的行。

- 笔数、胜率（沿用现口径：`realized_pnl > 0`）
- 平均盈利、平均亏损、盈亏比（平均盈利 / 平均亏损的绝对值）
- 获利因子（盈利合计 / 亏损合计的绝对值）
- 上面四项再按 `sell_reason` 各算一遍
- 没有任何 `realized_pnl < 0` 时，盈亏比和获利因子写 `unavailable`，不写无穷大。`realized_pnl == 0` 仍算进现有胜率的亏损分母，但不进入平均亏损的分母。JSON 另写零盈亏笔数

`human_analysis.txt` 增加的两行只引用上面两个文件里的数，不另算一套。

### P2（另批）

`pnl_by_stock.csv` 增加占已实现盈亏的比例，以及盈利最多的前 5 只占全部正盈利的比例。前 5 不足 5 只时按实际只数写，并写明只数。

### P3（另批）

单独文件，不写进 `human_analysis.txt` 的结论句。二选一，由 Q7 定：

- 切窗：同一导出上把净值按日期切成前段与后段，后段只出分，不在本工具里重选参数
- bootstrap：对日收益重抽样，给总收益和夏普一个区间

P3 不调用回测入口。

## 4. 口径（第二轮后）

账户自身的区间收益、复利年化、波动、夏普、最大回撤只用完整净值，不因为缺基准而删日子。\(n\) 为净值行数减 1；\(n<1\) 时年化写 `unavailable`。日期须唯一且严格升序，否则失败。\(E_0\le 0\) 或基准 \(B_0\le 0\) 时，相关比值写 `unavailable`。

基准只参与超额。对齐要求终点日和前一日都是两边共有的单步；多日缺口不并成一个日收益。丢掉的间隔数写入 JSON。缺基准的日子不前向填充。几何超额和超额回撤用重叠日上的水平，\(E_0\)、\(B_0\) 取第一个重叠日。

| 名 | 算法 |
|---|---|
| 区间收益 | \(E_T/E_0-1\)。\(E_0\) 取净值首行。这不是 summary 里的「总收益率(全资金)」，JSON 写明「相对净值首行」 |
| 复利年化 | \((E_T/E_0)^{252/n}-1\) |
| 夏普 | 日收益减去 \((1+r_f)^{1/252}-1\) 后的均值，除以样本标准差，再乘 \(\sqrt{252}\)。\(r_f\) 默认 0。零波动时年化波动写 0，夏普写 `unavailable`。实现不得 import `metrics_pack`，夹具必须与它的数值相同 |
| 期末几何超额 | \((E_T/E_0)/(B_T/B_0)-1\) |
| 期末算术超额 | \((E_T/E_0-1)-(B_T/B_0-1)\) |
| 日超额 | 单步对齐上的 \(r^E_t-r^B_t\)。间隔少于 2 或标准差为 0 时，信息比率写 `unavailable` |
| 信息比率 | 日超额的均值 / 样本标准差 \(\times\sqrt{252}\) |
| 超额夏普 | 对 \((1+r^E)/(1+r^B)-1\) 做夏普，无风险利率固定 0。它和信息比率不是同一个数 |
| 超额最大回撤 | 在 \((E_t/E_0)/(B_t/B_0)\) 上做峰值回撤 |
| 回撤长度 | 谷底取回撤最小的最先一行，与现有 `max_drawdown_date` 的 `idxmin` 一致。峰值日是该谷底之前最后一次净值等于当时运行最高点的行。交易日长度是两个位置序号之差。自然日长度是日历差。回撤为 0 时长度写 0 |
| 当月收益 | 该月最后一条净值 / 该月之前最后一条净值 \(-1\)。样本的第一个月，分母用该月第一条。没有行的月不补。先把日期收成 `YYYY-MM-DD` 再取年月 |
| 当月几何超额 | \((1+r^{月}_E)/(1+r^{月}_B)-1\)。分子日和分母日必须在两条序列上是同一天，否则该月 `unavailable`。\(1+r^B=0\) 时也是 `unavailable` |
| 单边换手 | 只累加 `side` 为 BUY 或 SELL 的名义额，\((买入额+卖出额)/2\) / 全部净值行的算术平均。年化再乘 \(252/n\)。JSON 写 `one_way`。缺名义额时用价格乘股数，价格或股数无效则 `unavailable`。平均权益为 0 时 `unavailable` |
| 费用拖累 | 佣金合计 / 平均权益。佣金列缺失或非数字时写 `unavailable`，不用读入时填上的 0。不把印花税或过户费估计进去 |
| 佣金加回 | 期末净值 + 佣金合计，字段名 `equity_commission_added_back`。佣金不可用时为 `unavailable`。它不是一笔笔复利重放 |

盈亏比、获利因子只来自已平仓且 `realized_pnl < 0` 或 `> 0` 的笔。没有任何严格亏损时两项都是 `unavailable`。未平仓的 `mtm_pnl` 不进入。

基准输入二选一，都不是默认必填：

- `--benchmark-csv`：只认列 `date,equity`。不认 `close` 别名
- `--benchmark-index`：经 `resolve_index_daily_root()` 读指数日线。根目录不存在就失败，不猜盘符，不把异常收成 `unavailable`

两条都没给：基准字段为 `unavailable`，原因写 `benchmark not supplied`。交易页照常写。单测只用 CSV。CI 不调用 `--benchmark-index`。

## 5. 不做什么

- 不改 `csv_minute_backtest.py` / `csv_daily_backtest.py` 的 `simulate` 与 `run` 成交结果
- 不把分析指标写进 run 的 `summary.txt`，也不写进盘后 `summary.json`。新数字只在 `account_curve.json` 和 `trade_payoff.json`。`human_analysis.txt` 只加两行引用。因此允许更新盘后整目录 SHA 夹具，夹具必须同时覆盖这两个新 JSON
- 不改 `metrics_pack` 的 `rb13-v1` 字段集合
- 不新增策略书，不改 6.53 / version9 的卖点
- 不把 Qlib IC、`score_ic`、多空回测当作本仓成绩
- 不在 P1 做图。JSON 和 `human_analysis.txt` 的两行就够
- 不读 `out/`、不把 6.53 或策略 9 的全窗结果再跑一遍当作验收。单测用合成净值

## 6. 实施时允许碰的文件（现在还不许改）

- 新模块：`backtest/research/result_analysis.py`（纯函数，无 IO 或 IO 只在导出层）。源码不得出现 `metrics_pack` 这串字，也不 import 它。夏普公式按它的定义抄一份，并用夹具断言与 `compute_metrics_pack` 相同，含非零无风险利率和零波动
- `backtest/research/csv_analysis_export.py` 的 `write_bundle`
- `scripts/research/export_csv_human_analysis.py` 增加可选基准参数
- `docs/backtest/csv-analysis-fields.txt`
- `docs/backtest/prompt-csv-human-analysis.md` 只加「引用新文件，不要手算」一句
- 新测试：`tests/test_result_analysis.py`

导出不得 import 分钟或日线 `simulate`。

## 7. 验收（P1 开工之后才跑）

合成数据，不靠湖：

1. 手算一笔几何超额、一笔算术超额，与 JSON 一致
2. 一条上升净值配一条更快的基准，几何超额为负
3. 无亏损回合时获利因子为 `unavailable`
4. 不传基准时交易页仍有盈亏比，基准字段为 `unavailable`
5. 构造一组日收益，使「日均 × 238」与复利年化不相等，断言实现值等于复利年化
6. 现有 `tests/test_rb13_metrics_pack.py` 与盘后导出测试仍过
7. 对一份已有 run 目录再导出一次：`trades.csv` 与 `daily_equity.csv` 哈希不变

CI 不读 F 盘湖。指数路径只在显式传入且根目录存在时使用；单测用 CSV。

## 8. 评审题

请按题号回答「同意草案 / 改成……」。不要把没问的引擎改动写进答案。

| 题 | 草案 | 要决定的点 |
|---|---|---|
| Q1 | 基准默认不传。不传则基准字段 `unavailable`，其余照常导出 | 要不要改成默认尝试 `000300.SH`，失败再降级 |
| Q2 | `--benchmark-index` 的复权必须由参数写明 `none` 或 `front`，缺省就拒绝，不从回测目录推断 | 是否允许在能读到 run 的 dividend 标记时自动跟随 |
| Q3 | 对外先报期末几何超额；算术超额并列，不互相替代 | 标题行是否改成先报算术超额 |
| Q4 | 回撤长度的标题用交易日；自然日写在旁边 | 是否改成只报自然日（RQAlpha 的日历差） |
| Q5 | 换手按单边：买卖额之和除以 2，再除以平均权益，并标注 `one_way` | 是否改成双边（不除以 2） |
| Q6 | P1 含月度表，不含连胜连亏和持有天数分桶 | 月度表是否挪到 P2；连胜是否提前到 P1 |
| Q7 | P3 先做切窗，不做 bootstrap | 是否颠倒，或 P3 整段不做 |
| Q8 | 夏普的无风险年利率为 0；超额夏普固定为 0，不受 Q8 改动影响 | 是否改成必须传入利率、否则夏普 `unavailable` |

八题都有书面答案，并且 Human 写「批准实施」之后，才开始 P1。P2、P3 不包含在那一次批准里。

## 9. 评审记录（2026-10-10）

主持人：本会话。第一轮三路独立，第二轮只投修正案。没有改成交代码。

| 路 | 模型 | 角色 |
|---|---|---|
| A | grok-4.7-xhigh-fast | 公式 |
| B | cursor-grok-4.6-high | 导出合同 |
| C | composer-2.5-fast | 范围 |

Q1–Q7 三票同意草案。Q8 三票同意「无风险利率默认 0，不因没传入就让夏普 unavailable」。超额夏普另按 M5 与信息比率拆开。

| 修正 | 票 | 主持人收束 |
|---|---|---|
| M1 账户指标用完整净值 | 3 同意 | 写入第 4 节 |
| M2 当月收益 | A、C 同意；B 反对含糊的「前一行」 | 采用 B 的句子：该月最后一条 / 该月之前最后一条；首月用该月首行 |
| M3 缺佣金则 unavailable | 3 同意 | 写入第 4 节 |
| M4 禁止 import `metrics_pack` | 3 同意 | 写入第 4、6 节 |
| M5 超额夏普用几何日超额 | 3 同意 | 写入第 4 节 |
| M6 回撤峰值日 | B、C 同意；A 反对未规定并列谷 | 谷底用现有 `idxmin` 最先一行；峰值日用该谷底前最后一次触及当时最高点 |
| M7 零盈亏不进平均亏损 | B、C 同意；A 要求没有严格亏损时必须 unavailable | 两者都写入第 3、4 节 |
| M8 基准 CSV 只有 `date,equity` | 3 同意 | 写入第 4 节 |
| M9 不改 `drawdown_and_win_rates` | 3 同意 | 写入第 2 节 |
| M10 新数字不进两份 summary | 3 同意 | SHA 夹具还要盖住两个新 JSON |

第二轮结束时 A、B 要求先把上述收束写进正文才批 P1，C 在写入后批 P1。正文已经按这张表改完。**这仍不是实施许可。** Human 写「批准实施」之后才做 P1。P2、P3 不随那一次批准开工。
