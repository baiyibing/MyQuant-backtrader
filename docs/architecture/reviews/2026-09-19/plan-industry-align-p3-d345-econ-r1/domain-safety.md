# domain-safety

## 结论

**GO-WITH-NITS，仅针对 docs-only 提案；不构成生产安全验收或 Human GO。** 工作假设 δ3=A、δ4=A、δ5=B(design)、δ6=A（可另选账本设计 B）可以保留。发现 1 条 P2 表述勘误、2 条 P3 范围/验收边界补充；应回填文档，不能借此修改生产实现。对“PIT 已关闭”“容量已具备因果性”“除权经济已闭环”一律 **NO-GO**。

开工执行 `git rev-parse HEAD`，结果为指定 PR HEAD `1e9994e88a67d0f5f651953fa7ad0e57b59a3677`；`git rev-parse --verify 1049b904bdd818dbb79f51f1830a008c8f83b141^{commit}` 成功，且该 IMPLEMENTATION_BASE 是 HEAD 祖先。base→HEAD 的全部变更恰为本次五份 plan/index；所查生产/测试源码与基线无 diff。以下行号来自本次读取的 HEAD/worktree 版本。先全文读取提示文件和五份文档，再核查实现、既有测试源码与跨文档约束。

没有发现本 PR 的生产冻结泄漏、δ6 C 暗中授权或 P1/P2/P4 被重开。保留历史 fail-open 行为的合同，不等于认可该行为满足 fail-closed 安全标准；本路认可的是准确记录和冻结范围。

## Findings（file:line）

1. **DS-01 / P2：δ6 将书账本的通用估值描述为 raw close，缺少源域前提。**

   定位：`docs/backtest/plan-industry-align-p3-d6-exdiv-economics-2026-09-19.md:28`，相关残留概括在同文件 `:49`。表格将书 NAV 无条件写成“原股数×当日/最近历史 raw close”。实现 `backtest/research/csv_ledger.py:173`、`:178` 直接取传入 DataFrame 的 close；`backtest/research/csv_simulate_loop.py:399`、`:403` 直接按该值估值，没有 raw 域识别或转换。`backtest/research/csv_daily_backtest.py:568`、`:571` 允许 qlib_day/front/back 输入，`:585` 只是跳过 E-R6，随后仍把同一 bars 交给模拟器。`backtest/research/qlib_bin_daily.py:6` 的仓内域声明则是后复权。

   因此，“不增股/不入红利”的账本事实成立，但 raw 价跳变造成的特定 NAV 差额只在 none/raw 且行情与事件落日一致的夹具中成立。通用账本事实与 raw 路径残留混写，会让后续 δ6 C 把已复权 close 再叠加真实权益，产生重复补偿。此处也与该 plan `:52` 保留混域残留、`:123` 要求显式验证估值域的约束不够一致。

   **最小修订：** 表格改为“按输入 bars 的 close 估值；none/raw 路径才是 raw mark”，给 `:49` 及 B1/B2 残留 oracle 就地标明价格域前提。保留 daily 已有连续域跳过与 minute/v7 源组合残留，不把本勘误转成域转换实现。核实入口行为可沿用 `docs/backtest/plan-industry-align-p3-d2-exdiv-2026-09-19.md:75`、`:79`、`:81` 的分源合同。

2. **DS-02 / P3：δ4 书侧未知板块早拒的真值表遗漏固定 qlib band 例外，与 δ3 的限定不齐。**

   定位：`docs/backtest/plan-industry-align-p3-d4-v7-limits-none-2026-09-19.md:38`，以及同文件 `:107` 的 Slice A 完成条件。这里把未知板块直接对应为持仓循环的 `skip_unknown_board`。但 `backtest/research/csv_common.py:80` 明确在 `qlib_limit_pct is not None` 时返回固定 band，绕过名称/板块计算；daily/minute 消费点分别为 `backtest/research/csv_daily_backtest.py:320`、`backtest/research/csv_minute_backtest.py:612`。这不是虚构接口：`backtest/research/csv_strategy_books.py:713` 已有策略接线。

   `docs/backtest/plan-industry-align-p3-d3-st-pit-2026-09-19.md:32` 已正确记录该例外。δ4 的“实际 limits=None 就早拒”仍然成立；不成立的是脱离 named-band 前提的“未知板块必然产生 None/早拒”。两份 plan 独立阅读时，当前写法会把政策范围扩大，未来 pin 也可能误选固定 band 入口。

   **最小修订：** δ4 §2.2 标明书侧未知板块反例使用 `qlib_limit_pct=None`、非 ST 名称；增加固定 band 绕过板块分类的边界行，并让未来 B2/B5 明确该前提。无需修改 predicate、扩大 BOOKS 或重裁 P1/P2/P4。

