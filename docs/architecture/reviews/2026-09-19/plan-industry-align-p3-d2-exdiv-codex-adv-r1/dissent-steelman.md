# dissent-steelman

## 结论

**REQUEST_CHANGES：反对按当前 v0.1 的范围说明与 B1–B6 验收表直接推荐全 A。** 主船仍可限定为 δ2 的文档与未来 data-free 契约测试，但必须先补足参考价错域的另一类残留、不可达字段的证明边界及遗漏的接线向量。本意见不要求在本轮修生产，也不要求并入 δ3/δ4/δ5 或完整公司行动记账。

最强反例是：**除权日因子缺失、下一日恢复时，loader 可以把跨日 k 写到下一日；那一天的昨收及除权日新买 lot 已在新价格域，却再次乘 k。** 这与计划已承认的“停牌日键不回放”不同：行情可以连续、有有效有限 k，错域依然发生。只分别验证因子 LAG 与手工注入 map 的模拟接线，不能识别这一问题。

本路按强制反方立场完成；依 `docs/prompts/prompt-adversarial-subagent-review.md:11`，这是对抗草案，**不计独立票**。未 spawn 子 agent，未运行嵌套 `codex exec`。

基线与阅读版本：

- 开工执行 `git rev-parse HEAD origin/master`：HEAD=`23024cc5bd93eeac777607eea13616058ab0f085`；本地 `origin/master`=`1ad010cca013afe8186f20275cbdcca71e500823`。
- 计划 `docs/backtest/plan-industry-align-p3-d2-exdiv-2026-09-19.md:5` 的 IMPLEMENTATION_BASE 与上述 `origin/master` 完全一致。`git merge-base --is-ancestor IMPLEMENTATION_BASE HEAD` 返回 0；基线到 HEAD 仅新增本计划，生产与既有测试行号未漂移。当前 HEAD 是计划提交，不应误写成仍等于实施基线。
- 先完整阅读计划 1–323 行；其 Git blob 为 `50372694b6e3b6e091f27bfbf39b79e77afd98a5`。以下行号均对应此次阅读版本。开工工作区为空净状态；本次唯一写入为本报告。

## Findings（file:line）

**DS-01 · P1 · 有效因子前行与昨收前行不是同一时间锚点；B1/B2/B4 分开通过仍不能证明“映射到 D 域”。**

定位：`docs/backtest/plan-industry-align-p3-d2-exdiv-2026-09-19.md:32`、`docs/backtest/plan-industry-align-p3-d2-exdiv-2026-09-19.md:57`、`docs/backtest/plan-industry-align-p3-d2-exdiv-2026-09-19.md:82`、`docs/backtest/plan-industry-align-p3-d2-exdiv-2026-09-19.md:176`。

证据链：`backtest/research/exdiv_map.py:210`、`backtest/research/exdiv_map.py:216` 将无效因子从 cleaned series 移除；`backtest/research/exdiv_map.py:295` 取前一有效行，`backtest/research/exdiv_map.py:310` 在当前行日期按大跳变兜底写 k。这个日期未必是 ex index 的日期。消费者则独立取最近实际行情昨收：`backtest/research/csv_common.py:43`、`backtest/research/csv_daily_backtest.py:315`；分钟对应 `backtest/research/csv_minute_backtest.py:594`、`backtest/research/csv_minute_backtest.py:605`；v7 对应 `backtest/research/ashare_session.py:44`、`backtest/research/ashare_session.py:59`。这些路径没有核对两种前行的日期或价格域。

最小反例（源码推演，未执行）：

| 日期 | raw close / 可成交行情 | 因子输入 | ex index | loader 输出 |
|---|---|---|---|---|
| D−1 | 10 | 1 | 无 | 无 |
| D | 5 | NaN 或缺行 | 有 | 无 k |
| D+1 | 5 | 2 | 无 | `k=0.5`，落在 D+1 |

