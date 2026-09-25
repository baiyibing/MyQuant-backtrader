# MyQuant-backtrader 分钟线回测引擎与 09-21 三套策略：只读审查汇总（2026-09-25）

- 审查基线：`baiyibing/MyQuant-backtrader` 的 `origin/master` @ `057761a`（2026-09-25 11:57 CST）；审查在只读 worktree 中完成，未修改代码或提交。
- 流程：Codex（gpt-6-astra, ultra）、Kimi（kimi-code v0.39.1）、Grok 4.7（xhigh）三路独立审查。随后由 Grok 4.7 对着代码交叉核对：逐条读 file:line，并用无湖合成夹具直接调用 `simulate()` 复现关键数字。
- 随本报告提交的原始材料：[`report-codex.md`](raw/report-codex.md)、[`report-kimi.md`](raw/report-kimi.md)、[`report-grok.md`](raw/report-grok.md) 和 [`crosscheck-grok.md`](raw/crosscheck-grok.md)；提示词、CLI 日志及 PR 正文/评论备份未纳入本次提交。
- 状态标记：**confirmed** 表示交叉核对在代码中确认（多数附合成复现）；**disputed** 表示有争议或被降级；**needs-data** 表示要读真实湖数据才能定。「x/3」是三份独立报告中提出该条的份数。

---

## 0. 三套策略是哪三套，代码和文档在哪

09-21 这一天实现并注册进双引擎（日线 + 分钟）的策略书是下面三套。三份报告和交叉核对的认定一致。

| # | 策略 | 代码 | 设计 / 人裁记录 |
|---|---|---|---|
| 1 | **策略 12 / version12「金榕元」均线减仓书**（`--strategy 12`）：MA5 减仓/收复买回、MA10×0.90 止损/收复、+20% 台阶加仓 | `../../../backtest/research/strategy12_rules.py`、`../../../backtest/research/strategy12_engine.py`；接线 `../../../backtest/research/csv_strategy_books.py:648-672,1458-1470`、`../../../backtest/research/csv_minute_backtest.py:1108-1186` | plan `../../../docs/backtest/plan-strategy12-jinrongyuan-2026-09-21.md`；handoff `../../../docs/backtest/handoff-strategy12-codex-impl-2026-09-21.md`（§0 为有约束力的人裁）；四路评审 + 共识 `../../../docs/architecture/reviews/2026-09-21/plan-strategy12-jinrongyuan/`；PR #151（评论里有 latch=A、residual=2 两次人裁），后续 #158（分钟用 none）、#169、#170 |
| 2 | **策略 11 / version11 ma_chip CSV 移植** | `../../../backtest/research/strategy11_rules.py`、`../../../scripts/data/export_strategy11_pool.py`；`../../../backtest/research/csv_strategy_books.py:984-1003` | plan / handoff `../../../docs/backtest/*-version11-*-2026-09-21.md`；共识 `../../../docs/architecture/reviews/2026-09-21/plan-version11-machip-csv/`；PR #152（契约日、周线、volume=A 三次人裁；Slice D 显式跳过） |
| 3 | **策略 8 里程碑书 8.1 / 8.2 / 8.3**（同一族三本，commit `b2b406e`，09-21 13:05 直接合入，**没有 PR，也没有设计评审链**） | `../../../backtest/research/strategy8_1_rules.py`、`../../../backtest/research/strategy8_2_rules.py`、`../../../backtest/research/strategy8_3_rules.py`（8.3 的卖点委托 `../../../backtest/research/livermore_exit_rules.py`）；注册 `../../../backtest/research/csv_strategy_books.py:1339-1377` | 只有各书 HELP_LOCK 和 `../../../tests/test_strategy8_milestones.py` |

不算策略的几项：
- **#156 fullstrat Q2/H2**：研究回放格，不进 `BOOKS`。当天有人裁（H2、Q2、卖单过期），已收进决策表。
- **ma_infra**：#150 / #154 是共享均线库。
- **8.4–8.6**：09-23 才加入。

> 说明：「多轮多 agent 设计评审 + 实施中反复问用户」这个模式只对应策略 12 和策略 11。8.1–8.3 是同一天直接注册的冻结参数包。如果你心里的「第三个」是 #156 研究格，它的人裁同样在第 3 节决策表里（D52–D55）。

---

## 1. 主要发现（共识排序）

排序按「默认研究命令会不会算出另一本账」，不按「有没有人裁」。

