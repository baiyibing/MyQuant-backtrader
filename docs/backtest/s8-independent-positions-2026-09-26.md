# 策略 8 家族：按信号日期独立持仓、持仓整体退出（2026-09-26）

工作树基于 master `5518323`，分支 `fix/s8-independent-positions`。第一提交 `cb38c32` 已建立按信号日期独立的持仓；用户随后明确要求首买与价格加仓作为一个持仓整体退出，本次后续提交落实该决定，覆盖第一提交的逐 lot 独立退出临时语义。

范围仅为 8、8.2、8.3、8.4、8.5、8.6 六书默认 `per_name`，包含日线、分钟 `fix_minute_cash_order=False/True`。不增加开关或新策略版本；8.1、v7、其他书及六书非 `per_name` 路径保持原行为。用户已批准这些目标书旧低资金用例改为严格现金异常；未提高任何资金，默认 2,100 万或目标 OFF golden 如出现不足仍须停止报告。

## 1. 最终规则及实现口径

### 1.1 独立持仓、再现和价格加仓

- 同码在后续信号日期再次入池时新建独立持仓，身份如 `600000.SH@20251031`。新仓各有完整预算，不受旧仓盈亏或旧仓 `add_gate` 限制。**再现按新仓经过指数新仓 gate**；8.2 本身没有指数 gate，继续没有。卖出当天仍可按新信号首买，没有增加 `skip_sold_today`。
- 8/8.4/8.5 以各持仓自己的首笔成交成本为 +20% 台阶锚，每级仍使用一份 `name_budget`；每持仓每日最多成功一级，成交后才递增历史级数。首买锚与历史级数不随部分卖出回退；全部股份卖完才关闭，关闭后不再加仓。独立组处于待退出状态时也不再加仓。
- 8.3 每个信号独立分配 50% 试仓、50% 确认补仓。该持仓 `px >= 首笔成本` 且 `peak >= 首笔成本 × 1.03` 时补剩余 50%，与是否仍在池无关，每个持仓只成功补一次。8.3 继续遵守 `INDEX_BLOCKS_ADD=True`；8/8.4/8.5 的价格台阶不受仅挡新仓的指数 gate 限制。8.2、8.6 没有价格加仓。
- 日线价格加仓在收盘池买之后扫描；分钟在 14:55 池买之后扫描，保留 14:30–14:55 缺 bar 回退。价格加仓涨停仍跳过，不产生追买。
- 09:45 追买以代码加原信号日期为队列键，保留独立预算，不同信号日互不覆盖。8.3 先把预算算为 50% 再排队，修复旧 `per` 泄漏到 100 万的问题。追买按新仓经过指数 gate；日线仍以当日 open/close 近似追买判断。T+1、peak/stale 的起点是实际首笔成交日。

### 1.2 持仓整体成本、peak 与退出

每个独立持仓只评估一套止损、止盈、trail、stale、保留涨停/开板及其他既有退出规则。退出成本为：

```text
持仓成本 = sum(该持仓仍持有 lot 的股份 × 该 lot 成交成本) / 仍持有总股份
```

成本沿用原账本的买入成交价口径，**不把佣金计入成本**；费用继续在买卖现金和每笔成交中单独扣除。除权时仍走现有显式价格/权益调整路径。价格台阶仍锚定首买成本，退出判断则使用加权成本，两者用途不同。

peak 初始为首买价，从首买的 T+1 起按原行情规则更新；加仓不重置 peak 或峰值分钟。stale 从首买实际入场日计算，不从加仓日重新计数。任一退出信号针对整个独立持仓；其他信号日的同码持仓不受影响。8.2/8.6 也经过同一整体视图，单 lot 时成本、peak、时钟和既有退出行为保持一致。

卖出仍逐 lot 记录原数量、成交费用和 `(position_id, lot)`，以保留成交归属与原输出列。逐 lot 输出不再表示逐 lot 独立评估卖点。

### 1.3 T+1、待退出与跌停

退出当日只卖 `entry_idx < 当前交易日` 的可卖股份。今日新加股份继续留仓，成交记录在原退出原因后追加唯一后缀 `|t1_deferred`，例如 `trail:band:2|t1_deferred`；下一个交易日第一个可卖时机继续卖出，避免价格反弹后取消已经触发的整体退出。标记依据是该 lot 在原退出日是否被 T+1 锁定，不是最终成交日：加仓后日线重评遇收盘跌停时，保留原退出原因及原退出日，不能给整个持仓统一拼后缀。日后解禁成交，原本可卖的旧股不带后缀，当日新加的股份才带后缀；其间继续跌停不改变归因。

