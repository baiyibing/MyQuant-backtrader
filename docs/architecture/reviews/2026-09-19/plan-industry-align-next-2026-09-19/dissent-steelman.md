# dissent-steelman 对抗评审

## 1. 元信息

- 角色：dissent-steelman；强制反对主笔裁决，以代码和可反驳的验收条件为依据；本稿不计独立票。
- 对象：`docs/backtest/plan-industry-align-next-2026-09-19.md`。
- 日期：2026-09-19（Asia/Shanghai）。
- 工作目录：`/workspace/wt-industry-align-impl`。
- 实读规范：`docs/prompts/prompt-adversarial-subagent-review.md`。
- HEAD：`eb5eb6ca2c1f333e36aaaa72af5f749b8c1da3cb`；本地 `origin/master`：`41f3d11a34c665cc8a21b3e1d351b9e06b0466b5`。
- 本次仅静态审阅与只读 Git/路径检查；只写本评审文件。未改计划或业务 Python，未开 PR，未把 OSS 类比当行为证据。

## 2. 结论：BLOCKING

反对以当前文本作为实施验收依据：必跑 gate 不存在，无法兑现 Slice C。另有状态迁移和覆盖矩阵缺口，可能让“保持分叉”在验收时退化为“没有成交就算通过”。这不构成修复既有 fail-open 或重开 #112 的授权。

## 3. Findings

### F1 🔴 必跑 gate 在本树不存在，Linux/CI 同构验收无法成立

- **证据**：`docs/backtest/plan-industry-align-next-2026-09-19.md:153` 要求执行 `scripts/run_common_package_contract_gates.py`；`:128`、`:172` 要求 gates 通过、每条命令退出码为 0。亲验该脚本不存在。`.github/workflows/python-tests.yml:38` 起实际执行四个 `scripts/gates/verify_*.py`。计划 `:156` 注释中的 stream bundle 也不存在。
- **为何反对主笔**：这是验收不可执行，不是行号小错。删除失败步骤或以最后一次 freeze diff 的成功退出代替逐步成功，会得到伪通过；注释中的 stream 命令当前不执行，不能把它夸大为第二个必跑失败。
- **建议回填**：将 §7 必跑清单对齐本仓真实 CI 四个 data-free gates，明确解释器来自受控环境，逐条保存退出码并遇错停止。删除无本仓入口的 stream 示例或明确不适用，不从交易栈搬入脚本。同步 Slice C DoD。

### F2 🟡 卖侧分叉已有 pin，新增价值与“两层状态”验收仍不够可测

- **证据**：计划 `docs/backtest/plan-industry-align-next-2026-09-19.md:99` 至 `:106` 只列宽泛目标；`tests/test_ashare_simulate_predicates.py:119` 至 `:134` 已覆盖未知板块/无昨收 × daily/minute/v7 的卖侧差异。`backtest/research/csv_minute_backtest_v7.py:208` 至 `:210` 买入可因现金/股数失败，`:226` 至 `:231` 卖出可因没有 T+1 合格 lot 返回 0；`:367` 至 `:380` 加仓成功还会推进 stage。
- **为何反对主笔**：不能把已有六格卖侧测试当成本轮新闭环；“无成交”既可能是门禁拦截，也可能是门禁放过后账本拒绝。只测 predicate 或只断言 trades 为空都无法证明 F-R4，也抓不到加仓失败却错误推进 stage 的变化。
- **建议回填**：写出“已有/需新增/不适用”矩阵。复用现有卖侧 pin，新增真实 held-path 下的 stop/add/timer 用例，分别覆盖 `None` 原因、触发前提、门禁返回、账本调用及成交/不成交结果。用测试侧 spy 保留真实实现，断言 cash、lots、stage 和 reason；现金不足与 T+1 阻止成交须各有一例。缺昨收的首次建仓应断言 `skip_no_prev_close`，未知板块应断言 `skip_unknown_board`，不能合并。

### F3 🟡 chase 在拒绝门禁前已消费 pending，存在本轮运行内的不可逆窗口

