# pattern-evidence

## 结论

**支持 §3 仅保留 δ2 的 docs-only 主船；建议补充以下证据限定后进入未来人裁/实施。未发现要求重做 E-R6、接入 StockDataReader 或复活 chip_indicator 的依据。** 本路发现 1 项 P2 文档/验收定义缺口及 3 项 P3 补证项；没有 P0/P1 生产阻断结论，也不把已明确 deferred 的风险重新包装成实施要求。

审查对象为 `docs/backtest/plan-industry-align-p3-d2-exdiv-2026-09-19.md` v0.1，已先完整读取 1–323 行。下文简称“plan”，全部行号对应本次读取版本；生产文件在本次 HEAD 与固定基线之间无差异。

开工基线核对：

- `git rev-parse HEAD`：`23024cc5bd93eeac777607eea13616058ab0f085`。
- `git rev-parse origin/master`：`1ad010cca013afe8186f20275cbdcca71e500823`，等于 plan:5 的 `IMPLEMENTATION_BASE`。
- `git merge-base --is-ancestor 1ad010cca013afe8186f20275cbdcca71e500823 HEAD`：exit 0。固定基线至 HEAD 仅新增该 plan，323 行；开工工作区干净。这里检查的是本地 remote-tracking ref，未 fetch。
- 静态核对：plan UTF-8 有效、BOM=0、NUL=0；基线至 HEAD 的 `git diff --check` 通过。§8.3 数组与 §9 表格的 15 个生产路径逐项一致，包含 δ1 原清单全部 10 个路径。没有执行 pytest、gates、回测、湖读取或生产模块导入。

本路按“怀疑过度类比”独立审查，仅产出此文件；未 spawn 子 agent，未嵌套执行 codex，未代写其他两路或 host 共识。

## Findings（file:line）

**PE-01 · P2 · “qlib 连续域”应限定为日线源约定，B6 需要明确 daily/minute 源组合。**

- Plan 锚点：`docs/backtest/plan-industry-align-p3-d2-exdiv-2026-09-19.md:67`、`:68`、`:69`、`:148`、`:181`。daily 的跳过分支描述正确；问题是“front/back/qlib 连续域”与 minute/v7“无跳过分支”并列后，没有说明 `qlib_day` 和 `qlib_1min` 不是同一个价格域约定，B6 也只明确了 daily 的四态。
- 实现证据：`backtest/research/ashare_bars.py:98` 路由 `qlib_day`，`:217` 路由 `qlib_1min`。`backtest/research/qlib_bin_daily.py:6` 声明本仓日线 dump 的 close 是后复权，而 `backtest/research/qlib_bin_1min.py:4` 声明分钟 dump 来自 none 湖。不能只信这些声明：实际日线读取在 `backtest/research/qlib_bin_daily.py:94` 取 `close.day.bin`；分钟在 `backtest/research/qlib_bin_1min.py:46` 取 `close.1min.bin`，`:57` 起直接组帧，二者均未在读取时做域转换或校验。`tests/test_qlib_bin_1min.py:33`、`:43` 也只是写入/读出数值原样相等，不能认证真实 dump 的域。
- 实际分叉：`backtest/research/csv_minute_backtest.py:845` 和 `:852` 分别选择日线、分钟源，`:883` 无条件加载 map；v7 在 `backtest/research/csv_minute_backtest_v7.py:563`、`:565` 分别传源，`:571` 加载 context。因此 `minute=qlib_1min,daily=lake` 按仓内约定仍可为 none/none，保留 E-R6 本身不是“连续域遗漏跳过”；`daily=qlib_day` 则存在另一种域组合，不能用同一句“qlib”概括。
- 影响：未来实现者可能把“统一跳过”理解为看到任何 qlib 源就关闭 map；也可能把捕获 `exdiv=None` 的接线测当作真实输入已经连续的证明。本计划冻结生产，故这是未来合同定义缺口，不是要求本 PR 修入口。
- 建议回填：在 §2.3 将 daily 的“qlib”明确为 `qlib_day`，补两种 bin 的仓内域约定及“读取器不认证域”。B6 对 minute/v7 明确 `daily_source∈{lake,qlib_day}` × `minute_source∈{lake,qlib_1min}` 的受控接线预期：**当前各组合仍加载/传递 map**。这些 pins 只记录现状，不据此宣称所有组合域一致，不改变 F-R5。

