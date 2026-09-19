# dissent-steelman

## 结论

**BLOCKING：反对主笔“v0.2 已无 blocker”的裁决；不反对 delta1 单船方向。** 当前文本还不能作为“费用契约可测、生产行为冻结”的实施放行依据。最重要的缺口是：E-03 用涨跌停分叉测试替代了费用接线测试；最低费用的计收单位未进入验收契约；E-05 的冻结清单仍遗漏能改变成交窗口的生产依赖。原主笔放行结论见 `docs/architecture/reviews/2026-09-19/plan-industry-align-p3-fees/adversarial-errata.md:36`。

审查对象已先全文读取：`docs/backtest/plan-industry-align-p3-fees-2026-09-19.md`，Proposed v0.2，共 227 行；以下 plan 行号均据此版本。文件 SHA-256：`acf6f90b506a451e7e272462cc01d0f1441b675a25b098c9c290fc86bec136da`。旧评审中引用的 v0.1 行号不作为当前 plan 的定位依据。

开工基线核对（实际执行的只读 Git 命令）：

- `git rev-parse HEAD origin/master`：两者均为 `9e2e9eb774345d0d0bf6075192739780a3f0ee47`，提交标题为合入 P3 fee plan 的 PR #116。
- plan 固定的 `IMPLEMENTATION_BASE` 为 `c65b10dd6d26342bd9ec1cbed5465d875f82470f`，见 `docs/backtest/plan-industry-align-p3-fees-2026-09-19.md:5`、`:144`；它是当前 HEAD 的祖先，`git merge-base --is-ancestor` 返回 0。
- 按 plan §8 的十个冻结文件执行 `git diff --exit-code <IMPLEMENTATION_BASE> HEAD -- <十文件>`，返回 0。这只证明这十个文件在两提交间无差异，不证明依赖闭包冻结。
- 当前本地 `origin/master` 已不等于 plan 基线。按现有值推演，§8 `:149-151` 的比较会停止；本次没有 fetch，因此不宣称核验了远端最新 tip。此处是正确的 fail-closed，不应删掉比较来求绿。实施前须记录基线迁移及漂移审查，本次不替主笔改 SHA。

本路仅做静态审查和只读仓库核对；未运行 pytest、验收脚本、模拟或回测，未修改 production Python，未启动子 agent 或嵌套 `codex exec`。开工已有暂存文件 `scripts/run/run_codex_adversarial_lanes.py`，未触碰。

## Findings（file:line）

### D-01 · HIGH / 阻断放行：E-03 的“已覆盖”换了被测问题

**证据。** 原 dissent 指出的缺口是 daily 的费用 override、minute 默认继承及 v7 显式 schedule 的差异，见 `docs/architecture/reviews/2026-09-19/plan-industry-align-p3-fees/dissent-steelman.md:20-24`。主笔的修复仅是把 predicates 文件加进 quick suite，见 `docs/architecture/reviews/2026-09-19/plan-industry-align-p3-fees/adversarial-errata.md:29`。当前 plan 又把这项写成 unknown-board / `limits=None` 分叉，见 `docs/backtest/plan-industry-align-p3-fees-2026-09-19.md:125`、`:157-160`，并在 `:226` 记为已补 asymmetry pin。

实际的 `tests/test_ashare_simulate_predicates.py:122-135` 只断言卖因、价格、仓位和未知板块计数；v7 helper 在 `:68-72` 不传 `fee`。费用单测在 `tests/test_ashare_fees.py:10-24` 检查两个 schedule 的少量公式结果及同一函数的 re-export，没有调用 ledger 卖出、daily CLI 的 `--qlib-cost` 接线或 v7 自定义 schedule。仓库另有有效的 ledger 买入扣款测试 `tests/test_qlib_bin_daily.py:129-135`，但没有列入本 plan 的 quick suite；不能笼统说全仓无费用测试。