| 排名 | ID | 严重度 | 共识 | x/3 | 位置 | 一句话 |
|---:|---|---|---|---|---|---|
| 1 | X-01 | **critical** | confirmed（已合成复现） | 2/3 | `../../../backtest/research/csv_minute_backtest.py:1108-1125,1180-1186,990-996`；`../../../backtest/research/strategy12_engine.py:223-267` | **策略 12 分钟版混用了两套价格**：MA、涨跌停价、持仓市值用前复权（front）日线，成交用原始（none）分钟价，三者直接比较。合成夹具（分钟价恒为 10）中：日线 10.5 时出现假减仓（卖 5 万股）；日线 12 时全天卖不出，且不记延期；日线 5 时出现假涨停拒买；权益也凭空多出 5 万 / 20 万。**09-22 已公开的 s12 分钟五本 NAV（−7.69%）不能拿来和其他书比。** |
| 2 | X-02 | major | confirmed（复现） | 2/3 | `../../../backtest/research/csv_minute_backtest.py:731-853` 之后才到 `:888-964` | **共享分钟循环（8.x、version8 等）先把全天卖出记进现金，再下 09:45 追买和 14:55 池买**，下午的卖款能付上午的买单。现金紧张时会多买。v7 在跨股票之间也有同样的逆时问题。策略 12 按分钟推进，没有这个问题。 |
| 3 | X-03 | major | confirmed（复现） | 2/3 | `../../../backtest/research/strategy11_rules.py:102-106`；`../../../backtest/research/csv_simulate_loop.py:535-539`；`../../../scripts/data/export_strategy11_pool.py:281` | **策略 11 进场信号用 front，出场 SMA5 用引擎的原始价日线**。跨除权时原始均线会跳空，产生假破位卖出。例子：原始 SMA5 为 9.99，复权一致口径为 9.18。 |
| 4 | X-04 | major | confirmed（复现） | 1/3（Codex） | `../../../backtest/research/csv_simulate_loop.py:275-331`；`../../../backtest/research/strategy8_3_rules.py:45-50` | **8.3 首笔涨停追买绕过了「50% 试探」**，按 100 万排队（追买 90,900 股，约 100 万）。追买股数还取决于名单里前一只票是否先走过普通买：先走过则只追 45,400 股。 |
| 5 | X-05 | major | confirmed（复现） | 1/3（Codex） | `../../../backtest/research/strategy8_1_rules.py:41-48,89` | **8.1 峰值恰好 +60% 时的浮点错档**：`16/10-1=0.6000000000000001`，落进 +50% 地板档，本该按 +30% 地板。结果是提前卖出。 |
| 6 | X-06 | major | confirmed（复现） | 1/3（Kimi） | `../../../backtest/research/strategy12_rules.py:165-170`；`../../../backtest/research/strategy12_engine.py:106-107`；`../../../backtest/research/csv_ledger.py:285` | **策略 12 止损把 lot0 卖光后，+20% 台阶永久停止加仓**：`step_add_due` 找不到 `lot_id==0`。P13「lot0 保底 100 股」只保护减仓，不保护止损。创业板 / 科创板 20% 档更容易触发。 |
| 7 | X-07 | major | confirmed | 2/3 | `../../../backtest/research/market_layer.py:57-64` | **名称带 ST 一律按 5% 涨跌幅**，不看板块（创业板 / 科创板 ST 应为 20%），也不看日期。2026-07-06 起主板 ST 改为 10%，默认研究窗 20251023–20260909 跨过这一天。 |
| 8 | X-08 | major | confirmed；幅度 needs-data | 1/3 | `../../../backtest/research/csv_minute_backtest.py:1108-1123`；`../../../scripts/data/export_strategy11_pool.py:281` | **front 分区按最新锚点整段落盘**，加载时不按决策日重新锚定，未来的除权会改写更早的均线（前视）。影响策略 12 日线和策略 11 导出器。 |
| 9 | X-09 | major（模型差异） | confirmed | 1/3 | `../../../backtest/research/csv_daily_backtest.py:382-403` 对比 `../../../backtest/research/csv_minute_backtest.py:328-336` | 同一套 8.x 止损公式，日线按最低价触发、按触发价成交；分钟不看最低价、按该根收盘成交。日线账和分钟账不是同一个成交模型。 |
| 10 | X-10 | major | confirmed | 3/3 | `../../../backtest/research/csv_ledger.py:223-233,254-259` | 买入一律按 100 股整手，科创板 688/689 可以只买 100 股（规则是 200 股起）；卖出允许任意股数（主板零股应一次卖完）。 |
| 11 | X-11 | major（公开 API） | confirmed | 1/3 | `../../../backtest/research/csv_minute_backtest_v7.py:333-350` | `simulate_v7` 传 DataFrame 且不传 `index_days` 时，日历只剩名单日。标准 CLI 会传 `index_days`，不受影响。 |
| 12 | X-12 | major | confirmed；是否已命中旧缓存 needs-data | 1/3 | `../../../backtest/research/ashare_bars.py:416-418,584-590` | 分钟缓存文件名只有 `minute_none_{start}_{end}`，命中时不校验湖来源、版本或 schema。换湖或修数后可能静默读到旧行情。 |
| 13 | X-13 | major（仅在显式打开权益时） | confirmed | 1/3 | `../../../backtest/research/csv_minute_backtest.py:734-742`；`../../../backtest/research/csv_minute_backtest_v7.py:373-381` | 默认不记送转和红利（δ6 人裁）。打开后，主书和 v7 在缺当天 bar 时会永久漏记。 |
| 14 | X-15 | major（验收状态） | confirmed | 3/3 | `../../../docs/backtest/reviews/slice-d-version11-seed30-universe-2026-09-21.md:6` | 策略 11 的 Slice D 仍是 STOPPED，「ma_chip 信号是否有效」没有任何对照证据。 |