**PE-02 · P3 · 既有 v7 trial-stop 向量是局部布线证据，夹具不能直接升级为同域验收 oracle。**

- Plan 锚点：`docs/backtest/plan-industry-align-p3-d2-exdiv-2026-09-19.md:99`、`:178`、`:179`。盘点写“trial stop 的公开 simulate_v7 路径”本身属实，但缺少这一向量特有的证据限制。
- 夹具证据：`tests/test_csv_minute_backtest_v7.py:296` 的 D1 14:55 分钟价为 100，`:297` 却把同一 D1 日线 close 设为 50；`:300` 又在 D2 注入 k=0.5。该测试不是日线/分钟一致的 none 夹具。
- 按代码静态推演：`backtest/research/ashare_session.py:59` 将 D1 的 50 再映射成 25；`backtest/research/csv_minute_backtest_v7.py:328`、`:329` 将它用于档位。与此同时 trial stop 由 `backtest/research/strategy7_rules.py:52` 给出，100 的存量参考缩放后止损线是 45。D2 价 48 不触发该止损，即使 held 路径的昨收映射被遗漏，`:303` 的无止损断言仍能成立。它不能同时证明持仓缩放、同域昨收及档位数值链完整正确；独立的初次买入档位测 `tests/test_csv_minute_backtest_v7.py:238` 也不是这个 held 场景。
- 建议回填：§2.5 注明此为人为隔离的止损布线向量。未来 B3/B4 增加日线与分钟一致的 held 夹具，并分开断言缩放值、映射昨收/档位及交易结果。例如买入 100，下一交易日真实收盘 96，再下一事件日 k=0.95、价格 90：未缩放止损线 90 且原档跌停 86.4，缩放后止损线 85.5；可避免靠不一致的昨收解除跌停拦截。该示例是静态设计建议，未运行，不要求本次修改测试。

**PE-03 · P3 · B3 应区分 helper 保留字段与正常 simulate_v7 可达状态。**

- Plan 锚点：`docs/backtest/plan-industry-align-p3-d2-exdiv-2026-09-19.md:41`、`:99`、`:178`。`add1_A1` 的非空缩放分支确实存在，但与其他字段并列为“完整集合”时，未交代如何取得非空状态。
- 代码证据：`backtest/research/csv_minute_backtest_v7.py:73` 默认 `add1_A1=None`，`:194`、`:195` 只在非空时相乘；正常建仓在 `:215`、`:216`，加仓记账在 `:219`、`:220`，阶段迁移在 `:374` 至 `:383`，均不赋非空 `add1_A1`。本次在 `backtest/` 与 `tests/` 对该精确标识符的检索只有默认声明和这两行缩放。`simulate_v7` 在 `:288` 自建空状态，也没有 initial-position 参数。
- 影响：正常公开入口测试无法自然覆盖该非空分支。若为满足“全字段公开接线”临时改生产赋值，就会越过冻结；若注入状态后仍宣称它是自然加仓可达字段，也会夸大证据。
- 建议回填：明确 B3 的两层证明：helper 层人工构造非空 `add1_A1`，钉乘法及 None 保留；公开入口层钉自然可达字段、存量/新买/加仓顺序与原股数现金。Plan 已写“不只调用私有 helper”，并未禁止这种组合，所以本项是补足验收定义，不是认定计划不可实施。

**PE-04 · P3 · 应补 v7 除权接线的历史来源，避免把原 E-R6 人裁外推到全部后续引擎。**

