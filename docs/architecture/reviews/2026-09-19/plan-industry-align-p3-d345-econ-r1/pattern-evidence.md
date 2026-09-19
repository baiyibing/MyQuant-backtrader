# pattern-evidence

## 结论

**GO-WITH-NITS，仅适用于五份 docs-only 提案；不是生产 GO，也不是人裁。** 本路维持“怀疑过度类比”的立场，发现两处应回填的 as-built 限定遗漏：δ4 将默认 named-band 的未知板块拒绝泛化为书引擎事实；δ6 将估值函数消费的 close 一概称为 raw close。第一处会影响未来分叉 pins 的适用范围，第二处会模糊 δ2 已保留的输入域差异。未发现足以否定 A/A/B(design)/A 工作假设的生产越界证据。

开工实测 `git rev-parse HEAD` 为 `1e9994e88a67d0f5f651953fa7ad0e57b59a3677`，与指定 PR HEAD 一致；固定 IMPLEMENTATION_BASE 为 `1049b904bdd818dbb79f51f1830a008c8f83b141`，祖先检查成功。base→HEAD 只新增指定五份 Markdown，共 1231 行；tracked worktree/index 无差异。因此下文读取的生产代码和既有测试也属于该 IMPLEMENTATION_BASE，不是借后续实现为旧 plan 背书。行号以本次读取的 HEAD 文件为准。

已先通读审查提示与五份 plan 全文，再静态核对实际函数、调用链和测试断言。本路不修改 plan/生产/测试，不运行 pytest、gates、模拟器、CLI 回测或湖任务，不派生 agent、不嵌套 Codex；只写本报告。对抗草案不充作额外独立票，亦不代拟另外两路。

## Findings（file:line）

### PE-01 · P2 · δ4 的书侧未知板块真值表缺少 named-band 前提，与 δ3 已记录的例外不一致

- **位置**：`docs/backtest/plan-industry-align-p3-d4-v7-limits-none-2026-09-19.md:38`；同类未限定表述延续至 `:47`。对照 `docs/backtest/plan-industry-align-p3-d3-st-pit-2026-09-19.md:32`。
- **文档问题**：δ4 daily-held 行直接写“未知板块在 lots 卖出循环前 skip_unknown_board + continue”，未限定 `qlib_limit_pct is None`、名称非 ST。其 minute/chase/pool/step 行以真正的 `limits=None` 为条件，那个条件本身正确；问题是把“未知板块”无条件映射为 None/早拒。δ4 `:26` 已说明 ST 例外，却没有把 δ3 的固定 qlib band 例外带入这份声称可独立审阅的真值表。
- **实现证据**：`backtest/research/csv_common.py:80` 在 `qlib_limit_pct is not None` 时直接返回固定 band，绕过代码/名称判断；`backtest/research/csv_daily_backtest.py:286`、`:320` 和 `backtest/research/csv_minute_backtest.py:612` 实际把该 hook 传入。该路径并非虚构参数：`backtest/research/csv_strategy_books.py:713`、`:788` 为两类 topk 书设置固定档位；`tests/test_topk_dropout_book_a.py:74` 锁定 0.095，`:299` 对照锁定 version6 的 None 默认。另有 `backtest/research/market_layer.py:63` 的 ST 优先分支。
- **静态反例**：对非 ST 未知前缀 `999999.SZ`、有效昨收 100，named-band 返回 None；给定 `qlib_limit_pct=0.095` 则返回约 109.5/90.5。后者不会进入 `skip_unknown_board` 分支，后续是否成交仍取决于其它门。此反例由控制流得出，本次未运行模拟器。
- **影响**：直接将 δ4 表变成“所有书遇未知板块均早拒”的公共验收，会把现存固定 band 路径误判为回归，或者诱导在 helper 中增加代码拒绝而改变冻结生产行为。δ3 对同一 helper 的准确例外不能自动弥补 δ4 单独审阅时的缺口。
- **最小回填**：给 δ4 `:38`/`:47` 增加“默认 named-band、非 ST、且实际算得 limits=None”的前提；明确固定 band 为现存独立路径，本刀不改。未来 None pins 显式使用默认 named-band；若补反例，验证固定 band 不进入 unknown-board 分支即可，不顺势改 topk 策略或扩张生产范围。

