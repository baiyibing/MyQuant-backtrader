# Plan: industry-align P3 δ6 ex-div economics / NAV residual (2026-09-19)

> **Status**: **v0.2 · docs-only · Human GO P3δ6.1=A recorded 2026-09-19（Asia/Shanghai）**：残留+oracle；账本可选 B，仅 docs。**明确不是 C：生产增股/入账/NAV 须另裁 C，本轮不授权且禁止修改。** 本次仅录入 GO，未来 Slice A→B→C 未实施，未新增/执行测试。
> **Main ship / 单行范围**: 按 Human GO A 固定 δ2/E-R6 deferred 的送转增股、现金红利入账和 NAV 经济残留/oracle；账本设计可选 B，仅文档，不改生产。
> **IMPLEMENTATION_BASE**: `1049b904bdd818dbb79f51f1830a008c8f83b141`（本 worktree `git rev-parse HEAD` 已核实全 40 字符；post #123，含 δ1 + δ2）。
> **Human GO recorded**: **P3δ6.1=A**；账本设计可选 **B（仅 docs）**。**只有另裁显式 C 才批准另案生产经济变更；本轮未授权 C，禁止生产 shares/cash/NAV 修改。** 其余设计候选见 §5；P1/P2/P4 继续挂起。
> **前序**: [δ1 fees](plan-industry-align-p3-fees-2026-09-19.md)、[δ2 exdiv contract](plan-industry-align-p3-d2-exdiv-2026-09-19.md)、[E-R6 原计划](plan-exdiv-refprice-2026-09-16.md)、[engine SSOT](engine-ashare-correctness.md)、[next fill gates](plan-industry-align-next-2026-09-19.md)；[四刀索引](plan-industry-align-p3-d345-econ-index-2026-09-19.md)。

---

## 0) One-line scope

区分触发参考价与经济权益，写清当前未增股/未入现金的残留、可验收经济 oracle 与未来账本候选；本轮 Human GO A 仅授权残留+oracle，账本设计可选 B docs，不表示生产经济残留已修复。

## 1) Why now

δ2 已在 post #123 固定参考价缩放、事件门、入口差异和 raw mark 残留；E-R6 的作用是减少触发参考错域，**没有完成送转股数、现金分红与经济 NAV**。本刀承接其明确留下的经济面，而非 redo E-R6。另一个研究路径 Mode B 有 `shares /= k` 的 fractional-shares 近似，容易被误用为全仓总回报账本已经存在的证据；必须把这条边界和真正经济事件数据的缺口先写清。

## 2) Verified as-built anchors（本 IMPLEMENTATION_BASE 的 file:line）

### 2.1 当前书 / v7 经济状态

| 合同项 | 已核实行为 | 锚点 |
|---|---|---|
| E-R6 map | `k=prev_cum/cum`，输出 code/day/ratio；以有效因子 LAG 和事件/噪声门筛选，不输出登记/到账/新增股明细 | `backtest/research/exdiv_map.py:233-239`、`:288-319` |
| 书 lot | shares 是 int；rescale 只乘 cost/peak，其它 lot 元数据不改 | `backtest/research/csv_ledger.py:68-79`、`:147-156` |
| 书现金流 | 买入扣成交额+佣金，卖出加成交额−佣金；缩放不调用现金分红入账 | `backtest/research/csv_ledger.py:215-225`、`:261-276` |
| 书 NAV | equity=cash+各 lot 原股数×**传入 bars 的**当日/最近历史 close（函数不做 raw 域认证）；**仅默认 none/raw 入口**下该 close 才是 raw mark 残留；无行情才回落 cost；EOD_MARK 仅标记、佣金0。混域（front/back/qlib_day）估值域随入口，见 δ2 分源合同与本刀 `:52` | `backtest/research/csv_ledger.py:165-184`；`backtest/research/csv_simulate_loop.py:381-421` |
| v7 lot | `_rescale_position` 乘 entry_A/avg_cost/peak/非空 add1_A1/lot.price；保持 lot.shares/buy_date/kind | `backtest/research/csv_minute_backtest_v7.py:60-81`、`:187-196` |
| v7 现金与 NAV | 现金只在该买卖记账路径变化；会话末 holdings=原股数×last_prices，缺值才 avg_cost fallback | `backtest/research/csv_minute_backtest_v7.py:205-251`、`:416-418` |
| 缩放时机 | 书有相应 bar/昨收后，v7 有 records 后，先缩放事件日已有仓，再扫描；不是通用事件账本 | `backtest/research/csv_daily_backtest.py:300-327`；`backtest/research/csv_minute_backtest.py:586-636`；`backtest/research/csv_minute_backtest_v7.py:316-340` |
| 已有经济残留 pins | 100 股小 oracle、双书公开 raw mark 股数/现金不补偿、v7 自然多 lot 的快照差额 | `tests/test_exdiv_refprice_engines.py:554-579`；`tests/test_csv_minute_backtest_v7.py:328-357` |