**被降级或判为有争议（行为属实，但属于已人裁的研究口径，不算实现错误）：**
- 当根收盘成交（cheat-on-close）、分钟止损不看最低价：已写进 HELP 和宿主合同，降为「已声明口径」。
- 14:57 后仍按连续竞价成交：P1=A。
- 默认双边 10bp，无印花税、无最低 5 元：δ1。另外 `../../../docs/backtest/engine-ashare-correctness.md:34` 的文档已过时。
- 打开 `--participation-rate` 后策略 11 的 09:30 单结构性零成交：volume=A 的直接后果。建议只在 CLI 加提示。

**次要（minor，已确认）：**
- X-20：策略 11 执行预热只有 10 个自然日，SMA 不够时静默 HOLD。
- X-21：策略 12 分钟每根 bar 都重跑完整 `scan_held_day`；Numba 卖出核被 `reserve_state` 挡住。
- X-22：入口文档把 8.1 写成「每票 100 万」，实际是日额度。
- X-23：8.3「再加 50 万」没有笔数上限；HELP 也没写上限。
- X-26：几处缺 bar 时静默 `continue`，没有计数。
- X-27：`scale_memory` 把记忆缩到 0 时不解锁周期 latch。
- X-32：8.1 / 8.2 静默落到 `reserve_limit_up=False`。
- X-33：8.1–8.3 没有评审链。
- X-34：8.3 的 `build_sse_ma10_block_new` 是死代码。
- X-35：策略 12 分钟卖出不写 `session_phase`。
- X-36：qlib 1 分钟缺 open/high 时用 close 顶上。
- X-37：8.1 HELP 写「2%×2」，代码是 6%，属于措辞问题。

**被删除的错误说法**（详见 [`raw/crosscheck-grok.md`](raw/crosscheck-grok.md) §6）：
- Kimi「成交与估值全程 none」「策略 12 人裁已全部落实」「8.3 等号点失真」「预热 200+」「跌停计数固定放大 240 倍」「策略 12 五本未执行」。
- Grok 首轮「v7 没有卖款逆时」「v7 峰值会更早触发」。
- 把 09-15 旧剖面的 75% 当作当前卖扫占比（当前实测为 52–54%）。

**做对了、后续不要顺手改掉的：** T+1、未知板块拒单、午休排除、S1 部分卖出不再丢股、策略 12 的周期 latch 和不足 100 股的记忆、#169 按信号时点锁 lot、策略 11 的 `limit_up_chase=False`、周线 opt-in、09:30 严格可得量、除权参考价与权益分层。

---

## 2. 实施时的决策：大白话对照表

下表只列**你当时实际拍板的问题**，以及几个悄悄决定结果的默认值。全部 62 项（含引擎 δ 系列、ma_infra、8.x 分档等号等）见 [`raw/crosscheck-grok.md`](raw/crosscheck-grok.md) §4。