### PE-02 · P3 · δ6 把默认 none 输入下的 raw mark 写成了估值函数的普遍属性

- **位置**：`docs/backtest/plan-industry-align-p3-d6-exdiv-economics-2026-09-19.md:28`。
- **文档问题**：该 as-built 行写“原股数×当日/最近历史 raw close”，但所引函数只消费调用方给定的 close，既不确认 raw，也不强制 raw。raw 是此经济残留夹具和默认 none 路径的前提，不是通用估值 helper 的保证。
- **实现证据**：`backtest/research/csv_ledger.py:173`、`:178` 直接返回输入 DataFrame 的 close；`backtest/research/csv_simulate_loop.py:399`、`:403` 用该值乘股数。`backtest/research/csv_daily_backtest.py:524`、`:526` 保留 dividend_type/qlib 输入，`:585` 对 front/back 或 qlib bins 跳过 exdiv 加载。`tests/test_exdiv_refprice_engines.py:635`、`:640`、`:642` 已明确区分 none/front/back/qlib_day 的入口合同。`docs/backtest/engine-ashare-correctness.md:135`、`:138` 也将入口差异及内存调用者的域责任单独写明。
- **影响**：可能把“原股数没有经济补偿”与“所有输入都按原始价格估值”混为一事，进而把 3000→2500 的 raw 夹具残留外推给复权输入，或者把价格域归一化夹带进经济修复。δ6 `:52` 保留混域残留、`:130` 限定经济 oracle，减轻了风险，但没有修正 `:28` 的普遍断言。
- **最小回填**：改为“消费传入行情的当日/历史 close；在默认 none/raw 输入下，原股数×raw close，缺行情回落 cost”，并指向 δ2 的入口域矩阵。维持原股数/现金未补偿的结论；不修改 loader、不统一复权域、不动已有 oracle 预期。

## 对 plan 默认人裁（δ3/δ4/δ5/δ6）与主船范围的独立裁决

以下是本路审查建议，不把用户给定工作假设或 plan 的推荐列记作已完成的人裁。

| 刀 | 独立裁决 | 依据与允许范围 |
|---|---|---|
| δ3 | **支持 A**；三项默认 A 不升格 | `csv_common.py:90`、`:100` 的单调名称更新与 `ashare_session.py:81` 的窗口平铺是两种现有合同；`csv_minute_backtest_v7.py:327` 确实消费同一 flat map。`plan-industry-align-p3-d3-st-pit-2026-09-19.md:48` 正确区分日期 as-of 与 available_at，`:56` 将 v7 生产修复留给 C。未来只补实缺 pins，不能用统一 helper 解释为已获修复授权。 |
| δ4 | **支持 A，先回填 PE-01** | `csv_minute_backtest_v7.py:345`、`:374`、`:389`、`:405` 支持首开拒绝与 held stop/add/timer 不拦截的分叉。`tests/test_ashare_simulate_predicates.py:173` 现有 held-add pin 只证明 gate-pass 后现金拒绝；plan `:55`/`:115` 没有冒称成功加仓已经覆盖。fail-closed 或 policy 参数仍须 `.1=C`，不能从次级 `.2=B/C` 偷渡。 |
| δ5 | **支持 B，仅设计**；不支持当前申请生产 C | `csv_ledger.py:187`、`:215` 与 v7 `:208` 的量来自预算；`ashare_bars.py:370` 只做整日零量过滤并丢列；`qlib_bin_1min.py:57` 输出无 volume。现有路径不提供容量预算。plan `:50`–`:57` 逐项区分输入、时间、共用预算和状态，`:110` 明确要求完整源合同/部分成交状态/迁移验收后才能申请 C；当前未给 p 默认值是正确的。 |
| δ6 | **支持 A；需要账本设计时可另选 B；生产 shares/cash/NAV 必须显式 `.1=C`** | `csv_ledger.py:147`、`csv_minute_backtest_v7.py:187` 只缩放参考价，真实 cash 只随现有买卖变化。plan `:87`、`:100`、`:126`、`:147` 对 A/B/C 出口的约束清楚；纯送转、现金、混合 oracle 不等于新账已接入。回填 PE-02 不需要生产更改。 |

