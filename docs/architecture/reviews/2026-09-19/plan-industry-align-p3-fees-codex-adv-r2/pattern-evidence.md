# pattern-evidence

## 结论

**CONDITIONAL：支持 §3 只选 delta1；不支持将 v0.2 认定为费用契约证据已闭环、可原样进入实施验收。** 本路发现四项应回填的文档／验收问题；未发现需要改 production Python 才能解决的问题。不应借本轮复用筹码指标、改造行情读取器、合并双账本或接入实盘费用策略。

审查对象已先完整读取：`docs/backtest/plan-industry-align-p3-fees-2026-09-19.md`，Proposed v0.2，共 227 行。下文行号均为本次工作区版本；文件 SHA-256 为 `acf6f90b506a451e7e272462cc01d0f1441b675a25b098c9c290fc86bec136da`。遵循 `docs/prompts/prompt-adversarial-subagent-review.md:9-13` 的证据优先原则，仅执行其 `:21` 指定的 pattern-evidence 路；本报告不计独立票（该协议 `:11`）。

开工基线核对：

| 项目 | 实际结果 |
|---|---|
| `git rev-parse HEAD` | `9e2e9eb774345d0d0bf6075192739780a3f0ee47` |
| `git rev-parse origin/master` | `9e2e9eb774345d0d0bf6075192739780a3f0ee47`，本地远端跟踪引用；本路未 fetch |
| plan `IMPLEMENTATION_BASE` | `c65b10dd6d26342bd9ec1cbed5465d875f82470f`（plan `:5`、`:144`） |
| 存在性／祖先检查 | `git cat-file -t` 返回 `commit`；`git merge-base --is-ancestor` 退出 0，仅核验祖先关系，未用 merge-base 替换基线 |
| plan §8 十个冻结文件 | `git diff --exit-code <IMPLEMENTATION_BASE> HEAD -- <十个文件>` 退出 0，无差异 |

因此，基线确有时间漂移，但不能据此声称费用生产实现已漂移。开工时另有预先暂存的 `scripts/run/run_codex_adversarial_lanes.py`；本路未修改或执行它。

## Findings（file:line）

### PE-01 · P2 · 费用不对称的证据被成交门分叉测试替代，E-03 尚未真正闭环

**定位：** `docs/backtest/plan-industry-align-p3-fees-2026-09-19.md:121-125`、`:156-160`、`:226`。此前勘误将“不对称未被 quick tests 锁定”的修复写成加入 `test_ashare_simulate_predicates.py`（`docs/architecture/reviews/2026-09-19/plan-industry-align-p3-fees/adversarial-errata.md:20`、`:29`）。

**实证：** 该测试文件的相关断言锁的是未知板块／无昨收下的卖出、买入、追买和 v7 加仓门语义（`tests/test_ashare_simulate_predicates.py:120-190`），没有断言 fee 参数接线或佣金金额。其辅助函数在 v7 分支甚至不转发 `**kwargs`（`:65-72`）；直接借它写 `fee=QLIB_PORTANA` 用例会丢参数。现有 fee 单测只检查若干公式结果和 ledger 重导出（`tests/test_ashare_fees.py:10-24`），不证明引擎选择了正确 schedule。

真实费用分叉是三种接线：日线 `main()` 的 `--qlib-cost` 选择三个标量，再经 `run()` 转发到 `simulate()`（`backtest/research/csv_daily_backtest.py:683-685`、`:593-595`、`:272-280`）；分钟 `simulate()` 经共享初始化取得 `SimState` 默认标量（`backtest/research/csv_minute_backtest.py:549-556`；`backtest/research/csv_simulate_loop.py:102`；`backtest/research/csv_ledger.py:87-89`）；v7 则接收并向买卖路径传递 `FeeSchedule`（`backtest/research/csv_minute_backtest_v7.py:279`、`:352-354`、`:396-397`）。因此，`DEFAULT_SCHEDULE is BILATERAL_10BP` 也只能证明对象别名，不能单独证明书引擎默认值。

**影响：** 成交门测试通过不代表日线 opt-in、分钟默认和 v7 fee 转发已被验证；将两种“asymmetry”混写，既高估修复完成度，又把 delta4 的保留行为误列成 delta1 新交付。