### 2.2 Mode B 是独立近似，不能关闭本刀

| 事实 | 证据 | 允许的结论 |
|---|---|---|
| Mode B instance path 对事件做 cost/mark×k、shares÷k，使用 float shares，缺分钟时也先调整 | `backtest/research/unified_exit_modeb.py:407-427` | 这是 Mode B 自己的价值缩放近似；不证明书/v7 同样增股 |
| Mode B equity 路径也按 k 调 shares/mark，现金仍走买卖；元数据明确 `no cash dividend` | 同文件 `:788-824`、`:1029` | 没有逐笔现金红利、应收/实收、登记日权利账闭环 |
| fractional shares 与 shared ledger 不增股并存 | `tests/test_unified_exit_modeb_exdiv.py:13-22`、`:61-64` | 可回归“两个模型分叉”，不能宣称真实权益或本仓经济残留已关闭 |

一个 k 无法唯一分解现金分红、送转、配股等事件。将 `q/k` 当真实送转股数、同时再计现金红利可能重复补偿。Mode B 夹具绿灯、代数市值不变、未验证的收益提升都不构成本刀完成证据；本次冻结 Mode A/B，不改它们的历史定义。

### 2.3 已关 / 仍钉 / deferred

| 面 | 当前状态 | δ6 处理 |
|---|---|---|
| E-R6 参考价修正 | 事件落日/价格域一致且可处理时，缩放已有参考并映射昨收；δ2 已 pin | 保留已关面，不 redo、不称所有域均安全 |
| 原股数/原现金 raw NAV 残留 | 基线已有明确数值 pin | A：继续文档化并扩展必要 oracle |
| 送转权益、登记资格、到账/上市、现金分红、NAV 含应收 | deferred 的经济面 | **已人裁 A，账本可选 B docs**；不实施生产，C 须另裁且本轮不授权 |
| 因子恢复日错域、缺 bar 不回放、helper 非幂等、原始因子可得性/修订 PIT | δ2 已揭示，未关闭 | 保留独立残留；新经济账不能假设旧 map 已满足这些保证 |
| 小额事件噪声门、v4 SMA 原始序列、minute/v7 qlib_day 混域 | 未关闭 | 不随本刀默认修；经济事件不能直接沿用会漏现金的小噪声过滤 |
| 历史收益/假止损回收 | 本次未测 | 不量化改善、不称已追回历史损失 |

## 3) Delta roadmap

| 刀 | 基线/路线 | 与 δ6 的关系 |
|---|---|---|
| δ1 fees | 基线已含；生产冻结 | 股数/现金变化会影响后续成交费用；公司行动不是 BUY/SELL，不自动套佣金 |
| δ2 exdiv reference | 基线已含；参考价合同已关、经济 deferred | **δ6 只打开经济面**，不抹掉 δ2 的受限结论 |
| [δ3 ST PIT](plan-industry-align-p3-d3-st-pit-2026-09-19.md) | 建议先契约 | ST 日期 PIT 与经济事件登记/可得时间是两个合同 |
| [δ4 limits-none](plan-industry-align-p3-d4-v7-limits-none-2026-09-19.md) | 建议接着契约 | 不以改经济账统一 None 政策 |
| [δ5 volume-cap](plan-industry-align-p3-d5-volume-cap-2026-09-19.md) | 先做设计 | 新增权益/现金不是市场成交，不消耗 volume budget；若生产并行改造须重核组合合同 |
| **δ6 economics** | **本文件：Human GO A；账本可选 B docs；C 未授权** | 具备事件证据/账本设计/迁移方案并另裁显式 C 后方可实施生产案 |

## 4) F-R* hard locks

