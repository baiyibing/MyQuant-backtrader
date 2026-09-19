# dissent-steelman

## 结论

**REQUEST CHANGES：反对将当前 A/A/B/A 推荐及其验收矩阵原样收口。** 本结论针对计划的证据与验收充分性，不指控本 PR 已修改生产，也不建议以修复之名实施任何 C。主笔应先回填下列勘误，再提交人裁；本路不构成 Human GO，也不冒充另外两路或三路综合意见。

开工实测 `git rev-parse HEAD` 为 `1e9994e88a67d0f5f651953fa7ad0e57b59a3677`，与指定 PR HEAD 相同；`git rev-parse '1049b904bdd818dbb79f51f1830a008c8f83b141^{commit}'` 返回指定 IMPLEMENTATION_BASE，ancestor 检查通过。base→HEAD 恰为五份新增 Markdown、1231 行；所查生产/测试/脚本/CI 相对 base 无差异。以下 plan 行号来自完整读取的 HEAD 工作区版本；源码和测试证据已与这一无生产差异的 base 对照。

已先通读审查协议及全部五份 plan，再读相关实现、既有测试与前序裁决。最强反对理由是：**δ4 未给出 held-None 的自然可达性证明；δ5 尚不能验收首次触发被容量拒绝后的剩余路径；δ6 的“无 bar 仍记权益”没有对应的无 bar NAV/窗口状态 oracle。** 这些问题能被当前列出的单点算术或 seed 测试绕过。

文档已有的边界应保留：δ6 明确禁止用 Mode B fractional shares 关闭经济残留，且生产经济变更要求 `.1=C` 与独立实施案；不存在据此直接判定“C 已获授权”的证据（`docs/backtest/plan-industry-align-p3-d6-exdiv-economics-2026-09-19.md:70`、`:72`、`:87`、`:147`）。五文档白名单也覆盖冻结表以外的受跟踪生产文件，不能把未列 `strategy7_rules.py` 本身当作冻结泄漏（`docs/backtest/plan-industry-align-p3-d345-econ-index-2026-09-19.md:22`）。

## Findings（file:line）

严重度“中”表示须修改计划的事实限定或验收合同；不是旧人裁 P1/P2/P4 的编号。下列反例均为静态推导或明确的设计夹具，未执行模拟、测试或回测。

**DS-1｜中｜δ5 推荐部分成交，却缺少“首次触发零成交后继续扫描”的决策与 oracle；P4 边界尚不能验收。**

- **Plan 证据：** `docs/backtest/plan-industry-align-p3-d5-volume-cap-2026-09-19.md:54` 规定先过既有门再限制成交量，`:57` 只提出 partial 后 stop/timer/pending 如何续行，`:68` 的 D4 仅验证卖出后数量，`:107` 推荐允许部分成交；`:96`、`:116` 同时挂起 P1/P4。`:123` 要求状态设计，但现有 D1–D7 没有明确扫描恢复位置、零成交路径或剩余持仓的日末 peak/mark 断言。
- **As-built：** `backtest/research/csv_minute_backtest.py:287`、`:290` 在第一个 stop 条件成立时立即返回；`:318`、`:329` 对其它退出原因同样返回。调用方每个 lot 只调用一次 scanner（`:623`、`:629`），先写回扫描所得 peak/peak_hm/reserved（`:659`），随后一次 `_sell`（`:670`）。`backtest/research/csv_ledger.py:292` 删除售出 lot，并在 `:298`–`:304` 递归卖出 rider。当前没有容量拒绝后的继续游标，也没有 partial 后的剩余日内扫描。
- **可证伪反例：** 昨日可卖 lot=300；10:00 首次触发 stop，但该桶 R=0；14:55 存在另一个真实退出触发且该桶 R=200。若只在 scanner 返回后加 cap，第一次没有卖成，后续触发仍不会被扫描。再令第一次只卖100，则剩余200如何更新此后的 peak、是否再次触发、是否带 rider 同卖，D4 的“留下老100+新200”无法回答。把残量沿第一次触发价延期成交，则又改变触发与成交时点的关系。
- **对“已覆盖”的反驳：** 文档提到了 pending/stage，不等于已经覆盖 scanner 的提前返回。一个只实现 `min(request, eligible, R)` 的参考账本能通过全部数量算术，却完全没有继续扫描能力；因此这些 oracle 不能支撑“部分成交状态设计已验收”。
- **最小回填：** 新增必须选择的状态表：`首次触发×零/部分/全部成交×后续触发×桶结束`，明确游标、残量、rider、peak/mark、原因与费用次数；至少加入上述两个多 bar oracle。若选择当日不再尝试，须明确写出这个结果及其代价。任何改变既有 touch/mark 关系或成交时点的候选，明确停在 P4/P1 的独立人裁出口。当前只需改文档，不实施 scanner/cap。

