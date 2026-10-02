# MyQuant-backtrader 分钟线回测引擎与分钟策略评审报告（kimi，2026-09-25）

- 评审对象：worktree `/workspace/wt-bt-minute-review`（detached，origin/master @ 057761a，2026-09-25）。
- 性质：READ-ONLY。未修改仓内任何文件；实测仅用 `~/.venvs/bt-ci/bin/python`（Python 3.12.14）跑合成 bench 与 fixture 测试。
- 证据分级：每条 finding 标注 **verified-in-code**（已在 worktree 对照行号核实）或 **inferred**（代码路径推断/未实测）。文中行号均对当前 HEAD 核实过（关键发现由本评审亲自抽查复核，非纯转述）。

---

## 0. 三个策略的识别与证据

2026-09-21 当天落地的三个策略，经 `context/git-log-0919-0923.txt` 与代码核实：

1. **策略12 金榕元 MA 减仓书（version12）**。代码：`backtest/research/strategy12_rules.py`（纯规则）、`backtest/research/strategy12_engine.py`（书侧编排）、注册 `backtest/research/csv_strategy_books.py:648-672, 1458-1471`；测试 `tests/test_strategy12_rules.py` / `tests/test_strategy12_engine.py`。文档：`docs/backtest/plan-strategy12-jinrongyuan-2026-09-21.md`、`docs/backtest/handoff-strategy12-codex-impl-2026-09-21.md`（§0 binding 人裁）、`docs/architecture/reviews/2026-09-21/plan-strategy12-jinrongyuan/`。PR 链：#151（合并 commit `013a2d5`）→ #158（分钟允许 `--dividend-type none`，`161f13a`）→ #169（日线延期卖钉信号时 lot，`9b5b1ce`）→ #170（D1 nits，`4b59cc1`）。
2. **version11 ma_chip CSV 移植（strategy11）**。代码：`backtest/research/strategy11_rules.py`、导出器 `scripts/data/export_strategy11_pool.py`、双引擎接线；测试 `tests/test_strategy11_rules.py` / `tests/test_strategy11_engine.py` / `tests/test_export_strategy11_pool.py`。文档：`docs/backtest/plan-version11-machip-csv-2026-09-21.md`、`docs/backtest/handoff-version11-codex-impl-2026-09-21.md`、`docs/architecture/reviews/2026-09-21/plan-version11-machip-csv/`。PR #152（`e741915`）。
3. **第三策略 = strategy 8 里程碑书 8.1/8.2/8.3**（而非 #156 fullstrat 研究回放）。证据：commit `b2b406e`（2026-09-21 13:05，"feat(research): register strategy 8 milestone books 8.1/8.2/8.3"）经本地分支 `feat/v8-milestone-books` 直接 merge（`599a894`，无 PR 号）；代码 `backtest/research/strategy8_1_rules.py` / `strategy8_2_rules.py` / `strategy8_3_rules.py`，注册于 `csv_strategy_books.py:1339-1378`（双引擎共用注册表），测试 `tests/test_strategy8_milestones.py`。判定理由：8.1/8.2/8.3 是**当日新注册、可通过 `--strategy` 直接运行的策略书**；#156（`fullstrat_research_*.py`，`9a1a609`）是只读研究回放 harness（Q2 定量 / H2 时钟置换），不产生新策略书，因此归入 §4 决策清单而非"第三个策略"。共享基建 `backtest/research/ma_infra.py`（#150 plan / #154 实现）同日落地，被 strategy4/11/12 消费。

---

## 1. 行业惯例对齐（vs backtrader / vectorbt / zipline / QMT / 聚宽）

### 1.1 Bar 时间戳语义与信号→成交映射

- **As-built（verified）**：湖分钟 `time` 为"中国墙钟标成 UTC"（`csv_minute_backtest.py:7,153`）；当日首根 bar 标 09:30，即 **bar-START 标签**（09:45 bar = 区间 [09:45,09:46)），`_open_quote_for` 精确要求 `hm==570`（`csv_minute_backtest.py:589-592`）。4090 探针文档佐证 START 口径（`docs/backtest/reviews/results-minute-sensitivity-b-batch2-2026-09-20.md:23-25`）。
- 中国数据商（Wind/通达信/聚宽默认）多用 **bar-close 标签**（(09:30,09:31] 标 09:31）。本仓标签口径本身无对错，但**标签语义只存在于文档与探针，生产代码无运行时断言**（inferred 风险）：若湖重建改成 END 标签，所有买/卖钟静默偏移 1 分钟。
- **信号→成交为同 bar 成交（cheat-on-close 口径，verified）**：扫描器 `scan_held_day_python` 用触发 bar 自身 close 判定并按该 close 成交（`csv_minute_backtest.py:334-336, 374-391`）；池买在 14:55 bar close（`BUY_HM=895`，`:127,565-572`），追买在 T+1 09:45 bar close（`CHASE_HM=585`）。backtrader/vectorbt/聚宽/QMT 的分钟默认均为"bar t 出信号 → bar t+1 open 成交"。叠加 START 标签，14:55 bar 的 close 实际 14:56 才可知，成交却记在 14:55 —— 存在约 1 分钟的同 bar 前视偏差。**这是有意的向量化简化**：HELP_LOCK 明示口径，且 minute-sensitivity batch1–4 已量化 next-open 对照（`docs/backtest/reviews/plan-minute-sensitivity-b-2026-09-20.md:20`），#156 的 H2 人裁也在研究域换过全 fill 时钟。**[F-E1, major]**

### 1.2 成交价模型 / 滑点 / 触价

- 成交价 = 选中 bar 的 open（gap stop，`csv_minute_backtest.py:332-333`）或 close（其余全部路径）；**无滑点、无排队/冲击模型**（verified）。
- **触价止损只看 close，不看 bar 内 low**：扫描循环只读 `o/h/c` 三数组（`:321-336`），`stop_loss:touch` 定义为 `px_close/cost-1 <= -stop_pct`。bar 内 low 击穿止损而 close 收回时不触发 → 系统性偏乐观（少触发、触发价更好）。HELP_LOCK（`:159` 附近）明示此口径，属研究简化。**[F-E2, major]**
- 跌停保护双保险：open 跌停即跳过（`:330-331`）+ 成交前 `defer_sell_at_limit` 再检（`:835-841` 及书引擎 `strategy12_engine.py:101-103`）。

### 1.3 A 股规则