到 D+1，消费者把 raw 昨收 5 再乘 0.5 得到 2.5，普通档位变成 `(2.75, 2.25)`。若 D 日书路径以 5 新买一 lot，D+1 的存量缩放又把其 cost 改为 2.5。前一日旧 lot 的确可能需要补缩放，新 lot 与昨收却不需要；用同一个当日 k 无条件作用三者并不成立。这是 loader 自己接受缺行后生成的有限 k，不是计划 `:61` 排除的任意非法 map 注入，也不要求停牌、front/back 或 qlib 混域。

不可逆窗口还早于补到因子的时点：把上述 k 换为 `19/20=0.95`，D 日 raw open/close=9.50，D−1 存量 cost=10、止损 2%。D 当天无 k，旧止损线为 9.80，旧跌停线为 9.00，源码会允许 9.50 的 `stop_loss:gap_open`（`backtest/research/csv_daily_backtest.py:340`、`backtest/research/csv_daily_backtest.py:345`）。`backtest/research/csv_ledger.py:261` 已更新现金并记 SELL；下一日参考价重标定不能撤销这笔成交。这里的“不可逆”限定为本次模拟的成交与状态沿时间前进，重新运行可以重算；不是声称 docs 提交或文件不可回滚。

对“已有覆盖”的反证：缺因子测试的因子夹具止于 NaN 当日，没有恢复日（`tests/test_exdiv_map.py:117`）；引擎测试使用预制同日 map（`tests/test_exdiv_refprice_engines.py:19`）。v7 现有试仓止损向量中，D1 分钟买价是 100，daily 却给 D1 close=50，再在 D2 注入 0.5（`tests/test_csv_minute_backtest_v7.py:295`）；按 session 接线，其 D2 档位基准实际是 25，但断言只检查买入及止损 reason（`tests/test_csv_minute_backtest_v7.py:302`）。这个向量能验证局部止损字段变化，不能证明 lot、昨收与事件落日的一致性。

要求回填：§2.2/§2.4 增列“因子恢复日与行情已换域的时间错配”，收窄“已映射到 D 域”的前提；B1–B4 增加一条合成 parquet 经真实 `load_exdiv_ratios` 输出、直接交给公开模拟器的跨日链，不在两层之间手工修 map。分别观察 map 日期、旧/新 lot cost、昨收档位和恢复前真实 SELL；按现状 pin 残留即可，修复仍另案。仅写“缺 bar 不回放”或“经济补偿 deferred”不能关闭此 Finding。

**DS-02 · P2 · B3 的完整字段承诺缺少可达性划分；`add1_A1 != None` 无法由当前公开模拟自然产生。**

定位：`docs/backtest/plan-industry-align-p3-d2-exdiv-2026-09-19.md:41`、`docs/backtest/plan-industry-align-p3-d2-exdiv-2026-09-19.md:99`、`docs/backtest/plan-industry-align-p3-d2-exdiv-2026-09-19.md:178`、`docs/backtest/plan-industry-align-p3-d2-exdiv-2026-09-19.md:189`。

源码确实存在缩放非空 `add1_A1` 的分支（`backtest/research/csv_minute_backtest_v7.py:194`），但该字段默认是 None（`backtest/research/csv_minute_backtest_v7.py:73`）。首次 `_buy` 构造 position 时不赋该字段（`backtest/research/csv_minute_backtest_v7.py:215`），加仓成功后的 stage 转换分支也不赋该字段（`backtest/research/csv_minute_backtest_v7.py:374`）；本文件所有 `add1_A1` 引用只有声明与上述缩放。`simulate_v7` 每次新建状态，也没有 initial-state 参数（`backtest/research/csv_minute_backtest_v7.py:277`、`backtest/research/csv_minute_backtest_v7.py:288`）。

因此，“跑过公开 simulate_v7 + 观察所有返回 position 的字段”可以一直只看到 None，即使删掉非空分支也无法识别。反过来，monkeypatch 构造器或 helper 人工塞非空值，只能证明人为状态下的兼容分支，不能当作自然交易会走到该状态的证据。计划没有区分这两种证明，B/C 的“完整集合、必需 pins 均执行”容易出现条件断言空过或过度声称。

