# domain-safety

## 结论

**REQUEST_CHANGES（后续实施合同）；支持 §3 只选 delta1。** 当前 v0.2 的费用合约遗漏最低费用的计费粒度，生产冻结证明也不足以覆盖其宣称的零行为变化。下列 DS-01、DS-02 应先回填计划；修订均可保持 docs-only。本路不要求把既有 ST PIT、v7 fail-open 或除权行为修复塞进费用主船，也不给现存引擎整体 fail-closed 的背书。

已先完整读取 `docs/backtest/plan-industry-align-p3-fees-2026-09-19.md`，共 227 行，版本 Proposed v0.2；下文行号均以本次工作区读取版本为准。文件 SHA-256：`acf6f90b506a451e7e272462cc01d0f1441b675a25b098c9c290fc86bec136da`。按 `docs/prompts/prompt-adversarial-subagent-review.md:11`、`:15`、`:24`，采用证据优先、核对实现而非只信 docstring 的 domain-safety 立场。

开工基线核对结果：

| 项目 | 结果 |
|---|---|
| `git rev-parse HEAD` | `9e2e9eb774345d0d0bf6075192739780a3f0ee47` |
| `git rev-parse origin/master` | `9e2e9eb774345d0d0bf6075192739780a3f0ee47`（本地远端跟踪引用，本路未 fetch） |
| plan `IMPLEMENTATION_BASE` | `c65b10dd6d26342bd9ec1cbed5465d875f82470f`，见 `docs/backtest/plan-industry-align-p3-fees-2026-09-19.md:5`、`:144` |
| 祖先关系 | `git merge-base --is-ancestor c65b10dd6d26342bd9ec1cbed5465d875f82470f HEAD` 退出 0 |
| plan 十个冻结文件 | 基线→HEAD、工作区未暂存、索引暂存三组 `git diff --exit-code` 均退出 0 |

因此 **HEAD = 本地 origin/master ≠ IMPLEMENTATION_BASE**。按 `docs/backtest/plan-industry-align-p3-fees-2026-09-19.md:149` 的条件，若 fetch 后仍是当前 tip，验收会在 `:151` 主动退出。这是正确的 fail-closed 停止，不是脚本误报；不得静默替换 SHA 或假称 §8 全部通过。两基线之间还有其他已提交的生产文件变化，所以十文件零差异也不能表述为整个仓库零生产差异。后续实施须先记录基线漂移及明确的实施基线决定。

本路仅静态读取、Git 核对和报告文件检查；未执行 pytest、CI gate、模拟或回测，未读取行情湖。开工已有暂存文件 `scripts/run/run_codex_adversarial_lanes.py`，未改动、未执行。唯一写入为本报告。

## Findings（file:line）

**DS-01 · P1 · 冻结清单不能证明所承诺的停牌、复权与成交窗口零漂移。**

- **计划锚点：** `docs/backtest/plan-industry-align-p3-fees-2026-09-19.md:78` 要求零生产行为变化，`:83` 锁住 P1/P2/P4；但 `:169`–`:184` 的证明只检查十个文件，`:192` 将这些差异为零作为放行标准，`:211` 又宣称可编辑面仅 docs + data-free tests。
- **实现证据：** 未入冻结表的 `backtest/research/ashare_bars.py:302`–`:306` 决定分钟时段是否进入撮合，`:369`–`:371` 丢弃整日零量 K；未入表的 `backtest/research/csv_daily_loader.py:83`–`:84` 丢弃零量日线，`:104`–`:110` 选择复权分区；未入表的 `backtest/research/exdiv_map.py:77`–`:92` 决定涨跌停昨收是否换入除权日价格域。这些并非旁路文件。
- **漏检反例（静态推导，未修改代码）：** 只删除日线 loader 的零量过滤，或只改变 `ashare_bars._in_session` 的端点，十文件 diff 仍可全部为零。`tests/test_ashare_simulate_predicates.py:32`–`:40` 直接构造无 volume 的 DataFrame，不走零量 loader；`tests/test_ashare_simulate_import_fence.py:32`–`:49` 检查导入关系，也不会识别这种行为变化。真实零量场景已有独立用例 `tests/test_csv_daily_backtest.py:990`，但不在本计划 `:157`–`:160` 的快速测试集合。故目前的证明允许影响停牌或 P1 的改动漏过。
- **影响：** 后续合同实施即使报告上述门禁全绿，也不能据此断言“停牌不成交、复权域、成交窗口和 NAV 均未改变”。本次未发现这些遗漏文件被本路改动；Finding 针对验收设计，不把可能漏检说成已发生回归。
- **最小勘误：** 在明确记录基线漂移后，为本轮新增“变更路径只能落在约定文档和合成测试文件”的检查，覆盖提交差异、暂存、未暂存及未跟踪文件；把现有十文件表保留为重点证据。或补齐显式冻结依赖并相应收窄零漂移声明。不要扩大 `SIMULATE_HOT_PATH` 为 research 全目录导入扫描；生产冻结与导入围栏是两个不同检查。