**建议回填：** 将 `test_ashare_simulate_predicates.py` 明确标成已有分叉回归保护，可保留在 quick suite；另把三种费用接线列为 Slice B 的具体验收项，并指定新增／扩展的 fee 测试文件进入 §8。日线 CLI 可 stub `run()` 和产物写出，只断言参数，不触湖；数值验证使用合成状态／帧。v7 直接调用可接收 `fee` 的入口，或只在测试中修正 helper。不得借此改生产签名或统一费率。

### PE-02 · P2 · “共用公式”未交代最低费用的计收粒度，不能推导双账本费用等价

**定位：** `docs/backtest/plan-industry-align-p3-fees-2026-09-19.md:48-50`、`:80`、`:115`、`:123`。plan 要求如实记录 floor behavior，却未要求消费表写清每次收费覆盖一个 lot 还是多个 lot，也未指定 v7 现金扣／增路径的验证。

**实证：** 书引擎逐 `Position` 调用 `_sell`（`backtest/research/csv_daily_backtest.py:325-333`；`backtest/research/csv_minute_backtest.py:609-651`）；账本以该 lot 的 `shares * px` 单次算佣金（`backtest/research/csv_ledger.py:242-245`）。v7 的 `_sell_lots` 先合计本次符合 T+1 与 kind 条件的股数，再对 `sold * price` 调用一次 `credit_sell`（`backtest/research/csv_minute_backtest_v7.py:223-242`）。floor 位于单次公式调用内部（`backtest/research/ashare_fees.py:23-31`）。

**静态反例（未执行模拟）：** 两个均可卖的 lot，各 100 股、同价 10 元，使用现有 `QLIB_PORTANA` 的卖率 0.0015、最低 5 元（`backtest/research/ashare_fees.py:18-20`、`:54`）：书账本两次卖出合计费用 `5 + 5 = 10`；v7 一次合并卖出费用 `max(2000 × 0.0015, 5) = 5`。这是配置非零 floor 后已有的调用粒度差异，不是说当前默认 10bp／无 floor 已发生这项差额，也不是断言两个引擎会产生相同仓位。

**影响：** 只证明 `trade_commission` 相同，无法证明现金或 NAV 等价。若照外部 broker“同一订单最低五元”模式归并交易，或把两个账本都改用一种扣费流程，会改变已存在的调用边界。

**建议回填：** 在 fee 消费表增加“计费单位／调用粒度”列：书侧逐 lot，v7 每次 `_sell_lots` 汇总可卖量；写明 default 无 floor，但可选 schedule 的 floor 按上述粒度生效。Slice B 增加多 lot 与小额 floor 的合成现金断言，保留双账本。另明确 research 公式对正 notional、`rate=0, min_cost>0` 仍收费，而负 rate 返回 0（`ashare_fees.py:25-30`）；不可从 broker 实现反推此边界。

### PE-03 · P2 · §3 的 delta2 将未完成的除权经济语义缩写成已完成的参考价修正

**定位：** `docs/backtest/plan-industry-align-p3-fees-2026-09-19.md:62-69`，尤其 `:67` 的“Ex-div / lot-cost rescale … E-R6 already covers core behavior”。

**实证：** 被承接的 P3 明确后置的是“改股／现金红利／ST PIT”等事项（`docs/backtest/plan-industry-align-refactor-2026-09-18.md:131`）。撮合收口 plan 也明确把 E-R6 残留的 shares、现金红利继续锁住（`docs/backtest/plan-ashare-engine-refactor-2026-09-18.md:141`、`:155`）。现状 SSOT 只宣告参考价修正；明确 shares、现金红利入账未改，跨除权 lot 的 trades pnl／净值仍有结构性失真（`docs/backtest/engine-ashare-correctness.md:78-79`）。代码也只缩放 cost／peak（`backtest/research/csv_ledger.py:141-150`），v7 重建 Lot 时保留 `lot.shares`（`backtest/research/csv_minute_backtest_v7.py:185-193`）。