要求回填：将 B3 明确拆为“人工 Position 的 helper 字段/不变量矩阵，包含非空 add1_A1”和“自然公开模拟可达的 entry_A/avg_cost/peak/Lot.price、先缩放后扫描及新买/加仓路径”。非空 add1_A1 标注为兼容字段分支，禁止写成已验证自然加仓赋值。若使用测试注入，也要标注注入点与证明限度；不需修改生产或扩展状态 API。

**DS-03 · P2 · B4 的唯一新数值链不能识别 Decimal 舍入退化，已知能识别的向量又不在定向验收命令中。**

定位：`docs/backtest/plan-industry-align-p3-d2-exdiv-2026-09-19.md:98`、`docs/backtest/plan-industry-align-p3-d2-exdiv-2026-09-19.md:179`、`docs/backtest/plan-industry-align-p3-d2-exdiv-2026-09-19.md:234`。

计划 B4 给出 `10×0.5→5→(5.50,4.50)`，它能发现漏乘 k，却不能区分 Decimal HALF_UP 与普通 float/round；两个实现都会给出相同数字。实际生产舍入点是 `backtest/research/market_layer.py:80`。已有 session 测试虽算出 mapped=9.5，却将 **raw** 送进档位函数（`tests/test_ashare_session.py:25`、`tests/test_ashare_session.py:30`），计划对这一不足的识别是正确的，但所提替代数值仍未测试舍入分界。

仓库已有能区分该行为的 `1.65→(1.82,1.49)`（`tests/test_market_layer.py:48`），该文件未列入 §8.2 定向测试清单（计划 `:234`、`:241`）。冻结表零 diff 是变更审计，不能替代“完整数值链已被 pin”的测试证据；全量 CI 可能覆盖也不等于本节定向命令已经覆盖。

要求回填：在既定 `tests/test_ashare_session.py` 着陆一个 `raw_prev=3.30,k=0.5→1.65→(1.82,1.49)` 的贯通向量，必须把实际 mapped 返回值送入真实档位函数。保留 10→5 的直观例子即可，无需新增生产文件、测试文件或 CI 配置。

**DS-04 · P2 · 主船把台阶加仓列为 E-R6 接线，但 B2/B4 可以全部通过而完全没有触达该独立消费点。**

定位：`docs/backtest/plan-industry-align-p3-d2-exdiv-2026-09-19.md:39`、`docs/backtest/plan-industry-align-p3-d2-exdiv-2026-09-19.md:177`、`docs/backtest/plan-industry-align-p3-d2-exdiv-2026-09-19.md:179`、`docs/backtest/plan-industry-align-p3-d2-exdiv-2026-09-19.md:247`。

独立消费点是 `backtest/research/csv_simulate_loop.py:341`；它不是 pool/chase 的复用调用。daily 与 minute 分别在 `backtest/research/csv_daily_backtest.py:471`、`backtest/research/csv_minute_backtest.py:749` 调用并单独传 exdiv。现有 step 测试确实调用了 `run_step_adds_day`，却没有传 exdiv（`tests/test_csv_simulate_v8_hooks.py:112`、`tests/test_csv_simulate_v8_hooks.py:118`）。B4 只要求复用 held/chase/pool vectors；B2 的“多 lot、新买不重乘”也未要求 lot 来自 `add:step20`，可以全由 pool 买产生。

可区分的最小状态向量：已缩放基础 lot cost=5、尚无 step lot、足够现金、`sizing=per_name`，报价 raw 昨收=12、事件 k=0.5、当日报价=6.60。真实 step 条件相对基础 lot 成本计算（`backtest/research/strategy8_rules.py:57`），正确映射后的涨停线为 6.60，必须挡住 step；若只漏掉台阶支路的映射，涨停线成了 13.20，就可能落下 `add:step20` BUY（`backtest/research/csv_simulate_loop.py:353`、`backtest/research/csv_simulate_loop.py:377`）。其他 held/chase/pool 向量仍可保持绿。此例是内存状态的静态测试设计，未在本轮运行，也不声称它已构成自然策略完整交易历史。