**DS-02 · P2 · 最低费用缺少“逐 lot / 聚合卖出 / 无成交不计费”的合同，T+1 与费用的交界未锁住。**

- **计划锚点：** `docs/backtest/plan-industry-align-p3-fees-2026-09-19.md:48`、`:50` 只列账本调用和 v7 schedule 参数；`:80` 要求准确记录 floor/asymmetry，`:121`–`:125` 却没有规定最低费用落在哪一笔成交、如何处理部分 T+1 可卖仓位。`:125` 新增的 asymmetry 检查是涨跌停门分叉，并不证明费用聚合粒度。
- **实现证据：** 日线在 `backtest/research/csv_daily_backtest.py:325` 逐 lot 循环，在 `:329`、`:336` 判断 T+1 后调用 `_sell`；分钟在 `backtest/research/csv_minute_backtest.py:609` 逐 lot 扫描，在 `:620` 传递 T+1 可卖性，在 `:651` 卖出。共享账本每次 `_sell` 都对该 lot 单独执行最低费用公式（`backtest/research/csv_ledger.py:242`–`:245`）。v7 则在 `backtest/research/csv_minute_backtest_v7.py:226`–`:231` 先筛 T+1 和 kind、无可卖股直接返回，再于 `:240`–`:243` 对本次合计卖出金额计一次费用。其 schedule 可通过 `:279` 显式传入；分钟书路径默认没有同等费用覆盖入口。
- **金额反例（按实现手算，未运行模拟）：** 对两笔均已 T+1 可卖、各卖出 1,000 元的 lot，显式使用卖费率 0.0015、min_cost=5 时，书账本两次 `_sell` 收 `5+5=10` 元；v7 一次 `_sell_lots` 合计 2,000 元只收 `max(3,5)=5` 元，现金分别增加 1,990 与 1,995 元。默认双边 10bp 无 floor 时，两种分组的总费用均为 2 元，因而默认测试无法暴露这个差别。
- **测试证据：** `tests/test_ashare_fees.py:10`–`:24` 只验证公式、小额买费下限和重导出，未检查卖出聚合或实际现金；`tests/test_ashare_simulate_predicates.py:88`–`:91`、`:105`–`:109` 核对 T+1/跌停后的成交日期和价格，未断言被挡当日没有费用现金变化。共享 `_sell` 自身也不判 T+1，不能只调用该函数就宣称验证了成交资格。
- **最小勘误：** 在 Slice A 写明最低费用以现有成交调用为单位、书逐 lot 与 v7 聚合保留差异、仅实际成交金额参与 debit/credit；在 Slice B 指定合成断言：两笔老 lot 的计费粒度、老 lot 与当日新 lot 混合时只卖老 lot、全为当日 lot 或涨跌停拦截/现金不足时无成交费用入账。断言现金变化及留仓股数；v7 没有 commission 列时从现金验证，不重开 P2。测试留给后续实施，本路不新增测试、不统一账本、不改费率。

**五项强制领域核查（静态证据；下列现存边界不等于本轮新回归）：**