**影响：** 标题声称是“P3 split”，但 delta2 只剩参考成本合同细化，会让后续主笔误以为原先延期的改股／现金红利已被 E-R6 覆盖，或把已经落地的 cost rescale 重做一遍。这是路线图语义遗漏，不构成本轮改股或改 NAV 的理由。

**建议回填：** 把 delta2 写成“除权残留（shares／现金红利，继续延期）；E-R6 参考价／cost／peak 修正已落地，只引用，不重做”。如本表只打算列文档整理工作，则明确它不是延期行为项的完整拆分，并保留通往上述残留项的引用。delta2 仍不得进入本轮主船。

### PE-04 · P2（实施前置）· 固定基线已落后；§8 会按设计提前退出，需记录漂移后再启动实施

**定位：** `docs/backtest/plan-industry-align-p3-fees-2026-09-19.md:5`、`:85`、`:144-154`、`:189-192`。

**实证：** 开工 `HEAD == 本地 origin/master == 9e2e9eb774345d0d0bf6075192739780a3f0ee47`，不同于 plan 的 `c65b10dd6d26342bd9ec1cbed5465d875f82470f`。`git log c65b10d..HEAD` 可见本 plan 的合并提交 `9e2e9eb`，也有数据路径提交 `dc42029`、`f25386f`。十个指定冻结文件在此区间 diff 为零，整个仓库则不是零差异。

**影响：** 在远端未发生回退的前提下，§8 fetch 后的相等检查会在测试之前退出。这是 guard 的正常保护，不是 ghost script、不是错误地用祖先检查通过冒充 tip 相等，也不否定最初记录 c65b10d 的历史真实性。但当前评审不能沿用上一轮“基线仍一致”的结论。

**建议回填：** 保存原计划基线的来源，并添加本次 HEAD／本地 origin/master／冻结文件零 diff 的漂移记录。真正启动实施时重新 fetch、核对当时 tip 与生产差异，再明确实施基线；不得静默替换 SHA、删除 tip 检查，或因本报告仅验证十个文件便宣称全仓冻结已通过。

### 必查项核验：复用与包边界（未发现需新增依赖的理由）

| 核验项 | 本路裁决及直接证据 |
|---|---|
| `chip_indicator` | **不复用、不复活。** 当前 `git ls-files -- backtest/chip_indicator.py` 无输出；删除历史为 `59ba18db9886b3f1afad2ce9cd795683c35ef693`。现行定位明确 Cerebro／chip 宿主壳已退场（`docs/backtest/engine-positioning-ssot.md:7`、`:29-33`）；当前筹码函数做分布及因子计算（`oskh_factors/chip/core.py:403-434`），不是交易费计算器。旧文档中的筹码“成本”不能作为 fee 复用证据。 |
| `StockDataReader` | **本船无需接入或改造。** 它构造数据根与可选 DuckDB 连接（`oskh_data/reader.py:153-195`），`read_stock` 读取行情且默认 `adjust_type='front'`（`:363-388`）；实际筹码消费者用它取得日线前复权窗口（`backtest/research/chip/filter_chip_stocks.py:74-98`）。本船公式只收 notional／rate／floor（`backtest/research/ashare_fees.py:23-31`），不需要行情 IO。不能把读取器已有的复用惯例套进纯费用合同，也无需为此修改当前 CSV loader。 |
| `trade_fee_policy` | **继续隔离，非可直接替换的同义实现。** broker kernel 使用 Decimal、分位 HALF_UP，并仅在 commission rate 大于 0 时计佣金（`trade_fee_policy.py:367-372`），另有按码过户与卖侧印花（`:374-399`）；research 公式使用 float、未做分位舍入，rate=0 时仍可触发 floor（`backtest/research/ashare_fees.py:25-31`）。不只 docstring 不同，运算也不同。 |
| 热路径边界的覆盖范围 | **沿用枚举边界，不扩成全 research 扫描。** `tests/test_ashare_simulate_import_fence.py:13-29` 列出文件，`:32-49` 解析静态 import，`:61-64` 检查该清单；`AGENTS.md:21` 禁止扩成全目录扫描。仓内另有 `backtest/research/engine.py:21-24`、`:57-79` 直接调用 broker fee 的历史 MVP；它不在该枚举内。因此本 plan 的“research fee SSOT”应保持限定于所列 CSV 路径，不应被扩写为整个 research 包都不使用 broker policy。 |
| `QLIB_PORTANA`／OSS 类比 | **保留本地参数名，不恢复外部引擎。** 对象是本地 `FeeSchedule` 实例（`backtest/research/ashare_fees.py:53-55`），日线 CLI 注入本地常数（`backtest/research/csv_daily_backtest.py:683-685`）；定位文档已停用 PortAnaRecord／Exchange（`docs/backtest/engine-positioning-ssot.md:29`），围栏拒绝 `qlib` import（`tests/test_ashare_simulate_import_fence.py:45-48`）。plan §10 明示类比不是行为证据（`docs/backtest/plan-industry-align-p3-fees-2026-09-19.md:215-220`），这一限制正确。 |