| ID | 硬锁 |
|---|---|
| **F-R1** | 本 PR 仅 docs；默认 A/B 都不改生产 shares、现金、NAV、参考价、trades 或 CLI。 |
| **F-R2** | δ2/E-R6 只修参考价；送转不增股/分红不入现金的书/v7 经济残留不能写成已关。 |
| **F-R3** | Mode B fractional shares、factor-only 代数守恒与未验证收益均不是经济残留关闭证据。 |
| **F-R4** | `k` 不是现金红利或送转比例；不能由因子跳变/噪声门反推完整经济事件，不双计 q/k + 红利。 |
| **F-R5** | 必须区分登记权益、除权参考、到账现金、新股可卖；T+1/新股可卖日期不可由 rescale 自动推定。 |
| **F-R6** | NAV 守恒 oracle 必须隔离市场价格变动、手续费、税费、外部资金流；应收转现金不产生二次收益。 |
| **F-R7** | 成本参考与经济成本账分离；helper 重复调用不幂等的现状不改，新账如设计去重须独立事件键/版本。 |
| **F-R8** | P1/P2/P4、δ1/δ2 当前行为、ST/limits/cap 分叉保持；C 不能顺手重开它们。 |
| **F-R9** | A/B 只用内存/tmp_path data-free oracle，无湖、回测、外部下载/merge；仅消费上游，缺数据合同先报缺口。 |
| **F-R10** | §9 超集冻结与全路径白名单同时生效；不复活 live/LEBS/MockQMT/Cerebro/PortAnaRecord，不扩大热路径 import fence。 |

## 5) P* human cuts（Human GO .1=A 已录入；账本可选 B docs；非 C）

> **Human GO recorded 2026-09-19 (Asia/Shanghai):** P3δ6.1=A — δ6=A：残留+oracle；账本可选 B；**生产增股/入账/NAV 须另裁 C，本轮不授权**。A 授权后续残留契约与 data-free oracle pins；可选账本 B 仅限设计文档，**明确不是 `.1=C`，本轮禁止生产 shares/cash/NAV 修改**。P1/P2/P4 继续挂起。

### 5.1 主裁决：经济面交付层级

| ID | A | B | C | 本轮人裁 |
|---|---|---|---|---|
| **P3δ6.1** ✅ Human GO 2026-09-19 | **继续只文档化残留 + oracle pins**，生产零行为变更 | **设计账本但不改生产**，补事件/权益/现金/NAV 状态表 | **批准生产行为变更（增股/入账/NAV）**；需独立实施计划/PR 与完整验收 | **A**；账本可选 **B（仅 docs）**。**明确非 C，本轮不授权** |

本轮 Human GO 已正式录入 A（账本可选 B，仅 docs），未给任何生产经济变更授权。后续选择 C 必须另行人裁，把裁决日期、范围、前置证据与允许修改的路径写入新实施记录。未来 Slice C 是验收阶段，绝不替代这里的人裁选项 C；§5.2 仍是设计候选，不能从次级选项推导生产授权。

### 5.2 B/C 设计时需要补齐的决策

| ID / 决策 | A | B | C | 推荐与依赖 |
|---|---|---|---|---|
| **P3δ6.2：事件源** | 列缺口；要求上游显式事件明细与 PIT/版本证据后才实现 | 仅设计因子近似账户，明确非真实权益 | 采纳经验证的逐事件合同，进入消费接线设计 | **A**；禁止本仓新增采集/合并 |
| **P3δ6.3：权益/现金/NAV** | 保留基线残留 oracle | 设计 record→entitled/receivable→payable/listed→cash/tradable 分层状态 | 选择有充分数据支持的其它记账时点，列 NAV 差异 | **A** 随 .1=A；.1=B 时推荐 **B**，仍无生产授权 |
| **P3δ6.4：股数与零碎股** | 记录整股现状/零碎规则缺口，不以 q/k 自动生成 | 设计独立 entitlement 精度及上市可卖数量，零碎/现金替代显式规则 | 批准具体新股可卖/零碎处置行为 | **A**；设计时可 B；C 还需 .1=C |
| **P3δ6.5：报告与兼容** | 保持现有 trades/equity schema | 设计独立公司行动账/对账视图，不改 trades | 实施产物变更；涉及既有 trades 新列须明确重开 P2 | **A** 随 .1=A；设计时 B |