| 规则 | As-built | 对齐判定 |
|---|---|---|
| T+1 | `t1_sellable = buy_date < session`（`ashare_session.py:39-41`）；扫描器 T+0 整日跳过（`csv_minute_backtest.py:317-320`）；部分卖路径也强制（`csv_ledger.py:341-345`） | **对齐**（verified） |
| 涨跌停幅度 | Decimal HALF_UP 到分（`market_layer.py:73-84`）；300/301/302/688/689=20%，北交所 30%，主板 10%，ST 名称正则 5%（`:57-65`+`:15-22`）；未知板块 fail-closed → `skip_unknown_board` | **对齐且优于多数 OSS**（Decimal 锁定例：1.65×10% 跌停=1.49 禁银行家舍入）。**缺口（inferred）**：注册制上市前 5 日无涨跌幅、主板新股首日 44% 未建模；无昨收则天然不交易 |
| 涨停不能买/跌停不能卖 | `hit_limit_up`（`ashare_session.py:29-31`）当日拒买+可选 pending 追买；一字板次日 09:45 追买仍板则 `chase_skip_limit` 放弃、只评一次（`csv_simulate_loop.py:164,183-185`）；任何卖因跌停 defer 次日再评（E-R1） | **对齐**（verified） |
| 停牌/缺 bar | 当日无分钟切片 → 持仓冻结跳过；净值用最近有 K 的 close，不用成本冒充（`csv_ledger.py:201-220`）；整日零量剔日（`ashare_bars.py:383-385`） | **对齐**（E-R4）。边界（inferred）：湖 parquet 无 volume 列则无法识别零量日 |
| 午休 11:30–13:00 | session 过滤只留 [09:30,11:30]∪[13:00,15:00]（`ashare_bars.py:27-28,308-312`） | **对齐** |
| 集合竞价 | **无 09:25 开盘竞价 bar**，最早成交 09:30 open；**14:57–15:00 收盘集合竞价不建模**，按连续竞价处理（`ashare_fill_clock.py:12-27`；P1=A 人裁锁定） | **偏离（人裁接受）**：高估尾盘可成交性；是否真有 15:00 bar 取决于湖（本次未读湖验证）。**[F-E3, minor]** |
| 整手 | 买入一律 100 股整手（`csv_ledger.py:223-233`），`shares_override` 也 `//100*100`（`:259`）；**科创板 200 股起/1 股递增未建模**（verified）。部分减仓可留非整百余股并跨多次卖出（δ5 合同明示）——真实规则要求零股一次性申报，偏离（inferred） | **部分对齐 [F-E5/F-E7, minor]** |

### 1.4 费用

- SSOT `ashare_fees.py`：默认 `BILATERAL_10BP` = 双边各 0.1%、无最低 5 元（`ashare_fees.py:17,53-55`）；`--qlib-cost` opt-in 切 QLIB_PORTANA（买 5bp/卖 15bp/min 5）。公式 `max(notional×rate, floor)`（`:23-31`）。
- **无印花税、无过户费**（verified+文档明示）：真实印花/过户留在 live `trade_fee_policy` 且禁止 import（`docs/backtest/engine-ashare-correctness.md:37`）。故"2023-08-28 起卖方 0.05%"的日期依赖性无从谈起——根本没建模。
- 行业对照：**偏离（人裁锁定 δ1=A/A/A）**。默认口径≈佣金的 4 倍、不含卖方印花 0.05%、不含过户费 0.001%、无 min 5；大单向费用高估、小单向 floor 低估。对相对比较研究可用，对绝对收益不可比。**[F-E4, minor]**（显式研究决策而非疏漏）

### 1.5 复权与除权经济

- 成交与估值全程 `dividend_type=none` 原始价；分钟 `--dividend-type front` 仅 v12 可选且缺 1m/front 分区 fail-closed（`csv_minute_backtest.py:1049-1055,1129-1138`）；v12 日线信号域固定 front（#151 人裁，`:1108-1125`）；**front 日线信号+none 分钟成交下 E-R6 remap 显式关闭，禁静默双重调整**（`:1180-1186`）。对齐且防线明确。
- E-R6 参考价修正：除权日缩放持有 lot 的 cost/peak（`csv_ledger.py:154-163`），prev_close 映射回 D 域算档位（`exdiv_map.py:77-92`）。对齐交易所昨收调整规则。
- 除权经济（δ6，默认 off）：显式事件供给才启用；现金红利挂应收、送转股限售（`ashare_exdiv_economics.py:85-137`）。默认 off 时跨除权持有 pnl 有结构性失真（E-R5 收窄声明）。**部分对齐**：文档化的研究残留。

### 1.6 现金/持仓记账

- 买入即 `cash -= notional + comm`、卖出即 `cash += notional - comm`（`csv_ledger.py:280,390`）；无 T+1 资金交收滞后——与 A 股"卖出资金当日可用"口径一致（对齐）。
- lot 级持仓、同码多 lot 各自 cost/peak/lot_id；部分成交仅 volume-cap 路径，普通路径整笔成/整笔拒。
- **脆弱契约（verified）**：`daily_quota_used` 在 per_name 模式下 vestigial，但 `execute_buy` 内部仍无条件累加（`csv_ledger.py:281`），靠调用点保存/恢复才不出错（`csv_simulate_loop.py:351-354`）。**[F-E6, minor]**

### 1.7 日终处理 / 缺 bar

- NAV mark 用**日线 close**（停牌取 prior close），不用分钟 15:00（P4=A 人裁：touch 资格与 mark 独立两轴）；对齐。
- 无挂单概念：决策当 bar 成交或作废，追买 pending 是唯一跨日"订单"（无限保留至有报价日）。无限价单排队/撤单模型——偏离（简化，研究口径可接受）。
- 读取失败 fail-closed（`MinuteBarReadError`/`DailyBarReadError`）；分钟 cache 无新鲜度守卫是文档明示的已知限制（`engine-ashare-correctness.md:48`）。
- 附带：`engine-ashare-correctness.md` 内嵌的旧 file:line 锚点相对当前 HEAD 已漂移（#198/#199 后函数移动），引用需重新核对。**[F-E8, minor]**

---

## 2. 业务需求符合度（实现 vs plan/handoff/人裁）

### 2.1 策略12（version12）

**总体结论：人裁全部落实，未发现与 §0 binding 人裁矛盾的实现。** Grok 核评审 PASS_WITH_NITS。MA5 周期减仓/买回 + MA10 止损/买回、latch=A（仅周期锁、reclaim 即 re-arm、同日可再减、无每日锁）、residual=2（<100 残差保留合并下轮）、双通道独立记忆、日线收盘评估次日开盘成交/分钟逐 bar close 评估当 bar 成交、日线信号域 front + 分钟成交域默认 none（front 可选 fail-closed）、exdiv remap 混域关闭 —— 均与代码一致（落点详见 §4 表）。S1 部分卖守恒已修（`csv_ledger.py:428-434`）。#169 信号时 lot 锚定、#170 clamp 保 lot0≥100 均在位（`strategy12_engine.py:88-96,104-107`、`strategy12_rules.py:108-122`）。

