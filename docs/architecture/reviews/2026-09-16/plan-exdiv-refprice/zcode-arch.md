# 除权修正片 plan 语义评审（host: zcode-arch）

READY-AFTER-FIXES

> 评审对象：[plan-exdiv-refprice-2026-09-16.md](../plan-exdiv-refprice-2026-09-16.md) v1.0（dissent-steelman 语义对抗，只读）。
> 裁决背景不重开：scoped 修正 = 除权日缩放 cost/peak/prev_close 参考（k=cum[D-1]/cum[D]），成交价/净值不动；≤0.5% 噪声带不修正；全部书生效；买入日除权的新 lot 不调整。
> 证据基线：master 代码（csv_daily_backtest.py / csv_minute_backtest.py / csv_simulate_loop.py / csv_ledger.py / strategy1–10_rules.py / market_layer.py / exdiv_hold_hits.py）+ survey-exdiv-adj-data-prep + er5-recheck-5e8-note + np2 host-note + daily-adjusted-update-ssot。

## 0. 结论速览

- **方向裁决：修 cost/peak/prev_close（方案 A）正确**。全部卖点规则是 (px, cost, peak) 的 0 次齐次谓词或 1 次齐次触发不等式，整体 ×k 后严格不变；档位舍入发生在 D 域（交易所口径）；一次性缩放对多事件复利自然成立。反方向（px×(1/k) vs cost）数学等价但实现更易错且舍入域错位，拒绝（§2）。
- **🔴-1（须修后再合）**：X-R2 检测源**与 survey 设计锁相反**——survey §3 / `exdiv_hold_hits.py` DESIGN_LOCKS 均裁「主源 ex_date_index、因子跳变 ε=5e-3 仅 parity 副证，never the primary enumerator」；plan 改为跳变单源，会把 **145 个非事件跳变日**（precision 95.4% 的 4.6%，低价股舍入噪声可 >1e-2）错误缩放，违反自家 X-R7「非除权日不做任何调整」；另有 1 起跳变记在除权前一日的错位。
- **🔴-2（须补声明）**：跨除权持有 lot 的 **trades pnl / 净值残留失真未声明**——送转不增股、现金分红不入账，假止损消失 ≠ 亏损回收：5 笔 -196 万只会回收约 +35~125 万，其余换一个卖出原因与日期继续留在账上。切片 D 预期与 E-R6 都必须写明，否则读数会被误读。
- **🟡-3**：X-R3 的 prev_close 消费点枚举不全（漏 pool-buy 涨停挂 chase 判定，两引擎各 3 处）。
- **🟡-4**：v4 SMA 门（buy_gate/sell_gate 用截至昨收原始 closes）在除权日域不匹配 → 假 `ma_signal` 卖 / 假 buy_gate 拒——现状已存在、本片不修但**未声明**。
- **🟡-5**：X-R4「所有书 v1–v10」与 X-R7「不改 v7」矛盾（v7 是独立引擎独立账本，实际不会被覆盖）；切片 B DoD 缺「假成交消失」断言（修正同时消灭除权日按旧域跌停价撮合的假 fill）。
- 🟢：PX-1/2/3 认可；佣金/notional 记账不受 cost 缩放污染；chase 金额预算、pending_exit、T+0、多 lot、多事件复合全部自洽；内存量级无虞；无湖/CI 路径与 golden 不受影响；落点建议 ledger 纯函数正确。

---

## 1. 修正后的完整语义推演（10 送 10，k≈0.5，lot cost=10, peak=12）

### 1.1 逐步走查（日线引擎 `csv_daily_backtest.simulate` 日环）