**DS-2｜中｜δ6 的无 bar 生命周期 oracle 没有估值真值；照搬基线 mark 会重复补偿。**

- **Plan 证据：** `docs/backtest/plan-industry-align-p3-d6-exdiv-economics-2026-09-19.md:119`–`:123` 要求权益/估值/事件次序，`:139` B6 要求“无 bar 仍按事件生命周期记权利”，但该行只列资格、重复事件和记权利；数值 B3/B4（`:136`–`:137`）都直接给了除权价。`:147` 允许 A/B 通过后称残留明确或账本设计验收。
- **As-built：** 书的 `market_close_mark` 在无当日 bar 时使用最近历史 close（`backtest/research/csv_ledger.py:173`–`:184`）；会话末按该值乘 shares（`backtest/research/csv_simulate_loop.py:394`–`:404`）。v7 无 records 会在 rescale 前 continue（`backtest/research/csv_minute_backtest_v7.py:318`–`:326`），最后按缓存 last_prices 估值（`:416`）。Mode B 则连无 bar 日也同时缩放 mark 和股数（`backtest/research/unified_exit_modeb.py:421`–`:427`）；它的停牌测试锁定的是这种近似（`tests/test_unified_exit_modeb_exdiv.py:35`–`:39`），不能替新权益账选择估值政策。
- **数值反例：** 沿用文档 q=100、旧价10、cash=2000、纯现金 c=1 的隔离前提，除权日无 bar、最近 mark 仍为10。新账确认应收100，而沿用基线 mark，NAV 就是 `2000+100×10+100=3100`，不是3000。純送转 b=1 时，若把200股/权益都按旧 mark=10 计量，则为4000。只断言“无 bar 权利存在、event_id 不重复”仍会通过。
- **不可逆窗口：** 若 pay/list 日位于无行情会话，是否确认现金/上市权益及是否立即可用于后续买入，必须先定；一旦错误现金进入下一笔买入，后来补 mark 不能靠对账抹去已经改变的交易路径。另需区分“单证券无 bar”与“所有证券均无 bar 导致没有会话”：书的日历取 bars 日期并集（`backtest/research/csv_common.py:48`–`:58`），本来就不是事件日历。
- **最小回填：** B6 加入纯现金及送转的无 bar 数值轨迹，明确旧 mark 的价格域、非交易权益估值、pay/list 转换及首个复牌 mark；增加无行情事件日是否进入账本日历的决策。不能以 Mode B `q/k` 或把基线残留 pin 改成守恒来过关。未定政策时应标“B 估值设计未验收”，而非只留一个泛化的 NAV 公式。

**DS-3｜中｜δ4 未锁定 held-None 的自然不可达性；δ3 未来改为 as-of 会改变这一前提，四刀独立决策缺少具体交接门。**