- 未启用成交量约束时，延迟股份在下一可卖日首个可用且允许卖出的 bar **open** 成交；日线为日 open。缺 bar、跌停或其他既有卖出约束仍顺延。
- 启用完成桶成交量约束时，bar open 尚不能使用该 bar 的完整成交量；在首个容量可用的已完成 bar **close** 成交。已完成 bar 的 open 跌停而 close 已打开时，按 close 判断是否能卖；不借用尚未完成的成交量。
- 对四本有价格加仓的书，因成交量不足只卖出部分，或退出尝试无可用容量时，整个持仓保留退出意图，后续可卖 bar 继续处理；纯容量延迟不额外加 T+1 标记。待退出期间不再增加价格仓。
- 8.2/8.6 没有组内加仓；单 lot 仍以整体视图评估，但结算沿原账本路径，包含可选容量约束下首次尝试/部分成交后的原停止扫描语义，以及原已存在 pending 的处理。不会额外把原非 pending 的容量不足强制改为下一 bar 重试。
- 普通、尚未生成 pending 的跌停触发沿用各书原 defer/下 bar 或次日复评规则，未一律改为锁定信号；已经存在的 pending（包括 T+1 尾股）保持原退出原因，跌停卖不出则继续顺延。这样保留 8.2/8.6 等单 lot 的既有跌停行为。

“跌停 defer”与“已经挂起退出”因此并不等价。8.3 普通退出尝试被跌停拒绝、且没有生成 `pending_exit` 时，持仓仍可在当日 14:55 通过原价格确认条件补仓；已经挂起退出的持仓一律不补仓。该边界保留现有行为，分钟 OFF 的确认 peak 还受下节的保守截取限制。

### 1.4 日线与两个分钟时钟

日线继续先处理当日旧仓退出，再处理追买、池买与收盘价格加仓；普通收盘止盈仍按原规则挂次日开盘。**仅对当日成功价格加仓的持仓**，在加仓后以新加权成本、当前收盘价重评退出；触发时当日收盘卖旧股，今日新股按 T+1 延迟。此处不重新拿当日加仓前的 low 触发新成本止损，避免回看加仓前行情。

分钟 ON 沿真实事件时点处理。分钟 OFF 对有价格加仓的四书（8/8.3/8.4/8.5）把旧仓扫描分成两段：先扫截至 14:55 的卖点，再执行原 OFF 阶段中的 09:45 追买、14:55 池买与价格加仓，最后按新成本扫 14:55 之后的卖点。其用途是让当日加仓参与后段整体退出，并防止 15:00 未来 peak 倒灌 14:55 补仓。**OFF 仍非完整因果现金时钟**，例如 09:45 追买仍排在前段扫描之后；需要真实现金时序继续使用 ON。无价格加仓的 8.2/8.6 保留原 OFF 全日卖出扫描顺序。

该必要分段使四书 OFF 的 14:55 买单不能再借用 14:59 卖款；对应旧低现金用例按用户规则改为异常，见 §3.3。未通过提高资金掩盖时序变化。

8.5 的 `close_clear` 保留缺 15:00 bar 时回退到当日最后一根 bar 的规则，先处理该 bar 的原有盘中退出判断，再尝试收盘清退回退。在分钟 OFF 中，若最后一根位于 14:55 或之前，回退发生在前段扫描，使用加仓前成本；若触发退出导致持仓关闭或挂起退出，随后价格加仓会被拦住。若最后一根晚于 14:55，回退发生在后段扫描，使用已成功加仓后的成本；有 15:00 bar 时亦在后段执行。因此缺失末 bar 可能改变“清退与加仓”的先后顺序，本轮只明确这一既有回退口径，不改变行为。

8.3 分钟 OFF 的 `confirm_peak` 为 `min(卖出扫描后首买 lot 的 peak, max(日初 peak, 当日不晚于 14:55 的最高 high))`；当日新追买且没有日初快照的持仓沿用其入场 peak。这一截取防止 14:55 之后的高点倒灌补仓，但不会用完整前缀 high 反向抬高卖出扫描器已保留的 peak。边界是：普通退出尝试被跌停 defer 后，扫描器可能停止继续观察，导致当天后续、不晚于 14:55 的合法高点也未进入确认 peak，因而少补一次仓。只要未挂起退出，且保留下来的 peak 与现价仍满足确认条件，该日仍可补仓；已有 `pending_exit` 则直接禁止补仓。该限制是保守的现有行为，本轮不改为强制观察所有前缀 high，也不把普通跌停 defer 自动改成 pending。

### 1.5 严格现金、needed 口径与输出

六书 `per_name` 的池首买、追买和价格加仓，现金不足支付整单及费用时抛出 `InsufficientCashError` 并停止。异常公开 `date`、`code`、`needed`、`available`、`shortfall`，其中 `shortfall = needed - available`；不缩单、不中途改预算，不改默认总资金 `21,000,000`。8.1 和其他书保留原 `skip_cash`。

**needed 当前为按预算及原整手/force_min 规则算出的实际下单本金，加原费用；不是完整预算加费用。** 现金检查在可选成交量容量裁剪之前。例：预算 1,000、价格 6，只能下 100 股，默认佣金 0.60，needed 为 600.60；现金 939.06 足以买入，即使低于预算 1,000。是否应改为“完整预算加费用”的更严格门槛仍列为待用户确认项，本次保留已获要求的实现口径。

共享 `init_sim_state(hooks)` 自动、幂等绑定这六书的策略上下文；直接传 version8 hooks 调用共享买侧也必须严格检查，不能因为绕过 CLI 而静默回到 skip_cash。用户点名的四个底层用例因此均已迁移。内部 `fullstrat_research_book` replay 明确移除借用 version8 hooks 时的这项上下文，保留其范围外实验行为。