任何次级 C 不独立授权生产；`.1=C` 也不能绕过尚未解决的数据、税费、可卖、迁移等前提。默认没有自动触发 NP2/宿主重跑；如以后需经验测量或触及 engine SSOT 的 E-R5 重开条件，另立宿主任务与人裁，本次不运行。

## 6) Non-goals

- A/B 不实现增股、现金分红入账、应收账款、NAV 改写、除权事件补发或新 tax/fee 分录。
- 不由 `k` 反推送转比例，不把 Mode B 的 q/k 移植到书/v7，不把它称真实总回报。
- 不修 δ2 因子 PIT/错域、噪声带、SMA、入口域差异；不撤销历史真实 SELL、不追回假止损。
- 不开展收益、税法、交易所日期规则或真实事件数据核验，不跑回测/湖/探针，不报收益改善。
- 不改 v7 stage/首开时间、T+1、ST/limits、fee floor、capacity；P1/P2/P4 继续挂起。

## 7) Slices A → B → C（未来路径；按 A/B 人裁默认生产冻结）

§5 Human GO A 授权后续残留+oracle；可选 B 仅授权账本设计文档。未来 Slice C 只验收残留/设计，生产选项 C 未授权；B 下的账本参考模型测试仍是后续候选，不由本次可选 docs B 自动授权。本次所有 slices 均未实施。

### Slice A：残留合同与候选经济账

先写清两套量：触发参考 `cost_ref/peak_ref` 与经济账 `entitlement/receivable/cash/quantity/cost_basis`。以下字段/流程仅为 B 设计候选，**不是现有 dataclass/API**。

| 候选合同 | 必须回答的问题 |
|---|---|
| 事件身份 | code、event_id、revision、available_at、record_date、ex_date、pay_date、list_date；每旧股现金 c、新增比例 b、金额税前/税后口径与来源，缺失不得猜 |
| 权益快照 | 在已裁登记时点锁定 eligible lots/数量；登记后卖出是否保留权利、除权日新买是否无权按夹具前提明确；新股上市/可卖独立建模 |
| 状态与顺序 | 事件识别/权益确认/应收估值/现金到账/新股上市/交易/mark 的会话内次序；不要把 ex_date 当所有动作同时发生 |
| 重放与修订 | 事件键幂等、部分入账恢复、修订冲销/差额、跨停牌/无 bar 日处理；旧 rescale 无去重状态不能充当新账事件处理器 |
| 金额精度 | 股数和权益精度、分币舍入及残差账户、gross/net/tax 明细；税规则未核实，不从 δ1 代理佣金推导 |
| NAV 对账 | cash + tradable/nontradable shares 的已定义估值 + receivables − liabilities；不得丢应收或到账时双计；原价/复权价域需显式验证 |
| 成本与产物 | 经济成本分配与触发参考成本分离；公司行动不是成交，不复用 BUY/SELL/EOD_MARK 伪造现金流；先设计独立账，不本刀改 schema |

DoD：A 只承诺残留/oracle；B 在文档完成状态表、缺数据项与迁移风险，未解决项显式 pending。单靠 E-R6 map 不足以实现上述账本。以后的 C 还需独立生产 slices、版本/重算/回滚合同，不能把本节当成可直接开写代码的授权。

### Slice B：可验收 oracle 与真实已有测试落点（未来，非本 PR 测试修改）

以下用受控经济夹具，**设无市场额外涨跌、无税费/外部资金流，事件资格由夹具给定**；不是实际登记、税务或交易所公式认证。简化送转+派现情况下，旧股 q、旧价 P、每旧股派现 c、新增比例 b，理论除权价 `P_ex=(P−c)/(1+b)`；以经济权益完整计量可得 `q×P = q×(1+b)×P_ex + q×c`。不能把这个受限等式用于任意公司行动或直接从 k 求 b/c。