**最小反例。** 即使丢掉 daily CLI 的 `min_cost=QLIB_MIN_COST` 传参，或把 v7 某个 `fee=fee` 转发漏掉，上述 limit 谓词断言也不是费用 oracle。真正接线分别在 `backtest/research/csv_daily_backtest.py:683-685`、`backtest/research/csv_minute_backtest_v7.py:352-354`、`:396-397`。这是对测试能力的静态反例推演，未作 mutation 实验；完整冻结检查可另行拦住这些生产文件改动，但不能因此把 predicates 宣称为费用契约测试。

**要求回填。** E-03 应标为未闭合。未来 Slice B 须明确费用断言及其落点：daily CLI 开关两态的参数传递、状态有效 rates/min；minute 默认 rates/min；v7 非默认且买卖不对称的 schedule 传递；真实扣款、入账、commission/cash 的数值。金额须同时覆盖 floor 区和比例区，否则最低费用会掩盖费率接反。可复用现有有效测试；不要求本次 docs-only 审查新增或运行测试。`DEFAULT_SCHEDULE is BILATERAL_10BP` 本身也不能证明书引擎默认值：`SimState` 直接绑定 `COMMISSION`，见 `backtest/research/csv_ledger.py:87-89`。

### D-02 · HIGH / 阻断放行：“min 5”没有计收单位，无法验收跨引擎契约

**证据。** 主船明确包含 floor behavior 和 daily/minute/v7 consumption map，见 `docs/backtest/plan-industry-align-p3-fees-2026-09-19.md:13`、`:66`、`:80`。但 Slice B 的 formula parity 只明确 ledger/shared loop，见 `:123-125`；未要求逐 lot 与合并卖出的计收单位。书引擎逐个 `pos` 调用 `_sell`，见 `backtest/research/csv_daily_backtest.py:325-333`；每次 `_sell` 单独计算佣金，见 `backtest/research/csv_ledger.py:242-245`。v7 则合计全部可卖 lot，再对 `sold * price` 调一次 `credit_sell`，见 `backtest/research/csv_minute_backtest_v7.py:226-243`。

**最小反例。** 在两笔 lot 都满足 T+1、各为 100 股、卖价均为 10 元、同次退出的条件下，两侧显式采用 15bp/min5：书账本两次各收 5 元，总计 10 元；v7 一次合计 2,000 元，收 `max(3, 5)=5` 元。相同公式、相同 rates/min，并不产生相同总费用。此例为源码算术推导，不是回测结果，也不是要求修正既有双账本差异。

**要求回填。** 费用合同应写“按哪次调用/哪种成交分组收 floor”，并为上述双 lot 例固定两个不同期望值；v7 自定义 schedule 的核验不能从 delta1 中漏掉。另须写清 EOD_MARK 属估值而非卖出，其 commission 明确为 0，见 `backtest/research/csv_simulate_loop.py:324-337`。这些都是 delta1 内的 as-built 契约，既不需要改成交行为，也不应留给 stamp-tax 或 P2 后续方案。

### D-03 · HIGH / 阻断放行：E-05 仍不能证明 P1/P4 冻结，存在具体漏网依赖

**证据。** v0.2 宣称扩大 freeze 集合保障 P1/P2/P4，见 `docs/backtest/plan-industry-align-p3-fees-2026-09-19.md:226`；实际十文件数组和 diff 见 `:169-184`。其中没有 `ashare_bars.py`、`csv_daily_loader.py`、`strategy5_rules.py`，而前船冻结表明确包含它们，见 `docs/backtest/plan-industry-align-next-2026-09-19.md:226-230`。

**最小反例。** `backtest/research/ashare_bars.py:28` 的 `PM_CLOSE` 决定 `_in_session` 上界（`:302-306`），实际 lake reader 使用该筛选（`:350-355`）。若它从 15:00 改成 14:56，14:57–15:00 的输入 bar 就会消失，plan 中十文件可以完全不变。import fence 虽枚举了该模块，却只检查 imports，见 `tests/test_ashare_simulate_import_fence.py:22`、`:32-49`、`:61-64`；它不是字节冻结。quick predicates 的分钟数据直接造在 14:55，见 `tests/test_ashare_simulate_predicates.py:37-40`、`:65-80`，不能证明 reader 保留了尾盘窗口。未实际修改常量或运行测试，本反例定位的是验收缺口。