发现的问题：

- **[F-S12-1, major, verified] STOP 可杀死 +20% 台阶锚**。止损 `keep_anchor=False`（`strategy12_engine.py:106-107`：`keep_anchor=reason==REDUCE`），lot0 可清空；`lot_id` 单调不复用（`csv_ledger.py:285`）。若止损后仍有其它残余 lot（如 T+1 锁定的 lot1）留存，后续 pool 新买拿 lot_id>0，而 `step_add_due` 的 `parent=None` 直接返回 False（`strategy12_rules.py:165-170`）→ 该码 +20% 台阶**永久停加**。P13 人裁只给减仓保了 lot0≥100，未覆盖止损情形；HELP_LOCK 未声明。影响：极端路径下买侧行为与"历史包口径"分叉。建议：STOP 后若仍有持仓则保留 lot0≥100（与 REDUCE 同锚），或在 HELP_LOCK 显式声明该分叉；加针对测试。
- **[F-S12-2, minor, verified] 分钟侧缺当日 K 帧的 pool 代码静默 `continue`**（`strategy12_engine.py:226-231`），不进名单、不计 `skip_no_bar`；只影响可观测性（grok nit 2 仍在）。
- **[F-S12-3, minor, verified] `scale_memory` 把 <100 记忆 floor 到 0 时不动 `latched`**（`strategy12_rules.py:157-161`）：会以 0 股 latch 挡住 MA5 再减，直到下一次合格 reclaim 走 `reclaimed(0)` 自愈。仅显式 exdiv economics 开启时可达（grok nit 3 仍在）。
- **[F-S12-4, minor, verified] `_normal_buys` 写死 `allow_add=True`/`buy_gate=None`**（`strategy12_engine.py:142,147`），不读 hooks；对 v12 当前为真，但书字段漂移不会生效（grok nit 6 仍在）。
- **[F-S12-5, minor, verified] 分钟跌停延期统计按 bar 计数、日线按笔**：分钟 `fill_exit` 每根 bar 各调一次（`strategy12_engine.py:101-103` + `run_minute_day:264-267` 逐 bar 调用），跌停日 `defer_sell_limit_down` 被放大约 240 倍；stats 跨引擎口径不一致，未文档化。
- **[F-S12-6, minor, verified-doc] Slice D 实湖五本对比未执行**（plan §7-D / handoff / grok nit 1 三处一致）。#165 回填了 4090bot 的分钟五本 NAV（窗 20251023–20260909，none），但属"数字誊录、不主张 parity"；日线 front 五本 smoke 已有记录。业务定位仍是"未验证多头"。
- **[F-S12-7, minor(perf), verified] v12 分钟路径逐 bar 构造单元素 numpy 数组调用完整 scan**（`strategy12_engine.py:232,254-263`）：每 (code,day) 先 `itertuples()` 物化整帧 dict，再对 240 根 bar × 每持仓 code 各调一次 scan。见 §3。

### 2.2 version11（ma_chip）

**总体结论：四项锁定人裁逐条落实（契约日 / 周线 prefix-equivalent / volume=A / 禁追买），Grok PASS_WITH_NITS；未发现 plan/handoff §0 与代码的实质矛盾。** 边缘信号（close>SMA20>SMA60>周MA20 且 high>布林上轨 ddof=1 且 cyqk>0.70，`strategy11_rules.py:43-67`）、entry-close 退出 FSM（`:76-94`）、严格契约日 T（`export_strategy11_pool.py:99-112`）、分钟 09:30 open 成交（`csv_minute_backtest.py:589-592`）、volume=A 未完成桶买 skip/卖 defer、卖出日不重入、`--stop-pct` 拒绝、池篱笆拒绝 `stock_pool/` —— 均在位。

发现的问题：

- **[F-V11-1, major, verified] `--participation-rate` 开启时 v11 分钟结构性零成交**。买侧 `volume_at=AM_OPEN-1=569` 而 bucket=570（`csv_minute_backtest.py:947`），卖侧同（`:792`）；`VolumeCap.clamp` 的 `bucket<=at` 校验恒假（`ashare_volume_cap.py:55-59`）→ 买必 skip、卖必 defer。这是 volume=A 人裁的直接后果，handoff 已声明"不能把零成交解释为无信号"，但意味着 cap 开启的 v11 分钟回测产出全空。建议：CLI 层对 `version11 + --participation-rate` 组合显式拒绝或大字警告，而不是静默跑空。
- **[F-V11-2, minor, verified] pending 卖缺开盘 bar 静默 `continue`、无任何计数器**（`csv_minute_backtest.py:777-779`）；买侧同情形计 `skip_no_bar`、零量计 `defer_sell_volume`，卖侧不对称、不可观测。
- **[F-V11-3, minor, verified] SMA5 短窗静默 HOLD**：持仓不足 5 根日线时 `sma_series(closes[-5:],5)` 为 None → `_finite` 假 → HOLD（`strategy11_rules.py:104-106`）。生产预热 200+ 不受影响（grok nit 9）。
- **[F-V11-4, minor, verified] "日线契约收盘买"零新增代码**：复用引擎通用 `_pool_quote_for` 返回 `row["close"]`（`csv_daily_backtest.py:486-493`）。未来若改日线默认买钟会静默改 v11 契约；建议给 v11 日线加显式 price_rule pin 测试。
- **[F-V11-5, minor, verified] `circulating_capital_asof` 按 `stock_code` 精确匹配、无归一**（`oskh_factors/bridge/turnover_resist.py:97`）：宿主股本表代码形态不一致时表现为大量 `skip_cyqk_nan` 而非报错。Slice D 启动前需先核。
- **[F-V11-6, major(status), verified-doc] Slice D 静态档案对照 STOP 未跑**：seed-30 vs 7 份 Cerebro 静态档案、全市场敏感性、真 Rust pyd 身份采集均未做（`docs/backtest/reviews/slice-d-version11-seed30-universe-2026-09-21.md:16-53`）。定位"框架移植先行、非已验证多头"是诚实的，但**业务上 v11 的信号有效性至今无任何对照证据**。

### 2.3 strategy 8.1/8.2/8.3