| Pin | 数值输入 / 预期 | 真实已有落点与证明边界 |
|---|---|---|
| B1 基线残留 | 100 股，cost=10，peak=12，cash=2000；k=.5、raw 10→5：参考 5/6，仍100股/cash2000，equity 3000→2500，非 SELL | `tests/test_exdiv_refprice_engines.py` 已有 `test_d2_economic_residual_small_oracle` 与 `test_d2_public_book_raw_mark_keeps_shares_and_cash`；复用，不改成守恒期望 |
| B2 v7 基线 | 自然首开→加仓，按除权前快照 q/cash；事件后仍 q、cash 不变，差额=q×raw 价差；同日新买 lot 不重复缩放 | `tests/test_csv_minute_backtest_v7.py` 已有 `test_d2_v7_public_multilot_fields_once_and_economic_delta` / `test_d2_v7_exday_add_then_stop_sells_only_old_lot`；小数值 oracle 不冒充 public Position 注入 |
| B3 纯送转设计 | q=100、P=10、b=1、c=0、cash=2000：权益200股×5+2000=3000；上市前若100旧股可交易+100新股权利，须只计一次新增权益 | 独立设计 oracle 未来可放 `tests/test_exdiv_refprice_engines.py`；as-built 仍2500。不可只断言 q/k 后声称已接权益数据 |
| B4 纯现金/到账设计 | q=100、P=10、c=1、b=0：ex 日股值900+cash2000+应收100=3000；pay 日现金2100、应收0，总值仍3000 | 同文件未来设计 oracle；当前实现无应收/入账，raw equity 为2900；在该 oracle 应收确认时点已显式设定 |
| B5 混合 + 不可识别性 | b=1、c=1：200股×4.5+cash2000+应收100=3000。另取 k=.9：纯现金 c=1 与纯送转 b=1/9 都可产生9元理论价，权益结构不同 | 同文件仅作独立模型/文档代数证据；证明 k 单值不足。不是给真实 fractional shares 授权 |
| B6 生命周期 | 给定登记资格；登记后卖出者保留已锁权益，除权日新买无权；重复 event_id 不重复入账；无 bar 仍按事件生命周期记权利 | 同文件未来设计 oracle；最终生产须真实事件账接线，不能通过修改 E-R6 停牌测试消除现存残留 |
| B7 模型边界/费用 | Mode B 的 q/k、book 原股数继续并存；公司行动 oracle 不产出 SELL/EOD_MARK 现金、不收交易佣金；随后真成交按 δ1 | `tests/test_unified_exit_modeb_exdiv.py`、`tests/test_ashare_fee_wiring.py`；只复用边界，不把 Mode B 回归当经济关闭 |
| B8 事件输入残留 | 噪声门、因子恢复日落键、缺当日 bar 不回放；日期前缀不证明 available_at | `tests/test_exdiv_map.py`、`tests/test_exdiv_refprice_engines.py`、`tests/test_ashare_session.py`；延续 δ2 真实 pin，完整经济源另案 |

B3–B6 尚未写测试；A 可先保留文档 oracle，未来若加 tests-only 参考模型须标明 design-only。纯现金即便落在 E-R6 ≤0.5% 噪声带也是真实经济权利的候选，不得因参考价不缩放而跳过经济入账；这是新账设计要求，非本次修改 loader。守恒只隔离事件跳变，不要求真实市场每日 NAV 不变；税费/费用/市场变化按明确项调节，不塞进无法解释的“误差”。

### Slice C：残留/设计验收与生产出口

执行 §8 的未来 data-free 定向检查，记录基线 pins 与 design-only oracle 各自覆盖；§9 冻结零 diff。A/B 通过只能称残留已明确或账本设计已验收。**经济残留关闭**必须另有 `.1=C`、事件明细证据、双账本真实 public 入口的增股/应收/实收/NAV 对账与迁移验收；本 PR 不宣称这些成果。

## 8) Linux/CI isomorphic acceptance（真实命令；区分本次 docs 与未来 pins）

### 8.1 本次 docs-only：基线、全路径、编码与 whitespace

从仓库根目录用 Bash 执行。`IMPLEMENTATION_BASE` 是本 worktree 起点的 `git rev-parse HEAD` 实测值；以下重新解析同一固定 commit，不跟随移动的 master、不推算 merge-base。将来实施分支若换基线，须在人裁/实施记录中重新用 `git rev-parse` 写全 SHA，并保留此 proposal 的历史锚点。