- Plan 锚点：`docs/backtest/plan-industry-align-p3-d2-exdiv-2026-09-19.md:21`、`:41`、`:169`。当前 plan 依据固定基线纳入 v7 正确，但“E-R6 已落地”的统一叙述缺少历史范围分界。
- 文档证据：原 `docs/backtest/plan-exdiv-refprice-2026-09-16.md:59` 的 X-R4 明确 v7 不接；`:66`、`:76` 的人裁同样如此。当前 `docs/backtest/engine-ashare-correctness.md:96` 则已经包括 v7。代码现状在 `backtest/research/csv_minute_backtest_v7.py:187` 和 `:325` 确有独立缩放实现与调用。
- Git 补证：`git log -S '_rescale_position' -- backtest/research/csv_minute_backtest_v7.py` 与对应 diff 显示，该 helper 及接线由 `28c4ce265c1136d9559ecad512217b54e95d2acd`（2026-09-18，shared A-share session/bars/fees）引入，早于本次固定基线。不是 δ2 新增，也不是 2026-09-16 原片已包含。
- 建议回填：在本 plan §2 或未来 Slice A 加一句沿革，区分“原 E-R6 书侧落地”与“后续 shared-session 改造纳入 v7”。保留旧 plan 的历史人裁，不为消除表面冲突改写历史范围；本项不要求重审或回滚既有生产接线。

## 对 plan §3 / 主船范围的独立裁决

**同意 δ2 单船，维持 docs-only / 默认生产零 diff；不从任何类比推导实施 GO。** δ1 的费率结论、δ3/δ4/δ5 及 P1/P2/P4 继续按 plan:110–116、`:124`、`:130` 冻结。PE-01 应在未来 B6 实施前明确；PE-02 至 PE-04 可通过计划补注及已有 Slice A/B 落点解决，无须扩大主船。

必查项的独立复用裁决如下：

| 对象 | 裁决与证据 |
|---|---|
| `chip_indicator` | **不复用、不复活。** 当前 `git ls-tree HEAD -- backtest/chip_indicator.py` 无条目；删除提交为 `59ba18db9886b3f1afad2ce9cd795683c35ef693`。现行 `docs/backtest/engine-positioning-ssot.md:7`、`:30` 明确宿主壳退场。保留的筹码逻辑在 `oskh_factors/chip/core.py:403`、`:416`、`:429` 计算分布和因子，不是投资组合 lot 的除权账本；“筹码成本”与 lot cost 名称相似不足以构成复用依据。 |
| `StockDataReader` | **δ2 不接入、不改造。** `oskh_data/reader.py:363` 的接口读股票 bars，`:369` 默认 front，`:380` 对 `as_of_date` 直接抛 NotImplementedError；不是事件枚举或时点因子比接口。构造器还解析数据根并可能初始化数据库（`:153`、`:180`）。真实 chip 消费者在 `backtest/research/chip/filter_chip_stocks.py:74` 读取 front 窗口计算因子，不能据此推导 none 撮合链必须替换现有 loader。 |
| 现有 loader / resolver | **保留各自职责。** `backtest/research/csv_daily_loader.py:108` 默认 none，`:94`、`:96` 做去重/零量处理；`backtest/research/exdiv_map.py:246`、`:249` 经 resolver 定位两份散装源，再按 `:294`、`:305` 计算有效行比。`common/infra/data_root.py:155` 在根未配置时抛错，与 map 已解析后缺文件返回空的 `exdiv_map.py:258` 不同。Plan:74 已正确区分，不应照“统一读取层”的口号重写。 |
| book 与 v7 账本 | **共享事件和市场事实，保留缩放实现分叉。** `backtest/research/csv_ledger.py:155`、`:156` 只改 cost/peak；v7 在 `backtest/research/csv_minute_backtest_v7.py:191` 至 `:196` 改独立字段并重建 Lot 值。`docs/backtest/engine-ashare-correctness.md:22` 明确 v7 不进 BOOKS、不 import 书的 SimState。无需为了“统一一次性事件”新建共同账本或通用公司行动框架。 |
| NP2 / `exdiv_hold_hits` | **可复用日期规范化，不能复用为完整经济审计证明。** `backtest/research/exdiv_map.py:26` 仅复用 `normalize_date`，其实现见 `backtest/research/exdiv_hold_hits.py:129`。NP2 自有的 parity-secondary 口径在同文件 `:38`、`:41`，不同于 map 的事件兜底规则；import 一个 helper 不等于将 NP2 诊断口径纳入撮合合同。Plan:102、`:303` 的范围处理合理。 |
| Mode B | **不移植其经济模型。** `backtest/research/unified_exit_modeb.py:421` 至 `:426` 先改 cost、shares、mark，后检查分钟切片；书侧在 `backtest/research/csv_minute_backtest.py:589` 至 `:601` 先过缺 bar 分支，再只缩参考价。shares/=k 与停牌事件处理均不等价。Plan:102 已明确排除，不能借同名 exdiv map 宣称两条链的 NAV/停牌行为相同。 |
| import fence | **保留固定范围，不扩扫描。** `tests/test_ashare_simulate_import_fence.py:13` 是固定枚举，`:45` 至 `:48` 是具体禁入项，`:63`、`:64` 对枚举文件检查；`:95` 还明确允许 bin readers 与 qlib_cost。其通过只能支持规定边界，不能认证事件数学、全部传递依赖或第三方引擎同构；plan:101、`:133`、`:183` 没有越界扩大证明。 |