- **Plan 证据：** `docs/backtest/plan-industry-align-p3-d4-v7-limits-none-2026-09-19.md:4` 以 held fail-open 为主船，`:53` 只提醒 seed 不代表“自然首开仓可达未知板块”，`:115`–`:116` 要求两来源的 held add/timer pins。`docs/backtest/plan-industry-align-p3-d3-st-pit-2026-09-19.md:92` 允许另裁 v7 as-of 改造；索引 `docs/backtest/plan-industry-align-p3-d345-econ-index-2026-09-19.md:7`、`:12` 将两刀列为独立合同，却未要求在名称改造时重做 None 可达性证明。
- **As-built 推导：** 在普通、固定 Mapping、正常价格且不 monkeypatch 的 `simulate_v7` 中，state 从空仓建立（`backtest/research/csv_minute_backtest_v7.py:286`–`:288`）；自然首买必须 previous 非 None 且 priced 非 None（`:389`–`:400`）。daily closes 已一次性物化，后续日期仍能找到首买时存在的更早 close（`backtest/research/ashare_session.py:44`–`:46`）；name 则每个会话取同一 flat map（`backtest/research/csv_minute_backtest_v7.py:327`）。代码板块/名称不变，故首买可计算的档位后来不会因“无昨收/未知板块”变成 None。未知前缀若靠 ST 得到5%首买，整个 run 内仍是同一 ST 名称（`backtest/research/market_layer.py:63`–`:65`）。因此两类 held-None 都需要合成初态或改变上述输入/状态合同；不只是“未知板块首开”一个特例。
- **既有测试的证明范围：** `tests/test_ashare_simulate_predicates.py:43`–`:52` 用 monkeypatch 替换 `SimResult` 注入持仓；`:120`–`:135`、`:173`–`:191` 的分叉事实成立，但不是一次自然建仓后出现缺昨收的证明。
- **跨刀反例：** 未来若 δ3 C 引入逐日名称，未知前缀 D1=*ST、有昨收，可先自然买入；D2 改普通名，档位才首次变成 None。原本仅靠 seed 触发的 held fail-open 因名称接线改变而自然可达。δ4 helper 零 diff 并不能证明它的适用范围没变。
- **最小回填：** 增加“普通公开 run 不可达 / seed-only 防御合同 / 未来输入变化后可达”的逐来源表及一个自然建仓不变量 pin。为 δ3 C 增加强制交接：重新列 δ4 首开/held 可达性矩阵并显式接受或另裁政策；不可只用各文件零 diff 作为分叉未受影响的证明。默认 A 可以保留防御性 pins，但不得把它们提升为当前真实运行风险已复现或已修复。

**DS-4｜中｜δ4 的书侧未知板块早拒表漏了 δ3 已明确列出的 qlib band 例外。**

- **Plan 证据：** `docs/backtest/plan-industry-align-p3-d4-v7-limits-none-2026-09-19.md:38` 写未知板块在 lot 循环前 `skip_unknown_board`，`:39` 给 minute 同样结论；`:107` 的 DoD 没有 named-band/qlib-band 两域。对照 `docs/backtest/plan-industry-align-p3-d3-st-pit-2026-09-19.md:32`，该文已明确固定 qlib band 绕过 named limits。
- **As-built 反例：** `backtest/research/csv_common.py:80`–`:82` 在 `qlib_limit_pct` 非 None 时直接返回固定比例档位；daily/minute 的真实 held 路径分别传入该值（`backtest/research/csv_daily_backtest.py:320`–`:321`；`backtest/research/csv_minute_backtest.py:612`–`:614`）。该参数并非死接口：`backtest/research/csv_strategy_books.py:713`、`:788` 有实际 hook 配置。给未知非 ST 代码、prev_close=100、pct=.095，helper 返回109.5/90.5而非 None；因此该来源不能无条件归入书侧未知板块早拒。
- **对“已覆盖”的反驳：** 现有 `tests/test_ashare_simulate_predicates.py:80` 选择 version6；其 unknown-board 结果只覆盖默认 named-band 路径。δ3 提过例外，不会自动使 δ4 这份声称可独立审阅的真值表成立（索引 `docs/backtest/plan-industry-align-p3-d345-econ-index-2026-09-19.md:20`）。
- **最小回填：** δ4 §2 表头和相关 F-R/pin 显式限定默认 named-band，增加固定 band 的对照行；分别判定“代码板块未知”与“最终 limits=None”。这只是纠正 as-built 范围，不扩大到重写 topk 策略或 qlib 政策。

**DS-5｜中｜δ3 将真实 context→names→成交接线 pin 写成可选，当前测试可在名称接线失效时继续全绿。**

- **Plan 证据：** `docs/backtest/plan-industry-align-p3-d3-st-pit-2026-09-19.md:29`–`:30` 将 context/CLI 接线作为已核实锚点；`:117` B3 复用手工 flatten 的测试；`:120` 却写“v7 CLI context 链如需 pin”。默认 A 的交付正是名称分叉及真实买卖合同（`:92`、`:116`）。
- **既有证据缺口：** `tests/test_csv_minute_backtest_v7.py:276`–`:295` 直接调用 `flatten_pool_names` 后把结果送入 `simulate_v7`；未经过真实名称 loader/context。δ2 的 public main 接线测试也把 by-day names stub 为 `{}`，mock 模拟器，最后只核对 exdiv 参数（`tests/test_exdiv_refprice_engines.py:689`、`:692`、`:703`）。空池 CLI 测试没有两个日期的名称变化（`tests/test_csv_minute_backtest_v7.py:212`）。
- **可测性反例：** 若未来有人在真实入口错误地丢掉 `names=names`（当前正确接线位于 `backtest/research/csv_minute_backtest_v7.py:583`–`:584`），手工 flatten+simulate 的 ST 测试仍然通过；δ2 stub-context 测试的上述断言也不发现此错误。这不是声称本 HEAD 已断线，而是现有/计划允许的验收无法保护主船关键连接。
- **最小回填：** 将至少一个非空双日期名单的真实 `load_pool_names_by_day→load_limit_context→simulate_v7` 接线 pin 改为必需，并配套真实 main 的 names 参数传递断言；允许它们分成两个可组合的单元测试。仅 stub exdiv/行情/index/writer 等 I/O，名单用 tmp_path，不运行宿主 CLI 回测。正向/摘帽方向与窗口前缀的主船验收须依赖这条证据，不能只要求测试文件存在。