```bash
set -euo pipefail
IMPLEMENTATION_BASE="$(git rev-parse --verify '1049b904bdd818dbb79f51f1830a008c8f83b141^{commit}')"
[[ "$IMPLEMENTATION_BASE" =~ ^[0-9a-f]{40}$ ]]
git merge-base --is-ancestor "$IMPLEMENTATION_BASE" HEAD
P3_DOCS=(
  docs/backtest/plan-industry-align-p3-d3-st-pit-2026-09-19.md
  docs/backtest/plan-industry-align-p3-d4-v7-limits-none-2026-09-19.md
  docs/backtest/plan-industry-align-p3-d5-volume-cap-2026-09-19.md
  docs/backtest/plan-industry-align-p3-d6-exdiv-economics-2026-09-19.md
  docs/backtest/plan-industry-align-p3-d345-econ-index-2026-09-19.md
)
P3_AUDIT_DIR="$(mktemp -d)"
trap 'rm -rf -- "$P3_AUDIT_DIR"' EXIT
git diff --name-only "$IMPLEMENTATION_BASE" HEAD > "$P3_AUDIT_DIR/head"
git diff --name-only > "$P3_AUDIT_DIR/worktree"
git diff --cached --name-only > "$P3_AUDIT_DIR/index"
git ls-files --others --exclude-standard > "$P3_AUDIT_DIR/untracked"
sort -u "$P3_AUDIT_DIR/head" "$P3_AUDIT_DIR/worktree" \
  "$P3_AUDIT_DIR/index" "$P3_AUDIT_DIR/untracked" > "$P3_AUDIT_DIR/paths"
while IFS= read -r path; do
  p3_allowed=false
  for doc in "${P3_DOCS[@]}"; do
    if [[ "$path" == "$doc" ]]; then p3_allowed=true; break; fi
  done
  if [[ "$p3_allowed" != true ]]; then
    printf 'OUT OF SCOPE: %s\n' "$path"; exit 1
  fi
done < "$P3_AUDIT_DIR/paths"
for path in "${P3_DOCS[@]}"; do
  test -f "$path"
  perl -MEncode=decode,FB_CROAK -e '
    local $/; open my $fh, "<:raw", $ARGV[0] or die $!;
    my $raw = <$fh>; die "BOM\n" if substr($raw,0,3) eq "\xEF\xBB\xBF";
    my $nul = () = $raw =~ /\x00/g; die "NUL=$nul\n" if $nul;
    decode("UTF-8", $raw, FB_CROAK);
    print "$ARGV[0]: UTF-8 OK; BOM=0; NUL=0\n";
  ' "$path"
done
git diff --check "$IMPLEMENTATION_BASE" HEAD
git diff --check
git diff --cached --check
for path in "${P3_DOCS[@]}"; do
  p3_ws_rc=0
  git diff --no-index --check /dev/null "$path" > "$P3_AUDIT_DIR/whitespace" || p3_ws_rc=$?
  if [[ "$p3_ws_rc" -gt 1 || -s "$P3_AUDIT_DIR/whitespace" ]]; then
    cat "$P3_AUDIT_DIR/whitespace"; exit 1
  fi
done
```

最后的循环覆盖尚未跟踪的新文档；no-index 正常内容差异可返回 1，故同时要求 rc≤1 且 whitespace 诊断为空，不能简单忽略所有非零退出码。全路径审计覆盖 base→HEAD、staged、unstaged、untracked，不靠一张有限冻结表推断其它路径安全。未来 tests-only 实施时必须先在新实施记录中批准/列出 §7 实际测试落点并收窄更新白名单；**本次五文档白名单不允许任何 tests/Python 修改**。

### 8.2 未来 Slice B/C：真实 data-free tests / gates（本 PR 不执行）

以下仅在未来获准的合同/pins 刀执行；本次不会以“现有测试存在”冒报“本次测试已通过”。CI 同构依据为 `.github/workflows/python-tests.yml:27-43`、`:49-56` 的受控 Python 3.12、四个 repo-only gates 与 pytest marker；这是定向合同验收，不代表全量 CI 或宿主回测。

遵循 AGENTS 解释器顺序：`OSKH_MERGE_PYTHON` → `VANNA312_PYTHON` → `VANNA311_PYTHON`。Linux 先显式指定已准备好的项目/CI 3.12 解释器；未设置时本命令失败，不偷偷回落系统 python/pip。Windows 默认解释器由现有 `scripts/_script_bootstrap.py` 的 `resolve_oskh_python` 管理，本命令不探测盘符、不安装依赖。