表内简写文件均位于 `backtest/research/`、`tests/` 或本组 `docs/backtest/` 的已核对同名文件；下面给出其余重点的完整证据路径。

**复用裁决：不用 chip_indicator 替代这些合同；不将 StockDataReader 接入本船。**

- `backtest/chip_indicator.py` 在固定 base 与 HEAD 均不存在；退场来源见 `docs/backtest/_archive/plans/plan-cerebro-retire-2026-09-16.md:30`，当前仓边界见 `AGENTS.md:22`。现存 `oskh_factors/chip/core.py:377` 的函数处理筹码因子，`:405` 的分钟 hybrid 路径要求 front 日线，`:429` 返回 cyqk/asr/ckdw/prp；它不是名称 PIT、限价政策、容量预算或公司行动权益账。因“都有 volume/除权/成本”而复用属于过度类比，也会错引价格域与依赖。
- `oskh_data/reader.py:363` 的 StockDataReader 是行情 I/O 层，默认日线 adjust_type 为 front（`:369`），显式 `as_of_date` 在 `:380` 直接抛 NotImplementedError；scan 的同类行为见 `:418`。因此它不能补上 δ3 的名称发布时刻、δ5 的成交量 available_at/单位证明或 δ6 的登记/到账事件明细。未来 C 设计可以评估在加载边缘消费此 reader，但必须重新证明价格域、单位和缺数据行为；当前 A/B 无理由替换已冻结的 loader。
- 可复用的是各自实际合同：名称用 `backtest/research/csv_pool.py:161` 与 `backtest/research/csv_common.py:85`，限价微结构用 `backtest/research/market_layer.py:57` 与 `backtest/research/ashare_session.py:63`，费用使用既有 `backtest/research/ashare_fees.py` 和其接线 pins，数据路径走既有 resolver。不能为了“复用”让 `market_layer` 反向依赖 reader/策略/引擎；该叶子约束见 `backtest/research/market_layer.py:4`，session 不反向 import ledger/loop 的边界见 `backtest/research/ashare_session.py:11`。
- 四份新 plan 没有新增 chip/reader 禁令条目，本路不据此制造生产冻结漏洞：它们已有全路径白名单与零生产 diff 要求。可以补一个简短“不复用的理由”说明，但无需扩展 `tests/test_ashare_simulate_import_fence.py:13` 的固定枚举。该 fence 实际只检查 `:45` 所列导入；不能把它通过解释为全仓架构认证。

**Mode B 与 δ6：隔离成立，没有查到 C creep。** `backtest/research/unified_exit_modeb.py:423` 和 `:806` 明确 shares÷k；`:810`/`:819` 的 cash 是买卖现金流，`:1029` 写明 no cash dividend。`tests/test_unified_exit_modeb_exdiv.py:19` 与 `:64` 分别锁定 fractional shares 和 shared ledger 不改股数。这些测试可证明两个模型并存，不能证明真实权益闭环。δ6 `docs/backtest/plan-industry-align-p3-d6-exdiv-economics-2026-09-19.md:42`、`:72`、`:105` 与索引 `docs/backtest/plan-industry-align-p3-d345-econ-index-2026-09-19.md:16` 已正确禁止这种外推。本路没有将 design-only oracle 或 B 账本设计当作生产实现计划。

**主船：维持五份提案；P1/P2/P4 不重开。** 索引 `docs/backtest/plan-industry-align-p3-d345-econ-index-2026-09-19.md:18` 与前序 `docs/backtest/plan-industry-align-next-2026-09-19.md:77`–`:80` 一致。δ5 更改 fill 时点明确须另裁 P1（`docs/backtest/plan-industry-align-p3-d5-volume-cap-2026-09-19.md:106`）；δ4 输出 schema 与 δ6 trades 新列要求另行处理 P2（对应 plan `:92`、`:98`）；δ6 F-R8 保留 P4（`:77`）。没有以局部 P3δN 编号、Slice C 阶段名或 Mode B 的局部 P1 改写旧人裁。