目标书 BUY/SELL/EOD_MARK 在原列之后保留第一提交新增的 `position_id`、`entry_signal_date`；存活 lot 序列化同样带身份。容量不足产生的 SKIP 行也携带这两项身份，覆盖首买、追买、价格加仓和卖出尝试。组内 lot 号从 0 开始，完整键为 `(position_id, lot)`。不对范围外书添加列或统计键。六份 HELP_LOCK 已说明整体退出和 T+1，删除逐 lot 独退与“单码单日上限 2 笔”的旧说法；关键句和旧上限禁用文字均有断言锁定。目标书 `execute_buy` 收到不含 `@` 的 `position_id` 时抛出清晰的 `ValueError`，避免以字符串拆分的 `IndexError` 代替输入校验。

## 2. Baseline 范围与逐 case 差异

以下按 **历史 baseline → 第一提交 cb38c32 → 本次最终规则** 比较；金额单位为元。两套矩阵保留原资金和行情，本轮只重录目标书 case：主矩阵只有 8.3 日/分钟两例字节变化，次级矩阵同样只有 8.3 日/分钟两例变化。其余目标 case 与 cb38c32 原字节一致；非目标书继续对照不可变历史文件。

两套 fixture **没有资金不足异常，也没有 `|t1_deferred` 成交**。因此下表的本轮经济变化来自整体加权成本退出，不来自资金上调、T+1 延迟或新输出列。T+1/容量及现金失败由专项测试覆盖。输出身份和再现行为变化发生在历史→cb38 阶段，仍逐项保留下表。

### 2.1 主 OFF/raw/canonical 矩阵：12 个目标 case

不可变历史文件及 SHA-256：

- `tests/fixtures/off_byte_baseline_eff77f3.json`：`3bfe51b6d3e20b665c3fed0449ebf8569988022719da275b7fcc9635a9988c6c`。
- `tests/fixtures/off_canonical_baseline_eff77f3.json`：`34f611da359f1a1d059bc78be75b2e9e2458c533b1dc3b46cfd61130fca7a04e`。

`tests/fixtures/off_byte_baseline_s8_independent_20260926.json` 只覆盖六书 × 日/分钟 12 case，修订标识改为 `s8-independent-group-exits-2026-09-26`。全部 39 case 仍同时校验参数省略及显式 OFF；非目标 27 case 继续原 raw/library 字节与 canonical/account 契约。录制工具 `--record-s8` 仅允许该覆盖范围、要求 pandas 3.0.6、拒绝无意覆盖已有文件；本轮按用户授权更新目标 overlay 并校验无关 case 不变。

fixture 总资金 500 万、每个完整独立仓预算 100 万，同一 `600000.SH` 于 10/29、10/31、11/06 三次入池。未达到 +20% 台阶，也未触发涨停追买。历史→最终所有目标 trades 因身份列不同；除 8.3 两例外，各 case 的 equity 原字节从历史到最终均不变。

| Case | BUY/SELL 历史→cb38→最终 | 期末现金 历史→cb38→最终 | 期末权益 历史→cb38→最终 | 逐 case 原因 |
|---|---|---|---|---|
| version8/daily | 3/3 → 3/3 → 3/3 | 5,116,090.9375 → 5,116,090.9375 → 5,116,090.9375 | 5,116,090.9375 → 5,116,090.9375 → 5,116,090.9375 | 历史→cb38：仅身份列；卖后同日首买保留。cb38→最终：全部记录、stats、equity 原字节不变。 |
| version8/minute | 3/3 → 3/3 → 3/3 | 5,121,173.35 → 5,121,173.35 → 5,121,173.35 | 5,121,173.35 → 5,121,173.35 → 5,121,173.35 | 历史→cb38：仅身份列。cb38→最终：全部记录、stats、equity 原字节不变。 |
| version8_2/daily | 3/1 → 3/1 → 3/1 | 2,958,862.825 → 2,958,862.825 → 2,958,862.825 | 4,969,862.825 → 4,969,862.825 → 4,969,862.825 | 历史→cb38：三次全码 lot 0/1/2 改各组 lot 0；两笔存活仓及 EOD_MARK 加身份，add_lots 2→0。本轮全部字节不变。 |
| version8_2/minute | 3/1 → 3/1 → 3/1 | 3,008,812.825 → 3,008,812.825 → 3,008,812.825 | 5,019,812.825 → 5,019,812.825 → 5,019,812.825 | 历史→cb38：同日线身份与 add_lots 变化；两笔未平仓数量不变。本轮全部字节不变。 |
| version8_3/daily | 3/2 → 6/5 → 6/4 | 4,395,790.5625 → 4,308,003.6375 → 3,772,589.5875 | 4,935,790.5625 → 4,848,003.6375 → 4,824,589.5875 | 历史→cb38：三组各一次 50% 补仓，新增 lot 独立退出。cb38→最终：按加权成本整体退出；SELL 5→4，期末两 lot 属同组。 |
| version8_3/minute | 2/2 → 6/5 → 6/4 | 4,945,740.0625 → 4,380,381.1875 → 3,772,589.5875 | 4,945,740.0625 → 4,920,381.1875 → 4,824,589.5875 | 历史→cb38：恢复 11/06 再现首买并三组各补一次。cb38→最终：按加权成本整体退出；SELL 5→4，期末两 lot 属同组。 |
| version8_4/daily | 3/2 → 3/2 → 3/2 | 3,790,655.2 → 3,790,655.2 → 3,790,655.2 | 4,871,655.2 → 4,871,655.2 → 4,871,655.2 | 历史→cb38：10/31 再现及卖出 lot 1→组内 0；存活仓/EOD_MARK 加身份；add_lots 1→0。本轮全部字节不变。 |
| version8_4/minute | 3/1 → 3/1 → 3/1 | 2,891,555.2 → 2,891,555.2 → 2,891,555.2 | 4,972,555.2 → 4,972,555.2 → 4,972,555.2 | 历史→cb38：10/31、11/06 首买改各组 lot 0，两个存活仓加身份；add_lots 2→0。本轮全部字节不变。 |
| version8_5/daily | 3/3 → 3/3 → 3/3 | 5,046,410.6875 → 5,046,410.6875 → 5,046,410.6875 | 5,046,410.6875 → 5,046,410.6875 → 5,046,410.6875 | 历史→cb38：仅身份列，lot/stats 无差异。本轮全部字节不变。 |
| version8_5/minute | 3/3 → 3/3 → 3/3 | 5,019,412.7125 → 5,019,412.7125 → 5,019,412.7125 | 5,019,412.7125 → 5,019,412.7125 → 5,019,412.7125 | 历史→cb38：仅身份列，lot/stats 无差异。本轮全部字节不变。 |
| version8_6/daily | 3/3 → 3/3 → 3/3 | 5,116,090.9375 → 5,116,090.9375 → 5,116,090.9375 | 5,116,090.9375 → 5,116,090.9375 → 5,116,090.9375 | 历史→cb38：仅身份列，无价格加仓。本轮全部字节不变。 |
| version8_6/minute | 3/3 → 3/3 → 3/3 | 5,121,173.35 → 5,121,173.35 → 5,121,173.35 | 5,121,173.35 → 5,121,173.35 → 5,121,173.35 | 历史→cb38：仅身份列，无价格加仓。本轮全部字节不变。 |