```bash
set -euo pipefail
P3_CONTRACT_PYTHON="${OSKH_MERGE_PYTHON:-${VANNA312_PYTHON:-${VANNA311_PYTHON:-}}}"
: "${P3_CONTRACT_PYTHON:?Set OSKH_MERGE_PYTHON to a controlled Python 3.12 executable}"
[[ -x "$P3_CONTRACT_PYTHON" ]]
"$P3_CONTRACT_PYTHON" -c 'import sys, pytest, pandas, numpy, pyarrow; assert sys.version_info[:2] == (3, 12); print(sys.executable)'
"$P3_CONTRACT_PYTHON" scripts/gates/verify_oskh_data_contract.py
"$P3_CONTRACT_PYTHON" scripts/gates/verify_data_path_ssot.py
"$P3_CONTRACT_PYTHON" scripts/gates/verify_no_hardcoded_machine_paths.py
"$P3_CONTRACT_PYTHON" scripts/gates/verify_tr_bridge_import_ssot.py

# §7 实际既有落点文件；新增 pin 完成后，逐项记录实际执行结果。
"$P3_CONTRACT_PYTHON" -m pytest -q -m "not production and not benchmark" \
  tests/test_exdiv_map.py \
  tests/test_exdiv_refprice_engines.py \
  tests/test_ashare_session.py \
  tests/test_csv_minute_backtest_v7.py \
  tests/test_unified_exit_modeb_exdiv.py

# 固定热路径边界与 δ1 回归，不能单独替代本刀 pins。
"$P3_CONTRACT_PYTHON" -m pytest -q -m "not production and not benchmark" \
  tests/test_ashare_simulate_import_fence.py \
  tests/test_ashare_fees.py \
  tests/test_ashare_fee_wiring.py
```

所有 gate/test 路径在本基线真实存在；无新造验收脚本。未来只允许合成内存 `simulate` / `simulate_v7` 单元向量或显式 tmp_path/I/O stub，不允许 CLI/宿主回测、湖访问和以真实行情输出为验收。本次连这些合成 tests 也不运行。缺环境依赖记阻塞；必需 pin 被 skip 不算通过；只跑旧测试不能声称 §7 待补组合已覆盖。

### 8.3 默认生产冻结（本次及未来 A/B；与 §9 逐项相同）

先执行 §8.1 设置固定 base。保留 δ1 十文件、δ2 十七文件全部项目，再扩展名称/策略/Mode A/B 边界，共 **22** 个；这不改变旧 plan 的历史冻结结论。

```bash
FROZEN_PRODUCTION_FILES=(
  backtest/research/ashare_fees.py
  backtest/research/csv_ledger.py
  backtest/research/csv_simulate_loop.py
  backtest/research/csv_daily_backtest.py
  backtest/research/csv_minute_backtest.py
  backtest/research/csv_minute_backtest_v7.py
  backtest/research/ashare_session.py
  backtest/research/market_layer.py
  backtest/research/csv_common.py
  backtest/research/csv_artifacts.py
  backtest/research/exdiv_map.py
  backtest/research/exdiv_hold_hits.py
  backtest/research/ashare_bars.py
  backtest/research/csv_daily_loader.py
  backtest/research/ashare_fill_clock.py
  backtest/research/qlib_bin_daily.py
  backtest/research/qlib_bin_1min.py
  backtest/research/csv_pool.py
  backtest/research/csv_strategy_books.py
  backtest/research/strategy5_rules.py
  backtest/research/unified_exit_modea.py
  backtest/research/unified_exit_modeb.py
)
for path in "${FROZEN_PRODUCTION_FILES[@]}"; do test -f "$path"; done
git diff --exit-code "$IMPLEMENTATION_BASE" -- "${FROZEN_PRODUCTION_FILES[@]}"
git diff --exit-code "$IMPLEMENTATION_BASE" HEAD -- "${FROZEN_PRODUCTION_FILES[@]}"
git diff --exit-code -- "${FROZEN_PRODUCTION_FILES[@]}"
git diff --cached --exit-code -- "${FROZEN_PRODUCTION_FILES[@]}"
```

### 8.4 验收结论的范围

本 PR 只可记录 docs 路径、UTF-8/BOM/NUL、whitespace、锚点/链接/真实文件名、冻结数组与表一致性；未运行 §8.2、未新增测试、未实施 §7。将来 Slice C 要另填“commit / 基线 / 环境 / 命令 / exit / 实际 pin / skip / 冻结结果”，不得挪用 δ1/δ2 的历史 passed 数。默认 A/B 全部生产零 diff；如需 C，必须另立明确生产范围和验收合同，不能删除本冻结检查来假装默认路径仍通过。