- **证据**：计划 `docs/backtest/plan-industry-align-next-2026-09-19.md:31` 仅称 shared helpers 拒绝未知板块。`backtest/research/csv_simulate_loop.py:140` 至 `:145` 显示无报价时保留 pending，有报价后立即 `pending_chase.pop(code)`；随后 `:155` 至 `:157` 才因 `limits is None` 计数并跳过。
- **为何反对主笔**：两个分支都无成交，但一个保留未来尝试，另一个消费尝试资格。把“拒绝”写成“冻结”或把门禁重排到 pop 之前，会改变次日行为；单日 trades/cash 检查发现不了。这里的不可逆是本次模拟状态已丢失 pending，不是声称发生外部不可逆交易。
- **建议回填**：分叉矩阵增加 pending 生命周期，合成两日用例分别锁住“缺报价仍 pending”和“报价存在但未知板块已移除 pending”。记录它是既有行为，禁止顺手改成统一重试；若本船不补测，明确列为未覆盖，不能宣称 helpers 契约完整。

### F4 🟡 “已有 halt/ST 覆盖”把估值、成交冻结与名称时间语义混在一起

- **证据**：计划 `docs/backtest/plan-industry-align-next-2026-09-19.md:47`、`:48` 的复用表；`tests/test_csv_daily_backtest.py:964`、`:986` 测缺 bar 时估值，真正零量买卖冻结测试从 `:990` 起，成交断言在 `:1050`。`tests/test_daily_mark_cache.py:30` 至 `:36` 也只验证 mark。`tests/test_csv_minute_backtest_v7.py:199` 至 `:205` 只输入静态 ST 名称；窗末名称平铺发生于 `backtest/research/ashare_session.py:81` 至 `:85`、`:97`。
- **为何反对主笔**：估值正确不能证明不能买卖；静态 ST 5% 涨跌停带测试不能证明名称平铺的非 PIT 语义被锁住。计划以 halt/ST 为主主题之一，却在 Slice A 仅明确列出 limits 分叉，允许这些语义缺口随“复用现有测试”被带过。
- **建议回填**：纠正 halt 锚点，分别列缺 bar、零量占位过滤、买卖冻结和 mark 的覆盖路径；不可将 daily loader 的测试外推为 v7 全路径证据。ST 增加跨日期名称变化的合成契约及入口传递断言，锁住现状而不修 PIT；或缩小本船承诺并显式登记未覆盖项。

### F5 🟡 九文件冻结只能证明局部无 diff，不能证明全部生产代码冻结

- **证据**：计划 `docs/backtest/plan-industry-align-next-2026-09-19.md:61`、`:192` 仅允许 docs 与 data-free tests；`:159` 至 `:168` 的验收只比较九个路径。`backtest/research/ashare_session.py:21` 至 `:24` 依赖 `csv_pool`、`exdiv_map`、`market_layer`、symbol normalizer，它们不在该冻结表。
- **为何反对主笔**：修改表外 `market_layer` 的限价行为，九文件 diff 仍能通过。这里给出的是验收反例，不是指控当前存在该修改。若据此宣称全生产行为零变更，证明强度不足。
- **建议回填**：保留九文件重点冻结检查，额外检查 base→HEAD 全量 changed-path 清单只含授权 docs/tests，并在实施交接中要求工作区干净；明确任何表外生产代码变化同样失败。此为变更范围检查，不扩张既有热路径 import 扫描，也不要求枚举所有业务依赖。

## 4. 对 P1–P4 默认“继续后置”的独立立场（不计票）

| 裁点 | 独立立场 | 条件与理由 |
|---|---|---|
| P1 | 支持继续 A | #112 已裁 A；本船没有 14:57–15:00 新撮合证据。F2 的门禁测试不授权过滤该时窗，不选 B/C。 |
| P2 | 支持继续 A | 不加 trades 输出列。用测试 spy、状态断言实现可观测性，不把测试困难变成 schema 变更理由。 |
| P3 | 附条件支持继续 A | 不改费用、ST PIT 或 v7 fail-open；必须将“冻结已知差异”与“已验证正确”分开，补 F2/F4 的边界记录。延后修复不应延后说明风险。 |
| P4 | 支持继续 A | 触价资格与标记用途仍独立；F4 的估值测试不能代替成交冻结证明，反之亦然。 |

