# domain-safety

## 结论

**REQUEST_CHANGES（文档契约与未来验收定义）；同意 §3 只承接 δ2、生产零行为变更的范围。** fail-closed 的裁决对象是证据是否足够，不能因此越权修改现有 fail-open 行为。DS-1、DS-2 应先回填计划；DS-3、DS-4 应明确加入未来 pins，不能把现有 B/C 定义当作领域安全已经闭合。本结论不要求本 PR 修改 Python、执行测试或回测。

已先完整读取目标计划 v0.1，共 323 行；下文计划行号均对应本次读取版本。按 `docs/prompts/prompt-adversarial-subagent-review.md:35` 执行 domain-safety 单路；未启动子 agent，未嵌套 `codex exec`，不代拟另外两路。依该提示 `docs/prompts/prompt-adversarial-subagent-review.md:11`，本对抗草案不计独立批准票。

开工基线核对：

- `git rev-parse HEAD`：`23024cc5bd93eeac777607eea13616058ab0f085`。
- `git rev-parse origin/master`：`1ad010cca013afe8186f20275cbdcca71e500823`，与 `docs/backtest/plan-industry-align-p3-d2-exdiv-2026-09-19.md:5` 的 IMPLEMENTATION_BASE 完全相同。
- `git merge-base --is-ancestor <IMPLEMENTATION_BASE> HEAD` 返回 0。两者间只有提交 `23024cc docs(p3-d2): ex-div / lot-cost rescale contract plan`，差异只有目标计划的 323 行新增。未把 HEAD 与分支起点应当不同误报为漂移。
- 生产与测试目录相对基线的 `git diff --exit-code` 返回 0；基线至 HEAD 的 `git diff --check` 返回 0；开工工作区干净。因此本报告引用的现有源码、测试行号也适用于 IMPLEMENTATION_BASE。

## Findings（file:line）

**DS-1 · P1 · 缺少因子在决策时刻可得的契约；日期 LAG 不能证明没有未来信息。**

计划位置：`docs/backtest/plan-industry-align-p3-d2-exdiv-2026-09-19.md:32`、`docs/backtest/plan-industry-align-p3-d2-exdiv-2026-09-19.md:46`、`docs/backtest/plan-industry-align-p3-d2-exdiv-2026-09-19.md:176`。这些条款定义有效前行、当日因子与 warmup，但没有交代当日因子何时可得，以及事后重建因子是否等同于当时版本。

证据链：`oskh_data/adj_factor.py:137` 至 `oskh_data/adj_factor.py:145` 实际以当日 `close_front / close_none` 计算 cumulative 因子；`backtest/research/exdiv_map.py:194` 至 `backtest/research/exdiv_map.py:210` 只读日期、代码、因子并按日期过滤，没有决策时点或版本过滤；`backtest/research/exdiv_map.py:295` 至 `backtest/research/exdiv_map.py:307` 使用当前行因子构造 k。此 k 在日线开盘止损之前、分钟扫描之前、v7 首根 bar 之前已使用，分别见 `backtest/research/csv_daily_backtest.py:307`、`backtest/research/csv_daily_backtest.py:344`、`backtest/research/csv_minute_backtest.py:597`、`backtest/research/csv_minute_backtest_v7.py:322`。

这不是只有理论风险：仓内前序调查 `docs/backtest/survey-exdiv-adj-data-prep-2026-09-16.md:76` 记录该比值含价格舍入噪声，`docs/backtest/survey-exdiv-adj-data-prep-2026-09-16.md:82` 记录仅有最新版 front、无逐日版本，`docs/backtest/survey-exdiv-adj-data-prep-2026-09-16.md:107` 明确把参考价修正方案的 as-of 口径列为缺口。这些是已有调查记录，本路没有重读湖验证其当前状态。

影响：当日日收生成的观测因子或后来重写的历史因子，被用于当日更早的参考价与档位。无舍入、统一乘法重标定时，公共因子可能在比值中抵消；现有证据不能保证这种抵消，也不能把“前一有效行”升级为“当时可知”。尚不能据此断言某笔真实交易已发生泄漏，但必须拒绝“未来函数已排除”的结论。

最小回填：在 §2/§6 明确区分“日期顺序不读取 D 之后的行”与“F_D 在开盘/扫描前可得”；后者标为未证、历史观测近似，不归入已关闭面。未来 B1 可加入截断到 D 与追加 D 后数据的前缀一致性 pin，以及无前行不得向后借因子的反例；同时明确这类合成测试仍不能证明原始数据的 PIT 可得性。若要关闭后者，须另案取得可得时间/版本证据，不在本刀改 loader 或引入采集。该问题属于 δ2 自身因子输入的时间语义，不能仅用 §3 的 δ3“ST PIT 已挂起”代替说明。