另一个直接行为依赖是零量过滤 `backtest/research/csv_daily_loader.py:83-85`；遗漏它同样无法由十文件零 diff 推出停牌输入行为不变。

**要求回填。** E-05 不能列为充分修复。除补齐已确认的有限依赖外，增加“本实施增量只能改 docs 和 data-free tests”的变更路径检查，并覆盖提交、暂存、工作区及新增文件；明确测试目录也不能用作生产依赖的新入口。冻结表与命令数组保持一致。此建议是 Git 变更范围校验，不是把 import 热路径扩成 research 全目录扫描；不改变 `AGENTS.md:21` 的固定清单限制。

### D-04 · MEDIUM：不可逆窗口在现金门和证据持久化处，当前合同没有说明如何观察

**证据。** book 买入先判断 `notional + comm > cash`，通过才减 cash、建立 lot，见 `backtest/research/csv_ledger.py:210-220`；per-name 预检会直接跳过该候选，见 `backtest/research/csv_simulate_loop.py:284-290`。v7 同样先按 fee 算 cost，再产生 `skip_cash` 或买入，见 `backtest/research/csv_minute_backtest_v7.py:205-219`。因此费用会决定成交是否存在，不能仅视为成交结束后的 NAV 调整。

**最小反例。** 目标 100 股、价格 10 元、现金 1,003 元时，10bp/no-floor 需要 1,001 元，可买；5bp/min5 需要 1,005 元，拒买。对同一次模拟，过了该现金门再补一个“费用差”不能恢复被拒的 lot 及后续退出路径。ledger 金额比较用 `>`，因此还应区分恰好足够与少一分。已有 `tests/test_csv_strategy_books.py:269-273` 只覆盖默认佣金导致资金不足的一例，且不在本 plan quick suite。

**证据丢失窗口。** v7 支持调用者传 `fee`（`backtest/research/csv_minute_backtest_v7.py:279`），但 `_event` 不记录 fee/commission（`:196-199`），summary 不记录 schedule（`:455-459`），writer 固定输出字段也不含它们（`:465-472`）。调用结束后若未保留参数，仅凭这些产物不能唯一证明实际 schedule 或每次扣费。daily 的 summary 反而可写有效 rates/min，见 `backtest/research/csv_artifacts.py:107-111`，不能把两者的可审计性写成一致。

**要求回填。** 在 delta1 契约里标明 cash-gate 的路径依赖、fee 的可观测位置，以及 v7 产物的审计限制；未来 data-free 测试应在内存状态上断言扣费前后现金、成交/拒单、positions 与 EOD_MARK 不收费，避免只比较汇总 NAV。必要的运行参数可由调用方另行留存，但本轮不新增 trades 列、不改变 writer。这里没有真实订单或不可回滚的外部动作；“不可逆”仅指同次模拟已丢失的路径，以及未留存时不能从产物唯一还原的证据，完整重跑不在本次审查范围。

### D-05 · MEDIUM：§3 用“E-R6 已覆盖核心”缩窄了旧 P3，未给残留经济语义保留明确归属

**证据。** `docs/backtest/plan-industry-align-p3-fees-2026-09-19.md:62-70` 将表称为 P3 split，delta2 仅列 ex-div / lot-cost 的 as-built refinements，并说 E-R6 已覆盖核心、不要重做。旧 P3 被明确后置的内容却包括“改股 / 现金红利”，见 `docs/backtest/plan-industry-align-refactor-2026-09-18.md:131`。E-R6 明确只修参考价，shares、佣金、现金红利不动，而且保留 trades pnl/NAV 的结构性失真，见 `docs/backtest/engine-ashare-correctness.md:78-79`；真实书账本也只缩放 cost/peak，见 `backtest/research/csv_ledger.py:141-150`。