要求回填：B2/B4 明列 step 路径与两引擎的 exdiv 参数传递，至少包含“映射后命中涨停而阻止 step”及“允许 step 时新 lot 保持当日原始成交 cost”两个观察点。可以落入已允许的 `tests/test_exdiv_refprice_engines.py`，使用合成状态证明 helper 分支、公开模拟证明调用接线；不要用多 lot 数量或普通 pool 买代替台阶来源证明。

## 对 plan §3 / 主船范围的独立裁决

**§3 主船仍只选 δ2；当前 v0.1 退回补契约，不给未来 A→B→C 的验收方案直接放行。** §3 的 docs-only 状态本身没有伪称交付（`docs/backtest/plan-industry-align-p3-d2-exdiv-2026-09-19.md:111`），问题是把各局部行为分别钉住后，仍可能过早收口“参考价纠正”的完整边界。

| 裁决面 | 本路独立意见 |
|---|---|
| P3δ2.1 / P3δ2.2 | 当前 A 文案不足。DS-01 的迟到因子错域必须进入 as-built 残留和跨层 pin；DS-02 必须划清 helper 兼容字段与公开可达状态。完成这些文档勘误后，仍可维持零生产 diff 的 A。 |
| P3δ2.3 | 可以继续 deferred，但必须将“股数/红利缺失造成的经济残留”与“错域导致的错误触发、旧成交不能靠后续 rescale 撤销”分开。后者不能由 NAV 特例 3000→2500 替代。 |
| P3δ2.4 | 保留阈值及等号两侧 pins。DS-01 的例子远离噪声阈值，不能用已有噪声声明关闭。 |
| P3δ2.5 | minute/v7 无连续域跳过已被计划承认，本路不把该承认重复报成新发现；但其声明不能覆盖 none 域下的因子/行情落日错配。B6 的 loader/simulate 参数捕获也不能替代 DS-01 的真实组合链。 |
| B/C 收口 | 增补 DS-01 跨日链、DS-02 可达性分类、DS-03 舍入分界与 DS-04 step 分支；将每项对应的观察点写入验收记录，才有条件宣布必需 pins 已执行。 |
| 仍挂起的工作 | P1/P2/P4、δ3/δ4/δ5、shares/现金红利记账、生产去重/补偿修复、湖与宿主回测继续挂起。以上勘误不要求扩大这些实施面。 |

主笔若采纳，须把 DS-01–DS-04 的让步、对应 plan 段落及 pin 变更列入勘误表；不能只在评审回复里改口后保留原验收文案（`docs/prompts/prompt-adversarial-subagent-review.md:10`）。

## 未验证

- 未运行 pytest、CLI、回测、湖读取、下载或 merge；未安装依赖。所有反例与数字均来自源码分支及算术推演，不是实测通过/失败报告。
- 未对真实数据确认缺因子恢复日错配的发生频率、影响标的、损益规模或数据构建器是否另有保证。本仓 loader 接受这种输入已足以要求契约说明；不能把“输入可进入代码”写成“湖中已发现该异常”。
- 未访问远端或 fetch；基线比较针对开工时本地 `origin/master` 与计划固定 SHA。未执行计划 §8.2 的未来验收，也未挪用既有 CI 成绩。
- 未审查另外两路的报告，不代拟 host 综合裁决。计划已明说 helper 非幂等、停牌事件不保证回放、经济残留未关闭，本路没有把这些已承认事实伪装成新缺陷。
- 运行时未暴露可核实的具体模型后缀与 reasoning effort；下节如实记录这一限制。

## 模型与 effort（写你实际用到的）

- 模型：本会话系统标识为 **GPT-6 / Codex**；具体服务模型 ID 后缀未向会话暴露，无法核实。
- Effort：本会话未提供可核实的 reasoning-effort 配置值；已检查的专用环境变量也未给出该值，记为 **未暴露 / 未验证**。
- 全程仅使用当前模型会话，未切换模型、未调用子 agent。提示词 `docs/prompts/prompt-adversarial-subagent-review.md:28` 列出的 `gpt-6-astra + xhigh` 是环境说明，不能据此冒认本路实际运行参数。