**DS-2 · P2 · 引用的 v7 止损夹具混用了同日价格尺度，证据限度没有写全。**

计划位置：`docs/backtest/plan-industry-align-p3-d2-exdiv-2026-09-19.md:99` 将已有测试列为“官方昨收映射与 trial stop 的公开 simulate_v7 路径”，但未限定第二个测试的输入不满足一致的 none 行情域。

直接证据：`tests/test_csv_minute_backtest_v7.py:295` 至 `tests/test_csv_minute_backtest_v7.py:305`，D1 14:55 分钟买价为 100，D1 日收却为 50，D2 分钟价 48，再注入 D2 的 `k=0.5`。D1 的前日日收还是 100。`backtest/research/ashare_session.py:56` 至 `backtest/research/ashare_session.py:60` 取 D1 日收再乘 k；`backtest/research/market_layer.py:80` 至 `backtest/research/market_layer.py:84` 据此定档。

静态数值推导：该夹具 D2 的映射昨收实际为 `50×0.5=25`，10% 档位为 `(27.50,22.50)`，分钟价 48 已高于这个涨停价；不传 map 时，昨收 50 给出跌停 45，48 才能成交为旧 stop。若将 D1 日收改为与买价一致的 100，则不传 map 的跌停为 90，48 会被 defer，不能继续期待旧分支真实 SELL。D1 日收 50 本身也不在以前收 100 计算的普通 10% 档内。卖出门只检查下限的源码见 `backtest/research/csv_minute_backtest_v7.py:344` 至 `backtest/research/csv_minute_backtest_v7.py:357`。

影响：该测试确实走了公开 API，也能观察参考价缩放改变 stop 判断；它不能证明一致 none 域下“参考价—档位—成交”的整条安全链。把它作为 B3 的正向模板，会允许错误昨收掩盖真正的跌停拦截。

最小回填：§2.5 明写这项夹具限制；未来 B3 增补自洽行情，并同时断言修正前后的 stop/defer 与实际成交。可用温和除权构造合法反例：存量买价 100、除权前最后日收 98、k=0.95、D 日价 89；修正后 stop=85.5、跌停=83.79，未修正 stop=90、跌停=88.20，两条链可独立解释。D1 若在 100 买入，应在夹具中补一致的收盘 98。以上只是未来向量建议，未运行或修改测试。

**DS-3 · P2 · B3 的“字段保留、新买/加仓不重乘”未明确验收除权日新老 lot 混持时的 T+1。**

计划位置：`docs/backtest/plan-industry-align-p3-d2-exdiv-2026-09-19.md:126` 锁定 T+1 不变，`docs/backtest/plan-industry-align-p3-d2-exdiv-2026-09-19.md:178` 要求新买/加仓与字段不变量，但没有要求“加仓后同日再次触发 stop，只卖老 lot”。`docs/backtest/plan-industry-align-p3-d2-exdiv-2026-09-19.md:247` 又允许以现列 B1–B6 完成情况作为 C 通过条件。

源码保留了正确的逐 lot 门：`backtest/research/csv_minute_backtest_v7.py:196` 保留 buy_date，`backtest/research/csv_minute_backtest_v7.py:229` 至 `backtest/research/csv_minute_backtest_v7.py:245` 两次按 `t1_sellable` 筛选卖出股数，`backtest/research/ashare_session.py:39` 至 `backtest/research/ashare_session.py:41` 要求买日严格早于当前会话日。既有 `tests/test_csv_minute_backtest_v7.py:83` 是无除权的新开仓 T+1；`tests/test_csv_minute_backtest_v7.py:101` 的加仓与清仓发生在不同日，均不能单独覆盖该交叉场景。

影响：只验证乘法及事件瞬间股数不变，不能证明随后的聚合 stop 不会卖掉当日新增份额；这里报告的是未来验收缺口，没有声称当前源码出现 T+0 卖出。

最小回填：在现有 B3 文件内，未来经公开 `simulate_v7` 构造老 lot 100 成本、前收 100、事件 k=0.5，14:45 在 52 加仓，随后在 48.5 触发 FOUR stop（仍高于当日跌停 45）。断言 D 日 SELL 只包含老 lot，当日新增 lot 保留 buy_date/price/股数，D+1 才能卖；事件缩放本身不增减现金，与后续真实交易现金变化分别断言。B2 同时明确 book 的 entry_idx 不重置、除权日新买不进入当日卖出 pass。无需新增生产状态，也不要求扩大四个具名测试文件的修改范围。