| 必查项 | 核查结果与证据 | fail-closed 裁决 |
|---|---|---|
| T+1 | `backtest/research/ashare_session.py:39`–`:41` 为严格 `buy_date < session`；书侧日期映射在 `backtest/research/csv_daily_backtest.py:329`、`:336` 和 `backtest/research/csv_minute_backtest.py:620`；v7 逐 lot 筛选在 `backtest/research/csv_minute_backtest_v7.py:226`–`:235`。已有三引擎同日拒卖测试 `tests/test_ashare_simulate_predicates.py:87`–`:91`。 | 未见 delta1 拟改变 T+1；不能仅以单 lot 的日期测试替代 DS-02 的部分可卖及无费用断言。 |
| 未来函数 / PIT | 默认书昨收切片在 `backtest/research/csv_common.py:38`–`:44`、`backtest/research/csv_minute_backtest.py:464`–`:466`，v7 昨收只取 `< today`（`backtest/research/ashare_session.py:44`–`:46`）；v7 指数门使用前一已完成会话（`backtest/research/strategy7_rules.py:177`–`:186`）。但 ST 名称按整个窗口覆盖（`backtest/research/ashare_session.py:81`–`:85`、`:97`），然后用于历史每一天（`backtest/research/csv_minute_backtest_v7.py:324`–`:326`）。`tests/test_csv_minute_backtest_v7.py:222`–`:241` 明确用 D2 的 ST 名称改变 D1 买入。 | 确认现存 ST 未来信息风险；§3 delta3 可以继续独立延期，但“费率已锁定”不能推导出历史回放具备 PIT。未核验外部名单的实际生成时刻，不能对信号端无未来函数作保证。 |
| 复权混用 | 默认书日线 loader 为 `none`（`backtest/research/csv_daily_loader.py:96`、`:104`–`:110`），分钟湖根为 `none`（`backtest/research/ashare_bars.py:381`）；E-R6 只缩放参考 cost/peak（`backtest/research/csv_ledger.py:141`–`:150`），成交费用仍用 `shares * px`（`:210`–`:214`、`:243`–`:245`）。日线 front/back/bin 分支关闭 E-R6（`backtest/research/csv_daily_backtest.py:558`–`:562`）。v7 的日/分钟来源独立可选（`backtest/research/csv_minute_backtest_v7.py:512`–`:518`），加载链没有同域校验（`backtest/research/ashare_bars.py:261`–`:285`），且仍无条件加载并传入 E-R6 context（`backtest/research/csv_minute_backtest_v7.py:546`、`:558`–`:559`）。 | 默认 none 路径有实现证据；可选来源组合不能一并认定安全。`qlib_bin_daily.py:94` 读取 close.day.bin，非原始 adjclose；该 dump 的后复权标注见 `backtest/research/qlib_bin_daily.py:6`，实际 bin 内容未读。若该标注成立，raw 分钟 + 调整日线昨收 + E-R6 存在错域风险。§3 delta2 所说 E-R6 已覆盖核心行为，不是所有数据源同域证明。 |
| 盈筹率单位 | `qlib_cost/cyq.py:238`–`:245` 以总筹码归一化后求和，正常分布得到 0–1 比例，空分布返回 NaN；`:256`–`:257` 明确拒绝区间外的 cost 分位参数。费用模块则使用独立的十进制费率 `0.001/0.0005/0.0015`（`backtest/research/ashare_fees.py:17`–`:20`），不消费 CYQ。外部日频 feeder 的归属见 `docs/backtest/plan-h13-cyq-tr-boundary-2026-09-15.md:15`。 | 本次费用范围未发现盈筹率按 0–100 与 0–1 混用的变更。不能把“10bp”与“10% 盈筹率”混为同一单位；不因此给外部馈源或全仓 chip 消费路径背书。 |
| 停牌 / 涨跌停 | 日线零量过滤 `backtest/research/csv_daily_loader.py:83`–`:84`，分钟整日零量过滤 `backtest/research/ashare_bars.py:369`–`:371`；书缺 K 时跳过持仓交易（`backtest/research/csv_daily_backtest.py:301`–`:303`、`backtest/research/csv_minute_backtest.py:575`–`:582`），估值取最近 close（`backtest/research/csv_ledger.py:159`–`:178`）。默认板块档位经 Decimal HALF_UP（`backtest/research/market_layer.py:73`–`:84`）；书常规未知板块拒绝在 `backtest/research/csv_simulate_loop.py:260`–`:262`。v7 持仓路径的 None 门返回“不拦截”（`backtest/research/ashare_session.py:73`–`:78`），可继续卖出或加仓（`backtest/research/csv_minute_backtest_v7.py:342`–`:354`、`:367`–`:372`）。 | 已知 `limits=None` fail-open 仍在；T+1 不能替代涨跌停证明。零量过滤还依赖数据带 volume（`backtest/research/csv_daily_loader.py:57`、`backtest/research/ashare_bars.py:343`），不能将缺量列或注入记录等同于已验证非停牌。支持保持既有行为，但不得把分叉测试通过称作交易资格全部安全。 |