此前 ghost gate 问题不重复报为未修复：v0.2 §8 的四个路径均实际存在，且与 `.github/workflows/python-tests.yml:38-43` 一致。stamp 文案已明确“不新增独立 stamp runtime booking”（plan `:81`、`:94`），符合 ledger 当前记账调用（`backtest/research/csv_ledger.py:211-229`、`:242-255`）；不能由此进一步宣称这些简化费率等价于某个交易所、日期或券商的真实税费。

## 对 plan §3 / 主船范围的独立裁决

**同意结构，要求回填 PE-01 至 PE-04 后再把实施条件标为齐备。** delta1 仍是唯一主船：记录并用 data-free 合成测试锁定已有费率、选择方式、计收粒度和现金流。P3.1／P3.2／P3.3 的 A/A/A 默认建议有本地证据支持；这不是替代人裁的实施授权。

主船边界建议明确为：

1. 保留双边 10bp／无 floor 默认、日线显式 opt-in 和 v7 显式 fee 对象；共用叶子公式，不合并账本，不强制三入口使用同一种配置接口（`backtest/research/csv_ledger.py:87-89`；`backtest/research/csv_daily_backtest.py:272-280`；`backtest/research/csv_minute_backtest_v7.py:279`）。
2. fee 测试证明 fee 契约；成交门测试仅保留为既有分叉保护。delta4 已在前一 plan 契约化，不能算本轮新费用证据（`docs/backtest/plan-industry-align-next-2026-09-19.md:99-107`）。
3. delta2 改正路线图措辞后继续延期；delta3、delta4、delta5 和 P1／P2／P4 均不扩入本船（目标 plan `:67-70`、`:83`）。
4. 文档同步应限定在现有 CSV fee SSOT／消费表；不新增 `chip_indicator`、`StockDataReader`、`qlib` 或 broker fee 依赖，不重开行情、筹码、实盘栈或全目录 import 治理。

## 未验证

- 本路为静态审查，未运行 pytest、四个 gate、任何 CLI 回测或生产模拟，未读取市场湖。报告中的费用数字由已读公式手算，不是回测／单测结果。
- 未执行 `git fetch`；origin/master 只表示本地跟踪引用。本路不声称已验证当前网络远端 tip。
- 只执行了明确列出的基线与冻结文件只读检查；未把十个文件无差异扩大为全仓无差异或未来验收必过。
- 未验证外部 Qlib、交易所或券商费用规则，也未验证 1.3／MyQuant 的现行实现；本报告只评价仓内合同与证据的对应关系。
- 未为静态 import 围栏补充动态加载、任意传递依赖的证明；保留其现有枚举覆盖声明。
- 未修改 plan、测试或 production Python；仅写入本路报告。未 spawn 子 agent，未运行嵌套 `codex exec`。

## 模型与 effort（写你实际用到的）

- 实际审查会话：Codex；本会话身份说明为基于 GPT-6。未调用其他模型或子 agent。
- 精确模型部署 ID 与 reasoning effort 档位未在本会话可核验元数据中提供；不能据目录名、宿主默认值或旧报告推定为某个模型／`high`／`xhigh`。此处如实记为**未披露，未自行切换**。