- **[F-8-3, minor, verified] 当日唯一无治理文档的新注册书**：8.1/8.2/8.3 无 plan、无 handoff、无评审链（b2b406e 本地分支直 merge，无 PR 号），与同批 strategy12/version11 的完整 plan→fan-out→人裁链形成反差。冻结语义唯一锚是 `tests/test_strategy8_milestones.py`；治理依据只有 AGENTS.md"已落地的 8.1–8.6 不回溯合并"和 `research-backtest-entry.md:85`"冻结里程碑不当现行宿主书"。
- **[F-8-2, minor, verified] 8.1/8.2 静默继承引擎默认 `reserve_limit_up=False`**（apply 只传三键，`csv_strategy_books.py:729-733,758-762`；setdefault 在 `:131-157`）——base 8 是 `reserve_limit_up=True`。属冻结历史包的有意口径，但 HELP_LOCK 未写涨停处理，对比回测时易误读为与 base 8 同涨停语义。另 8.1 sizing 落 dataclass 默认 `daily_quota`（`csv_strategy_books.py:72,1339-1350`），8.2/8.3 显式 `per_name` —— 8.1 的资金口径与其余两书不同，对比时需注意。
- **[F-8-1, minor, verified] HELP_LOCK 与实现不符（两处）**：8.1 "须先摸到 2%×2"字面 4% vs 代码 SMALL_ARM=0.06（`strategy8_1_rules.py:26,101`，注释自认"用户口径 2% 的两倍按 6%"）；8.3 HELP 写 `[15%,50%)`/`[50%,100%)` 而代码是 `<=1.50`/`<=2.00`（`livermore_exit_rules.py:28-36` vs `strategy8_3_rules.py:89-93`），恰好 +50%/+100% 的等号点文档失真。
- **[F-8-4, minor, verified] 8.3 的 `build_sse_ma10_block_new` 是死代码**（引擎装载走 `strategy8_rules.load_sse_ma10_block_new`，`csv_minute_backtest.py:1213-1221`）。
- 里程碑书 HELP_LOCK 无测试 pin（`test_csv_strategy_books.py:176-184` 只 pin 了 6/8/9/10 字样），文档可静默漂移。
- 行为注：8.1 止盈 T+0 即可触发（`del n_days`）、8.2 反向（T+1 不评止盈，`strategy8_2_rules.py:83-84`）——两书 T+1 行为相反，均为冻结史实；引擎 `can_sell` 会挡住 T+0 实际成交，影响限于语义层。

---

## 3. 性能

### 3.1 实测数字（本次评审在 bt-ci 上复跑）

合成 bench（无湖，真实 `simulate()`，version8、30 日 × 16 码 × 240 分钟 × 10 pool 日）：

```
$ PYTHONDONTWRITEBYTECODE=1 ~/.venvs/bt-ci/bin/python scripts/research/bench_minute_simulate_hotpath.py
simulate total: 3.7716s  per_run=1257.19ms
  sell_scan        52.63%  calls=11280
  pool_buy          6.19%
  ledger_mark       0.87%
  orchestration    40.29%
  nested: day_slice 3.21%  prev_close_prep 8.14%
scan backend: python（reserve_state/take_profit 使 numba offload 条件不满足）
```

对照仓内存档（`docs/backtest/minute-simulate-profile-results-2026-09-15.md:19-32`，4090 上 1218.48ms/run、sell_scan 75.51%、orchestration 18.61%）：**sell scan 仍是第一大头，orchestration 余量在本机占比反而更高（40.29%）**——两轮数字共同指向"Python 逐 bar 扫描 + 编排开销"是全部成本，I/O 不在热路径。

fixture 回归：`pytest tests/test_csv_minute_backtest.py tests/test_strategy12_engine.py tests/test_strategy11_engine.py` → **109 passed in 1.22s**（数据面绿，可作 replay 基线）。

### 3.2 热点排序（profile-by-reading + 实测，均 verified）

1. **H1 逐分钟 Python 卖出扫描（52.6% 实测 / 75.5% 存档）**：`scan_held_day_python`（`csv_minute_backtest.py:317-405`）每 (code,day,lot) 循环 240 bar，每迭代 4 次 numpy 标量装箱 + `hit_limit_down/up`（`ashare_session.py:29-36`）+ `peak_gap_blocks`（`csv_ledger.py:112-114`）+ version8 每 bar 调 `take_profit` callable（`:375`）。numba kernel 存在但 offload 条件（`:447-457`）在真实 book 下全不满足。
2. **H2 orchestration 余量（40.3% 实测）**：`_slice_day` dict+iloc（`:548-557`）、`mapped_prev_close` 两级 dict（`exdiv_map.py:77-92`）、`t1_sellable` 的 Timestamp `.date()` 构造（`:775,807`）、函数闭包调用。
3. **H3 prev_close_prep（8.14%，重复劳动）**：`_previous_rows` = `df.loc[df.index < day]` 全表布尔 mask（`csv_minute_backtest.py:560-562,739`），且 chase/pool/step_add/buyback 多处各自重调、`prev_rows["close"].tolist()` 每 lot 重建（`:820-822,930`）。
4. **H4 买侧 quote 布尔 mask**：`_buy_px`/`_chase_quotes`/`_open_quote_for`/`_volume_bucket_for` 每日每候选 `day_df.loc[day_df["hm"]==X]` 扫 240 行（`:565-592,855-864`）。
5. **H5 涨跌停价 Decimal 热构造**：`limit_prices` 每调用 2 次 Decimal 乘法+quantize（`market_layer.py:73-84`），sell 准备/pool/chase/step_add/buyback/EOD 六个调用点（部分已按 (code,day) 缓存，chase/pool 仍按候选重复）。
6. **H6 v12 专属：run_minute_day 的 itertuples 物化 + 单元素 numpy scan**（`strategy12_engine.py:232,254-263`）：v12 分钟路径比一般 book 多一层 per-bar Python 开销，240 bar × 持仓 code 各一次完整 scan 调用。

### 3.3 优化建议（按期望收益排序；均不要求 byte-identical，但须 replay 对账验证正确性）