| 步骤 | 代码锚点 | 修正后语义 | 判定 |
|---|---|---|---|
| prev_close→档位 | `csv_daily_backtest.py:260-261`（`closes[-1]`→`_named_limits`）；`market_layer.py:71-80`（`Decimal` 先乘档再 HALF_UP 到分） | prev_close_ref = 10×0.5 = 5.0 → limit_up = 5.50、limit_down = 4.50（D 域分舍入 = 交易所除权参考价口径，与 `l2_analytics/ref_data.py` `prev_close×cum[D-1]/cum[D]` 同式）。D open=5.05 落带内 ✓ | 🟢 |
| gap_open 止损 | `csv_daily_backtest.py:277-292`（trigger = `pos.cost×(1-stop)`） | cost=5 → v8 trigger=3.5，open 5.05 不触发 ✓（v1 trigger=4.9 同样不触发）。修正前 trigger=7 → 5.05≤7 假触发，成交 -49.5% | 🟢 假止损从源头消失 |
| touch 止损成交价 | `csv_daily_backtest.py:293-298`（`_sell(..., trigger, ...)`） | SELL 行 price = 缩放后 trigger = 5×(1-stop)，天然 D 域；「成交价=触发价」的现行近似语义不变，只是域对了 | 🟢 |
| peak 更新 | `csv_daily_backtest.py:301`（`pos.peak = max(peak, high)`） | 缩放在日环开头一次完成 → max(6, D 域 high) 无混域 | 🟢 |
| trail band（v8） | `strategy8_rules.py:34-62` | peak_ret = 6/5−1 = 20% = 修正前 12/10−1，同档 (0.15,0.40] 地板 15% → 触发价 5×1.15 = **5.75** = 旧域 11.5×0.5 ✓；peak_dd：px ≤ 6×0.8 = 4.8 ✓ | 🟢 一致性检验通过 |
| trail（v6）/drawdown（v1/v2） | `strategy6_rules.py:34-49`；`strategy1_rules.py:26-41` | v6 全比值式；v1/v2 `(peak−px)/(peak−cost)` 0 次齐次 ✓ | 🟢 |
| target（v3/v5） | `strategy3/5_rules.py` | px ≥ cost×(1+target) 1 次齐次 ✓ | 🟢 |
| 佣金/notional | `csv_ledger.py:194-220`（execute_buy）、`:229-245`（_sell） | notional = fill_px×shares、comm = 0.1%×notional，**与 cost 字段无关** → 缩放不污染记账。BUY 行是历史成交记录永不重写；SELL 行 price = 实际 D 域成交（open / 缩放后 trigger / close） | 🟢 |
| 净值/EOD_MARK | `csv_simulate_loop.py:224-265`（raw close 估值，`pos.cost` 仅无 K 兜底） | 兜底 cost 缩放后反而在 D 域，与 D 域 mark 同域（比现状更一致）；估值本身不动 → 除权日净值仍含 ~k 的视觉+真实跳变（见 §6 声明项） | 🟡 须声明 |

**比例线性性论证**：所有卖点谓词形如 f(px,cost,peak)=g(px/cost, peak/cost)（0 次齐次）或 px ≤ cost×c / px ≤ peak×c（1 次齐次不等式）。对 (px→px, cost→k·cost, peak→k·peak)（价格在 D 日本来就在 D 域），f 严格不变。唯一非齐次项是档位的分舍入——而它恰好在 D 域按交易所口径重算（prev_close×k 后舍入），这是**本片修 prev_close 而非修成交价的根本理由**。浮点上 11.5×0.5 与 5×1.15 可差 1 ulp，「逐字节不变」承诺已正确限定在无除权路径（plan §5）。

**pnl 语义（SELL 止损触发价来自哪个 cost）**：日线 touch 的 SELL price 来自**缩放后的** `pos.cost`（引擎在日环里现算 trigger），不是 trades 里的 BUY 价；分钟引擎 gap_open/touch 分别以 bar open / bar close 成交（`csv_minute_backtest.py:578-582`），同样 D 域。因此 trades.csv 的 BUY/SELL 对（跨除权 lot）之间存在结构性 (1−k) 域差——这是 scoped 裁决的既定残留，不是实现事故，但必须落 E-R6 声明（🔴-2，详见 §5）。