| # | 问题的意思 | 当时选的 | 对结果的影响 | 是否合理 | 建议 |
|---|---|---|---|---|---|
| D17 策略 12 latch（#151 人裁） | 同一天跌破 MA5、站回、再跌破，还能再减一次吗？ | **A：只用周期锁**。站回即重新武装，没有「每天一次」 | 震荡日可以多次减仓、买回，交易次数和费用增加 | 与「跌破就减」的本意一致 | 保留 |
| D18 策略 12 零头记忆（#151 人裁 residual=2） | 卖了 150 股、只买回 100 股，剩下 50 股的「欠账」怎么办？ | **保留零头**，并入下一轮；不足 100 股且这次没买成，也照样重新武装 | 小额尘埃股不会凭空丢失 | 合理 | 保留 |
| D25/D57 策略 12 价格域（#151 选项 2 / #158） | 均线用复权价还是原始价？分钟成交用哪个？ | 日线信号固定 front，分钟成交默认 none，禁止再乘一次复权因子 | **目标对，但实现只接了一半**：MA、涨跌停、市值没有换算回原始价单位，所以出现 X-01 | 方向合理，实现不完整 | **修改**（见跟进计划 P0） |
| D15 策略 12 分钟触发与成交 | 跌破均线是逐分钟判断，还是一天一次？在哪个价成交？ | 用昨收算 MA；逐分钟看 close，当根 close 成交；日线版收盘信号、次日开盘卖 | 比「下一根开盘成交」乐观，而且比日线版更早 | 昨收避免了前视；当根成交偏乐观 | 保留，并在报告中写明「当根收盘成交」 |
| D16/D29 减仓量与 lot0 保底（P3/P13/#170） | 每次减多少、先卖哪一笔、最后留多少？ | 可卖股数的 50%，向下取到 100 股；先卖台阶 lot，lot0 最后卖且至少留 100 股 | 可卖 100–199 股时一次也不减；止损不受保底限制 | 减仓部分合理 | 保留减仓逻辑；止损导致台阶失效另修（X-06） |
| D20 当日笔数闸（P6） | 同一只票一天之内，池买、追买、台阶、买回能否叠加很多笔？ | 不设闸 | 单票日内名义金额可以远超 100 万 | 你明确选的 | 保留，HELP 已写明 |
| D21 上证十日线闸（P7） | 大盘弱时策略 12 要不要停止开新仓？ | 不要 | 同样环境下 8.3 会停，策略 12 照开 | 两书对比时必须写明 | 保留 |
| D22 名单来源（P8） | 默认从哪读股票池？ | `../../../stock_pool/` | 池文件一改，历史回测结果就变 | 可以 | 保留，并把池版本写进 manifest |
| D23 新买清空记忆（P9④） | 池买或追买成功后，还要不要买回之前减掉的仓？ | 清空两个通道的记忆 | 避免仓位翻倍 | 合理 | 保留 |
| D24 送转缩放记忆（P9③） | 送股时，买回记忆是否跟着乘比例？ | 仅在打开权益时缩放，再向下取整到 100 | 默认不生效；缩到 0 时 latch 不释放（X-27） | 基本合理 | 保留，另修 latch 释放 |
| D26 不继承 version8 规则（P12） | 要不要沿用 version8 的 20% 止损、涨停保留等？ | 都不要，只用 MA10×0.90 止损 | 策略 12 不会被 version8 的止损先清仓 | 合理 | 保留 |
| D30 日线延期卖单（#169） | 跌停拖过一天、价格已站回均线，第二天还卖吗？ | 仍按原单卖（锁信号时点的 lot） | 与分钟版「下一根重新判断」不一致 | 可接受 | 保留，并写明两版不一致 |
| D34 策略 11 契约日（#152 人裁） | 信号日 D 和买入日 T 怎么对齐？过期从哪天算？ | T = D 之后第一根有 bar 的交易日，且间隔 ≤4 个自然日；只用 ≤T−1 的数据；过期从 D 算 | 停牌超过 4 天的信号作废；不会用 D 日收盘去买 D 日开盘 | 严格防前视，合理 | 保留 |
| D35 策略 11 周线（#152 人裁） | 周线是整段历史对齐，还是每个 D 都当作数据截断在 D？ | 导出器显式传 `prefix_equivalent=True`，默认 API 不变 | 导出窗口变长不会改写早期信号 | 合理 | 保留；其他调用方要记得传该参数 |
| D36 策略 11 volume=A（#152 你显式确认） | 09:30 开盘价成交时，能不能用这一分钟结束后才知道的成交量来限量？ | 不能（`bucket<=at`） | 默认不开容量限制时无影响；打开后 09:30 单全部不成交 | 因果上保守，正确 | 保留，CLI 加提示 |
| D32/D33 策略 11 双跑（P1/P2） | 日线版买收盘，还是分钟版买开盘？卖在什么时候？ | 两个都做，以分钟版 09:30 开盘为准；收盘决定卖，次日开盘成交 | 两版成交价本来就不同 | 合理 | 保留；出场 SMA 的价格域要修（X-03） |
| D41 策略 11 Slice D（#152 人裁） | 没有静态档案和真 Rust pyd，验收要不要卡住？ | 显式跳过，不主张收益 | 只有「框架能跑」的证据 | 诚实 | 保留「未验证」标签；补跑见跟进计划 |
| D52 #156 H2 | 研究格是否把所有成交都换成下一根开盘？ | 全部换，当天严格到期，允许不成交乃至全现金 | 形成一套独立的交易集合 | 实验合同 | 只留在研究格 |
| D53 #156 卖单过期 | 当天没卖掉的单，明天还挂着吗？ | 不挂，下一交易日按策略重新评估 | 次日条件消失就继续持有 | 只属于研究钩子 | 保留；不要推广到生产书 |
| D54 #156 Q2 | 下一根更贵时，股数按信号价锁定还是按成交价重算？ | Q2：按成交价重新整手 | 更容易成交，单笔更小 | 与实盘和 `execute_buy` 一致 | 保留 |
| 默认值 D05 | 费率 | 双边 10bp，无印花税、无最低 5 元 | 往返约 20bp，不是真实账单 | 人裁防双计 | 保留默认，另加「真实账单」档 |
| 默认值 D11 | ST 涨跌幅 | 见名一律 5% | 见 X-07 | 已过时 | **修改**（加日期和板块） |
| 默认值 D59 | 资金不够时谁先买 | `--ration file_order`，即 CSV 行序；缓存默认开；`--strict-pool` / manifest 默认关 | CSV 行序会影响结果；默认产物无法证明名单已冻结 | 兼容旧 CLI | 正式研究时打开 strict + manifest |
| 8.x D43–D49 | 8.1–8.3 冻结了什么？ | 冻结卖点公式；费用、涨跌停、追买时钟跟随现行宿主 | 与当年 CSV 结果的差异来自宿主 | 对比时写「同引擎、异卖点」 | 保留；8.3 追买预算（X-04）和 8.1 浮点档（X-05）要修 |