| # | 建议 | 预期收益 | 风险 | 验证方式 |
|---|---|---|---|---|
| O1 | 编译化 sell scan：把 `take_profit`/`reserve_step_minute` 降级为数值参数集合并扩 numba kernel 分支，或逐 book 写专门 `@njit` | 最大头 52–75% 的 10–100× | 中（卖因分支多：force/close_clear/reserve 交错） | `tests/test_csv_minute_backtest.py` fixture + 合成 replay 字节对账 |
| O2 | prev_close/closes 历史按 (code,day) 预计算缓存，sell/chase/pool/step_add/buyback 五处共享 | ~8% + 消重复 | 低 | 同 fixture replay 对账 `st.trades` |
| O3 | 买侧 quote 向量化：`BUY_HM/CHASE_HM` 行定位改 `build_day_spans` 同款预索引（hm→row dict 或 searchsorted） | pool buy 6% → ~0 | 低 | fixture replay |
| O4 | v12 分钟路径重构：`run_minute_day` 的 exit 评估改为向量化预扫（MA 触发bar集合先算出来，只对触发 bar 走 Python 分支），去掉逐 bar 单元素 numpy scan | v12 分钟路径数倍 | 中（latch/re-arm 同日语义须保持，有 pin 测试 `test_minute_cycle_rearms_same_day_and_new_buys_remain_t1_locked` 兜底） | 现有 strategy12 测试 + replay |
| O5 | `limit_prices` 去 Decimal 热构造：缓存 `code→band`，或 HALF_UP 到分改整数分算术 | 中小 | **高敏感性**——成交正确性锁定 Decimal 档位价（`engine-ashare-correctness.md`），改动必须全量 replay 对账 | 黄金 NAV/trades 对账 |
| O6 | 分钟缓存读 `read_minute_cache` 的 per-row-group `groupby("symbol")`+concat（`ashare_bars.py:554-557`）改分桶累积单次 concat | 加载一次性成本，取决于窗口 | 低 | cache roundtrip 测试已存在 |

joint-return 回放域的 perf 弧（#182–#192，789s→237.6s，−69.9%，byte-identical）已收官且文档明确"不再开新刀"（`docs/backtest/handoff-joint-return-modeb-perf-20260924.md:79`），不建议主动再动。

---

## 4. 实现期决策点全清单

格式：大白话问题 → 当时选择 → 对回测结果的具体影响 → 行业惯例/业务评价 → 建议。证据来自 PR 评论档案（`/home/box/agent-data/bt-minute-review-2026-09-25/context/pr-*.md`）、handoff §0、plan P 项、merge-consensus 及 git log。

### 4.1 引擎级人裁（industry-align P/δ 系列）

1. **P1=A 收盘集合竞价不建模**（2026-09-20，`engine-ashare-correctness.md:70-92`）。大白话：14:57–15:00 深市真实是集合竞价、不一定能成交，回测要不要跳过这三分钟？选了 A：当作普通连续竞价，只改文档不动撮合。影响：尾盘 trail/force/close_clear 可按 15:00 close 成交，尾盘可成交性略高估。评价：与"研究相对比较"目标匹配；QMT 真栈验收时才需要补。**建议保留**；若湖无 15:00 bar 则影响为零，值得跑一次探针确认（inferred）。
2. **P2=B trades 增加 `session_phase`/`price_rule` 两列**。大白话：成交记录要不要标注"这是在哪个时段、按什么价规成交的"？选了 B：加两列纯标签，不影响价量费。影响：产物可审计性提升，零行为变化。**建议保留**。
3. **P3=A 费用/除权/ST/volume cap 不进 fill-clock 船**。大白话：一堆现实摩擦要不要趁引擎重构一起改？选了 A：费率行为冻结，各项各自开 plan。影响：默认费用口径保持代理（见 F-E4）。**建议保留**（逐项 δ 已随后落地）。
4. **P4=A touch 资格与 NAV mark 独立两轴**（2026-09-20）。大白话：15:00 能不能触价、和 15:00 用什么价记净值，是两件事还是一件事？选了 A：两轴独立裁决，均 as-built。影响：NAV 恒用日线 close，停牌用 prior close 不冒充。**建议保留**，与行业 EOD mark 惯例一致。
5. **δ1=A/A/A 费用冻结**：只写合同文档+接线测试，不改生产扣费。影响：默认双边 10bp、无印花/过户/min5 的代理口径延续。评价：相对比较研究可用、绝对收益不可比，文档已明示。**建议保留**；如未来要绝对收益口径，把 QLIB_PORTANA 或新增"印花+过户"schedule 提为显式 flag，而非改默认。
6. **δ4=C/B/A v7 limits=None fail-closed**：涨跌停价算不出来时是猜 10% 还是报错？选了 C：显式拒绝。影响：坏数据不会静默进成交。**建议保留**（fail-closed 与本仓数据盘规一致）。
7. **δ5=C/A/A/A volume participation cap opt-in 落地**：要不要模拟"成交量参与率上限"？选了 C：opt-in，默认 None 即基线不变；未完成分钟桶不可用（`bucket<=at`）。影响：cap 开启时成交变保守、可 partial。评价：`bucket<=at` 严格口径是正确选择（B 方案"同分钟近似"被否）；但与 v11 的 09:30 契约叠加产生结构性零成交（F-V11-1）。**建议保留 cap 本体，修组合提示**。
8. **δ6=C/A/B/B/A 除权经济默认 off**：要不要把现金分红/送转股算进账？选了 C：落地但默认关、显式事件供给才启用。影响：默认回测跨除权持有 pnl 有结构性失真（已声明）；开启后现金/送转/NAV 口径按合同。评价：默认 off 对"名单×卖出规则"研究可接受。**建议保留**。
9. **minute-sensitivity B = Human GO B**（#136 裁决、#137 引用，2026-09-20）。大白话：要不要改回测的成交时钟/费率默认？先不改动，只做只读敏感性实验。影响：产出了 batch1–4 证据链（同价比例、NAV 对照）而生产零风险。**建议保留该工作模式**。
10. **minute-sensitivity defaults 卡 = Human GO A**（git log `b0cb32f` "record Human GO A on minute-sensitivity defaults card"，2026-09-20；注意 #141 卡片档案内勾选项未回填，裁决记录在后续 docs commit）。大白话：敏感性做完了，动不动生产默认？选了 A：维持默认不动。影响：fill clock/费率默认保持 as-built。**建议保留**，并把 #141 卡片的勾选项回填（档案 hygiene）。

### 4.2 策略12 人裁（plan P 项 + handoff §0 binding + PR #151 评论）