依据：`docs/backtest/plan-industry-align-refactor-2026-09-18.md:129` 至 `:134` 已记录 A/A/A/A；当前计划 `docs/backtest/plan-industry-align-next-2026-09-19.md:74` 至 `:79` 保持后置。反对的是当前验收方案的充分性，不是推翻上述已裁边界。

## 5. 亲验清单结果

| 检查 | 结果 |
|---|---|
| cwd / HEAD / origin/master | `pwd` 与 `git rev-parse HEAD origin/master` 实查，值与元信息及 BOX_FACTS 一致。未 fetch，不声称验证远端实时 tip。 |
| IMPLEMENTATION_BASE vs origin/master | 计划头部 `:5` 与本地 origin/master 均为 `41f3d11a34c665cc8a21b3e1d351b9e06b0466b5`。ancestor 检查退出 0。 |
| §7 bash 一致性 | `:139` SHA 与头部一致；不存在 SHA 漂移。命令路径存在性与 CI 同构性有 F1 所述缺陷。仅 ancestor 检查不足以保证未来实施时仍为当时 master tip，实施开工需重核 F-R10。 |
| pytest 路径 | 五个文件均存在：`tests/test_ashare_session.py`、`tests/test_ashare_simulate_predicates.py`、`tests/test_csv_daily_backtest.py`、`tests/test_csv_minute_backtest_v7.py`、`tests/test_daily_mark_cache.py`。路径存在不等于已运行通过。 |
| gate 路径 | `scripts/run_common_package_contract_gates.py` 缺失（必跑）；`scripts/run_stream_execution_contract_bundle.py` 缺失（注释，当前不执行）。 |
| 冻结表 | §8 九个生产文件全部存在；逐项对照 §7 一致。执行列出的 base→HEAD 九路径 diff，退出 0、无输出。局限见 F5。 |
| book limits=None | `csv_daily_backtest.py:321`、`csv_minute_backtest.py:601`、`csv_simulate_loop.py:155` / `:260` 确为 early reject。缺昨收可在上游退出，例如 minute `:580` 至 `:582`，不应一概声称增加 unknown-board 计数。 |
| v7 limits=None | `csv_minute_backtest_v7.py:389` 至 `:391` 首次建仓拒绝 priced=None；held 路径 `:326` 计算 limits，`:342`、`:367`、`:402` 使用 predicates。`ashare_session.py:73` 至 `:78` 在 None 时返回 False，确为 fail-open；能尝试不等于必成交。计划核心描述准确。 |
| 已有分叉测试 | `test_ashare_simulate_predicates.py:119` 至 `:134` 已锁住 v7 卖出、book 冻结的两种 None 来源，不能漏报或宣称此前无 pin。 |
| halt 锚点 | `test_csv_daily_backtest.py:964` 是 equity mark；零量买卖冻结从 `:990` 起。 |
| 是否静默重开 #112 P1=B/C | 未发现。§4 明确保持 A，F-R2/F-R8 与非目标禁改 fill-clock。#112、#108 已 MERGED 采用用户 BOX_FACTS；本次未联网重新查询 PR。 |

## 6. 未验证项

- 未运行 pytest 或 CI gates，未安装依赖；本次结论不包含任何测试通过声明。未隐式调用系统 Python。
- 未执行真实回测、读取 F 湖或生产行情；F2/F3 的新增反例是据控制流提出的待实现测试，不冒称已动态复现。
- 未完成全仓 ST/停牌测试覆盖盘点，也未证明 v7 所有输入适配路径具有相同零量处理；F4 只否定所引证据足够，不断言全仓完全无测试。
- 未验证未来实施分支、表外全部生产依赖及真实 CI 环境；本次 freeze 结果仅覆盖列出的九文件与当前 SHA。
- 未核验交易所规则、OSS 实现或远端 PR 页面；这些均不作为本稿行为结论依据。