### 1.2 分钟引擎

接入点「`scan_held_day` 前同层」正确：`csv_minute_backtest.py:846-872` 日环按 code 取 prev_close（:862）→ 档位（:863）→ 逐 lot `scan_held_day`（:875）。缩放必须在 :862 之前（或与 prev_close 映射同一 helper），保证当日**首个 bar 评估前**完成——peak 在 bar 循环内更新（scan 内 `new_peak`），一旦首 bar 后再缩放就会混域。numba 路径（:447-504）cost 以 float 传入，同样受益，无需单独处理。

## 2. Steelman 反方：为什么不修 cost 而修触发比较（px×(1/k) vs cost）——裁决

反方最强论证形如：「cost 是成交事实，不该被改写；比较时把当日价格上折 (1/k) 回旧域即可，trades 可读性完美（SELL 触发判断直接对 BUY 价）。」

逐项对抗：

1. **数学等价但记账更错**：对 0 次齐次谓词两方向严格等价；但 touch 止损的**成交价** = cost×(1−stop) 必须落 D 域才能记账（成交价不动是硬约束），方向 B 仍要隐式计算 cost×k×(1−stop) ——等于偷偷做了方向 A。
2. **peak 混域与复利记账**：`peak = max(peak, high)` 逐日推进，方向 B 必须把 D 及之后每日 high 上折 (1/k_cum)，且每个 lot 各自携带事件史（分红季两次除权 = k1、k2 复合）；方向 A 一次性缩放即终态，多事件自动复合（cost×k1×k2）。出错面：B >> A。
3. **档位舍入域**：交易所除权日档位 = 除权参考价（D 域）×(1±档) 四舍五入到分（`market_layer.py:71-80`）。方向 B 把价格上折回旧域比较时，D 域已舍入的档位反向映射会产生不对称舍入误差——唯一与交易所同域的做法就是 prev_close×k 后在 D 域舍入（方向 A）。
4. **trades 可读性 / 研究表 ret**：两方向下 trades.csv **完全相同**（成交价都不动）——`research_lot_pnl` 类脚本的 `ret = sell_px/buy_px` 在两方向下**同等地**含除权跳变失真。即 ret 语义问题不是方向选择的判据，而是本片必须**声明**的口径（🟡-7）：跨除权 lot 的原始价 ret ≠ 真实持仓收益率，真实收益须用 exdiv_map 重建（k 复合）或等送转股数调整——均另开片，不入本片。方向 A 的代价（内部 cost ≠ BUY 行价）用 `exdiv_adjusted_lots` 计数 + E-R6 一句话声明即可覆盖。

**裁决：方向 A（plan 现案）胜**。反方唯一实质优点（cost 字段可读性）不构成语义收益；其在舍入域、peak 复利、成交价记账上三处劣于 A。

## 3. 边界组合逐案