| 决策 | 大白话 | 选择 | 影响 | 评价/建议 |
|---|---|---|---|---|
| P1 编号 | 新书叫几号？ | version12（不占 11） | 11 留给 ma_chip | 保留 |
| P2 评估口径 | 分钟书按什么节奏评估卖出？ | 逐分钟口径；日线收盘评估次日开盘成交 | 分钟书对跌破反应更快；日线书有一天延迟 | 与两引擎既有契约一致；保留 |
| P3 减仓 50% 语义 | "减半"减的是哪部分、先卖哪个 lot？ | t1_sellable×50% floor100；is_step 先、lot0 最后 | 保住底仓锚、先吐加仓 | 符合"减仓不清仓"业务意图；保留 |
| P4 买回语义 | 收复均线后买回多少？ | 通道记忆全额 floor100、无限循环、skip_cash | 买回忠实于卖出记忆 | 被 residual=2 覆盖补充；保留 |
| P5 止损/减仓共存 | 止损和减仓同日都触发怎么办？ | 先止损；双记忆并存各清各；同日先卖后买 | STOP 优先级明确 | 保留（但见 F-S12-1 锚问题） |
| P6 单日买向闸 | 要不要限制一天买几笔？ | 不加闸，HELP_LOCK 声明 5+ 笔 | 买侧不限流 | 声明到位即可；保留 |
| P7/P8 上证闸/池来源 | 要不要大盘闸、名单从哪来？ | 无闸；默认 `stock_pool/`（8 先例） | 与 v8 可比 | 保留 |
| P9 买回四锁 | 买回量怎么定、除权怎么办？ | ①shares_override ②扣 locked bonus ③送转 k 缩放 floor100 ④上限=记忆、新买清零 | 买回量保守且不越记忆 | 保留 |
| P10 价域（#151 follow-up LOCKED / #158 落地） | 信号用什么复权价、成交用什么价？ | 日线信号 front；分钟成交默认 none、front 可选 fail-closed；禁静默双重调整 | 混域时 E-R6 remap 显式关闭，避免双重调整 | 符合"消费侧 fail-closed"仓规；保留 |
| **P11 → latch=A**（binding，PR #151 评论 06:40:10Z） | 同一天减仓→买回→又跌破 MA5，还能不能再减？ | **仅周期锁**：reclaim 即 re-arm、同日可再减、无每日锁（覆盖 plan P11"每日一次"措辞） | 同日可多次减仓/买回循环，交易笔数与费用上升；更贴近"均线书"直觉 | 测试已 pin 死循环语义；保留 |
| **residual=2**（binding，PR #151 评论 06:50:47Z） | 减仓记忆剩个不足一手的零头，买回时抹掉还是留着？ | **保留 <100 残差合并下轮**；memory<100 无买入时合格 reclaim 不清残差仍 re-arm；禁等归零 | 残差不丢，长期股数守恒更好 | 符合 S1 守恒精神；保留 |
| P12 wiring 四键 | 接引擎时哪些钩子开/关？ | reserve/defer=False、prefixes=()、书侧自管止损、peak_gap_min=0 | v12 不走通用涨停保留逻辑 | 保留 |
| P13 lot0 保底 | 减仓要不要留底仓？ | 减仓保留 lot0≥100（#170 clamp 也保锚） | 锚不丢、台阶可续 | **保留；建议扩展到 STOP**（F-S12-1） |
| S1 部分卖守恒（consensus） | 部分卖出会不会静默丢股？ | 扣股移出条件分支、空 lot 才删 | 股数守恒 | 已修已 pin；保留 |
| Slice D 开工口径（人裁默认，PR #151 07:16:41Z） | 验收怎么跑？ | 4090 五本对比 front、**数字默认不入库、不主张收益/parity** | 五本 NAV 仅作誊录 | 保留诚实口径；F-S12-6 跟踪 |
| 分钟契约 = 选项 2（PR #151 07:28:29Z） | 分钟湖只有 none、原契约硬要 front，怎么办？ | **改契约允许 `--dividend-type none`**（日频仍 front） | 分钟五本得以在现湖上跑 | 务实且防线（禁双重调整）已落地；保留 |

### 4.3 version11 人裁（plan P0–P7 / handoff §0 / PR #152 评论）

| 决策 | 大白话 | 选择 | 影响 | 评价/建议 |
|---|---|---|---|---|
| P0 cyqk>0.70 语义 | 这个阈值信号算验证过的多头吗？ | a：框架移植先行，定位"非已验证多头" | HELP_LOCK 明示不宣称收益 | 诚实；保留；Slice D 是唯一补课路径（F-V11-6） |
| P1 成交时点 | 买入按日线收盘还是分钟开盘？ | a/b 双跑，分钟 09:30 为准；日线复用通用收盘 | 双引擎成交价不同是**契约而非 bug** | 保留；建议给日线侧加 price_rule pin（F-V11-4） |
| P2 卖出 | 卖出怎么走？ | 日线 pending_exit 次日开；分钟 09:30 首根卖、跌停 defer | 卖出统一在次日开盘 | 保留；补卖侧缺 bar 计数器（F-V11-2） |
| P3 导出器形态 | 信号从 TR store 读还是现算？ | 独立导出器；cyqk Rust 现算禁读 store | 无隐藏算法分叉 | 保留 |
| P4 抽样 | 先小样还是全市场？ | seed-30 parity 主交付 + 全市场模式 | 交付顺序明确 | 保留 |
| **契约日 D/T**（PR #152 06:42:49Z） | "信号日 D"和"买入日 T"怎么算、过期从哪天起？ | D=原信号日；T=严格晚于 D 首根有 bar 交易日；D→T ≤4 自然日；stale 从 D 起算；≤T−1 计算写池日 T | 停牌股不.instant 成交、信号无未来函数 | 严格 PIT，优于"on/after D"；保留 |
| **周线 = A prefix-equivalent**（同上评论） | 周线均线按每个信号日截断重算，还是整段历史一次算完？ | A：截断重算；ma_infra 显式 opt-in，默认行为不变 | 消除"导出窗口改变历史信号"的隐性前视 | 正确且克制（不动默认）；保留 |
| **volume=A 严格可用性**（PR #152 06:56:27Z 人裁默认 + 06:57:18Z 用户显式确认） | 09:30 当分钟量还没统计完，按开盘价买要不要等量桶完成？ | A：严格——开盘桶未完成则买 skip/卖 defer；否决 B"同分钟近似"例外 | cap 开启时 v11 分钟**结构性零成交**（F-V11-1）；cap 关闭时无影响 | 口径本身正确；建议在 CLI 层对 v11+cap 组合显式提示 |
| R9/V15 禁追买 | 涨停买不进要不要排队追？ | `apply()` 显式 `limit_up_chase=False` + chase 空队列 pin | 涨停 skip 消耗信号不追 | 与"禁追买"业务一致；保留 |
| V5/V6/V7 cyqk 失败契约 / asof 股本 | 数据坏了怎么办？ | 窗 NaN→日 skip；ValueError→码 skip；股本逐日 backward asof 禁快照 | fail-closed，无静默前视 | 保留；注意 F-V11-5 代码形态匹配 |
| V9 板块/ST | 哪些票进 universe？ | 沪60/深000-003/创300-301，排 688/689/BJ；universe 模式滤 ST 缺名称即 raise | 20%/30% 档票不进门 | 严于措辞（连 689 也排），可接受；保留 |
| V11 卖出日不重入 | 当天卖了还能买回吗？ | sold-today 集合买侧过滤 | 防同日反复 | 保留 |
| 池篱笆 | 名单能默认 `stock_pool/` 吗？ | 必须显式 `--pool-dir`，拒绝默认池 | 防止拿错名单 | 与 9/10 一致；保留 |
| **Slice D 显式 STOP**（PR #152 07:28:14Z） | 没有静态档案和真 Rust pyd，验收怎么办？ | 显式跳过 Slice D，诚实 STOP，不主张收益/parity | v11 有效性至今无对照证据 | 诚实；业务风险敞口见 F-V11-6 |