文档漂移还须在未来 Slice A 如实收口：`docs/backtest/engine-ashare-correctness.md:95` 仍概括“日线/分钟全程 none”，`:96` 用 cost/peak 总括 v7；实际 daily front/back/qlib_day 路由与跳过见 `backtest/research/csv_daily_backtest.py:568`、`:585`，v7 字段差异见其 `:191` 至 `:196`。本 plan:63–72、`:169` 已把这些差异及同步任务写明，故**不重复报为未覆盖的新阻断项**。未来同步应限定陈述适用入口，不以文档整齐为由统一生产行为。

`README.md:75` 对 StockDataReader 的概括也不能读成所有路径强制经同一类：`README.md:49` 本就同时允许 `oskh_data` / resolver，现有 CSV 实现实际直接使用 resolver。此处采用实现和具体路径合同，未因总览措辞要求扩大修改范围。§10 只列概念类比、明确不作行为证据（plan:312–317），本路不要求增加外部框架背书。

## 未验证

- 未运行 pytest、CI gates、任何 CLI/内存回测；上面的测试评价来自源码阅读，数值反例为静态推演，不是运行成绩。未来 B1–B6 是否实际收集、执行并满足 DoD 尚未验证。
- 未读取真实湖、真实 qlib bins、公司行动源或外部仓库。`qlib_day`/`qlib_1min` 的域是仓内消费约定；本路没有把注释或合成读写测试当作真实数据域认证。
- 未 fetch、访问 PR 服务或确认远端最新 master；基线结论仅针对本地提交对象和 ref。提交历史证明 v7 接线引入时间，不证明当时 PR 的全部人裁记录。
- 未证明完整传递依赖闭包，未验证经济守恒、任意停牌事件补偿、真实缺失率或收益误差大小。Plan 对这些保留项的声明不能替代未来实现验收。
- 本报告没有回填 plan、修改旧文档或测试；本次唯一写入路径为本文件。其他两路及 host 综合结论不在本路验证范围。

## 模型与 effort（写你实际用到的）

- 本次执行身份：Codex / GPT-6（会话提供的模型身份）；全程同一会话，无子 agent、无第二层 codex 调用。
- 精确 model ID 与运行时 reasoning effort 未向本会话暴露，未自行指定或切换；可见的父进程参数也未返回可核验值，故记录为**未验证**，不猜测。
- `docs/prompts/prompt-adversarial-subagent-review.md:28` 所述 `gpt-6-astra` / `xhigh` 是提示文档中的默认档位说明，不是本次运行元数据，不能据此冒填实际值。