主矩阵 8.3 的三笔确认买从 cb38 到最终全部不变：10/30 的 47,600 股 @10.5 属 10/29 组；11/03 的 45,400 股 @11 属 10/31 组；11/07 的 51,200 股 @9.75 属 11/06 组。三笔预算各 50 万，组内 lot 1，原因均 `add:confirm3`。

本轮 8.3 卖出变化逐组如下：

| 组 | cb38 日线 | cb38 分钟 OFF | 最终日线 / 分钟 OFF | 原因 |
|---|---|---|---|---|
| 10/29 | 补仓 47,600 股于 11/05 @9.625、trail；首买 50,000 股于 11/06 @9、touch stop | 补仓于 11/04 @10.5、trail；首买于 11/11 @10、trail | 两 lot 合计 97,600 股均在 11/06 @9.125、`stop_loss:gap_open` | 加权成本约 10.24385246 改变整体止损/止盈线；补仓不再独退。 |
| 10/31 | 两 lot 于 11/05 @9.625、gap stop | 同日线 | 两 lot 合计 91,900 股仍于 11/05 @9.625、gap stop | 新整体成本触发同一退出，经济字段相同。 |
| 11/06 | 首买留仓；补仓 51,200 股于 11/13 @10.125、trail | 首买留仓；补仓于 11/12 @9.75、trail | 首买 54,000 股与补仓 51,200 股都留仓，末日 @10 共 1,052,000 元 | 整体成本与共同 peak 未触发原补仓 lot 的独立止盈线；EOD_MARK 从 1 行变 2 行。 |

本轮主 8.3 日线权益变化 −23,414.05、现金变化 −535,414.05；分钟权益变化 −95,791.60、现金变化 −607,791.60。现金与权益变化相差 512,000，正是本轮继续持有的补仓末日市值。买入本金、预算和买入手续费未变。

| 主矩阵 8.3 stats | 日线 历史→cb38→最终 | 分钟 历史→cb38→最终 | 原因 |
|---|---|---|---|
| `buys` | 3→6→6 | 2→6→6 | 第一提交各组补仓，分钟恢复再现首买；本轮买侧不变。 |
| `add_lots` | 1→3→3 | 1→3→3 | 再现不算加仓，三笔组内补仓计数。 |
| `sell_stop` | 2→3→4 | 1→2→4 | 整体退出仍按实际 lot 成交记录统计。 |
| `sell_trail` | 0→2→0 | 1→3→0 | 本轮取消补仓独立止盈，末组保留。 |
| `skip_add_loser` | 0→0→0 | 1→0→0 | 再现无旧仓盈亏门槛。 |
| `invested_notional` | 1,499,375→2,997,775→2,997,775 | 999,875→2,997,775→2,997,775 | 成交本金，不含佣金。本轮不变。 |

### 2.2 次级 S1/策略12历史输出矩阵：6 个目标 case