**冻结与验收检查：没有发现 ghost commands 或冻结表漏项导致的本 PR 生产泄漏。**

- 四份 plan 都有 F-R1–F-R10；22 文件冻结数组与各自 §9 表的路径、顺序一致，四份彼此一致，且实测包含 δ1 的全部 10 项、δ2 的全部 17 项。全路径白名单覆盖 base→HEAD、staged、unstaged、untracked；明确未来 tests-only 须在新实施记录中批准实际测试路径，不能借有限冻结表改其它生产文件。证据例如 `docs/backtest/plan-industry-align-p3-d6-exdiv-economics-2026-09-19.md:169`、`:206`、`:309`。
- 静态核对五文档中提取到的 40 个不同 Python 路径均在 HEAD/base 存在；11 处具名测试引用对应 10 个不同测试函数，定义均存在。四份文档各 3 个 Bash 块经 `bash -n` 语法检查通过，五文件 UTF-8/BOM=0/NUL=0，base→HEAD `git diff --check` 通过。这些是本路的静态检查结果，绝不是 pytest/gates passed。
- 已有费用、名称、None、经济残留 pins 应按需复用。专门 held-add 成功、timer None、volume 新设计及经济生命周期组合仍是未来项，plan 未将它们冒报为已实现。δ6 未来命令含 `tests/test_exdiv_refprice_engines.py`，其中入口测试在 `:617`、`:683` 明确 stub 了 bars/map/index/simulate/writer；不能把这种内存接线检查类比为实际 CLI/湖回测证据。
- 索引 `docs/backtest/plan-industry-align-p3-d345-econ-index-2026-09-19.md:24` 是作者的历史文档核验记录。本路复核了上述部分，不替作者重新认证所有历史统计。开工已有未跟踪的评审目录；本报告也位于该目录，超出提案的五文件白名单，因此本路不声称在加入评审产物后的 worktree 原样重跑 §8.1 会 exit 0，更不把审查产物的存在误报为 PR HEAD 越界。

## 未验证

- 未运行任何生产模拟、backtest、pytest、gates、CLI 或湖访问；没有动态复现 PE-01/PE-02。两条 Finding 来自函数控制流与入口接线，不能据此声称新增 pins 已绿或已发现收益损失。
- 未认证真实名称/因子/volume/公司行动数据的单位、available_at、修订 PIT、税费和日期规则；这些是 plan 自己保留的证据缺口。本路只判断仓内事实与设计边界，没有开展外部金融/交易所规则核验。
- 未复现索引记录的发布副本流程、历史命令日志及全部 85 个锚点/41 个链接统计。已核对核心语义锚点、引用 Python 路径、具名测试、冻结一致性和命令语法；文件存在不等于断言全面覆盖。
- 未覆盖其它两路的全部 domain-safety/dissent-steelman 任务，未读取其它 lane 报告作结论来源；本路对完整三路汇总不作声明。
- 后续 δ5/δ6 若同时申请生产 C，真实新增股可卖、零碎股、现金可用时点、容量预算及费用粒度的组合仍须单独验收；本次 A/B 审查不预先批准该组合。

## 模型与 effort（写你实际用到的）

- 实际使用：本次单一 Codex 会话；会话身份说明为基于 GPT-6。未使用其它模型、子 agent、嵌套 `codex exec` 或模型覆盖参数。
- 精确部署 model ID 与 reasoning effort 未向本会话提供可核实值；定向查询相关环境变量及祖先进程参数也未取得。因此本报告将两者记为**未暴露／无法核实**，不冒填 `gpt-6-astra` 或 `xhigh`。`docs/prompts/prompt-adversarial-subagent-review.md:28` 的可用配置示例不能充当本次实际运行配置的证据。