3. **DS-03 / P3：δ5 D6 需要区分容量 oracle 的时间前缀保证与现有 loader 的整日过滤。**

   定位：`docs/backtest/plan-industry-align-p3-d5-volume-cap-2026-09-19.md:70`，对应未来 pins 为同文件 `:129`、`:131`。D6 要求追加 t 后巨大 volume 不改变 t 前分配/成交；这是合理的设计目标，但不能把它扩大成当前 loader→撮合链已经具备的保证。

   `backtest/research/ashare_bars.py:370`、`:371` 以整日 volume 总和决定该日所有分钟是否保留，再丢弃 volume。最小静态反例：相同 09:30 零量记录，后续记录也全零时早盘记录被删除；追加当日 14:55 正量记录后，09:30 记录被保留。既有 `tests/test_csv_minute_backtest.py:27`、`:43`、`:51`、`:52` 正是在固定“早盘零量、后续正量时保留早盘”行为。v7 在保留记录上会从首根 open 评 stop（`backtest/research/csv_minute_backtest_v7.py:343`），故这一输入筛选具有影响早时点交易尝试的通道。这里是源码推导，未运行模拟，也不声称任何真实停牌样本已经成交。

   plan `:28` 已承认不是逐分钟零量拒绝，`:134` 也已区分设计 oracle 与生产验收；问题是尚未把该具体的未来数据依赖交接给 D6。只在预制完成桶上验证 cap，不能证明端到端因果性。

   **最小修订：** D6 注明仅证明独立容量模型；在 B1 增列上述 loader 前缀反例，按 as-built 固定并显式保留为残留。未来 C 如要宣称因果可交易，必须单独解决/隔离该输入筛选依赖并做真实入口前缀验收；当前不得改变零量过滤、移动 fill 时点或将缺 bar 与合法零容量合并。

## 对 plan 默认人裁（δ3/δ4/δ5/δ6）与主船范围的独立裁决

下表是本路审查意见，不代替人裁；局部选项 C 与 Slice C 验收阶段必须继续分开。

| 项目 | 独立裁决 | 证据与边界 |
|---|---|---|
| δ3=A | 同意记录现状与未来 pins；不批准 PIT 修复声明 | `docs/backtest/plan-industry-align-p3-d3-st-pit-2026-09-19.md:48` 已明确名单日期不证明 available_at；`backtest/research/ashare_session.py:83`、`:97` 确实平铺窗口名称。未来追加名称影响早日 v7 决策是保留缺陷，不是安全认证。 |
| δ4=A | 同意合同化；生产 fail-closed 仍须另案 | `docs/backtest/plan-industry-align-p3-d4-v7-limits-none-2026-09-19.md:91`、`:94` 没有把方向选项当授权；`backtest/research/ashare_session.py:74`、`:78` 的 None 双门 False 及 v7 首开拒绝/held 放行均属实。DS-02 修正表格适用域。 |
| δ5=B(design) | 同意只做设计，拒绝据此宣布 cap 已接线或可因果交易 | `docs/backtest/plan-industry-align-p3-d5-volume-cap-2026-09-19.md:54`、`:56` 对资格/资金/无效 volume 保持拒绝原则，`:110` 要求完整合同后才申请生产 C。DS-03 应进入 B 级验收边界；部分成交的 stage/pending/ride_with/费用仍是待完成设计。 |
| δ6=A；可选 B | 同意残留/oracle 或独立账本设计；生产增股、现金、NAV 明确禁止默认授权 | `docs/backtest/plan-industry-align-p3-d6-exdiv-economics-2026-09-19.md:87`、`:100`、`:147` 均要求显式主裁决 C 和独立实施证据。次级 C 不独立授权。DS-01 收窄 raw 路径描述即可，不需要借勘误进入 C。 |
| 主船 / index | 同意五份 Markdown 的讨论范围与 A/A/B/A 顺序，不能批量生产 GO | `docs/backtest/plan-industry-align-p3-d345-econ-index-2026-09-19.md:7`、`:14`、`:18` 清楚保留逐刀授权、δ6 C 和 P1/P2/P4 挂起。上述勘误不改变该范围。 |

必查项逐项裁定：