## 9) Frozen production file table（δ1/δ2 超集；默认零 diff）

| File | 冻结理由 / 来源 |
|---|---|
| `backtest/research/ashare_fees.py` | δ1 费率/default/asymmetry/floor 不漂移 |
| `backtest/research/csv_ledger.py` | δ1/δ2 双向现金、整股、lot、参考价 rescale |
| `backtest/research/csv_simulate_loop.py` | δ1/δ2 chase/pool/step、资金门与 raw mark |
| `backtest/research/csv_daily_backtest.py` | δ1/δ2 daily 名称/档位/缩放顺序/入口域与费率 |
| `backtest/research/csv_minute_backtest.py` | δ1/δ2 minute 扫描/前置数据/门/入口域 |
| `backtest/research/csv_minute_backtest_v7.py` | δ1/δ2 v7 独立 lot/股数/现金/stage/时点 |
| `backtest/research/ashare_session.py` | δ1/δ2 ST/context、昨收、None predicates、T+1 |
| `backtest/research/market_layer.py` | δ1 ST 优先/板块/Decimal 档位 |
| `backtest/research/csv_common.py` | δ1/δ2 书 as-of、named band、bar/昨收前置条件 |
| `backtest/research/csv_artifacts.py` | δ1 产物 schema；P2 挂起 |
| `backtest/research/exdiv_map.py` | δ2 事件门/LAG/阈值/k/缺失行为，不改成权益源 |
| `backtest/research/exdiv_hold_hits.py` | δ2 引用的日期 normalize 与既有探针冻结 |
| `backtest/research/ashare_bars.py` | δ2 分钟帧/源域/缺 bar 与 volume 丢列行为 |
| `backtest/research/csv_daily_loader.py` | δ2 域/零量过滤与输出列 |
| `backtest/research/ashare_fill_clock.py` | δ2 已列；P1 时钟命名冻结 |
| `backtest/research/qlib_bin_daily.py` | δ2 qlib_day 域声明/读取不变 |
| `backtest/research/qlib_bin_1min.py` | δ2 qlib_1min 域/输出帧不变 |
| `backtest/research/csv_pool.py` | 新扩展：名称第二列/by-day/窗口/空名合同 |
| `backtest/research/csv_strategy_books.py` | 新扩展：BOOKS/hooks/卖出策略/P4 边界 |
| `backtest/research/strategy5_rules.py` | 新扩展：既有 force-sell 时点，不为 cap/None 改写 |
| `backtest/research/unified_exit_modea.py` | 新扩展：独立研究网格合同，不统一到 CSV 账本 |
| `backtest/research/unified_exit_modeb.py` | 新扩展：fractional-shares 近似保持独立，不借用作经济闭环 |

本表与 §8.3 数组的路径/顺序必须一致。表内零 diff 只证明这些文件；§8.1 的全路径白名单另行禁止其它生产与测试修改。不能以本表未列出为理由修改任何 Python、测试、CI 或数据文件；不扩大固定热路径 import-fence 测试的扫描面。


## 10) Changelog

- **v0.2 (2026-09-19，Asia/Shanghai)**：录入 Human GO P3δ6.1=A（残留+oracle），账本设计可选 B 且仅 docs；明确非 C，生产增股/入账/NAV 须另裁显式 C，本轮不授权且禁止修改。P1/P2/P4 继续挂起，保留 MC-2 勘误；未实施 slices、未新增/执行测试，经济残留未关闭，基线、白名单、冻结表与 §8 命令不变。
- **v0.1.1 (2026-09-19)**：r1 勘误——§2 书 NAV 收窄为「传入 close；none/raw 才是 raw mark」（见 reviews `plan-industry-align-p3-d345-econ-r1` MC-2）。
- **v0.1 (2026-09-19)**：post #123 核实 δ2/E-R6 仅参考价与书/v7 原股数/现金残留，隔离 Mode B fractional-shares 近似；打开经济 deferred 面，提出必须人裁 A/B/C（默认 A，可 B）、生命周期设计与纯送转/现金/混合 NAV oracle。仅 docs，无生产/测试修改、无回测/湖，经济残留未关闭、C 未授权。