| case | 推演 | 判定 |
|---|---|---|
| a) 除权日 = pending_exit 执行日（日线） | D-1 收盘评估在旧域**自洽**（当时价格、cost、档位全旧域），挂 pending_exit；D 开盘按「次日开盘离场」以 open（D 域市价）成交——成交价是市场价无域问题；跌停拦截用映射后 limit_down（4.5）✓（`csv_daily_backtest.py:269-274`）。缩放对该 lot 的 cost 无消费点（fill 不依赖 cost），提前缩放无害。**覆盖且语义正确，无需特判。** | 🟢 |
| b) 除权日 = chase 到期日（T+1 9:45/日线收盘近似） | `run_chase_due_day`（`csv_simulate_loop.py:103-155`）的 prev_close 来自 `quotes_for` 的 `closes[-1]`（旧域 close）→ X-R3 已点名 chase 链 ✓；`chase_decision(open, px, limit_up)` 三量同 D 域 ✓；**per_ch 是金额，k 不作用** ✓；chase 买入 lot 的 cost=D 域（PX-3 域内）✓。「昨日已 pop 未成」不存在——pop 只发生在报价成功后；D 无 K 则 pending 顺延到下一有 K 日（映射发生在实际评估日，域随该日）✓。缺口：chase 的 `buy_gate`（v4 SMA）见 🟡-4。 | 🟢（gate 例外） |
| c) 同日除权+跌停 | 修正后 limit_down=4.5（D 域）：D open=4.50 → `hit_limit_down` → **defer** ✓（现实排队锁死）。修正前 limit_down=9.0 → open 4.5 不触跌停 → 现引擎会**成交一笔现实里不可能的卖单**（`csv_daily_backtest.py:280-292` / 分钟 :906-911）。即本片不只消灭假止损，还消灭**假成交**——切片 B DoD 应补该断言（🟡-5）。defer 链语义：次日以 D 收盘为新 prev_close（无映射，非事件日）重评 ✓。 | 🟢（须加断言） |
| d) 买入当日除权（PX-3） | D 日 14:55/收盘价在 D 域 → lot cost 天然 D 域；日环顺序（持仓卖评 → chase → pool buys → 估值）保证缩放先于新 lot 创建（新 lot 不在 `st.positions` 里）→ **无双重缩放，核实成立** ✓；T+0 不评估、peak=cost（D 域）✓（分钟引擎 `can_sell=False` 分支不更新峰值）。 | 🟢 |
| e) 除权日持仓有 pending_chase 排单 | pending_chase 值 = (per_ch 金额, sig_idx)，无价格量 ✓ 不受影响；同码旧 lot 在 D 被缩放、chase 新 lot 在 D 域建仓，两域各自正确（v8 per_name 已持跳过；daily_quota 加仓路径 allow_add 时多 lot 并存，各自 cost 独立）✓。 | 🟢 |
| 补) 同一 lot 跨两个除权日 | 逐事件 ×k1、×k2 复合（map 按 (code, ymd) 查），域链 none 价格只在事件日跳 → 正确。plan §7 只写了多 lot，建议补一句多事件。 | 🟢 |
| 补) 除权日停牌（plan §7 开放项） | adj_factor 由 front/none 收盘生成，停牌日无 K 大概率无行 → 跳变落到**复牌首日 R**：k = cum[R-1 有行]/cum[R]，而引擎 prev_close 在 R = 停牌前最后 close → prev_close×k 恰为交易所除权参考价口径 → **「跳变落点日执行」的语义自洽**。建议照此定稿（缩放/映射均发生在首个有 K 日）并配 fixture。 | 🟡-6 定稿即可 |

## 4. 噪声带残留声明与 E-R5 收窄措辞

残留量级（ε=5e-3 以下，窗内 1,372 起）：止损触发距离偏移 ≤0.5pp（v8 −30% 实为 [−30.5%, −29.5%]；v1 −2% 实为 [−2.5%, −1.5%]——注意 0.5% 跳变**不足以单独**击穿 2% 档，故 v1 在噪声带内无假止损风险）；band 地板偏移同量级；档位边缘在低价股 1 分栅格下可差 1 分。可声明为「已知近似」。

**E-R5 收窄条目建议措辞**（替换 `engine-ashare-correctness.md:28` 现文）：

> **E-R5（收窄 2026-09-16）**：csv 日线/分钟链成交与估值全程 `dividend_type=none`；**除权日**（事件判定见 E-R6）的 cost/peak/涨跌停参考价已按 E-R6 修正。残留近似三句：①跳变 ≤0.5% 的小额分红（窗内 1,372 起）不修正——止损触发距离/止盈地板偏移 ≤0.5pp，低价股档位边缘可差 1 分；②跨除权持有 lot 的成交与净值按原始价×原始股数记账（送转不增股、分红不入账），trades pnl 与净值含 (1−k) 结构性失真（见 E-R6 残留声明）；③v4 SMA 门用截至昨收的原始 closes，除权日不换域（假 ma_signal/buy_gate 拒，历史行为保留）。21M 口径历史数字（命中 daily 8.1% / minute 2.0%）与 5 亿口径 149 笔止损为**修正前口径**。