---

## 3. 性能建议（按收益 / 风险排序）

**实测**（CI Python 环境，脚本 `../../../scripts/research/bench_minute_simulate_hotpath.py`，合成数据，version8，30 日 × 16 码 × 240 分钟）：

- 每次 `simulate` 约 **1.26–1.27 s**。其中卖出扫描 **52–54%**，编排约 40%，昨收准备约 8%，池买约 6%。Codex、Kimi 和交叉核对三方结果一致，可以复现。
- 设置 `CSV_SCAN_HELD_DAY_BACKEND=numba` 后，实际后端**仍是 Python**。原因是 `reserve_state` 和 `take_profit` 把 offload 条件挡住了（`../../../backtest/research/csv_minute_backtest.py:447-457,799`）。
- 同规模下，**策略 12 分钟版比 version8 慢 5.5–6.7 倍**，倍数随夹具变化。

| 顺序 | 改什么 | 预期收益 | 风险 | 验证 |
|---|---|---|---|---|
| 1 | 策略 12：按「每天每只」缓存 MA5 / MA10 / 止损线；分钟循环内联比较 close 与阈值、涨跌停，不再每根调用完整 `scan_held_day`；池买、追买只挂在真实时钟上（`../../../backtest/research/strategy12_engine.py:223-290`） | 吃掉 5–7 倍差距中的大部分（合成数据）；Codex 保守估计 1.5–3 倍 | 中：同日再武装、先卖后买、部分成交必须保持 | 现有 `../../../tests/test_strategy12_engine.py` + 多分钟穿越夹具 + 成交元组回放 |
| 2 | 没有涨停保留、也没有 Python 回调的书不再传 `reserve_state`；或把 `take_profit` 降为数值参数，扩展 Numba 核 | Amdahl 上限约 1.9 倍（卖扫占 53%，假设核快 10 倍，此 10 倍未实测） | 中：卖因分支多 | 保持 Python 默认，用成交元组对照 |
| 3 | 昨收、涨跌停价、09:30 / 09:45 / 14:55 报价按 (code, day) 只算一次；`_previous_rows` 改用 searchsorted（`../../../backtest/research/csv_minute_backtest.py:560,855,906`） | 5–20% | 低 | fixture 回放 |
| 4 | v7 不再每天 `to_dict("records")`，改用列数组；策略 11 在 `minute_open` 分支前省掉无用数组 | 未计时 | 中：先修 X-11 | v7 测试 |
| 5 | Parquet 读取做 row-group 谓词下推（`../../../backtest/research/ashare_bars.py:354`）；缓存 key 加入来源 / 版本（同时修复 X-12） | 取决于湖布局，全市场时 I/O 往往是瓶颈 | 中 | 缓存往返测试 |
| 6 | **不要**把涨跌停价的 Decimal 改成 float，也不要先把策略 12 状态机移植到 Numba/Rust | — | 高：X-05 已说明边界浮点问题 | — |