**DS-4 · P2 · B4 的整数结果不能辨别 Decimal 分位舍入是否被保留。**

计划位置：`docs/backtest/plan-industry-align-p3-d2-exdiv-2026-09-19.md:179` 唯一明列完整数值链是 `10×0.5→5→(5.50,4.50)`。现有 `tests/test_exdiv_refprice_engines.py:148` 也是同一结果；`tests/test_ashare_session.py:24` 至 `tests/test_ashare_session.py:33` 虽算出 mapped=9.5，却把 raw=10 传入后续档位计算。

证据：生产 `backtest/research/market_layer.py:80` 至 `backtest/research/market_layer.py:84` 使用 Decimal 与 ROUND_HALF_UP；既有合同 `docs/backtest/engine-ashare-correctness.md:93` 特别锁定 `1.65` 的 10% 跌停为 `1.49`。当前 B4 明列向量没有半分边界，浮点乘法或错误舍入也可得到相同简单结果。

影响：生产零 diff 能证明本 PR 没改算法，但这组向量不能承担未来“mapped prev_close 到 Decimal 档位完整数值链已钉牢”的证明。不是当前生产舍入错误。

最小回填：未来 B4 加入 `raw_prev=3.30,k=0.5→1.65→(1.82,1.49)`，在已列文件中断言映射结果实际传入档位函数，并检查映射跌停等值 defer / 涨停等值 skip。保持现有 float 映射和 Decimal 定档顺序，不借测试修改算法、容差或成交规则。

## 对 plan §3 / 主船范围的独立裁决

**范围成立，证据闭合暂不通过。** `docs/backtest/plan-industry-align-p3-d2-exdiv-2026-09-19.md:106` 至 `docs/backtest/plan-industry-align-p3-d2-exdiv-2026-09-19.md:116` 把 δ2 与 δ3/δ4/δ5 分开是合理的；本次差异也确实只有文档。保持 `docs/backtest/plan-industry-align-p3-d2-exdiv-2026-09-19.md:134` 的另案处理规则，不要求把以下已知风险在本刀改成 fail-closed。五个人裁仍未获 GO，本报告不替用户裁 A/A/A/A/A。

五项必查的独立核对结果如下。下表是范围与保留风险裁决，不将计划已披露的问题重复包装成新 Finding。

| 必查面 | 本路裁决与证据 |
|---|---|
| T+1 | 公开路径仍按严格更晚日期放行：daily `backtest/research/csv_daily_backtest.py:333`、minute `backtest/research/csv_minute_backtest.py:636`、v7 `backtest/research/csv_minute_backtest_v7.py:231`。书只改 cost/peak（`backtest/research/csv_ledger.py:155`），v7 重建 lot 保留 buy_date（`backtest/research/csv_minute_backtest_v7.py:196`）。未见本计划引入 T+0；混合 lot 的未来证明需补 DS-3。不能把 reason 名 `chase:T+1` 当作卖出资格证据。 |
| 未来函数 | 原始昨收 helper 只选严格早于 today 的日期（`backtest/research/ashare_session.py:45`）；因子扫描使用有序前行（`backtest/research/exdiv_map.py:294`），这些局部事实成立。但原始因子的可得时点未证，见 DS-1。v7 窗末名称应用于更早日期的既有非 PIT 行为已由 `tests/test_csv_minute_backtest_v7.py:273` 明确构造，源码 `backtest/research/ashare_session.py:81`；其 δ3 parked 状态不是“无未来函数”保证。 |
| 复权混用 | daily 跳过 map 的分支真实存在（`backtest/research/csv_daily_backtest.py:585`）；minute 无条件加载（`backtest/research/csv_minute_backtest.py:883`），v7 source 选择之后仍加载 context（`backtest/research/csv_minute_backtest_v7.py:557`、`backtest/research/csv_minute_backtest_v7.py:571`）。日/分钟来源还是独立参数（`backtest/research/ashare_bars.py:261`、`backtest/research/ashare_bars.py:275`），即使都选 qlib 也不能从名称证明同一数值尺度。计划 `docs/backtest/plan-industry-align-p3-d2-exdiv-2026-09-19.md:68` 至 `docs/backtest/plan-industry-align-p3-d2-exdiv-2026-09-19.md:72` 已正确限定，不要求本刀补入口；B6 捕获参数仅证明接线，不能证明域相容。DS-2 则是现有证据夹具本身的混域问题。 |
| 盈筹率单位 | δ2 的输入是累计复权因子与价格参考，`backtest/research/exdiv_map.py:194` 和 `backtest/research/csv_ledger.py:155` 没有引入 winner_ratio 字段；本次差异未触碰 CYQ。邻近 SSOT `qlib_cost/cyq.py:243` 至 `qlib_cost/cyq.py:245` 返回归一化筹码比例，`qlib_cost/cyq.py:256` 拒绝不在 [0,1] 的分位输入；不能把它与 [0,100] 百分数或除权 k 混用。`docs/backtest/plan-h13-cyq-tr-boundary-2026-09-15.md:15` 将 feeder 留在 MyQuant。本刀该项为“不涉及修改”，不为外部 feeder 单位作全链路认证，也不要求增设无关单位转换。 |
| 停牌/涨跌停 | 无 bar 发生在缩放前：daily `backtest/research/csv_daily_backtest.py:303`，minute `backtest/research/csv_minute_backtest.py:589`，v7 `backtest/research/csv_minute_backtest_v7.py:317`。map 仅精确命中当日键（`backtest/research/exdiv_map.py:102`），故停牌日事件不会自动补放；计划 `docs/backtest/plan-industry-align-p3-d2-exdiv-2026-09-19.md:59` 已如实承认。尤其要保留“事件日有日线、无分钟”也会漏掉 lot 缩放的前提，不能拿复牌日直接放 k 的 `tests/test_exdiv_refprice_engines.py:326` 证明一般补偿。零量过滤只在 loader 有 volume 时执行（`backtest/research/csv_daily_loader.py:95`、`backtest/research/ashare_bars.py:369`），内存模拟不能自动把任意占位 bar 当停牌。档位为 None 时 book 早退（`backtest/research/csv_minute_backtest.py:615`）；v7 持仓/加仓 helper 放行（`backtest/research/ashare_session.py:73`、`backtest/research/ashare_session.py:77`），首次开仓另行拒绝（`backtest/research/csv_minute_backtest_v7.py:392`）。这正是 δ4 保留的差异。Decimal 半分边界需补 DS-4。 |