### 4.4 fullstrat #156 决策（研究回放域，非生产默认）

1. **H2 时钟覆盖**（PR #156 06:54:09Z 部分裁定）。大白话：研究回放里把成交价换成"下一根开盘价"时，尾盘 14:55 的信号当天根本没法成交——只换几个探针路径，还是全换并允许当天白跑？选了 H2：换所有 fill、严格同日到期、接受未成交乃至全现金 NAV、不静默保留 baseline 入场。影响：回放结果会出现 UNFILLED/全现金 NAV，这是**特性不是 bug**；它量化了生产 cheat-on-close 口径的乐观度。评价：与 P1=A 的生产默认互补（生产不动、研究量化），符合"敏感性先行"工作模式。**建议保留**。
2. **卖单过期=次日重评**（06:55:10Z 补齐）。大白话：当天没成交的卖单，是挂着等还是第二天重新按策略判断？选了次日重评（不保留出场意图）。影响：回放里卖出意图不过夜，避免"僵尸卖单"。**建议保留**。
3. **Q2 成交价重新定量**（07:10:20Z，supersede Q1 文档）。大白话：信号说"10 元买 1000 股"，实际成交 10.1 元、现金只够 900 股——按成交价重算手数，还是死抱 1000 股钱不够就整单拒？选了 Q2：按成交价重新定量。影响：回放成交率更高、更贴近真实下单行为；覆盖此前 Q1 合同表述（`3e17d75` 落文档）。**建议保留**。

### 4.5 ma_infra 人裁（#150 plan P1–P4，全按共识）

大白话：共享均线库怎么做、放哪？裁定：**八件 API / 纯 Python 标准库（不引 pandas）/ strategy4 的 `sma_asof` 删 def 改 re-export / 落 `backtest/research/ma_infra.py`**。影响：strategy4/11/12 与导出器共用同一套均线/布林/周线口径，ddof=1 布林锁定，pandas 差分 oracle 有测试 pin。评价：纯标准库保证了 data-free CI 可测；`weekly_sma_series` 默认保留全历史 backward（plan 明说的保留行为）、prefix-equivalent 为显式 opt-in —— 默认与 opt-in 的分层是正确的。**建议保留**。注：`sma_live`/`bb_asof`/`weekly_sma_asof` 三件目前无生产消费者（为 strategy12 P2-B 预留），属可接受的预留而非死代码滥用。

### 4.6 8.1/8.2/8.3 的治理事实

**无 plan、无 handoff、无评审、无 PR 评论人裁**（b2b406e 本地分支直 merge，commit message 仅自述"全量 1398 passed"）。开新版本号的批准未见显式记录——对照 AGENTS.md"开新版本须用户明确批准"，批准通道不可追溯。功能本身有 `test_strategy8_milestones.py` pin 住冻结语义。**建议：补一页 retro 说明（冻结源 commit、与 base 8 的差异点、涨停口径差异），并给三书 HELP_LOCK 加测试 pin。**

### 4.7 编码进默认/CLI 的选择（非评论人裁，但同样是决策）

- `--dividend-type` 分钟默认 `none`、v12 日线强制 `front`（`csv_minute_backtest.py:1049-1055`、`csv_daily_backtest.py:593-596`）——原始价成交 + front 信号，混域 remap 关闭。保留。
- 默认费用 `BILATERAL_10BP`、`--qlib-cost` opt-in（`ashare_fees.py:53-55`、`csv_minute_backtest.py:1346-1348`）。保留（见 δ1）。
- `--stop-fill` 默认 `touch`，`close` 仅 topk 两书允许（`csv_strategy_books.py:56-59`）；v11/v12 `--stop-pct` 直接拒绝。保留。
- 买/卖钟常量 `BUY_HM=895`（14:55）、`CHASE_HM=585`（09:45）、`CLOSE_CLEAR_HM=900`（`csv_minute_backtest.py:127-128`）——尾盘买+次日早盘追的书骨架。与 HELP_LOCK 一致；保留。
- `FORBIDDEN_DEFAULT_STOCK_POOL={9,10,11}`（`csv_strategy_books.py:55`）——信号型策略强制显式 `--pool-dir`。保留。
- v12 预热 `STRATEGY4_CALENDAR_SLACK_DAYS=22`（`csv_daily_backtest.py:621-625`）——MA10 需要的最小历史窗。保留。
- `--participation-rate` 默认 None（cap 关闭）——δ5 基线不变。保留；修 v11 组合提示。
- `--buy-state-file` 默认关、`topk_score_exit` 拒绝（#167 接线，AGENTS.md 现行条款）。保留。

---

## 5. Findings 汇总