费用/税边界另行核实：`backtest/research/csv_ledger.py:211`–`:214`、`:244`–`:245` 以及 `backtest/research/csv_minute_backtest_v7.py:207`–`:211`、`:242` 只通过研究费用公式影响现金，没有独立印花税或过户费记账项。故计划 `docs/backtest/plan-industry-align-p3-fees-2026-09-19.md:81`、`:94` 的 boundary-only 方向成立。本路未将研究费率解释为真实税费拆分，也不因 QLIB_PORTANA 名称而要求引入 qlib 执行器或交易栈政策。

## 对 plan §3 / 主船范围的独立裁决

**同意 delta1 单船；反对把当前 v0.2 原样当作完整实施验收合同放行。** 主船保留 `FeeSchedule`、默认费率、调用粒度、非对称性及税费边界文档，并允许后续添加合成合同测试。DS-01、DS-02 属于使这一主船可审查的必要勘误，不需要生产代码更改。

| §3 项目 | 本路裁决 |
|---|---|
| delta1（`docs/backtest/plan-industry-align-p3-fees-2026-09-19.md:66`） | 支持；P3.1/P3.2/P3.3 默认 A/A/A 可保留。完成冻结范围与费用粒度勘误，并记录基线漂移后，再评价后续实施验收。 |
| delta2（`:67`） | 继续独立延期。E-R6 的触发参考价修正，不证明调整行情与原始成交域可混用，也不消除跨除权现金/股数残差；残差明确见 `docs/backtest/engine-ashare-correctness.md:78`–`:79`。 |
| delta3（`:68`） | 继续独立延期，但必须保留非 PIT 风险标签；不得因本轮审查而将其记作已解决。 |
| delta4（`:69`） | 继续独立延期；现存 v7 持仓未知档位放行只作为兼容事实固定，不能算 fail-closed 达标。 |
| delta5（`:70`） | 继续独立延期；本轮费用合同与停牌过滤均不能证明成交量容量或实盘可成交性。 |

P1（14:57）、P2（trades 列）、P4（touch/mark）继续按 `docs/backtest/plan-industry-align-p3-fees-2026-09-19.md:83`、`:101`–`:106` 排除。若后续必须改变 T+1、ST 生效时点、None 门或行情价格域，应另开相应行为计划；不能仅借 `:131` 的 P3.* 泛称取得改写这些领域规则的授权。本报告是单路对抗证据，不计作独立人裁票。

## 未验证

- 未 fetch；只确认本地 `origin/master`，未断言审查时真实远端 tip。未执行完整 §8，因此没有 pytest 或四个 CI gate 的通过结论。
- 未运行回测、模拟、行情探针或合成测试。DS-01 的漏检方式、DS-02 的现金差异均为代码路径及公式推导，不是已运行复现。
- 未读取湖或 qlib bin 内容，未验证真实数据的 volume 完备性、停牌占位、复权因子时间可得性、除权事件遗漏、名单产生时刻或历史 ST 生效日。ST 跨日风险有现存代码和测试源码证据，实际收益影响未量化。
- 未遍历全部策略/CYQ/TR 消费链，也未读取兄弟 MyQuant feeder；盈筹率结论限于所引本仓实现及 delta1 费用面。未检查外部真实税率、券商最低收费规则或交易所最新规则；研究公式不能当作这些外部政策的准确性证明。
- 费用函数的非法参数行为仍是现状：`backtest/research/ashare_fees.py:25`–`:30` 对负 rate 返回 0，未作统一有限数检查。本路未对 NaN/Inf/负值注入做动态验证，未据此要求本轮改生产校验；默认合法 schedule 的核对也不构成任意输入安全保证。

## 模型与 effort（写你实际用到的）

- 模型：当前 Codex 会话，系统标识为基于 GPT-6；未暴露可独立核验的部署细分 model ID。
- effort：本会话未暴露实际 `model_reasoning_effort` 值，无法核验；不把宿主脚本的默认值当作本次运行实参。
- 执行：仅本会话一个 domain-safety 路径；未 spawn 子 agent，未再调用 `codex exec`，未使用其他模型。