验收方式：比较成交元组（日期、代码、方向、价格、股数、原因、现金前后，最好加上分钟 `hm`），不要求字节一致。策略 12 修复 X-01 后 NAV 本来就会变，需要先修正确性，再做性能对照。

---

## 4. 建议的跟进计划（行为变更默认关闭）

1. **P0 策略 12 价格域（X-01）**：新增开关（如 `--s12-price-domain consistent`，默认关）。开启后，MA、涨跌停、市值统一换算到 none 成交域（`P_raw` × 当日因子比），或统一使用 front 分钟。补充「非 1 复权因子」的合成夹具和账户守恒测试。修复前在 run manifest 中标注「s12 分钟 NAV 不可比」。
2. **P0 现金时序（X-02）**：新增开关，让共享循环按分钟时刻推进现金（卖出成交时刻晚于买单时刻的钱不可用）；v7 同理。默认关，先跑差异报告。
3. **P1 策略 11 出场 SMA5 的价格域（X-03）** 和 **front 分区按决策日重锚（X-08）**：开关默认关，先用 needs-data 的真实湖数据测量影响面。
4. **P1 8.x 规则修正**：8.3 追买统一按 50% 预算并消除行序依赖（X-04）；8.1 的档位边界改用 Decimal 或容差比较（X-05）。作为新书版本（如 8.1b / 8.3b）或开关实现，保留旧冻结包以便对照。
5. **P1 策略 12 止损后的台阶锚点（X-06）**：先由你裁定「止损也保锚」还是「HELP 显式声明台阶终止」，再写测试。
6. **P1 市场规则**：ST 涨跌幅加日期和板块维度（X-07，含 2026-07-06 切换）；科创板 200 股起、1 股递增（X-10）；缓存 key 加来源 / 版本（X-12）。均默认关或新建规则版本。
7. **P2 可观测性与文档**：缺 bar 计数（X-26）、策略 12 卖出写 `session_phase`（X-35）、version11 + 容量开关的 CLI 提示、入口文档中 8.1 资金口径、8.1 HELP 措辞、`../../../docs/backtest/engine-ashare-correctness.md:34` 费率说明、补 8.1–8.3 的 retro 文档。
8. **P2 验证**：修复 X-01 后重跑分钟五本，基于 #169 / #170 之后的 tip；补跑策略 11 的 Slice D，或至少做全市场敏感性。
9. **P3 性能**：按第 3 节顺序 1→3→2 推进，每步做成交元组回放。

---

## 5. 执行情况

| CLI | 结果 |
|---|---|
| Codex gpt-6-astra（ultra） | 成功，[report-codex.md](raw/report-codex.md)（581 行，12 项发现）。**自行披露**：一次 pytest 加载了 `../../../tests/conftest.py`，在审查 worktree 中写入了被 git 忽略的 `artifacts/pytest_tmp/…` 空目录。仅限审查用只读 worktree，主 checkout 未受影响，受版本管理的文件未改。 |
| Kimi v0.39.1 | 成功，[report-kimi.md](raw/report-kimi.md)。前两次启动失败：`-p` 不能与 `--auto` 或 `--yolo` 组合，属于 CLI 参数问题，不是鉴权或额度问题；第三次改用纯 `-p` 后正常运行。 |
| Grok 4.7（xhigh） | 首轮审查成功，[report-grok.md](raw/report-grok.md)；交叉核对成功，[crosscheck-grok.md](raw/crosscheck-grok.md)。 |

**验证**：审查结束时 worktree `HEAD` 仍为 `057761a`，`git status` 干净（仅有被忽略的 `artifacts/`）；主 checkout 和其他工作树均无改动。整个过程没有读取真实分钟 parquet，所以「默认研究窗里 NAV 受影响多少」属于 needs-data，需要到 4090 上用湖数据复测。