**DS-6｜中｜δ6 把登记资格作为已知夹具输入，却未给跨登记/到账窗口的期初权利和清仓后权利留存验收；这是不能事后从当前持仓恢复的信息。**

- **Plan 证据：** `docs/backtest/plan-industry-align-p3-d6-exdiv-economics-2026-09-19.md:118` 列了 record/pay/list 日期，`:119` 要锁 eligible lots，`:121` 提重放/修订；但 `:130`、`:139` 的 oracle 都直接给定资格。`:126` 把版本/重算/回滚合同留给以后 C，B 可以在有 pending 项时结束；表 `:95`–`:98` 没有对应的窗口初态决策。
- **As-built 证据：** 书 lot 的持有日期以本次 calendar 的 `entry_idx` 表示（`backtest/research/csv_ledger.py:72`），清仓时从持仓删除（`:292`–`:295`）；v7 清仓也删除 Position（`backtest/research/csv_minute_backtest_v7.py:244`–`:250`），每次 public run 新建 state（`:288`）。这些事实不等于权利永远无法恢复，历史成交或另存快照可以提供证据；但当前计划没有选定这两者之一，不能从 pay 日 positions 反推登记权益。
- **不可逆信息窗口反例：** 在受控夹具中，D0 登记时持有100股、每股现金1元；D1 除权后卖光；D3 才到账。D1之后应保持应收100，D3发生100现金转换，即使 positions 已空。再从 D2 恢复/开始迁移，若期初记录只有 cash 和空 positions，就无法区分“从未取得权益”和“已经锁权但卖光”。给定 `eligible=100` 的 B6 能通过，却没有检验这一丢失资格证据的窗口。完整历史重跑与截断/恢复应各自定义，不能混称一套迁移验收。
- **最小回填：** B 设计增加窗口初态的人裁行：要求从登记前完整重放，或要求带版本的期初 entitlement/receivable 快照；证据缺失时显式拒绝或继续标残留，不猜权益。增加“登记→除权→清仓→无持仓到账”和“连续处理 vs 带快照截断恢复”的 oracle。A 仍可只记录残留；但不得用给定资格的代数测试表示这部分账本/迁移设计已完成。当前不要求新增任何生产持久化能力。

## 对 plan 默认人裁（δ3/δ4/δ5/δ6）与主船范围的独立裁决

以下为本路建议，不修改用户的工作假设为既有人裁，也不授予实施权限。

| 刀 / 主笔推荐 | 本路裁决 | 必须补的门槛 |
|---|---|---|
| δ3=A | **有条件接受 A；反对原验收范围直接 GO。** `.2/.3=A` 只能保留输入残留，不能算 PIT 证明。 | DS-5 真实接线 pin 必需；任何未来 `.1=C` 增加 DS-3 的 δ4 可达性交接。无需现在采集名称或修改 resolver。 |
| δ4=A | **仅接受收窄后的 A。** 保留现状/防御性 seed pins；反对将 seed-only held-None 当自然运行已复现，也不支持据此直接选择 fail-closed C。 | DS-3 的可达性表与不变量、DS-4 的 named-band 适用范围；首开拒绝、交易尝试、T+1/现金后的 fill 分层仍保留。 |
| δ5=B(design) | **只接受研究设计层级 B，反对现在推荐 `.3=A` 的部分成交合同可收口。** 当前优先 `.3=B`（整笔不满足则拒绝）的候选可降低部分状态复杂度，但仍须回答拒绝后扫描问题。 | DS-1 状态/时点矩阵先完成。`.2=A` 的完成分钟桶与同 bar 容量近似必须逐入口区分；未能给出可得时间/执行关系时，优先 `.2=B` 的事后容量诊断设计，保持 P1。不得把这些次级选择当生产授权。 |
| δ6=A，可选 ledger B | **接受 A 继续明确残留；反对把现有 oracle 套件作为可选 B 已验收的出口。** | DS-2 无 bar 估值和 DS-6 期初权利合同是 B 的必答项；未解决时保留 pending。prod shares/cash/NAV 仍必须显式 `.1=C`、事件证据及独立实施 PR。 |
| index / 五文档主船 | **保留五份 docs-only 范围；反对按原文完成计划收口。** | 把 DS-1～DS-6 回填到对应 plan，并在索引补交接依赖。建议顺序可以保留；不能把“独立人裁”解释为无需验证名称、None、容量与权益状态间的组合前提。 |

