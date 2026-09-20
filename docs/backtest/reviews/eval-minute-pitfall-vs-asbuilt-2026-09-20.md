# 分钟回测陷阱与本仓已实现行为评估（2026-09-20）

日期：2026-09-20。BASE SHA：`3d3e2dc`（完整：`3d3e2dcb2189140bdb15695b635a5695b69093d2`）；只读核实时工作区 HEAD 与该基线一致。

依据：对照用户「分钟线回测陷阱」三项主张，核对本仓源码与 SSOT（`engine-ashare-correctness.md` / `plan-industry-align-refactor-2026-09-18.md` F-R6 / `plan-industry-align-p3-fees-2026-09-19.md`）。下文区分已实现事实、条件性风险和待验证推论；未读取行情湖、未运行回测，不报告收益偏差数值。税费的外部核实仅用于纠正观点中的通用费率表述。

## A 观点评估（独立于仓库）

判别重点是信息何时可得、订单何时可提交、价格何时可成交。若决策必须等本 bar 完整 close 才能形成，却无延迟地按同一个 close 成交，就存在「同 bar close 偷看」类执行乐观假设；这与直接读入后续 bar 的信息泄漏应分开描述。预先确定的止损线遇到开盘跳空，采用当根 open 作为成交代理，本身不需要未来 close。

| 用户主张 | 评估 | 可证伪条件与边界 |
|---|---|---|
| ① 分钟回测最大陷阱是成交价；当前 bar close 成交就是偷看，应改 next bar open | **风险方向成立，两个绝对化判断不成立。** 成交价可以显著影响结果，但没有误差归因实验，不能认定它一定是“最大”来源；同价成交是否越过信息边界要看决策。 | close 确认的信号可对照下一可交易 bar open；预设保护性止损、跳空、限价单、预先提交的定时单和竞价单应分别定义。下一 open 也不保证有流动性，且必须在信号可得与订单提交之后。不能把“下一分钟”自动等同于“次日开盘”。 |
| ② 必须强制滑点；A 股应按万三佣金＋卖出千一印花＋合理滑点 | **应核算成本并做滑点压力分析；不支持一组固定参数适用于所有时期、账户和交易。** 万三可作待验证情景，千一须标历史适用期。 | 佣金协议、最低收费、税费适用日、买卖方向和订单规模应明确。滑点随价差、波动、参与率和延迟变化；单一常数只能是代理。容量约束限制成交量，滑点改变成交价，两者不能相互代替。 |
| ③ 分钟对短线更专业；next-bar 与费率/滑点不对，分钟曲线可能比日线更误导 | **条件性成立。** 分钟数据更适合研究盘中路径，但粒度本身不证明专业性或准确性。 | 若更细的数据掩盖了同价成交、信号可得性或成本误差，且据此做未经对照的绩效排序，误导可能更强。须用同一策略、信号、样本和资金/估值口径验证；不能仅凭分钟曲线更平滑或回报更高作判断。 |