- **T+1：** `backtest/research/ashare_session.py:39`–`:41` 按买日早于会话日判可卖；v7 `_sell_lots` 在 `backtest/research/csv_minute_backtest_v7.py:229`–`:234` 逐 lot 筛选，无可卖则不产生现金流。`tests/test_csv_minute_backtest_v7.py:363`–`:386` 已有除权日新老 lot 混持、只卖旧 lot 的源码证据。δ5 D4（plan `:68`）与 δ6 F-R5（plan `:74`）正确要求部分卖出及新股可卖资格独立；这些是已读到的实现/测试内容，未重新跑绿。
- **未来函数：** ST 窗末名未来信息及书侧数据发布时刻未证，δ3 已明示；因子修订/available_at 未证，δ6 `:51`、`:118` 仍保留。另有 DS-03 的分钟输入筛选依赖。不能以日期排序或设计 oracle 通过替代真实可得性证据。
- **复权混用：** DS-01 必须收窄通用 NAV 描述。δ6 `:51`、`:52` 正确保留因子恢复日错域、qlib_day 混域与 SMA 残留；本次冻结不解决这些问题。
- **盈筹率单位：** 五份提案没有引入 cyqk/winner_ratio 运算或单位转换，base→HEAD 也没有因子代码变化。实际研究筛选在 `backtest/research/chip/filter_stock_pool_by_chip.py:158`、`:164` 使用 0.5/0.8，`oskh_factors/chip/core.py:494` 直接作比例差，`:510` 仅保留小数、不乘 100。按 0–1 比例保留，不能把 δ5 participation p 或 δ6 k 当盈筹率。未发现本 PR 的百分比/比例混用；不要求把 chip 接到本刀。
- **停牌/涨跌停：** None 不代表依法无限价；无 records 的 v7 在缩放前 continue（`backtest/research/csv_minute_backtest_v7.py:318`–`:326`）。缺事件日 bar 不回放的经济残留在 δ6 `:51`、`:139`、`:141` 明确保留。涨跌停门与真实 fill 分层、ST 优先与 Decimal 合同有源码支持；DS-02/03 补充其入口范围和零量语义。

额外对抗焦点核查：

- **Mode B 不是经济闭环：** `backtest/research/unified_exit_modeb.py:422`–`:424` 是 cost/mark×k、shares÷k，`:805`–`:820` 没有独立红利现金分录；`:1029` 明示 no cash dividend。δ6 `:42`、`:72` 与 index `:16` 的否定性边界正确，没有发现借 fractional shares 关闭本刀的声明。
- **F-R / 人裁 / scope：** 四份 plan 均有 F-R1–10、主层级与次级选项边界。δ4 `:92`、δ5 `:106`、δ6 `:98` 分别要求涉及产物/时钟时明确重开 P2/P1；δ6 `:77` 还禁止 C 顺带改 ST/limits/cap。没有发现本次生产授权遗漏导致的越界。
- **生产冻结与 ghost commands：** 静态核对四份 plan 的 22 项冻结数组/表逐项同序，且覆盖 δ1/δ2 冻结超集；12 个 Bash 块只作 `bash -n`，语法通过。提取的 17 个不同 test/gate 路径均在 IMPLEMENTATION_BASE 存在，10 个独立反引号具名测试引用均找到 `def`。未发现所查验收命令引用幽灵文件；存在性/语法不等于执行成功或未来 pin 已覆盖。`git diff --check IMPLEMENTATION_BASE HEAD` 通过。

## 未验证

- 未运行 pytest、四个 gate、合成模拟、CLI、回测、湖访问或收益比较；未增加任何测试、生产代码、配置、CI 或数据文件。没有启动子 agent 或嵌套 codex exec。
- 未认证实际名称/公司行动供应方的 PIT、版本历史、volume 单位、真实复权 dump 域、交易所规则或税费日期。此处所有数值与交易路径判断均为仓内源码/既有夹具审阅或标明的静态推导。
- 未复现索引 `docs/backtest/plan-industry-align-p3-d345-econ-index-2026-09-19.md:24` 的全部历史计数、`:26` 的发布副本操作。本次静态提取口径与其历史统计不作等同，也不把未复现写成虚假声明。
- 开工已有本轮 review 输出目录为 untracked；原五文档白名单脚本会将 review 产物判为额外路径。本路没有为通过检查扩白名单或删除他路文件，也没有把原 §8.1 在当前审查目录下冒报为 exit 0。只覆盖写入本路 `domain-safety.md`。
- Findings 的最小修订尚未回填被审 plan；修订权留给调用方。本路未替用户作正式人裁，亦未批准任何生产 C。

## 模型与 effort（写你实际用到的）

- 实际会话身份：Codex，基于 GPT-6（运行上下文提供的身份）。没有使用其它模型或子代理。
- 精确后端模型 ID 与 reasoning-effort 参数未向本会话暴露，无法独立核实。审查提示中的 `gpt-6-astra + xhigh` 是默认配置说明，不作为本次实际运行参数证据；本报告不冒填该值。