本船无需扩大到生产或历史收益研究。P1=14:57、P2=产物列、P4=touch/mark 继续挂起；上述文档修订只识别未来哪些设计会触碰它们。尤其不能用 δ5 的容量续行需要来夹带 P4，也不能用 δ6 的守恒要求默认批准改参考价、改 trades schema 或迁移 Mode B `shares/=k`。δ6 的新经济估值也须区分会计记账与成交触发；若候选触及原 P4，另行列明，不能在 C 内顺手重开。

F-R* 形式上四份齐全，生产零变更、data-free、显式 C 与不复活交易栈均有文字锁。缺的是 DS-1/DS-3/DS-6 这种可验收的适用前提及交接条件，不是要求增加泛化口号或扩展 import-fence 扫描目录。主笔接受的让步须逐条登记并回填计划；仅在回复中承认不足不构成勘误完成（`docs/prompts/prompt-adversarial-subagent-review.md:9`–`:12`）。

## 未验证

- 未运行 pytest、四个 gates、任何 `simulate`/`simulate_v7`、回测、CLI、湖访问或真实数据探针。全部运行结果/覆盖率/收益影响均未验证；本报告的数值是隔离假设下的算术反例，不是市场或税务认证。
- 静态检查通过：base/HEAD 对照、三个 whitespace diff 检查；五份 plan UTF-8 解码通过且 BOM=0/NUL=0；四份 plan 的 Bash 命令块 `bash -n` 通过；22 项冻结数组与各自表及四文档之间一致。本路还静态核对了18个唯一 test/script 路径和10个去重后的反引号具名测试，均存在。统计口径不同于索引 `:24`，不据此声称复现其全部85个锚点、41个链接或11处引用检查。
- **没有找到 ghost test 文件/具名测试；命令实际通过仍未验证。** 四份 §8.2 都选择整份 `tests/test_csv_minute_backtest_v7.py`，其中含 tmp_path 下直接调用 `main()` 的既有单元测试（`tests/test_csv_minute_backtest_v7.py:212`–`:238`）；δ6 另选的 exdiv 文件也含 stubbed main 测试（`tests/test_exdiv_refprice_engines.py:680`–`:705`）。因此应将“禁止 CLI”明确限定为宿主/真实 I/O 回测，或明确筛选，不能按字面声称这些命令完全不调用 CLI 入口。这一表述问题不等于发现湖访问或虚构测试。
- 未复现主笔当时的逐字 §8.1 执行记录及发布副本字节检查。开工时本 out-dir 已有未跟踪内容；本路没有读取其它 lane 的报告。当前 reviewer 产物本来就不在 plan 的五文档白名单内，不能把如今在该工作区执行白名单会拒绝 review 文件，反推为主笔此前“exit 0”造假。
- 未发现当前 PR 的生产冻结泄漏、Mode B 经济已关闭的误报，或 A/B 已授权生产 C 的直接矛盾。DS-1～DS-6 指出的未来验收漏洞，不应改写成当前 production 已损坏的事实。

## 模型与 effort（写你实际用到的）

本路实际由当前 **Codex / GPT-6** 会话完成，未 spawn 子 agent，未套层 `codex exec`，未调用其它模型或云端审查。当前会话未向我暴露可核验的精确部署 model ID 与 `model_reasoning_effort` 配置值，故这两项记为**未验证**；不把审查提示词推荐的 `gpt-6-astra + xhigh` 冒报为实际运行配置。精确值应由调用方本次进程的启动元数据补证。