| ID | 严重度 | 证据 | 位置 | 摘要 |
|---|---|---|---|---|
| F-E1 | major | verified（口径文档化+敏感性已量化） | `csv_minute_backtest.py:334-336,374-391,565-586` | 同 bar close 判定+同 close 成交（cheat-on-close），约 1 分钟同 bar 偏差；bar-START 标签无生产断言 |
| F-E2 | major | verified | `csv_minute_backtest.py:321-336` | 触价止损不看 bar 内 low，系统性偏乐观 |
| F-E3 | minor | verified（P1=A 人裁） | `ashare_fill_clock.py:12-27` | 14:57–15:00 按连续竞价成交，尾盘可成交性高估 |
| F-E4 | minor | verified（δ1 人裁） | `ashare_fees.py:17,53-55` | 默认双边 10bp、无印花/过户/min5；绝对收益不可比 |
| F-E5 | minor | verified | `csv_ledger.py:223-233` | 科创板 200 股起/1 股递增未建模；注册制前 5 日无涨跌幅未建模（后者 inferred） |
| F-E6 | minor | verified | `csv_ledger.py:281` + `csv_simulate_loop.py:351-354` | `daily_quota_used` vestigial，靠调用点恢复的脆弱契约 |
| F-E7 | minor | inferred | δ5 合同 `engine-ashare-correctness.md:250` | 部分减仓可多次卖零股，违背零股一次性申报 |
| F-E8 | minor | verified | `docs/backtest/engine-ashare-correctness.md` 内嵌锚点 | 文档 file:line 锚点相对 HEAD 漂移 |
| F-S12-1 | major | verified | `strategy12_rules.py:165-170` + `strategy12_engine.py:106-107` + `csv_ledger.py:285` | STOP 清空 lot0 而其它 lot 残留时 +20% 台阶永久停加 |
| F-S12-2 | minor | verified | `strategy12_engine.py:226-231` | 分钟侧缺当日 K 帧静默 continue 无计数 |
| F-S12-3 | minor | verified | `strategy12_rules.py:157-161` | scale_memory floor 0 不清 latch，0 股 latch 挡 MA5 再减 |
| F-S12-4 | minor | verified | `strategy12_engine.py:142,147` | `_normal_buys` 写死 allow_add/buy_gate，不读 hooks |
| F-S12-5 | minor | verified | `strategy12_engine.py:101-103,264-267` | 分钟跌停延期按 bar 计数，stats 跨引擎口径不一致 |
| F-S12-6 | minor | verified-doc | plan §7-D / handoff / grok nit 1 | Slice D 实湖五本对比未执行 |
| F-S12-7 | minor(perf) | verified | `strategy12_engine.py:232,254-263` | v12 分钟路径 itertuples 物化 + 逐 bar 单元素 numpy scan |
| F-V11-1 | major | verified | `csv_minute_backtest.py:947,792` + `ashare_volume_cap.py:55-59` | cap 开启时 v11 分钟结构性零成交（volume=A 直接后果），CLI 无提示 |
| F-V11-2 | minor | verified | `csv_minute_backtest.py:777-779` | pending 卖缺开盘 bar 静默 continue 无计数，与买侧不对称 |
| F-V11-3 | minor | verified | `strategy11_rules.py:104-106` | SMA5 短窗静默 HOLD |
| F-V11-4 | minor | verified | `csv_daily_backtest.py:486-493` | v11"日线契约收盘"复用引擎通用行为，无专属 pin，静默漂移风险 |
| F-V11-5 | minor | verified | `oskh_factors/bridge/turnover_resist.py:97` | 股本 asof 无 symbol 归一，形态不一致表现为大量 skip 而非报错 |
| F-V11-6 | major(status) | verified-doc | `docs/backtest/reviews/slice-d-version11-seed30-universe-2026-09-21.md:16-53` | Slice D 对照 STOP 未跑，v11 信号有效性无对照证据 |
| F-8-1 | minor | verified | `strategy8_1_rules.py:26,101`；`strategy8_3_rules.py:89-93` vs `livermore_exit_rules.py:28-36` | HELP_LOCK 与实现两处不符 |
| F-8-2 | minor | verified | `csv_strategy_books.py:729-733,758-762,131-157,72` | 8.1/8.2 静默继承 reserve_limit_up=False；8.1 sizing 落 daily_quota 默认，与 8.2/8.3 不同 |
| F-8-3 | minor | verified | commit `b2b406e` 无 PR；`tests/test_strategy8_milestones.py` | 8.1/8.2/8.3 无 plan/handoff/评审链，批准通道不可追溯 |
| F-8-4 | minor | verified | `strategy8_3_rules.py` vs `csv_minute_backtest.py:1213-1221` | 8.3 `build_sse_ma10_block_new` 死代码 |

（性能类观察见 §3.2 H1–H6 与建议 O1–O6，不单列 finding。）

## 6. Top-10（按重要性排序）

1. **F-S12-1（major）**：STOP 清空 lot0 且其它 lot 残留 → 该码 +20% 台阶永久停加。策略语义级分叉，P13 人裁未覆盖；建议 STOP 也保锚或 HELP_LOCK 显式声明+测试。
2. **F-V11-1（major）**：`--participation-rate` 下 v11 分钟结构性零成交。人裁后果本身正确，但 CLI 静默跑空会误导使用者；建议组合拒绝/警告。
3. **F-V11-6（major-status）**：v11 Slice D 对照未跑，"ma_chip 信号有效性"至今零证据。这是业务层面最大敞口，比任何代码 nit 都重要。
4. **F-E1（major，已缓解）**：cheat-on-close 同 bar 成交 + bar-START 标签无运行时断言。研究口径可接受，但建议在装载侧加标签探针断言（湖重建换标签即报错），把文档假设变成代码防线。
5. **F-E2（major，已声明）**：止损触价不看 low，系统性偏乐观。已在 HELP_LOCK 声明；若要做绝对收益口径，需补 bar 内触价模型或至少敏感性标注。
6. **F-S12-6 / Slice D 五本**：strategy12 实湖五本对比未执行（#165 仅誊录 NAV）。两本新策略都停在"框架验证"而非"信号验证"。
7. **F-8-3（minor-治理）**：8.1/8.2/8.3 无 plan/评审/可追溯批准。建议补 retro 文档 + HELP_LOCK pin，防止冻结口径再漂移（F-8-1/F-8-2 已是漂移实例）。
8. **F-S12-5（minor）**：分钟跌停延期按 bar 计数，stats 跨引擎口径差 ~240 倍。横向对比 run 的 defer 指标时会误读；建议按笔聚合计数或文档化。
9. **F-V11-2 / F-S12-2（minor）**：两处静默 `continue` 无计数器（卖侧缺开盘 bar、分钟缺当日 K 帧）。可观测性缺口，排障时无法区分"无信号"与"无数据"。
10. **H1+H6 / O1+O4（perf）**：sell scan 占 52–75% 且 numba offload 在真实 book 下永不生效；v12 分钟路径再叠加逐 bar 单元素 numpy scan。编译化 sell scan（O1）与 v12 路径向量化（O4）是收益最大的两刀，均有 fixture replay 可验证。

---

### 附：本次评审的验证手段

- 代码抽查复核：finding 中所有 major 与关键 minor 的 `file:line` 均由本评审在 worktree 直接 Read 核实（非转述）。
- 实测：`bench_minute_simulate_hotpath.py`（合成数据、真实 `simulate()`，无湖）per_run=1257.19ms；`pytest tests/test_csv_minute_backtest.py tests/test_strategy12_engine.py tests/test_strategy11_engine.py` → 109 passed in 1.22s（bt-ci，`-p no:cacheprovider`，`PYTHONDONTWRITEBYTECODE=1`）。
- 决策点取证：`/home/box/agent-data/bt-minute-review-2026-09-25/context/pr-*.md` 全量阅读 + git log 交叉（如 #141 defaults 卡的 Human GO A 裁决在 `b0cb32f`，卡片档案内勾选项未回填）。