`tests/test_partial_sell.py` 的 24 case 原文件 `tests/fixtures/strategy12_default_outputs.json` 维持 SHA-256 `2f578d6fe9e601ad84a94bb6a269e1b5193c51ca4dd908366022769f0e1f31c2`。目标 overlay `strategy12_default_outputs_s8_independent_20260926.json` 只覆盖原矩阵包含的 8/8.2/8.3 × 日/分钟 6 case；原矩阵不含 8.4–8.6，不额外增录。其余 18 case 继续校验历史 hash。**全部使用原默认总资金 21,000,000，没有资金不足。**

| Case | BUY/SELL 历史→cb38→最终 | 期末现金 历史→cb38→最终 | 期末权益 历史→cb38→最终 | 逐 case 原因 |
|---|---|---|---|---|
| version8/daily | 3/3 → 3/3 → 3/3 | 21,188,058.33 → 21,188,058.33 → 21,188,058.33 | 21,188,058.33 → 21,188,058.33 → 21,188,058.33 | 历史→cb38：仅 trades 身份列；stats/equity 字节不变。本轮全部字节不变。 |
| version8/minute | 3/3 → 3/3 → 3/3 | 21,107,958.51 → 21,107,958.51 → 21,107,958.51 | 21,107,958.51 → 21,107,958.51 → 21,107,958.51 | 历史→cb38：仅 trades 身份列；stats/equity 字节不变。本轮全部字节不变。 |
| version8_2/daily | 3/2 → 3/2 → 3/2 | 20,074,213.29 → 20,074,213.29 → 20,074,213.29 | 21,000,383.29 → 21,000,383.29 → 21,000,383.29 | 历史→cb38：全码 lot 0/1/2 改各组 lot 0，BUY/SELL/EOD 加身份，add_lots 2→0；equity 不变。本轮全部字节不变。 |
| version8_2/minute | 3/2 → 3/2 → 3/2 | 20,135,482.5594 → 20,135,482.5594 → 20,135,482.5594 | 21,061,652.5594 → 21,061,652.5594 → 21,061,652.5594 | 历史→cb38：同日线，仍留一个 EOD lot。本轮全部字节不变。 |
| version8_3/daily | 3/3 → 5/4 → 5/3 | 20,946,540.892 → 20,417,310.652 → 19,835,812.732 | 20,946,540.892 → 20,942,510.652 → 20,915,502.732 | 历史→cb38：两组各补 50%，新增一个期末 lot。cb38→最终：整体加权成本退出，SELL 4→3，末组首买与补仓均保留。 |
| version8_3/minute | 2/2 → 5/4 → 5/3 | 20,947,717.6942 → 20,516,589.0742 → 19,826,528.2258 | 20,947,717.6942 → 21,041,789.0742 → 20,906,218.2258 | 历史→cb38：恢复 11/06 首买、两组补仓。cb38→最终：整体加权成本退出，SELL 4→3，末组首买与补仓均保留。 |

次级 8.3 两引擎从 cb38 到最终五笔买入全部不变。确认买仅两笔：10/30 的 47,600 股 @10.5 属 10/29 组；11/07 的 52,000 股 @9.6 属 11/06 组。10/31 组峰值 11.22 未达到 10.9×1.03=11.227，因此无补仓；与主矩阵的差别来自 fixture 行情。

| 组 | cb38 日线 | cb38 分钟 OFF | 最终日线 | 最终分钟 OFF |
|---|---|---|---|---|
| 10/29 | 补仓 11/05 @9.9、trail；首买 11/06 @9、touch stop | 补仓 11/04 @10.6、trail；首买 11/11 @10、trail | 首买 50,000 与补仓 47,600 股均 11/06 @9.1、gap stop | 两 lot 均 11/06 @9.009、gap stop |
| 10/31 | 单 lot 45,800 股 11/05 @9.81、touch stop | 单 lot 11/05 @9.801、gap stop | 保持 cb38 | 保持 cb38 |
| 11/06 | 首买 54,900 股 11/11 @10、trail；补仓 52,000 股留仓 | 首买 11/10 @10.3、trail；补仓留仓 | 两 lot 均留仓，末日 @10.1 共 1,079,690 元 | 同日线 |

次级末组因加权成本/共同 peak 的整体退出线不同，首买不再单独卖出。相比 cb38，日线期末权益 −27,007.92、现金 −581,497.92；分钟权益 −135,570.8484、现金 −690,060.8484。现金与权益之差 554,490 是新增保留的首买末日市值，不是新增买单。

| 次级 8.3 stats | 日线 历史→cb38→最终 | 分钟 历史→cb38→最终 |
|---|---|---|
| `buys` | 3→5→5 | 2→5→5 |
| `add_lots` | 1→2→2 | 1→2→2 |
| `sell_stop` | 2→2→3 | 1→1→3 |
| `sell_trail` | 1→2→0 | 1→3→0 |
| `skip_add_loser` | 0→0→0 | 1→0→0 |
| `invested_notional` | 1,498,810→2,497,810→2,497,810 | 999,220→2,497,810→2,497,810 |

历史文件生成后的既有 `daily_quota` / 费用自描述元数据不作为本轮规则差异重录；本轮 cb38→最终仅有上述卖出统计变化，没有新增 stats 键。

## 3. 获批迁移的测试逐项清单

### 3.1 第一提交已迁移的 18 个低资金参数 case