另须点名第四类残留：**ε 以上但 ex_date_index 无事件对应的跳变日**（survey §1②：ε=5e-3 下 145 个仅跳变日，低价股舍入噪声可 >1e-2）——按现 X-R2 会被错误缩放，这不是「不修正的近似」而是「修正错了」，归 🔴-1 处理，不入声明。

## 5. 对 5 亿研究结论的追溯影响（量级裁定）

- **止损笔数**：149 → ~144 是**下界**预期（5 笔可证实假止损消失）。er5 note 混合带 36 笔疑似（−1,139 万）中，凡跳变 >0.5% 者除权日不再假触发，其中部分（尤其 0.5%–10% 段对 v1 的 2% 档）也会转持有——实际止损数可能降到 ~120–135。真止损 113 笔（−3,440 万）不动。
- **总亏损不回收 -196 万（🔴-2 核心）**：5 笔假止损 lot 改为持有（cost 已缩放到 D 域），其后按正常规则在 D 域退出，trades 记录亏 ≈ notional×(k×(1+r)−1)。跳变 +30%~+46%（k≈0.68~0.77）：即便 r=0，记录亏 23%~32% vs 假止损实现亏 35%~47% → 每笔改善 7~24pp × ~100 万 ≈ **合计 +35~125 万上界**；其余 ~70%~85% 的「亏损」只是换了卖出原因与日期留在账上（净值同样：除权日 ~k 的下折仍在，仅不再被提前变现）。
- **对 5 亿口径总收益读数**：+35~125 万 / 5 亿 ≈ **+0.007~0.025pp** —— 若现读数 -3.25%，修正后约 -3.24% 以内的小数点后第二位变化。切片 D 短记必须预写此量级，防「假止损消失 ⇒ 大亏回收 12%」的误读。
- **追溯注记**：`er5-recheck-5e8-note`（-196 万/12% 叙述）、`np2-exdiv-hold-hits-host-note`（21M 口径数字）、已交付资本短记/研究表，统一加「修正前口径（<2026-09-16 引擎）」脚注并指向 E-R6；E-R5 保留历史数字（见 §4 措辞）。

## 6. 锁完备性（X-R1~R7 逐条）