经济边界也应继续保持：`docs/backtest/plan-industry-align-p3-d2-exdiv-2026-09-19.md:90` 的 100 股、现金 2000、raw close 10→5 对应权益 3000→2500，静态算术成立；源码参考价缩放不改股数/现金，mark 仍走原始价格。该声明诚实，不能因上述 Findings 转而要求本刀实现红利现金、送转增股或总回报模型。

主船可在补齐上述文字限定后继续作为 docs-only 计划评审；未来实施仍须 §5 人裁与真实 B/C 验收。即便未来 pins 全通过，允许宣称的也只是“限定前提下的 as-built 契约已验证”，不能扩写为“PIT、混域、停牌补偿、完整公司行动经济模型已安全闭合”。

## 未验证

- 未执行 pytest、gates、CLI、simulate 或任何回测；所有测试结论来自静态阅读，数值案例是手工推导，不报 passed 数。
- 未读取市场湖、因子 parquet、ex index、元数据 sidecar 或外部服务；未联网拉取 origin/master。本次 origin/master 是本地已有引用，未认证远端最新状态。
- 未核验 1.3/MyQuant 当前落盘管线、真实数据的重复日期、可得时间、历史版本、因子噪声大小、停牌覆盖率或真实交易所除权参考价。引用前序调查不等于重做调查；`oskh_data/adj_factor.py` 只作为仓内构造证据，不声称本仓应重新运行该构造。
- `oskh_data/adj_factor.py:7` 引用的旧 `docs/engineering/plan-front-adj-factor-dr-based-2026-07-09.md` 在本 checkout 不存在；DS-1 依赖的是已读实现与现存 survey，未用该缺失文件补证。
- 未穷举 1–10 每个策略的全部退出原因、全部 loader/source 组合或可选 numba 后端；未用当前零生产 diff 推断既有引擎全部领域规则正确。
- 因子同日多行、直接注入非有限 k 等输入未实测。计划 `docs/backtest/plan-industry-align-p3-d2-exdiv-2026-09-19.md:61` 已承认 loader 与直接 map 的校验强度不同；不能据此获得任意输入安全保证。
- Slice B/C 本身尚未实施，人裁尚未录入；不将本路建议写成已完成验收。只有指定 `domain-safety.md` 是本路写入产物。

## 模型与 effort（写你实际用到的）

- 本路由当前 Codex 会话直接完成；会话提供的模型身份为 **GPT-6**。
- 更细的实际服务模型 ID 与 reasoning effort 未向本会话提供可核验运行元数据，**无法确认**。未把提示文件示例中的 `gpt-6-astra` / `xhigh` 当作实际运行值，也未切换模型或调用其他模型。
- 未使用子 agent 或嵌套 Codex；工具只用于本仓只读审查、基线/静态检查及写入本报告。