下列 18 case 保留第一提交的严格异常预期，均断言 `date/code/needed/available/shortfall`。资金与预算没有修改，8.1 和其他书的 skip_cash 预期不变。表中金额顺序为 needed / available / shortfall，单位为元。

| 文件与测试 | 参数 case（数量） | date / code | 金额 | 原因与保留断言 |
|---|---|---|---|---|
| `test_minute_cash_chronology.py::test_pool_boundary_same_close_sell_proceeds_are_immediately_available` | `close-896-False`、`open-896-False`（2） | 20260902 / 600001.SH | 600.60 / 0 / 600.60 | ON 14:55 不可使用 14:56 卖款；audit 只含中断前首买。 |
| 同文件 `test_chase_cannot_spend_afternoon_sale_and_does_not_retry` | ON（1） | 20260902 / 600001.SH | 600.60 / 0 / 600.60 | 09:45 追买不可使用 14:59 卖款；本轮新增 OFF 同预期见 §3.3。 |
| 同文件 `test_unsold_position_contributes_no_cash` | `no_signal/limit_down/zero_capacity`（3） | 20260902 / 600001.SH | 600.60 / 0 / 600.60 | 未成交无现金；保留旧仓 100 股、现金 0 断言。 |
| 同文件 `test_partial_sale_only_credits_actual_shares_net_of_fee` | `min_cost=0/5`（2） | 20260902 / 600001.SH | 1801.80 / 1408.59 / 393.21；1805 / 1405 / 400 | 仅 150 股实际卖款可用，仍不足第二单；保留余 50 股/peak10；异常发生在后段继续卖出之前。 |
| 同文件 `test_whole_pool_denominator_ration_and_commission_match_legacy` | `version8_2-file_order/seeded_shuffle`（2） | 20260901 / 600002.SH、600001.SH | 均 1001 / 0 / 1001 | OFF/ON 及先前两笔 audit 相同；version8_1 两例保持原预期。 |
| 同文件 `test_close_clear_milestones_with_chronological_clock` | `version8_5-4-force_sell:t4_close-900-False/896-False`（2） | 20260907 / 600001.SH | 600.60 / 0 / 600.60 | ON 14:55 不可用 15:00/14:56 强平款；14:50 先强平成功例保留。 |
| 同文件 `test_close_clear_milestones_with_chronological_clock` | `version8_6-1-force_sell:t1_close-900-False/896-False`（2） | 20260902 / 600001.SH | 600.60 / 0 / 600.60 | 保持 8.6 末 bar 强平时钟，不提高现金。 |
| `test_minute_cash_audit.py::test_sidecar_preserves_state_and_records_real_clock_cash` | `True`（1） | 20251105 / 600001.SH | 600.60 / 0 / 600.60 | 有/无 audit 抛同字段异常；本轮 False 迁移见 §3.3。 |
| 同文件 `test_shared_cli_audit_sidecar_preserves_csv_surface` | `True`（1） | 20251105 / 600001.SH | 600.60 / 0 / 600.60 | CLI 传播异常，不写未完成 trades/audit；本轮 False 迁移见 §3.3。 |
| `test_minute_cash_red.py::test_chronological_cash_cannot_borrow_future_proceeds` | ON（1） | 20251105 / 600001.SH | 600.60 / 0 / 600.60 | ON 不能借未来卖款；本轮原 OFF 对照迁移见 §3.3。 |
| `test_csv_daily_backtest.py::test_d4_step_none_limits_rejects_before_floor_cash_gate` | `one-fen-short-known_board`（1） | 20251103 / 600000.SH | 1205 / 1204.99 / 0.01 | 本金 1200 加最低佣金 5，差一分即停；无昨收/未知板块仍先跳过，足额 1205 仍成交。 |

### 3.2 本轮用户点名的四个底层 version8 hooks 用例

旧 helper 只调用 `init_sim_state(hooks)`，此前未自动绑定独立仓策略上下文，因此错误地进入 skip_cash。现由共享初始化修复根因，这些用例代表真实目标书，均应严格报错，不能当作非目标书保留旧预期。四项全部校验异常五字段，保留原现金：

| 原测试 → 当前测试 | date / code | needed / available / shortfall | 原因 |
|---|---|---|---|
| `test_per_name_cash_short_skips_entire_second_order` → `test_per_name_cash_short_raises_before_entire_second_order` | 20251103 / 000001.SZ | 1,001,000 / 499,000 / 502,000 | 原 150 万只够首单；第二完整整手单即报错，首单成交保留。 |
| `test_per_name_commission_short_also_skips` → `test_per_name_commission_short_also_raises` | 20251103 / 600000.SH | 1,001,000 / 1,000,000 / 1,000 | 本金足够、佣金不足仍报错，无成交。 |
| `test_seeded_shuffle_is_stable_per_day_and_changes_cash_allocation`（名称不变） | 20251103 / 各顺序的第二代码 | 均 1,001,000 / 499,000 / 502,000 | file_order 与 seeded_shuffle 两种顺序均断言首单后报错；仍验证稳定乱序及首笔资金分配差异。 |
| `test_per_name_chase_budget_and_terminal_outcomes[cash]`（名称不变） | 20251104 / 600000.SH | 1,001,000 / 500,000 / 501,000 | 追买同样必须支付本金加费用；不转成 chase_buy_fail_cash。 |

