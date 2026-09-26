# 计划：topk 分钟执行模型开关（close / open / intraday / vwap）+ 涨停替补（2026-09-26）

> **状态**：2026-09-26 按 Kimi REQUEST_CHANGES 修订，待人裁。此 PR 仅改计划；批准后按 §5 切片实现，不改任何默认。
> **动机**：日线与分钟的收益差异仍值得拆分执行时点、涨停判定和拦截后额度去向。真实 master 的 TopK 分钟买入是 **14:55 close 一次尝试 + qlib 9.5% 浮点带 + 拦截不替补**，涨停拦截也发生在该报价上。初版把 2026-09-25 产物称为“分钟开盘”，缺少相应执行路径证据；本版撤下该组跑数及“三重保守下界”的归因，不把它们用作默认或 open 的验收数字。先登记 master-close 基线，再以显式研究开关量出执行模型敏感带。

**现状证据（本次核对 origin/master `696f317`，所列代码与本分支一致）**：

- [`csv_strategy_books.py`](../../backtest/research/csv_strategy_books.py#L1015) 中仅 `_apply_version11` 设置 `minute_open: True`（L1024）；[`_apply_topk_dropout`](../../backtest/research/csv_strategy_books.py#L1036) 未设置该钩子。
- [`csv_minute_backtest.py`](../../backtest/research/csv_minute_backtest.py#L1045) 的 `_pool_quote_for` 在无 `minute_open` 时调用 `_buy_px`；[`BUY_HM`](../../backtest/research/csv_minute_backtest.py#L145) = 14:55，[`_buy_px`](../../backtest/research/csv_minute_backtest.py#L583) 取该分钟 **close**，缺该 bar 时沿用 14:30–14:55 最后一根 close 的既有回退；该窗也无 bar 则不买。
- [tracker §6.5](topk-joint-research-tracker-2026-09-22.md#65-现有实现日线-vs-分钟as-built) 明记买成交 = 当日 **14:55 分钟收盘**。

**勘误 / 相对初版**：默认现状改为 14:55 close；09:30 open 改为新增 opt-in；旧跑数退出回归锚；ST/年龄补位只复用排名/名单思路，成交时替补是新增调度；明确 intraday 的 session 扫描和首次拦截替补组合；X-07 归修复专题，撤去错误 PR 归属，并区分真实档位 Decimal 路径与 TopK 的 qlib 浮点带。

## 1. 三根轴（A/C 独立设旗，组合见 §2.4；新行为默认关）

| 轴 | 旗标 | 取值 | 语义 |
|----|------|------|------|
| A 执行时点 | `--topk-exec` | `close`（默认=现状；不传同） | master TopK **14:55 close** 一次尝试，保留 `_buy_px` 回退及原有成交约束 |
| | | `open`（新增 opt-in） | 仅精确 **09:30 open** 一次尝试，参考 version11 的 `minute_open` 报价语义；缺 09:30 不借后行 |
| | | `intraday`（新增 opt-in） | 自 09:30 起扫描 session bar；walkdown 关时找首个 `open < limit_up` 的分钟，按该分钟 open 尝试成交；全天没有则到期。walkdown 开时采用 §2.4 的首次拦截移交 |
| | | `vwap`（P2） | 09:35–14:55 的 session 窗口内分片执行；量分布、切片报价及部分成交契约由 P2 明定，先做 close/open/intraday |
| B 涨停档位 | ——（不在本计划） | 现状仍为 qlib 0.095 | **X-07 归修复专题**；真实档位 Decimal 路径与 TopK 接线是两件事，见 §4 |
| C 拦截替补 | `--limit-walkdown` | 默认关；开须人裁 | 关：close/open 拦截额度闲置，intraday 保留原票重试；开：首次有效尝试被涨停拦截即将**整份额度**给下一名合格票，并按相同执行模式递归，见 §2.3–2.4 |

## 2. 语义细节（防歧义）

### 2.1 分母、额度与现金时点

- **分母不变**：每票额度仍 = `min(日额度,现金基数) × 0.95 ÷ D`。`D` 沿用原 planned 集合的 [`_buy_denom`](../../backtest/research/csv_simulate_loop.py#L87)：通常为 planned 只数，启用留空位时保留既有 `slot_count`。分配公式见 [`run_pool_buys_day`](../../backtest/research/csv_simulate_loop.py#L296)。与 #205 的资金配对解耦，不按成功成交数重分。
- **额度一次分配、整份移交**：每个原 planned 席位记住自己的额度 `q`；重试与替补都携带同一个 `q`，不再次除以 `D`，不将其他席位空闲额度合并过来。`q` 是预算，成交股数仍按原整手、费用及现金约束计算，实际成交额不要求恰等于 `q`。
- **现金与额度分开检查**：默认 close/off 的现金基数及处理顺序原样复现；新增 open/intraday 在当日 09:30 买入调度开始时冻结分配基数。替补在其**实际执行分钟**按当时可用现金检查 `q` 对应订单（含费用），不得用后来分钟的卖款预支、也不得因为发生替补而重算一份更大预算。现金不足沿用原 `skip_cash`，不触发涨停替补。
- 新研究路径须按分钟顺序处理资金到账；同分钟买入沿原 planned 顺序处理，候补归属该席位。卖出信号、报价和费用规则不变；默认 close/off 不借此改写现有循环。

### 2.2 intraday 扫描与报价

- **仅 session bar**：`hm ∈ [09:30,11:30] ∪ [13:00,15:00]`，边界均含；不读 09:25 竞价或午休分钟。依据 [`ashare_bars.py`](../../backtest/research/ashare_bars.py#L29) 的 session 常量、[`_in_session` / `annotate_session`](../../backtest/research/ashare_bars.py#L308) 以及湖读取时同一过滤函数（L373–377）。
- **从 09:30 开始**：若该分钟有效 open 已 `< limit_up`，且其他成交约束通过，就在 09:30 成交；此票的 intraday 与 open 相同。若 `open >= limit_up`，walkdown 关时继续找后续 session bar 的首个 `open < limit_up`，按该 bar 自身 open 尝试；等于上限仍拦截。
- **这是新增扫描逻辑**：现有 [`_open_quote_for`](../../backtest/research/csv_minute_backtest.py#L607) 只接受精确 09:30，不能原样复用为日内扫描。open 缺 09:30 即跳过；intraday 可从之后首个现有有效 session bar 开始，不补造缺失分钟、不把后行标成 09:30。
- `limit_up` 指当前书实际使用的上限，现状为 qlib 0.095 浮点带，并非已接入真实档位。`open < limit_up` 仅解除上限拦截，跌停禁买、买闸、现金等其他约束继续生效；缺数据或这些约束失败不能冒记成涨停替补。walkdown 关且有效报价全天都在上限的票，收盘记 `limit_retry_expired`；全天无有效报价按缺数据记，不算封板。

### 2.3 limit-walkdown：新增成交时调度

- **复用边界**：[`make_planned_for_day`](../../backtest/research/strategy_topk_dropout_rules.py#L128) 的 ST/年龄/15% 等过滤补位只在**计划阶段**运行，早于报价及涨停检查；当前 [`run_pool_buys_day`](../../backtest/research/csv_simulate_loop.py#L357) 拦截后直接 continue，没有成交时替补。本计划只复用按分数排名、合格名单筛选的思路，拦截后移交与重新报价是**新增调度**。
- **候补及去重**：从当日冻结排名中向下找下一名，沿用当日买入资格闸；排除持仓、原 planned 占用的票、已成交或已被其他席位选用的票。ST/年龄等计划补位及 `keep_buy_vacancy` 留空语义不变，本旗只处理涨停拦截，不填其他闸造成的空位。
- **整份额度 + 同模式**：下一名拿到被拦者的整份 `q`，在同一天、同一 `--topk-exec` 模式下报价并检查现金，原 planned 分母不变。若候补首次有效尝试也涨停，则继续向下移交同一份 `q`。
- **递归上限**：候补名单耗尽即停，余款闲置；每个候补当日最多被选择一次，每条链的候补尝试次数不超过当日候补名单长度。不得循环回头找已移交额度的原票，也不得重复花同一份额度。

### 2.4 intraday × walkdown 的组合（本版明确选择首次拦截）

**walkdown 开时，在所选模式的首次有效尝试被涨停拦截时触发，不等全日重试到期。** 原票立即退出该席位，当日不再重试；候补继承其额度和当前选择时刻 `t`。因此 intraday+walkdown 的含义是“优先换票”，intraday 单开的含义是“保留原票等开板”。

| 执行模式 | walkdown 关 | walkdown 开 |
|----|----|----|
| `close` | 14:55 close 单次拦截后额度闲置 | 同一 14:55 决策点按排名递归替补，各票沿用 `_buy_px` 报价及回退 |
| `open` | 精确 09:30 open 单次拦截后额度闲置 | 同一 09:30 决策点递归替补，仅用各票精确 09:30 open，不借后续分钟 |
| `intraday` | 09:30 能买即买；否则原票沿 session 重试，全天未过上限则到期 | 原票首次涨停拦截即换票；候补只扫描 **`hm >= t` 的剩余 session（含 t）**，用自身 open；若候补首次尝试也涨停，按同规则继续替补 |

- intraday 候补缺 `t` bar 时可等待其下一根有效 session bar；不得回看 `hm < t` 的便宜报价。至 15:00 后无剩余分钟就到期，不跨日。候补首根可成交则当场成交，原票以后即使开板也不复活。
- 这使 `{intraday, walkdown on}` 能在当日成交；不采用“全日失败后再选候补并回放早盘”的规则。若所有票都有有效 09:30 bar，两种模式的 walkdown-on 结果可能相同，这是允许的边界情形。
- `vwap × walkdown` 待 P2 明定分片/部分成交后额度归属，再人裁接入；未定义前显式拒绝该组合，不静默套用整笔替补。

### 2.5 可追溯与不变项

- 默认 close/off 的 trades `reason=pool` 及既有产物格式原样保留。新增模式用 `pool:open`、`pool:intraday`、`pool:walkdown:<exec>` 区分，并记录席位、原票、候补、选择/执行分钟、额度及报价 bar；不能再把 `pool` 解释成“开盘即成”。
- 新增研究计数 `limit_retry_fills / limit_retry_expired / walkdown_fills`：分别记录经上限拦截后重试成交、未解除上限而到期、候补实际成交；已移交的原票不再计 retry expired。候补名单耗尽、缺 bar、现金失败分别留审计原因。新字段放 opt-in 研究产物，默认产物不得因新增零值字段破坏 §3.1 字节锚。
- **卖出侧规则不动**：分钟 dropout 按扫描命中的那根 close 卖，涨跌停及 pending 规则沿原书（见 tracker §6.5）；不把它改述为统一日终收盘卖。**日线引擎不动**：本计划只挂分钟入口及 simulate 的 TopK 买侧路径。

## 3. 验收锚

### 3.1 默认回归锚

**默认 / 不传 / 显式 `--topk-exec close`，且 walkdown 关，均须逐字节复现当前 master TopK 分钟路径（14:55 close，含既有回退）。默认回归锚 = 现 master 分钟路径逐字节复现（数值待 P1 前从现产物重登记）。**

- P1 前固定 master SHA、2025 stag15 参数、pred/池/行情输入、依赖版本及产物 hash，核对产物确出自该 master 路径；缺可核验产物则先补跑登记，再动实现。对既有 trades / NAV / stats 产物做字节比较，不以改 golden 消除差异。
- `--topk-exec open` 是 P1 后另跑的研究模式；本版不为它指定未经核验的收益、拦截次数或买入数，不将其结果当成默认回归。

### 3.2 合成测试

| 场景 | 断言 |
|----|----|
| close 默认及缺 bar | 不传与显式 close 同 master；缺 14:55 时仅沿用 14:30–14:55 最后 close，该窗无 bar 不买 |
| open / intraday 起点 | 09:30 open 低于上限且其余约束通过 → 两者均在 09:30 成交；open 缺该 bar 不借后行，intraday 可扫之后有效 bar |
| intraday、walkdown 关 | 一字板全天不开 → 零成交且 expired；开盘在板、10:30 首次低于上限 → 恰在 10:30 open 成交；等于上限继续等 |
| session 过滤 | 即使 09:25 / 午休有低价行也不买；11:30、13:00、15:00 边界按 session 契约处理；无有效报价不冒记 expired |
| 整份额度及递归 | 下一名拿到 `q` 而非 `q/D`；候补也在板则再下一名继承同一 `q`；耗尽终止、不重复票、不改变原分母（含留空位） |
| 组合时序 | intraday+walkdown 在首次拦截时换票，可当日成交；原票后来开板不再买；晚选候补不回看 `t` 前 bar，缺 `t` 可向后扫；close/open 候补仍用本模式单次报价 |
| 现金时点 | 候补在执行分钟检查含费用现金，不借未来卖款；现金不足记录 skip_cash，不以涨停名义继续换票 |
| vwap（P2） | 分片预算合计等于原额度；实际成交额不超预算，未成交及整手余款归现金；部分成交与替补须先固定契约 |

### 3.3 产物纪律

成交价按模式追溯：close 必须对应 `_buy_px` 选中 bar 的 **close**；open/intraday（含同模式候补）必须对应实际执行 bar 的 **open**，不得倒填时点或造价。vwap 按 P2 冻结的逐片报价契约验证，不能套用“所有 fill 都是 open”的旧断言。

### 3.4 敏感带交付

2025 锚配置 × **{close, open, intraday} × {walkdown off/on} 六格**（见 §2.4）交付收益/回撤/成交数/重试到期/替补数，并做 **2026 窗交叉验证**。各格注明实际涨停价格路径，价域与其他配置保持一致。P2 定义并验收 vwap 及其替补组合后另补两格，完整矩阵为八格，不让 vwap 未定契约阻塞基础六格。

## 4. 边界与不做

- 不改任何默认：`--topk-exec` 默认 **close**，walkdown 默认关；open/intraday 均须显式选择。
- 不实现真实档位：**X-07 归修复专题**，见 [minute review README 的 X-07](../reviews/2026-09-25-minute-engine-review/README.md)。其对象是 [`market_layer.limit_pct / limit_prices`](../../backtest/research/market_layer.py#L57) 的**真实档位 Decimal 路径**；TopK 今天由 [`QLIB_LIMIT_PCT = 0.095`](../../backtest/research/strategy_topk_dropout_rules.py#L22) 接到 [`csv_common.book_limit_prices`](../../backtest/research/csv_common.py#L66) 的 **qlib 浮点带**。TopK 改用真实档位须另定接线并人裁，不能认为 X-07 合入就自动切换。执行时点与价格规则仍正交，各次实验明确记录所用判定。
- 不做排队/封单量概率模型；先做确定性研究开关，不包含打板/排板模型。
- 不动 joint_return 回放核、不动生产 fill/fee；不顺带改其他书的现金循环。
- `topk_score_exit` 是否同享开关：P1 先只挂 `topk_dropout`，P3 视结果再裁。

## 5. 切片

| 片 | 内容 | 依赖 |
|----|------|------|
| P1 | 先登记 master-close 字节锚；`--topk-exec close\|open\|intraday`（默认 close）+ 新扫描/时点现金调度 + opt-in 审计/计数 + 合成测试 + 默认回归复现 | 计划人裁；本片 walkdown 关 |
| P2 | `vwap` 分片报价、量分布及部分成交契约先明定，再做切片执行/成交率统计；与 walkdown 组合另经人裁后验收 | P1；组合实现还依赖 P3 |
| P3 | `--limit-walkdown`（**人裁后**才实现）：整份额度、首次拦截移交、同模式候补/递归上限 + 基础六格 + 2026 交叉 | P1，可与 P2 的独立分片部分并行 |
| P4 | （可选）真实档位接线获批并落地后，固定两种价格规则各跑完整可用矩阵 | X-07 修复专题 + TopK 接线人裁；仅 X-07 合入不构成触发条件 |

## 6. 维护

- 初稿：zcode（4090 机）· 2026-09-26；历史会话与 `csv_minute_topk_stag15_nostop_8a061ea4_2025_*` 仅作产物追溯线索，其旧“开盘”标签及跑数不再作为本计划的现状依据。
- 修订：Codex · 2026-09-26 · 对照 Kimi REQUEST_CHANGES 核查 master 代码及 tracker，完成上述勘误；仍是计划待人裁，不代表实现 GO。