| 锁 | 评 | 级 |
|---|---|---|
| X-R1 只修参考量 | 范围正确；建议补一句「shares 不调、现金红利不入账——跨除权 pnl/净值残留见 E-R6」把 🔴-2 钉进锁文本 | 🟢（补一句） |
| X-R2 数据源 | **与 survey 设计锁相反**：survey §3 L1 与 `exdiv_hold_hits.py` DESIGN_LOCKS 均为「primary=ex_date_index；因子跳变 ε=5e-3 parity-only，never the primary enumerator」。SSOT（`daily-adjusted-update-ssot.md:20`）禁的是 **dr 数值推导** front/因子，不禁用 ex_date 事件枚举——plan 的引用失真。后果：145 个仅跳变日被错误缩放（低价股噪声 k 可达 1%+，污染档位与触发两边）+ 1 起跳变记前一日错位 + 窗内 1,676 行 NaN/24 码无 front 未提处理。**修法**：事件门 = ex_date_index（窗口）∪{跳变>1e-2 且 ex 缺行的兜底}，k 恒取 cum[D-1]/cum[D]；或最低限「跳变∧ex 事件」双条件 + 缺行/NaN 计数 | 🔴-1 |
| X-R3 接入点 | 「两处」枚举不全：日线 prev_close 消费点 3 处（持仓环 `csv_daily_backtest.py:260-261`、chase `csv_simulate_loop.py:129-131`、**pool buys `csv_simulate_loop.py:195-202`**），分钟同 3 处（`csv_minute_backtest.py:862`、`_chase_quotes_for`/`_pool_quote_for` 供给的 closes）。pool-buy 的 `hit_limit_up(px, limit_up)`（涨停→挂 chase）若不映射：D 日 D 域涨停价 5.5 对旧域 11 永不触发 → **除权日系统性漏挂 chase**，与卖侧修正不对称。措辞改为「该码当日全部 prev_close→档位换算点（持仓/chase/pool-buy，两引擎）」，实现上给单一 helper（如 `mapped_prev_close(code, ds, closes[-1])`） | 🟡-3 |
| X-R4 行为范围 | 「所有书 v1–v10」不实：v7 是独立引擎独立账本（`csv_minute_backtest_v7.py` 自带 Position/simulate_v7），本片接入点不经过它 → 实际覆盖 v1–v6、v8–v10。改为明示 v7 不接。DoD 补「除权日假成交消失」断言（§3c） | 🟡-5 |
| X-R5 统计 | `exdiv_adjusted_lots` ✓；建议加 `exdiv_skipped_no_factor`（NaN/缺行）与 `exdiv_prev_close_mapped`（或并入前者），一次做全可观测 | 🟢 |
| X-R6 文档 | E-R6 须含三句：①**跨除权持有 lot 的 trades pnl/净值仍含 (1−k) 结构性失真**（本片只修触发参考，股数/分红/估值不动）；②v4 SMA 门除权日域不匹配（§4 ③）；③噪声带 ≤0.5%。缺 ① 即 🔴-2 | 🔴-2 / 🟡-4 |
| X-R7 不做清单 | 加三项明示：不调 shares、不入账现金红利、不修 v4 SMA 域（各自另裁） | 🟢（补） |
| 内存/性能 | 窗内跳变 3,133 条、ex 事件 4,389 条 → dict[code][ymd] 微不足道 ✓；分钟缓存（bar_cache）只存行情无 adj 信息，无失效问题 ✓ | 🟢 |
| 无湖/CI/golden | 空 map → 无除权路径 trades 逐字节不变 ✓（summary 因新 stats 键多一行，plan §5 措辞已准确限定 trades）；data-free CI 不触湖 ✓ | 🟢 |
| cost/peak 落点 | ledger 纯函数 `rescale_position(pos, k)` 优于引擎直改字段（两引擎一处定义、可单测、Position 字段唯一写者收敛）——plan §7 倾向正确，建议从「评审核实」升级为定稿 | 🟢 |

另核实：`pos.cost` 全部消费点为日线 trigger/take_profit（:279/:314）、分钟 scan 入参（:879）、净值无 K 兜底（`csv_simulate_loop.py:245/:253`）——缩放后三处语义均成立（兜底反而更一致），无第四处隐藏消费。equity 曲线除权日跳空**仍存在**（估值 raw close）且是真实低估（非仅视觉）——归入 E-R6 声明 ①。

## 7. 人裁点建议 + 边界 case 测试向量清单

### 7.1 人裁点建议（PX-1/2/3 复核认可，维持默认；新增四条）

| # | 问题 | 建议 |
|---|------|------|
| PX-4（新，🔴-1） | 检测门改回 survey 设计锁：事件 = ex_date_index（主）∪ 跳变>1e-2 兜底（防 ex 缺行），k 恒取因子比 | **是**（否则 145 个非事件日错误缩放，违反 X-R7 自我声明） |
| PX-5（新，🟡-4） | v4 SMA 门除权日换域（gate 的 closes 整窗 ×k——窗全在 D-1 及以前，恒等精确）入本片，还是声明残留另开微片 | 默认**声明残留另开**（v4 非当前主研究面；成本虽低但扩爆炸半径）；若人裁并入，落点=quotes/closes 供给层整窗 ×k，禁改 strategy4_rules |
| PX-6（新，🔴-2） | E-R6 增「跨除权 pnl/净值残留」声明 + 切片 D 预写「回收上界 +35~125 万（≈0.01~0.025pp），非 -196 万」+ 已交付研究文档统一加「修正前口径」脚注 | **是** |
| PX-7（新，小） | X-R4 措辞改「v1–v6、v8–v10；v7 独立链不接」；切片 B DoD 增「除权日假成交消失」断言 | **是** |