四项均位于 `tests/test_csv_strategy_books.py`。同文件再现/追买成功分支同步改为真实不同信号日期和 position_id，`add_lots` 不再统计再现首买；未改变其资金。

### 3.3 本轮 OFF 分段导致的四个旧成功分支改为现金异常

| 文件与测试 | 本轮新增异常 case | date / code | needed / available / shortfall | 原因 |
|---|---|---|---|---|
| `test_minute_cash_chronology.py::test_chase_cannot_spend_afternoon_sale_and_does_not_retry` | `False`（OFF） | 20260902 / 600001.SH | 600.60 / 0 / 600.60 | 四书 OFF 后段 14:59 卖款尚未入账，不可供前阶段追买。 |
| `test_minute_cash_audit.py::test_sidecar_preserves_state_and_records_real_clock_cash` | `False`（OFF） | 20251105 / 600001.SH | 600.60 / 0 / 600.60 | 14:55 买前不可借用 14:59 卖款；有/无 audit 字段相同。 |
| 同文件 `test_shared_cli_audit_sidecar_preserves_csv_surface` | `False`（OFF） | 20251105 / 600001.SH | 600.60 / 0 / 600.60 | 同一边界，CLI 传播异常而不写未完成输出。 |
| `test_minute_cash_red.py` 原 legacy OFF 测试 → `test_group_exit_off_scan_cannot_borrow_1459_proceeds_for_1455_buy` | OFF | 20251105 / 600001.SH | 600.60 / 0 / 600.60 | 删除已被新扫描边界覆盖的“可借未来款”成功断言，改核验五字段异常。 |

这些是人为低现金场景，不是默认总资金或目标 OFF golden 不足；没有提高原资金，也未改变 8.1/其他书用例。

### 3.4 其他必要预期适配

- 本轮 `test_minute_cash_chronology.py` 的旧 `first_rejected` 容量测试改名为 `test_group_exit_retries_capacity_without_observing_later_high`：14:54 首次退出无容量，整体 pending 在 14:56 @9.3 继续卖出，保留原原因和 peak10。
- 同文件 `test_partial_sale_funds_affordable_buy_and_preserves_trigger_high[min_cost=0/5]` 保留原资金、行情和每桶 150 股容量；14:54 卖 150 股、14:55 买另一代码后，14:56 继续卖原组余 50 股，peak 仍为触发时 13。这三例变化来自整体待退出意图持续，不是现金/容量放宽。
- 原专项中“step lot 单独退出后还能继续加仓”用例改为整体退出及 T+1 部分退出测试：历史级数保留，pending 期间禁止加仓，全部退出后不能重开旧组。除权测试仍验证首买锚与加权成本的正确缩放。
- 第一提交的再现 lot0/position_id、手工预置独立组、pending 代码@信号日期、开盘代码快照/新仓预算及未来 high 不影响再现等适配继续保留。它们不再以旧全码 lots 或旧 add_gate 作为新信号门槛。
- 范围外内部 fullstrat replay 的上下文排除仅防止共享初始化自动绑定六书规则污染其历史实验流程，没有新增研究/交易入口。

## 4. 验证

解释器 `~/.venvs/bt-ci/bin/python`，pandas 3.0.6。保留默认资金，未接入真实数据湖。

- 新增 `test_s8_group_exit.py`：**71 个参数 case 全部通过**，覆盖四本加仓书、日线/分钟 OFF/ON、T+1 首可卖 open、跌停后保持标记、容量完成桶 close、peak/stale 首买锚、组隔离及 8.2/8.6 单 lot 与旧退出路径对照。包含最终审查补充的日线加仓收盘跌停仍保留 T+1 标记，以及 8.2/8.6 容量为 0/部分成交的 OFF/ON 兼容测试。
- 上述整体退出专项与两套 baseline 联合复核：**159 passed**（71 项整体退出 + 88 项 baseline）；原独立持仓和底层 hooks 测试也纳入下方完整 CI。
- 三个现金时钟/audit 文件：**80 passed**。
- baseline 工具 `--check`：78 个 production CSV hashes 及 library hashes、27 个未改 case 加 12 个目标 account/canonical 契约通过；次级非目标 18 case 的历史 hash 同样通过。
- 四个 contract gates 与 `ruff check bt_contract` 通过。
- 8.2/8.6 另与第一提交 HEAD 做 8 个日线场景、16 个分钟场景的完整字段比较，均一致；可选容量的 8 个兼容参数 case 也覆盖初次无容量与部分成交，确保不改变这两书的原结算语义。

完整 CI 使用：

```text
~/.venvs/bt-ci/bin/python scripts/gates/verify_oskh_data_contract.py
~/.venvs/bt-ci/bin/python scripts/gates/verify_data_path_ssot.py
~/.venvs/bt-ci/bin/python scripts/gates/verify_no_hardcoded_machine_paths.py
~/.venvs/bt-ci/bin/python scripts/gates/verify_tr_bridge_import_ssot.py
~/.venvs/bt-ci/bin/python -m ruff check bt_contract
# All checks passed!
~/.venvs/bt-ci/bin/python -m pytest -q -m "not production and not benchmark"
# 2884 passed, 67 skipped, 24 deselected, 10 warnings in 37.85s
```