税费纠正：证券交易印花税向出让方征收；法定税率表列示千分之一，2023 年第 39 号公告自 **2023-08-28** 起减半征收，按这两项规定折算为卖出 **0.5‰（5bp）**。因此不能把“卖出千一”写成跨时期固定实收税率；历史回测仍须按交易日适用规则分段。[印花税法第三条](https://shanghai.chinatax.gov.cn/zcfw/zcfgk/yhs/202106/t458595.html)、[税率表说明](https://tianjin.chinatax.gov.cn/11200000000/0300/030005/20220725150235434.shtml)、[财政部、税务总局减半征收公告](https://www.mof.gov.cn/jrttts/202308/t20230828_3904235.htm)。

万三也不是所有账户的统一佣金合同；证监会公开答复说明佣金费用由双方协议约定并遵守相关规定。本报告不据此替用户指定券商收费或最低收费。[证监会佣金协议答复](https://www.csrc.gov.cn/csrc/c100210/c1498905/content.shtml)。采用总成本代理时，应先说明其覆盖范围，再决定是否拆分佣金、印花、过户；未经重新校准直接叠加，可能重复计算。

## B as-built 对照（以源码与 SSOT 为准）

建议代码统一为：**A＝仅文档钉清；B＝只读敏感对照实验；C＝行为改须人裁**。风险等级衡量结果被错误解释为可执行绩效的风险，不代表已测得的收益虚增：**高**表示有直接同价决策/成交机制或严重混比条件；**中**表示存在执行代理或证据缺口；**低**只表示该项未体现所讨论的同 close 信息问题。

### B.0 事实核实与 SSOT 边界

| 核实项 | 结果与引用 |
|---|---|
| 成交时钟与价格短表 | [成交核 SSOT §P1](../engine-ashare-correctness.md#p1-成交时钟合同human-go-closed-as-a2026-09-20)与[行业对齐计划 F-R6](../plan-industry-align-refactor-2026-09-18.md)一致：价格规则是**具名路径、非全量选价器、不含 v7**。源码核实不能只检索 `price_rule`，空标签也可能是真实成交。 |
| 主路径与符号核实 | 书引擎 open/close 取价、两只买入钟、默认双边 10bp、v7 独立仓位机、Mode B 独立入口均得到核实；本文按本次 BASE 的符号与行号引用。 |
| 税费表述修正 | 用户主张中的“卖出千一”缺适用期，按 A 节外部一手规则补正；不据此修改本仓研究费率，也不声称代理费率已经逐项包含现行法定税费。 |
| 历史计划状态修正 | [P3 费率计划](../plan-industry-align-p3-fees-2026-09-19.md)页首仍有“P4 deferred”的历史表述；本 BASE 的成交核 SSOT 已明确 **P1=A、P4=A closed**，P2=B 只落标签。费率合同仍是 P3.1/2/3=A/A/A，不用旧状态重开行为。 |
| Mode B 补充限定 | `assemble_instances` 实际传入 none 日线；虽复用的 Mode A 函数注释写“front close”，Mode B 的价格域以调用链为准。Q39 的常规退出与 Q38=A 的事后 oracle 是两条用途不同的路径，不能合称可执行策略。见[Mode B 组装](../../../backtest/research/unified_exit_modeb.py#L103)、[Mode A 取价](../../../backtest/research/unified_exit_modea.py#L234)、[oracle](../../../backtest/research/unified_exit_modeb.py#L752)。 |
| volume-cap 补充限定 | 已落地但默认关闭，只覆盖分钟书/v7 的显式调用。开启后，gap-open 因不能使用本根尚未完成的容量桶而被拒绝；不能理解成“基线所有成交照常、只扣一点量”。见[成交核 SSOT §2.4](../engine-ashare-correctness.md#24-p3-δ5-volume-participation-cap-productionhuman-go-caaa)。 |

对短表逐项核对如下。该表说明时钟与选价，不证明现实订单能够在该价成交。

| SSOT 短表项目 | 本 BASE 规则 | 对本次评估的约束 |
|---|---|---|
| 池买·分钟 | 名单日 T 的 14:55 close；缺该根才取 `[14:30,14:55]` 最后一根 close | 不是 T+1 open；还须核实名单在该分钟之前是否可得。 |
| 追买·分钟 | 通过持仓门、指数门后，自信号日后下一联合日历 session 起尝试；无报价继续 pending；可报价日 09:45 close，缺根用 `≤09:45` fallback | reason 保持 `chase:T+1`，不代表固定次日成交，更不代表当日 open。 |
| `minute_gap_open` | 分钟 `stop_loss:gap_open` 用该 bar open | 只命名此止损路径。 |
| `minute_trigger_bar_close` | 分钟 `stop_loss:touch` 用该 bar close | trail / profit_take / force_sell 等也有 close 成交，但不属于这个具名标签。 |
| 日线参照 | gap-stop＝触发日 open；stop-touch＝触发日 trigger；命中 `daily_same_bar_prefixes` 且通过涨跌停门才当日 close；只有实际写入 `pending_exit` 的 reason 才下一可卖日 open | 不能把日线概括成“一律 next-open”，也不能把分钟的 next bar 偷换成 T+1。 |
| `continuous` / `closing_call` 与估值 | P1=A：`closing_call` 只是 14:57–15:00 扫描窗口标签，不建模真实收盘集合竞价；P4=A：15:00 touch eligibility 与 official close/NAV mark 独立 | 标签不构成成交真实性认证。书 EOD mark 使用日线 close；不能因为某分钟成交资格受限就自动禁用该日估值。 |

以上规则出自[成交核 SSOT §P1、§P2、§P4](../engine-ashare-correctness.md)，并与[计划 F-R4～F-R8](../plan-industry-align-refactor-2026-09-18.md)对照。F-R6 锁价格路径；滑点、印花不是该计划的行为改造目标。书买入实现见 [`_buy_px` / `_chase_quotes`](../../../backtest/research/csv_minute_backtest.py#L487)，追买调度见 [`run_chase_due_day`](../../../backtest/research/csv_simulate_loop.py#L112)。

### B.1 主张①：当前 bar close 是否就是偷看，是否应一律 next-open

**书引擎 `csv_minute_backtest` 单独评估。** 模块说明与两个扫描实现都以 bar high 更新峰值、close 为现价，止损先检查 open；本次只读核对了 Python 分支及 numba 分支，未运行两者等价测试。源码入口：[模块说明](../../../backtest/research/csv_minute_backtest.py#L1)、[Python 扫描](../../../backtest/research/csv_minute_backtest.py#L240)、[numba 核心](../../../backtest/research/csv_minute_backtest.py#L179)。

| 路径 | 本仓现状 | 是否构成「同 bar close 偷看」类偏差 | 风险等级 | 建议 |
|---|---|---|---|---|
| gap-stop | 预设成本止损线；`open <= trigger` 时返回该根 open，成交前再过跌停门 | **否，就此选价而言。** 触发和价格不需要该根 close；仍有 open 是否可成交的执行代理问题。 | 低（同 close 问题） | **A** 写明 gap 例外；**B** 可单列开盘可成交性；改价属 **C**。 |
| `stop_loss:touch` | 未走 gap 后，以 close 收益率越过止损线触发，按同 close 成交；不是 low 触线即按止损线成交 | **存在同 close 触发/成交近似。** 若解释为 bar 完成后才发单，则是零延迟假设；若解释为预设保护规则的分钟代理，不宜直接称读了未来 bar。盘中曾跌破而收回也可能不触发，误差并非必然乐观。 | 中 | **A** 钉清 close-touch 含义；**B** 对照预设保护单与 close 确认后执行两种语义；统一改 next-open 属 **C**。 |
| trail / profit_take / force_sell | Python 扫描中止盈/回撤与时间强卖返回本根 close；峰值更新、峰值间隔门及策略回调共同决定是否触发 | close 确认的止盈/回撤存在同价执行假设；预定时间强卖不必等 close 才决定，但该 close 是否可成交仍未建模。不能因已知本 bar high/close 就断言读取后续 bar。 | 中；若宣称 close 后发单且精确同价成交，升高 | **A** 按 reason 解释；**B** 分开比较价格条件与定时条件；改扫描/取价属 **C**。 |
| 池买 14:55 | 名单日按 `_buy_px` 取 14:55 close，缺根取 14:30～14:55 最后 close；买门还可使用该报价 | **尚不能仅凭入口定罪或免责。** 名单与入场条件若已提前确定，可作定时成交代理；若依赖该 close 才生成，存在同价问题；若依赖更晚日终数据，则是更明确的信息越界。fallback 还涉及旧报价是否可执行。 | 中；证实名单晚于成交时点则高 | **A** 标注可得性未审计；**B** 先核实名单/因子时间戳；改 T+1 入场或取消 fallback 属 **C**。 |
| 追买 09:45 | `chase_decision(open_px, px, limit_up)` 用 09:45 close 判断 `px > open_px` 且非涨停，随后 `execute_buy` 仍用同一 `buy_px` | **是，存在直接的同价决策/成交机制。** 即使名单来自此前，追买条件本身仍依赖当前 close；尚无提交时刻/更细报价证明该价可在决策后获得。 | 高（执行解释风险，非已测收益虚增） | **A** 明写条件与成交共用报价；优先 **B** 对照决策后下一可交易 open；改追买条件/时钟属 **C**。 |

追买的直接证据是 [`chase_decision`](../../../backtest/research/csv_ledger.py#L115) 与 [`run_chase_due_day` 判断及成交调用](../../../backtest/research/csv_simulate_loop.py#L163)。[名单合同](../pool-csv-contract.md)规定文件名日就是买入日 T，但这一日期合同本身不证明名单在 14:55 前可得。本轮未审计名单上游生成链，不能把所有池买都判为已证实未来函数。

**Mode B `unified_exit_modeb` 单独评估。** `evaluate_exit_modeb` 的 Q39 合同与 fast/ref 实现都有“先 open-gap、后 close 触发/成交”的区分；它没有把 trigger 时点和 fill 时点拆成 next-bar 调度。fast 路径用 `ev` 表示事件，`fill` 数组表示成交代理价；ref 路径用条件与 `reason, fill` 表达同一规则。[fast `_first_hit`](../../../backtest/research/unified_exit_modeb.py#L495)、[公开入口及 ref](../../../backtest/research/unified_exit_modeb.py#L609)。

| 路径 | 本仓现状 | 是否构成「同 bar close 偷看」类偏差 | 风险等级 | 建议 |
|---|---|---|---|---|
| 入场与 open 退出 | 入场由 Mode A 实例取名单日 **none 日线 close**，不是书的 14:55。止损/止盈 open 越线时 fill=open；另有指数强卖的 open 路径 | open 退出本身不是同 close 偷看；日线 close 入场仍需证明名单可得时点。 | 中（入场证据缺口）；open 选价项低 | **A** 分开入场与退出钟；**B** 在 Mode B 自身口径内核实；改价属 **C**。 |
| close 退出 | 非 open 路径以 close 检查阈值/回撤并按该分钟 close 成交；high/low 不触发、不成交，peak 也按分钟 close 累积 | **有同 close 触发/成交近似。** 变量区分 trigger/fill 不等于成交已延后；不能套用书引擎 high 峰值来解释 Mode B。 | 中；按 close 完成后下单解释时升高 | **A** 写清 Q39；**B** 针对这些路径延后成交做对照；生产改调度属 **C**。 |
| Q38=A oracle | `oracle_exits` / `_oracle_from_path` 事后选择净收益最优的可用分钟 close；仅排除各跌停分钟，不模拟此前失败卖出 | **明确使用事后信息，但它是标识过的上界。** 不是常规 Q39 退出的因果策略，也不是“下一 bar 就能修复”的问题。 | 高（若误作可执行收益）；用途正确时边界清楚 | **A** 保持“事后上界”标识；**B** 与可执行规则分列；改变评价用途须 **C**。 |

**v7 `csv_minute_backtest_v7` 单独评估。** v7 不进 BOOKS、不使用书 `SimState`，不能用书价格短表或 P2 标签覆盖它。它显式透传 `FeeSchedule`，有自己的逐 lot 可卖检查。[`simulate_v7`](../../../backtest/research/csv_minute_backtest_v7.py#L315)、[`_sell_lots`](../../../backtest/research/csv_minute_backtest_v7.py#L256)。

| 路径 | 本仓现状 | 是否构成「同 bar close 偷看」类偏差 | 风险等级 | 建议 |
|---|---|---|---|---|
| 试仓 | 仅 `hm == 895`（14:55）用该根 close；缺根记 `skip_no_1455`，不采用书的尾盘 fallback | 同池买的可得性问题，不能从“严格 14:55”推出无偏。 | 中；证实名单晚于成交则高 | **A** 单列严格缺根规则；**B** 核实上游时点；改试仓钟属 **C**。 |
| 止损 | 仅当日扫描首根且 open 越过阶段止损线时用 open；其余检查/成交用 close | 首根 open 不是同 close 偷看；其余为 close 代理。与书“逐根先查 gap-open”的范围不同。 | 中（close 部分）；首根 open 项低 | **A** 写明首根限定；**B** 单独评估保护性止损语义；不得套改书规则，行为属 **C**。 |
| 加仓与 timer | 加仓用 close 调 `ladder_decision`，随后同 close `_buy`；timer 在最后一根记录按 close 卖出 | 加仓直接具备同价决策/成交机制；timer 是到期与末根记录的执行代理，不能混作价格信号。缺尾盘记录时“最后一根”也不等于官方收盘。 | 高（加仓）；中（timer） | **A** 拆开说明；**B** 优先对照加仓延后，timer 另列缺根情景；改仓位机/时钟属 **C**。 |

v7 取价与顺序证据：[止损、加仓、14:55 试仓和 timer](../../../backtest/research/csv_minute_backtest_v7.py#L387)。这些表只判机制与证据强弱，不推断不同规则的收益差值或固定方向。

### B.2 主张②：费用与显式滑点是否缺失，已有摩擦能否替代

| 引擎 | 本仓现状 | 是否构成「同 bar close 偷看」类偏差 | 风险等级 | 建议 |
|---|---|---|---|---|
| 分钟书引擎 | `COMMISSION=0.001`，`SimState` 的买/卖费率均取该常量，最低费为 0；共享账本按名义金额扣佣金。分钟 `simulate` **没有费率 kwargs，也没有显式 slippage 参数** | 费用本身不形成时间偷看；它不能补救 B.1 的信息/执行时点问题。没有滑点参数不等于没有成本，也不等于成本已经充分。 | 中；高换手/低容量且缺乏实盘校准时高 | **A** 写清佣金代理；**B** 保留代理基线后分解成本与滑点敏感性；改默认费率/增加滑点接线属 **C**。 |
| v7 | `_buy` / `_sell_lots` / `simulate_v7` 显式 `fee=DEFAULT_SCHEDULE`；默认也是双边 10bp、min=0；**没有显式 slippage 参数** | 不是同 close 偷看。费率相同也不保证最低费情景下跨引擎总费用相同。 | 中 | **A** 写清显式 schedule 与每次调用扣费；**B** 按 v7 自身成交粒度重估；行为改属 **C**。 |
| Mode B | 通过 `modea.COMMISSION` 取自 `ashare_fees`，买入成本乘 `1+0.001`，卖出所得乘 `1-0.001`；**没有显式 slippage 参数**，也没有书/v7 的 volume-cap 接口 | 不是同 close 偷看；不得把书的费用接线、容量门或最低费合同当成 Mode B 已实现功能。 | 中；误当完整执行仿真时高 | **A** 单列线性费用计算；**B** 在 Mode B 实例内对照成本；增加费用/容量行为属 **C**。 |

费率证据：[`ashare_fees`](../../../backtest/research/ashare_fees.py#L17)定义 `BILATERAL_10BP = FeeSchedule(COMMISSION, COMMISSION, 0.0)`、`DEFAULT_SCHEDULE = BILATERAL_10BP`；[`SimState`](../../../backtest/research/csv_ledger.py#L94)保存三个 float，**不读取 `FeeSchedule` 对象**，由 [`init_sim_state`](../../../backtest/research/csv_simulate_loop.py#L103)创建；[分钟签名](../../../backtest/research/csv_minute_backtest.py#L511)、[v7 签名](../../../backtest/research/csv_minute_backtest_v7.py#L315)、[Mode B 收支公式](../../../backtest/research/unified_exit_modeb.py#L350)分别核实。对上述入口及共享账本/循环/费率模块检索 `slippage`、`slip_perc`、`slip_fixed`、`滑点` 未发现独立滑点接线；该结论限定这些路径，不外推全仓。

[成交核 SSOT §1.1](../engine-ashare-correctness.md#11-研究费率合同p3-δ1-as-builtdocstests-only)与[P3 费率计划 F-R2～F-R5](../plan-industry-align-p3-fees-2026-09-19.md)明确：研究热路径仅做佣金记账，这是代理口径，**不等同现行印花税账单**；印花/过户只作边界说明，不能引入 live `trade_fee_policy` 或直接新增印花行。`QLIB_PORTANA` 的买 5bp / 卖 15bp / 最低 5 元只是日线 `--qlib-cost` 的可选费率合同，不是分钟默认，也不表示恢复 PortAnaRecord 引擎。

最低费按函数调用计：书 `_sell` 两次可触发两次最低费，v7 一次 `_sell_lots` 合并名义金额后只触发一次；默认 min=0 隐藏了这种差别。仅凭“缺独立印花/滑点列”既不能断言零摩擦，也不能断言双边 10bp 已足以覆盖真实成本。

已落地摩擦应纳入评价，但须保留覆盖范围：

| 摩擦 | 已实现事实与证据 | 仍不能证明什么 |
|---|---|---|
| 涨跌停与 defer | 书 E-R1 覆盖**任何卖因**，成交前检查选中 bar open 与拟成交价的跌停命中；买侧有涨停门与追买。见[书成交前门](../../../backtest/research/csv_minute_backtest.py#L682)、[SSOT E-R1～E-R4](../engine-ashare-correctness.md)。 | 有价格限制门不等于模拟了排队、盘口深度与冲击；不能据此认定一定能以 close 全额成交。 |
| T+1、数量/现金与缺行情 | 书扫描传入 T+1 可卖布尔，v7 `_sell_lots` 按 lot 过滤；买股整百、含费现金不足拒绝；书停牌/无 K 走冻结及估值路径。证据见[书扫描调用](../../../backtest/research/csv_minute_backtest.py#L643)、[书买账本](../../../backtest/research/csv_ledger.py#L232)、[v7 卖账本](../../../backtest/research/csv_minute_backtest_v7.py#L256)。 | 这些约束不能修复晚生成名单、同价信号或陈旧报价；缺 bar 与真实停牌也不能在解释上任意互换。 |
| volume-cap（书/v7） | `participation_rate: float \| None = None`，仅显式开启才创建 `VolumeCap`；预算 `floor(p×V)`，同桶买卖共享消耗，检查原始增量股数单位与 `available_at`，可限量/拒绝。源码 [`VolumeCap`](../../../backtest/research/ashare_volume_cap.py#L1)，合同 [SSOT §2.4](../engine-ashare-correctness.md#24-p3-δ5-volume-participation-cap-productionhuman-go-caaa)。 | 默认未启用；没有生产默认参与率，CLI/loader 未接容量。完整分钟 close 使用该桶容量仍是 completed-bar 近似；gap-open 的 `at=hm-1` 会拒绝本桶，不能冒用未来量。容量门不改成交价、不等于 slippage。 |
| v7 与 Mode B 的独立限制 | v7 首开及 held stop/add/timer 对缺昨收/未知板块在交易点拒绝，并过涨跌停门。Mode B Q7 在 open 跌停或拟成交价跌停导致失败后阻断当日后续卖出；入场有涨停等筛选。见[v7 分支](../../../backtest/research/csv_minute_backtest_v7.py#L398)、[Mode B 阻断](../../../backtest/research/unified_exit_modeb.py#L552)。 | 不能复制成“所有引擎门完全相同”。例如 Mode B 复用实例构造时缺前收仍可允许买入（[源码](../../../backtest/research/unified_exit_modea.py#L263)），并非书/v7 的同一拒绝合同。 |

### B.3 主张③：分钟曲线是否可能比日线更误导

| 对象 | 本仓现状 | 是否构成「同 bar close 偷看」类偏差 | 风险等级 | 建议 |
|---|---|---|---|---|
| 分钟书与日线书比较 | 二者买入钟不同，止损与 pending 的取价也分路径；分钟书费用固定继承默认，日线还有可选费率覆写；书估值仍按日线 close | **不能从曲线差直接归因。** B.1 的追买同价机制是具体风险，但跨粒度差异还混有入场、退出和配置因素。 | 中；未经对齐即作“分钟更真实”的绩效结论时高 | **A** 报告带齐时钟/费用/容量设置；**B** 固定信号与口径逐项对照；更换默认成交模型属 **C**。 |
| Mode B 与分钟书比较 | Mode B 日线 close 入场、close 峰值、独立实例及收支计算；分钟书 14:55 入场、high 峰值、书账本；Mode B 另有事后 oracle | **直接混比构成解释风险，不能由差值证明偷看。** oracle 若作可执行策略收益则使用了明确事后信息。 | 高（直接混比时） | **A** 明写不得直接对比 NAV 并宣称引擎优劣；**B** 先在同一引擎内消融，再做对齐桥表；统一引擎行为属 **C**。 |
| v7 与书/Mode B 比较 | v7 有独立阶段、加仓、严格 14:55、首根止损、末根 timer、费用调用粒度及估值实现 | 加仓同价风险已在 B.1 识别；其余曲线差不能自动视为时钟偏差。分钟粒度无法抹去策略与仓位机差异。 | 中；把差异全归因于分钟精度时高 | **A** 单列 v7 结果与合同；**B** 固定 v7 状态机做自身敏感性对照；跨引擎统一属 **C**。 |

因此，主张③可以作为验证假说，不能写成本仓已经发生的实证结论。本次源码审阅足以识别假设，不足以量化它们对收益、回撤或策略排名的影响。

## C 收束与人裁选项

**不自动改生产。** 本轮只交付本报告；不修改生产 Python 的成交、扫描、费率、仓位、估值、容量默认或 CLI，不新增测试或 pin，不执行敏感性回测。A/B/C 是本报告的建议分类，不覆盖既有人裁 P1=A、P2=B、P3.1/2/3=A/A/A、P4=A，也不自动授权新的行为切片。

| 人裁选项 | 具体内容 | 应交付的证据/判据 | 本轮状态 |
|---|---|---|---|
| **A：仅文档钉清** | 接受本报告对三项主张的条件化评价，列明书、Mode B、v7 分叉与成本边界 | BASE 可追溯，事实与条件推论分开；不把“全部 close 都偷看”“必须固定滑点”写为结论 | **本轮已执行，仅报告** |
| **B：只读时钟敏感对照** | 优先核实名单可得性、书追买和 v7 加仓；按路径对照基线与决策之后下一可交易 bar open；保护性 gap-stop 单列 | 信号可得时刻、bar 起止标签、触发时刻、候选成交时刻/价、未成交原因及逐笔差异；报告匹配率、净收益/回撤及排名变化，不能只报总 NAV | **建议后续选择，未执行** |
| **B：只读成本/容量敏感对照** | 保留双边 10bp 基线；另设明确覆盖范围的费用方案和滑点压力情景；书/v7 的 cap 开关作为独立轴 | 分离费用、滑点、容量各自贡献；记录最低费粒度、参与率、量可得时刻及 gap-open 拒绝数；不得把缺容量数据当零成本或无限流动性 | **建议后续选择，未执行** |
| **C：成交/扫描行为改变** | 决定哪些 close 确认信号延后、gap/定时单如何执行、缺 bar 如何处理，以及各引擎覆盖范围 | 另开计划，明确重开的时钟合同、预期经济变化与回滚；P1 成交窗口和 P4 估值轴分别裁决 | **须另行人裁，本轮不落地** |
| **C：费用/滑点/容量行为改变** | 决定代理费率是否替换、显式滑点怎样接线、是否启用容量默认；需要拆税费时先裁清覆盖与扣费粒度 | 先定义费用分解及适用期，证明不会在原代理上重复计入；保留研究与 live 边界，不导入交易栈费用模块 | **须另行人裁，本轮不落地** |

若后续选择 B，实验应读取已配置且实际存在的数据，输出到独立研究目录，不覆盖基线产物或改生产模块。先固定名单、策略参数、资金、价格域、复权/权益、费用与估值，再一次变更一个假设；Mode B、v7 和书引擎分别建立基线。改变成交时点会影响现金、后续可买和仓位，逐笔静态改价只可称局部价格敏感性，不能冒充完整策略重放。

滑点可先用每边 0/5/10/20bp 作为**未校准的压力档位**，不宣称它们是“合理默认”。next-open 对照须明确午休、隔夜、缺 bar、涨跌停、T+1 与容量规则；“信号后下一可交易 bar”只有在时间戳语义和订单延迟成立时才有意义。若缺少所需数据或可得性证据，应记录缺口，不输出伪精确收益结论。

本轮交付检查限于文档：引用目标存在、UTF-8 无 BOM、NUL 数为 0、diff 无空白错误；仅暂存此报告，由宿主 commit。未运行生产测试，未把既有测试名称或 SSOT 的历史验证记录当作本轮运行结果。