### 7.2 边界 case 测试向量清单（合成 fixture，两引擎各跑一遍除非注明）

1. **T1 假止损消失（日线+v1 与 v8 各一）**：D-3 买 @10（100 股）；D：prev_close 10、open 5.05、k=0.5 → 断言无 `stop_loss:gap_open`；`exdiv_adjusted_lots=1`。
2. **T2 档位映射**：同上 → D 日 limit_up=5.50 / limit_down=4.50（Decimal HALF_UP 分舍入）；D open=5.50 时买侧拦截/卖侧不误判。
3. **T3 假成交消失**：v8、D open=4.50（=映射后跌停）→ `defer_sell_limit_down` +1、无 fill（修正前会以 4.5 成交）。
4. **T4 touch 止损 D 域成交价**：v1、D low=4.85 ≤ trigger 4.9 → SELL price=4.9（非 9.8）。
5. **T5 band 一致性（v8）**：cost 10→5、peak 12→6；D 后 px 5.70 → `trail:band:15` @5.70（等价旧域 11.4 触发 11.5 线下）。
6. **T6 买入日除权无双重缩放（PX-3）**：D 日 pool 买 @5.06 → cost=5.06、D+1 trigger=5.06×0.98；同日旧 lot cost=5.0 并存，各自独立。
7. **T7 pending_exit 跨除权执行**：D-1 挂 trail pending → D open 成交、reason 保留、映射后跌停则 defer。
8. **T8 chase 到期日=除权日**：D-1 旧域涨停挂单；D chase quotes（open 5.05 / 9:45 px 5.20）对 limit_up 5.50 → buy @5.20；per_ch=100 万 → 192,300 股；同向量断言旧域 limit_up=11 时**不**因 5.20<11 误放行跌停态（反向:px=5.50 时 limit 拦截）。
9. **T9 pool-buy 涨停挂 chase 用映射档（🟡-3 回归）**：D 日 14:55 px=5.50 → 挂 chase（修正前 5.50<11 不挂）。
10. **T10 多 lot / 多事件复合**：D-5、D-2 两 lot 各自缩放；D1、D2 两次除权 cost×k1×k2。
11. **T11 停牌跨界**：D 无 K、复牌日 R 有因子跳变 → 缩放与 prev_close 映射发生在 R（首个有 K 日）。
12. **T12 噪声带不修正**：|Δf/f|=0.3% → 不缩放、计数为 0（声明性行为锁定）。
13. **T13 NaN/缺行**：D 日因子 NaN 或无行 → 跳过 + `exdiv_skipped_no_factor` 计数、不抛异常。
14. **T14 检测门（若 PX-4 采纳）**：跳变 0.8% 且 ex_index 无事件 → 不缩放；ex_index 有事件但跳变 0.3% → 不缩放（噪声带）或按人裁定；ex 缺行 + 跳变 1.5% → 兜底缩放。
15. **T15 无湖空 map**：exdiv_map 缺文件 → trades 与 master 基线逐字节一致 + stderr 一次性提示。
16. **T16 净值声明锁定**：D 日 equity 按 raw close 下折 ~k（断言现状值防误修），EOD_MARK 行为不变。

### 7.3 结论

方向与缩放语义成立、边界组合在现有代码结构下基本自洽；**合入前须完成 🔴-1（检测源改 ex_index 事件门 ∪ 大跳变兜底）与 🔴-2（pnl/净值残留声明 + 切片 D 量级预期 + 追溯脚注），并清 🟡-3/4/5 的措辞与断言缺口**。上述均为 plan 文本与 fixture 层修订，不动核心设计——READY-AFTER-FIXES。