最终完整选择已通过，包含最后的日线 T+1 跌停标记修复和 8.2/8.6 单 lot 容量兼容修复；四项 gates 与 ruff 也在该状态再次通过。所有改动 Python/Markdown 均以 UTF-8 无 BOM 保存，NUL 为 0；只创建授权的本地新 commit，不 amend、不 push、不开 PR、不 merge。

## 5. 未决问题与适用限制

- **needed 门槛待确认**：本次按“实际整手订单本金 + 费用”（容量裁剪前）检查，不按“完整预算 + 费用”。两种口径的差别和示例见 §1.5。
- 加仓属于持仓整体并一起退出已经用户确认，不再是待决项。T+1 与跌停限制按 §1.3 实施，没有通过提前卖出当日新股实现整体退出。
- 分钟 OFF 仍是兼容近似时钟，四本有价格加仓的书仅在 14:55 处分段；日线追买仍用 open/close 近似 09:45。完整因果资金时序应使用分钟 ON。
- 原人工分析包仍按代码 FIFO 配对/汇总，尚未迁移为 position_id 归因；原始输出新增身份列不表示后处理已正确归因，消费这些分析产物时需另行迁移核验。
- 目标低现金用例冲突已按用户决定迁移；默认 2,100 万及目标 OFF golden 均未报资金不足，没有未解决的引擎规则冲突。

## 6. 改动文件范围

本轮后续提交主要文件：

- 账本、共享循环与时钟：`backtest/research/csv_ledger.py`、`csv_simulate_loop.py`、`csv_daily_backtest.py`、`csv_minute_backtest.py`、`minute_cash_order.py`；范围外实验隔离：`fullstrat_research_book.py`。
- 六书 HELP_LOCK：`strategy8_rules.py`、`strategy8_2_rules.py`、`strategy8_3_rules.py`、`strategy8_4_rules.py`、`strategy8_5_rules.py`、`strategy8_6_rules.py`。
- baseline：`scripts/research/generate_off_byte_baseline.py`、两份带 `s8_independent_20260926` 后缀的目标 fixture、`tests/test_partial_sell.py`。
- 测试：`tests/test_csv_strategy_books.py`、`test_s8_independent_positions.py`、新增 `test_s8_group_exit.py`、`test_minute_cash_chronology.py`、`test_minute_cash_audit.py`、`test_minute_cash_red.py`。
- 文档：本文；另按用户要求更新工作树外 `/home/box/agent-data/bt-s8-reappear-2026-09-26/prb-body.md`，不创建远程 PR。

第一提交新增的身份、追买、台阶、现金检查及原测试/隔离范围仍保留，详细改动可用 `5518323..HEAD` 审查；本轮为 `cb38c32` 之后的新提交。

## 7. PR #212 第一轮审查修复

本节记录 `6623b65` 之后的新提交；前文 §2 的 baseline 数字及 §4 的 2,884 项通过记录属于整体退出提交。七个 P2 按用户决定处理如下：

- P2-1：修正日线加仓后遇跌停的 T+1 成交归因，按原退出日逐 lot 判断后缀，旧股不因同组新股锁定而被误标；跨日跌停继续保留原归因，新增回归测试。
- P2-2/P2-3：仅在 §1.3–§1.4 明确缺 15:00 bar 的清退回退顺序，以及 8.3 OFF 确认 peak 截取和普通跌停 defer 的补仓边界，代码行为不变。
- P2-4：目标书容量 SKIP 行补齐 `position_id`、`entry_signal_date` 并验证买卖路径；非目标输出保持原字段。
- P2-5：`execute_buy` 对缺少 `@` 的身份键抛 `ValueError` 并提供格式提示，新增输入校验测试。
- P2-6/P2-7：去掉 8.6 HELP_LOCK 的重复追买句；六书新增独立持仓、整体退出、T+1、严格现金关键句及不存在旧“上限 2 笔”说法的断言。
- 次要测试补齐：日线引擎验证不同信号日期的 pending 追买并存；台阶用例补验成交价及整手股数。

本轮不重录 baseline，全部历史文件和两份目标 overlay 与 `6623b65` 逐字节不变；主工具 `--check` 的 78 个生产 CSV hash、库序列化 hash、39 个 canonical/account case 全通过，次级矩阵也在完整 CI 中通过。修复涉及的异常/容量/T+1 跌停归因场景由专项测试补充。

本轮新增 53 个参数 case（容量/非法 ID 44、六书 HELP 6、日线双追买 1、跨日跌停归因新增 2）。相关四文件专项合计 311 passed。日线双追买测试只在 chase 报价回调处注入一次报价暂缺，不直接预填队列；正常完整日线 OHLC 共用同一天追买/池买报价，该测试用于核验日线入口的保留队列集成路径。

使用同一 `~/.venvs/bt-ci/bin/python`（pandas 3.0.6），四个 contract gates 与 `ruff check bt_contract` 全通过；完整 `pytest -q -m "not production and not benchmark"`：**2937 passed、67 skipped、24 deselected、10 warnings，40.22s**。所有修改文本 UTF-8 无 BOM、NUL=0；本轮创建新本地 commit，不 amend、不 push。