**反例。** 持有 100 股、原价 10 元，参考价因子 `k=0.5` 时，成本可缩到 5 元，但 shares 仍为 100；标记价为 5 元就只计 500 元市值，因为 equity 按 shares×mark 累加，见 `backtest/research/csv_simulate_loop.py:319-321`。这是 E-R6 明示的残留，不是已被“lot-cost core covered”消除的经济账本问题；本例不主张所有 `k=0.5` 事件都具有同一种公司行动含义。

**要求回填。** 明确区分“已完成的参考价缩放”与“仍后置的改股/现金红利/经济 NAV 处理”，给后者保留独立待裁项或显式外链，避免从 P3 roadmap 消失。仍不把这些生产改造拉进 delta1，也不重复 E-R6；这里要求的是延期事项不被误记为已覆盖。

## 对 plan §3 / 主船范围的独立裁决

**§3 方向有条件通过，现稿实施放行否决。** 唯一主船继续选 delta1；P1/P2/P4、ST PIT、v7 `limits=None` 策略变更、参与率上限及公司行动经济账本均保持后置。P3.1/P3.2/P3.3 默认仍建议 A/A/A；本报告不视为新的人裁或独立票。只给已有参数、扣费分组和可观测性补合同，不统一双账本，不增加印花税运行扣账行。

放行前须回填的具体勘误：

| 项目 | 独立裁决 / 主笔应回填内容 |
|---|---|
| E-03 / Slice B | 撤销“predicates 已覆盖费用 asymmetry”；保留涨跌停测试的原用途，另列真实 fee wiring 与 cash/commission oracle（D-01）。 |
| 主船 floor 契约 | 写明 book 每 lot 与 v7 合并卖出的差异及双 lot 期望值，补 cash 边界和 EOD_MARK 的观察面（D-02、D-04）。 |
| E-05 / Slice C | 十文件冻结不能推出生产冻结；补有限依赖和 docs/tests-only 增量边界（D-03）。 |
| §3 delta2 | E-R6 已闭合的是参考价缩放，旧 P3 的 shares/现金红利残留仍须显式后置（D-05）。 |
| 实施基线 | 当前 HEAD / 本地 origin/master 已越过 plan SHA；保留停止条件，在未来实施 handoff 中记录经漂移审查的固定基线，不静默改 SHA。 |

承认已修复的部分：§8 已列出真实存在的四个 gate 路径；“commission-only booking、stamp/transfer 不新增运行扣账行”的措辞已收窄；tip 不符即停止是正确方向。不能由这些局部修复推导主笔 `adversarial-errata.md:36` 的“无剩余 blocker”。本次只写本路报告，未代主笔回填 plan 或旧勘误表。

## 未验证

- 未 fetch、联网查询或核验 GitHub 当前远端；`origin/master` 仅指开工时已有本地引用。未运行 §8 整套验收，十文件 Git diff 成功不等于 suite 通过。
- 未运行 Python、pytest、gate、模拟或回测；上述金额为源码算术推导，漏测反例为静态测试路径分析，未实际改生产代码验证 mutation 能否逃逸。也未主张已有默认成交或 NAV 发生回归。
- 未评估当前税法、券商真实费率、Qlib 上游费用含义或 1.3 的实现；本路只审研究仓的本地消费与可测性，不以模块名称推断实际印花税是否已经济性包含在某个 rate 中。
- 未核验湖数据、真实交易样本、历史 NAV 偏差大小，也未验证 E-R6 宿主重跑结果；本报告引用的残留是本仓 SSOT 已有声明。
- 未启动另两路审查；本路按强制 dissent 立场给出证据和反例，不代表完整领域安全结论或多路共识。

## 模型与 effort（写你实际用到的）

- 执行者：本次单一 Codex 会话；会话指令标识为基于 GPT-6。未调用其他模型、子 agent 或嵌套 `codex exec`。
- 具体模型部署 ID 与实际 `reasoning_effort` 参数未向本会话暴露，无法独立核验。未把宿主脚本的默认值冒充本次实际参数；精确值应以宿主启动记录为准。
