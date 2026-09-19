# Plan: industry-align P3 δ2 ex-div / lot-cost rescale contract (2026-09-19)

> **Status**: **v0.2 · docs-only plan / 待人裁**（host-parallel Codex adversarial r1 勘误已回填）。本 PR 仅提交本计划 + adv-r1 评审记录；未实施 Slice B 测试或 Slice C 验收，不代表 A→B→C 已交付。
> **Main ship / 单行范围**: 仅 #112 P3 **δ2**：细化已落地 E-R6 的除权事件、lot 参考价重标定与经济残留契约，规划未来 data-free pins；默认 **零生产行为变更**。
> **IMPLEMENTATION_BASE（本 worktree 分支起点，已用 `git rev-parse` 核对全 40 字符 SHA）**: `1ad010cca013afe8186f20275cbdcca71e500823`。
> **前序**: [δ1 fee plan v0.3.3](plan-industry-align-p3-fees-2026-09-19.md) / PR #121 已合；本基线即其 merge commit。δ1 人裁与研究费率 SSOT、冻结表继续有效。
> **Host intent lock**: P1（14:57）、P2（trades 列）、P4（touch↔mark）及 δ3/δ4/δ5 全部挂起。§5 五项仅为 δ2 后续人裁，推荐全 A，**尚未获得实施 GO**。
> **Adversarial r1 record**: [codex-adv-r1](../architecture/reviews/2026-09-19/plan-industry-align-p3-d2-exdiv-codex-adv-r1/) — host errata E-d2-01..09；lanes dissent-steelman / domain-safety / pattern-evidence（all rc=0）。

---

## 0) One-line scope

只把 E-R6 已有的参考价修正整理为可核对、可验收的 as-built 契约；不重做 E-R6，不把 shares / 现金红利 / NAV 经济残留宣称为已关闭。本 PR 不修改生产 Python、测试代码、既有 δ1 文档或费率合同，不运行回测或读取湖。

---

## 1) Why now（E-R6 已落地 vs 契约缺口）

[δ1 roadmap](plan-industry-align-p3-fees-2026-09-19.md) `:93-101` 已把 δ2 列为下一刀；其 `:134` 明确 E-R6 只覆盖参考价 rescale，经济残留仍 deferred。[next plan](plan-industry-align-next-2026-09-19.md) `:3`、`:77-82` 的 P1–P4=A/A/A/A 是保留延后，不是授权行为改造。

[engine-ashare-correctness.md](engine-ashare-correctness.md) `:95-100` 已落 E-R5 收窄与 E-R6。缺口在于：事件枚举与实际可缩放事件的区别、k 的方向、书/v7 缩放字段差异、“一次性”的调用顺序前提、连续域跳过的真实入口，以及已有测试证明到哪里，尚未在同一验收表中钉牢。δ2 补这张表，复用既有 E-R6 测试，不重开旧实现片或宿主 Slice D。

---

## 2) Verified as-built anchors（以 IMPLEMENTATION_BASE 的 file:line 为准）

**沿革短注（E-d2-09）**：原 E-R6 人裁范围以书侧 daily/minute 为主，当时明确不含 v7；当前基线中 v7 的 `_rescale_position` 与调用由后续 shared-session 改造引入（早于本 IMPLEMENTATION_BASE），并已写入 `engine-ashare-correctness.md`。本 plan 按**现状**纳入 v7 字段分叉与 pins，保留旧 plan 的历史人裁记录，不重审或回滚既有接线，也不把“原 E-R6 人裁”外推为当时已覆盖全部后续引擎。

### 2.1 事件、k 与参考价接线

| 合同项 | 已核对行为 | 代码锚点 |
|---|---|---|
| 常量及因子读窗 | `NOISE_EPS=5e-3`、`FALLBACK_JUMP_EPS=1e-2`；向前读 10 个自然日 warmup，不保证无限追溯 | `backtest/research/exdiv_map.py:28-30`、`:51-53`、`:233-239` |
| 有效因子与 LAG | 非正数、NaN、Inf 不进入 cleaned series；按日期排序后取前一条有效因子行，不是日历 D−1 | `backtest/research/exdiv_map.py:65-74`、`:191-217`、`:294-305` |
| 事件主源与兜底 | ex 行存在时先过噪声带；无 ex 行仅因子跳变严格 `>1e-2` 才进入 map | `backtest/research/exdiv_map.py:172-188`、`:299-316` |
| k 方向 | `k = prev_cum / cum`；不是 `cum / prev_cum`，不直接拿分红字段作 k | `backtest/research/exdiv_map.py:305-314` |
| 当日查表 | `k_for` / `mapped_prev_close` 按 code + 当日 `YYYYMMDD` 精确查；None/空 map/无键保留原值 | `backtest/research/exdiv_map.py:77-108` |
| 书 lot 重标定 | `rescale_position` 只乘 `cost`、`peak`，不改 shares 或其它 lot 元数据 | `backtest/research/csv_ledger.py:68-79`、`:147-156` |
| 日线持仓 | 有当日 bar 和先前 closes 后，缩放已有 lots → 映射昨收 → 计算档位 → 卖出逻辑 | `backtest/research/csv_daily_backtest.py:300-327`；前置 helper `backtest/research/csv_common.py:22-45` |
| 分钟持仓 | 有日线、当日分钟切片及昨收后，缩放 → 映射档位 → `scan_held_day`；不在扫描与 peak 回写间缩放 | `backtest/research/csv_minute_backtest.py:586-636` |
| 共享 chase / pool / 台阶加仓 | 原始昨收在各档位计算点映射；不修改 chase 判定算法或额度 | `backtest/research/csv_simulate_loop.py:150-157`、`:257-263`、`:341-348` |
| session 层 | 最近早于 today 的 close 经 `mapped_prev_close` 后才送 `session_limit_prices`；T+1 仍按买日早于会话日 | `backtest/research/ashare_session.py:39-70` |
| v7 独立仓位机 | `_rescale_position` 已缩放 `entry_A` / `avg_cost` / `peak` / 非空 `add1_A1` / 各 `Lot.price`；不改 `Lot.shares`、`buy_date`、`kind` | `backtest/research/csv_minute_backtest_v7.py:60-81`、`:187-196` |
| v7 调用顺序 | 有当日 records 才缩放既有 position；随后 session 昨收/档位，再进入逐分钟扫描 | `backtest/research/csv_minute_backtest_v7.py:316-340` |

### 2.2 事件与一次性缩放的精确定义

令 `F_prev` 为 warmup 窗内 cleaned series 的前一有效行，`F_D` 为当前有效行，`j = abs(F_D − F_prev) / F_prev`。候选事件为 **`ex_date_index` ∪ `j > 0.01`**，实际输出还受有效因子/LAG 与噪声门约束：

| ex 当日行 | j | 默认输出 |
|---|---|---|
| 有 | `j <= 0.005` | 不写入 k；有事件不等于有修正 |
| 有 | `j > 0.005` | 写入有效 `k=F_prev/F_D` |
| 无 | `j <= 0.01` | 不写入 k；包括 0.5%–1% 区间 |
| 无 | `j > 0.01` | 因子跳变兜底写入有效 k |

因子上涨或下跌均用绝对跳变，k 可小于或大于 1。“≤0.5%”说的是 **因子行相对跳变 j**，不是 `abs(1−k)`；阈值比较保持现有 float 算法，无新增容差或 Decimal 化。未来等号测试可用 `200→201`（0.5%）与 `100→101`（1%）等输入钉住现有边界，另测阈值两侧。

“一次性”是**正常逐日循环中，在事件日扫描前对当时已持有 lot 进行一次缩放**，不是 helper 幂等性：`rescale_position(pos,k)` 没有已处理日期标记，重复调用会重复相乘。书路径当日新买 lot 在该 pass 后建立，v7 新开/加仓在逐分钟循环内建立，不再回头乘当日 k；跨多个可处理事件累计 `k1×k2`。不新增去重状态机。

缺 bar 的分支发生在缩放前，map 又只查当日键；**没有通用的跨停牌累计补缩放队列**。已有复牌测试把 k 直接放在复牌日（`tests/test_exdiv_refprice_engines.py:313-337`），不能据此宣称“任意停牌日事件都会自动递延至复牌”。δ2 只记录并规划 pins，不修改 loader、事件落日或复牌补偿逻辑。

有效因子约束来自 loader；直接给 `simulate(..., exdiv=...)` 注入任意 map 不是同样强度的输入校验（`k_for` / `mapped_prev_close` 仅排除非正数/NaN）。未来契约夹具使用有效有限 k，不借本刀添加数据清洗策略。

**因子恢复日与行情域错配（E-d2-01，as-built 残留）**：有效因子前行与昨收前行不是同一时间锚点。若除权日因子缺失/无效被 loader 跳过、下一日因子恢复，loader 可将有限 k 写到恢复日；此时昨收与除权日新买 lot 可能已在新价格域，却再乘一次 k。这与“停牌日键不回放”不同——行情可以连续、k 有限有效，错域仍可发生。分别验证因子 LAG 与手工同日 map 的模拟接线，不能关闭此残留。“已映射到 D 域”仅在**事件落日与行情域一致、且作用于事件日已持有 lot / 对应昨收**的前提下成立；未来 B1–B4 须规划经真实 `load_exdiv_rates` 输出再交给公开模拟器的跨日合成链（观察 map 日期、旧/新 lot cost、昨收档位、恢复前真实 SELL），按现状 pin 残留，修复另案。

**决策时刻可得性 vs 日期顺序（E-d2-02，未关闭面）**：日期 LAG / “不读取 D 之后的因子行”成立，**不等于**证明 `F_D` 在开盘/扫描前对决策者可得，也不等于历史因子版本与当时一致。仓内因子构造以当日观测比值等为依据，loader 无 as-of/版本过滤。δ2 将后者标为**未证 / 历史观测近似**，不写入“未来函数已排除”。合成前缀一致性 pin（截断到 D vs 追加 D 后数据）只能约束 loader 日期语义，不能证明原始数据 PIT；关闭后者须另案取得可得时间/版本证据。该项属于 δ2 因子输入时间语义，**不能**仅用 δ3“ST PIT 已挂起”代替说明。

### 2.3 价格域与 I/O 边界（不把入口局部规则写成全局保证）

| 路径 | As-built 边界 | 锚点 |
|---|---|---|
| daily `run()` | `use_qlib_bins` 或 `dividend_type != none` 时 `exdiv=None`；front/back/**`qlib_day`** 连续域跳过 E-R6；lake none 才加载 map。此处“qlib”特指日线源 `qlib_day`（仓内约定后复权 dump），**不是**任意带 qlib 名的源 | `backtest/research/csv_daily_backtest.py:583-588`、`:618`；路由 `backtest/research/ashare_bars.py` / `qlib_bin_daily.py` |
| book minute `run()` | 支持 daily/minute source 选择，但当前仍直接加载 exdiv，**无 daily 那个连续域跳过分支** | `backtest/research/csv_minute_backtest.py:841-861`、`:882-883`、`:914` |
| v7 CLI | source 选择后仍调用 `load_limit_context`，该 helper 无 source 参数；**不具有全入口连续域自动豁免保证** | `backtest/research/csv_minute_backtest_v7.py:557-571`、`:583-584`；`backtest/research/ashare_session.py:88-100` |
| 内存模拟 | daily/minute/v7 的 `exdiv=None` 默认为不修正；simulate 本身不识别 bars 的复权域，调用方承担域与 map 一致性 | `backtest/research/csv_daily_backtest.py:226`；`backtest/research/csv_minute_backtest.py:528`；`backtest/research/csv_minute_backtest_v7.py:280` |
| 源组合域约定 | `qlib_day` 与 `qlib_1min` **不是同一价格域约定**（日线 dump 后复权 vs 分钟 dump 来自 none 湖的仓内声明）；读取器不做域转换/认证。`minute=qlib_1min,daily=lake` 按约定仍可为 none/none，保留 E-R6 不是“连续域遗漏跳过”；`daily=qlib_day` 是另一类组合，不能用同一句“qlib”概括 | `qlib_bin_daily.py` / `qlib_bin_1min.py` 声明与读取；minute/v7 分源参数见上表锚点 |

P3δ2.5 的 A 仅保持上表：保留 daily 已有的连续域跳过（`qlib_day`/front/back），不把它补接到 minute/v7，不声称后两者已关闭混域风险，也不因看到任意 qlib 源就统一关闭 map。`--qlib-cost` 是 δ1 费率选项，不能用它判定价格域或代替 `use_qlib_bins`。读取器不认证真实 dump 域；B6 接线 pins 只记录现状传参，不宣称所有组合域一致。

`exdiv_map.py:246-253` 先调用路径 resolver；该阶段报错不在后续读文件 try 内。**路径已解析后**，缺/不可读 adj 文件会警告一次并返回空 map（`:258-272`）；缺/不可读 ex index 则降为 factor-jump fallback（`:274-287`）。这些是现存局部行为，不得扩大成“没配置根路径也静默无数据”，不新增盘符探测/空表 fallback。本 PR 不触碰真实数据；未来只用显式 tmp_path 或 I/O stub。

`exdiv_skipped_no_factor` 也是现存诊断计数，不是完整事件审计：例如 `len(points)<2` 在 `:290-291` 提前退出，不能声称所有缺 LAG 情况均计数。噪声抑制有意不计 skipped。δ2 不顺手修计数。

### 2.4 E-R6 已关闭什么 / δ2 仍要钉什么 / 什么仍 deferred

| 面 | E-R6 as-built 状态 | δ2 交付边界 |
|---|---|---|
| 触发参考错域 | 在事件落日与行情域一致时，已对可处理事件缩放**当时已持有**参考价，并把对应 prev_close 映射到事件日落价域档位；既有假止损/档位 vectors 已存在。**不含** E-d2-01 因子恢复日错配残留 | 钉清事件门、k 方向、字段集合、调用顺序、可处理前提及错配残留 pin；不重写算法、不本刀修 loader |
| 成交价与成交政策 | 仍走已有 open/trigger/close 分支，不把整条行情复权 | 相对本基线零变更；不是声称 E-R6 相对修正前永远不影响成交结果 |
| 股数与现金红利 | **送转不增股、分红不入账**；book `_sell` 仍按 shares×px 减佣金记现金，v7 同样按原股数成交 | 保持 deferred；只做“未进行经济补偿”的未来契约 pin |
| NAV 与 trades 推导收益 | none 路径仍按原始价×原股数估值/成交，含 **(1−k) 结构性失真**；历史假止损已实现亏损不回收 | 不宣称经济守恒/总回报正确，不新增收益修正或 P2 输出列 |
| 噪声 / v4 SMA | ≤0.5% 不修正；v4 原始 closes 序列不换域 | 保留 E-R5/E-R6 残留与既有重开条件；本刀不触发宿主探针/回测 |

现金与估值证据：`backtest/research/csv_ledger.py:218-248`、`:261-276`；`backtest/research/csv_simulate_loop.py:381-420`；v7 `:205-222`、`:226-252`、`:416-418`。书 mark 使用当前/最近有 K 的 close，无当前/历史 bar 才用 lot cost fallback；v7 使用 last_prices（无值才 avg_cost）。不把局部 fallback 描述成全局按 cost 估值。

**未来数值 oracle（声明现状，不修经济残留）**：隔离其他交易和费用，存量 100 股、cost=10、peak=12、现金=2000、k=0.5。重标定后 cost=5、peak=6，仍 100 股、现金 2000；若 raw close 从 10 变 5，权益从 3000 变 2500，而非经济补偿后的守恒值。这一特例的差额为 `100×10×(1−k)=500`，不能把 (1−k) 当成所有组合收益误差的固定百分比。

### 2.5 已有相关 tests 与证据限度（只读盘点，未运行）

| 文件 / 锚点 | 已有覆盖 | δ2 仍需钉点 |
|---|---|---|
| `tests/test_exdiv_map.py:32`、`:56`、`:77`、`:97`、`:117`、`:140`、`:182`、`:203` | 主事件、无事件大跳变、噪声、无事件 0.8%、NaN、缺 adj、warmup、昨收 helper | 两阈值等号/两侧；0.8% 有/无事件对照；k>1 与有效前行；缺 ex fallback |
| `tests/test_exdiv_refprice_engines.py:86`、`:95`、`:148`、`:206`、`:249`、`:265`、`:286`、`:313`、`:340`、`:358`、`:374` | cost/peak、假止损、D 域档位/触价、新买不双缩、chase/pool、复牌日键、空 map、raw NAV、分钟接线 | 多 lot 全字段保留、多事件复合、分钟/v7 一次性、精确现金/原股数残留、缺 bar 当日键不回放 |
| `tests/test_ashare_session.py:21` | session 昨收映射；board/ST 档位；既有向量算出 mapped=9.5 却仍可能把 raw 送入后续档位 | mapped prev_close **实际返回值**送入真实档位函数的完整数值链；须含 Decimal 半分边界 `3.30×0.5→1.65→(1.82,1.49)`（E-d2-04）；保留 None 行为 |
| `tests/test_csv_minute_backtest_v7.py:238`、`:295` | 官方昨收映射与 trial stop 的公开 `simulate_v7` 路径。**证据限度（E-d2-06）**：`:295` 夹具同日分钟买价与日收不一致（如 100 vs 50），属人为隔离的止损布线向量，不能当同域“参考价—档位—成交”oracle | 公开可达字段缩放清单、多 lot、新买/加仓不重乘、现金与股数不动；自洽 held 夹具分断言缩放/档位/成交；非空 `add1_A1` 仅 helper 兼容分支（E-d2-03），禁写“自然加仓已赋值” |
| `tests/test_csv_daily_backtest.py:126`、`:153` | loader 的 front/back 路径 | 不等于 daily `run()` 跳过 E-R6 的接线证明；需隔离 I/O 的入口 pin |
| `tests/test_ashare_fees.py`、`tests/test_ashare_fee_wiring.py`、`tests/test_ashare_simulate_import_fence.py` | δ1 费率与热路径边界回归 | 继续保留，不能代替除权契约接线证据 |
| `tests/test_exdiv_hold_hits.py`、`tests/test_unified_exit_modeb_exdiv.py` | NP2 命中探针 / Mode B 自有经济模型 | 只作相关库存；不纳入 δ2 实施面，不拿 Mode B fractional shares 证明书/v7 经济残留已修复 |

---

## 3) Delta roadmap（承接 δ1 同表，只选 δ2）

| Delta ship | 范围 | 本 PR 状态 |
|---|---|---|
| δ1 | 研究费率、印花税边界与费率接线合同 | **done**：PR #121 / v0.3.3；费率行为与冻结表不回退 |
| **δ2** | 除权 / lot-cost rescale as-built 契约细化 | **本刀，仅 docs-only plan**；A→B→C 为未来实施 |
| δ3 | ST PIT（书 as-of vs v7 窗末名） | **parked** |
| δ4 | v7 `limits=None` fail-open 政策变化 | **parked** |
| δ5 | 成交量 participation cap | **parked** |

P1/P2/P4 不并入此表任何 δ2 切片；旧 P3 经济行为调整也未因本计划获授权。

---

## 4) F-R* hard locks（δ2 局部编号；继承 δ1 边界）

| ID | 硬锁 |
|---|---|
| **F-R1** | 本 PR **只写本 plan + 本刀 adv-r1 评审目录**；禁止生产 Python、测试、配置/依赖/CI 修改。未来人裁 A 才允许 §7 列出的 docs + data-free tests；生产仍零 diff。 |
| **F-R2** | 不 redo E-R6 核心行为：保持事件门、k 方向、阈值和调用时点；不增加幂等标记、跨停牌补偿、校验/计数修复。 |
| **F-R3** | 不改成交价/选价规则、reason、shares、现金入账、佣金、NAV 算法、T+1 或 chase 判定；重标定仅保留 §2 的现存参考字段。 |
| **F-R4** | shares/现金红利/(1−k) 残留继续 deferred；不以“参考价修正”冒充经济守恒，也不添加分红/送转账本。 |
| **F-R5** | daily 连续域跳过照旧；minute/v7 入口差异如实记录，不补新接线、不扩大已修复声明。 |
| **F-R6** | δ1 研究费率 SSOT 不回退：`BILATERAL_10BP` 默认、日线 opt-in qlib-cost、v7 显式 schedule、每调用收费粒度均不变；commission-only，不新增印花行、不引入 live `trade_fee_policy`。 |
| **F-R7** | P1/P2/P4 全挂起；不改 14:57、trades schema 或 touch↔mark。δ3/δ4/δ5 及 v4 SMA 换域亦不做。 |
| **F-R8** | 不跑 CLI/宿主回测、不读湖、不做下载/merge/NP2 实测。未来 B 仅内存 `simulate` / `simulate_v7`、临时合成 parquet 或完全 stub 的入口接线测。 |
| **F-R9** | 固定本分支起点全 SHA；不拿后续 origin/master tip 或推断 merge-base 替换。§8 数组必须与 §9 冻结表逐项一致，且是 δ1 冻结表的超集。 |
| **F-R10** | 7 不进 BOOKS；不混入 LEBS/live、Cerebro、qlib PortAna/Exchange 或 Mode A/B 新设计。既有 import fence 固定清单不扩成 research 全目录扫描。 |
| **F-R11** | 发现需要生产行为修改时，记录差异并另开人裁/计划；不得用测试倒逼本 docs PR 改生产。B/C 通过前不得写“δ2 已验收/已 ship”。 |

---

## 5) P* human cuts（仅 δ2，全部待裁；默认推荐 A/A/A/A/A）

这里 **A = 保持 as-built，本刀只契约化 + 未来 data-free pins**。B/C 仅供后续选择，不包含在本 PR 或默认实施授权内；任一 B/C 都须先更新范围、生产冻结与验收方案，不能顺带实施。旧 P1–P4 与 δ1 P3.1/2/3 不重裁。adversarial r1（E-d2-01..09）均为文档/验收定义回填，**不强制**将任一项人裁从 A 重开到 B/C；人裁仍待录入，本 v0.2 不冒充 GO。

| ID | 人裁点 | A（推荐） | B | C |
|---|---|---|---|---|
| **P3δ2.1** | `ex_date_index` ∪ 因子跳变阈值的事件口径 | 文档化 §2.2 主事件+严格 >1% 兜底及因子可用性；只补契约测 | 另案改为仅 ex index 权威事件 | 另案重设计事件合并/缺行补偿策略 |
| **P3δ2.2** | k 与一次性缩放对象是否扩展 | 保持 `F_prev/F_D`；书 cost/peak only；v7 保持已存在的全部参考字段；不新增对象/去重 | 另案增加重放幂等/停牌累计应用机制 | 另案扩展为 shares/现金等完整公司行动记账 |
| **P3δ2.3** | 经济残留是否继续 deferred | 保留送转不增股、分红不入账及 (1−k) 失真声明；只钉原股数/现金/NAV oracle | 另案研究拆分送转与现金分红账本 | 另案迁移总回报经济模型并重裁收益口径 |
| **P3δ2.4** | ≤0.5% 噪声带是否保留 | 保持 `j<=5e-3` 不修正，包含已枚举事件；钉等号与两侧 | 另案降低/取消噪声带 | 另案按公司行动类型或价格精度重设阈值 |
| **P3δ2.5** | front/back/`qlib_day` 连续域跳过 E-R6 是否保持 | 保留 daily `run()` 现有跳过（`qlib_day`≠`qlib_1min`）；minute/v7 现存差异照录并冻结 | 另案统一所有入口的价格域/跳过接线 | 另案引入显式域类型与拒绝混域校验 |

---

## 6) Non-goals

- 不重开 E-R6 参考价算法或旧宿主 Slice D，不承诺纠正全部假止损、停牌遗漏、因子恢复日错域或经济亏损。
- 不增股、不发放现金红利、不补历史成交、不重算总回报、不统一 v7/book 的 lot 模型。
- 不修改噪声阈值、因子构建、缺失政策、warmup 长度、v4 SMA 价格域或 loader；不采集公司行动数据；不把“日期 LAG”升级为“决策时刻 PIT 已证”（E-d2-02）。
- 不重做 δ1，不改费率/最小费用粒度/印花税记账，不用 Mode A/B 的不同经济模型替换本刀。
- 不改 P1（14:57）、P2（任何新 trades 列）、P4（touch↔mark）；δ3/δ4/δ5 全挂起。
- 本 PR 不实施测试、不运行回测/湖，不宣称未来 B/C 已验收，不新建虚构 review 记录或占位脚本。

---

## 7) Slices A → B → C（未来实施路径，非本 PR 实施清单）

前置：§5 后续人裁录入。本 PR 提供 **v0.2** 可审计划（含 adv-r1 勘误回填）；下面每片均为未来动作。

### Slice A — 合同文字与证据收口

- 复核 §2 锚点，按人裁将事件矩阵、书/v7 字段差异、入口域差异、E-R6 已关/经济残留边界同步到 `engine-ashare-correctness.md`，必要时在 `docs/backtest/README.md` 加计划链接。
- DoD：旧 E-R5/E-R6 与 δ1 费率段不被扩大或回退；五个人裁逐项有结论；生产文件零差异。A 不冒充 B 的接线证明。

### Slice B — data-free 契约测（建议扩展现有文件，无幽灵着陆文件）

| Pin | 未来着陆文件（均已存在） | 必须验收的行为 |
|---|---|---|
| B1 事件门与 k | `tests/test_exdiv_map.py` | §2.2 四格、两个阈值等号/两侧、0.8% 有/无事件、k<1/k>1、有效行 LAG/warmup、缺 ex fallback；合成 parquet 显式 tmp_path，绝不走真实 resolver。可选：截断到 D vs 追加 D 后数据的前缀一致性、无前行不得向后借因子（仍不证原始 PIT，E-d2-02）。跨日因子恢复链见 B2 观察点（E-d2-01） |
| B2 缩放范围与顺序 | `tests/test_exdiv_refprice_engines.py` | 多 lot 的 cost/peak ×k，其余字段保留；公开 daily/minute `simulate` 证明老 lot 仅一次、新买不重乘、连续事件复合；保留 helper 非幂等事实；缺 bar 前置分支不伪装成递延补偿。**明列台阶加仓（step）路径**与两引擎 exdiv 传参：至少“映射后命中涨停而阻止 step”及“允许 step 时新 lot 保持当日原始成交 cost”（E-d2-05）；勿用普通 pool 买代替 step 来源。规划经真实 `load_exdiv_rates`→公开模拟器的因子恢复日错配链，按现状 pin 残留（E-d2-01） |
| B3 v7 保留分叉 | `tests/test_csv_minute_backtest_v7.py` | **两层证明（E-d2-03）**：（1）helper 人工 Position，含非空 `add1_A1` 的字段/不变量矩阵，标注兼容分支与注入限度；（2）公开 `simulate_v7` 钉自然可达的 entry_A/avg_cost/peak/Lot.price、扫描前一次性、新买/加仓、原股数/现金。非空 `add1_A1` 禁写“已验证自然加仓赋值”。另：除权日老/新 lot 混持后同日 stop 只卖老 lot 的 T+1 pin（E-d2-07）；自洽 held 夹具替换/补充混域 trial-stop 模板（E-d2-06） |
| B4 昨收到档位 | `tests/test_ashare_session.py`、`tests/test_exdiv_refprice_engines.py` | 保留直观例 `raw_prev=10,k=0.5→5→(5.50,4.50)`；**增补** `raw_prev=3.30,k=0.5→1.65→(1.82,1.49)`，mapped 返回值必须送入真实档位函数（E-d2-04）。复用 held/chase/pool，**并明列 step**（E-d2-05）；保持 Decimal 档位与 `limits=None` 现状 |
| B5 经济残留 | `tests/test_exdiv_refprice_engines.py`、`tests/test_csv_minute_backtest_v7.py` | §2.4 数值 oracle；参考字段变、股数现金不因事件变，raw mark 仍有跳变；不把 EOD_MARK 当真实 SELL 或给 v7 加产物列。将“股数/红利缺失造成的经济残留”与“错域导致的错误触发、旧成交不能靠后续 rescale 撤销”（E-d2-01）分开断言 |
| B6 价格域入口 | `tests/test_exdiv_refprice_engines.py` | 对 daily `run()` 的 lake none/front/back/**`qlib_day`** 四态隔离所有 I/O：stub bars/pool、map loader、simulate、artifact writer；捕获 exdiv 参数与 loader 调用。minute/v7：明确 `daily_source∈{lake,qlib_day}` × `minute_source∈{lake,qlib_1min}` 的受控接线预期——**当前各组合仍加载/传递 map**（E-d2-08）；只记录现状，不宣称域一致，不改生产补齐跳过 |

DoD：新增 pins 与既有测试互补；只有 pytest 内存/临时夹具，无 CLI 回测。不能只断言 helper 乘法就宣布 daily/minute/v7 接线闭合；不能只跑 fees/fence 就宣布 δ2 通过。若 B 暴露真实缺陷，记录事实并按 F-R11 留待另案，默认冻结不变。

### Slice C — §8 验收 + 生产冻结

- 在未来实施分支执行 §8.2 全部真实命令，记录各命令 exit code、pytest 通过/跳过数、环境与验证 HEAD；不可挪用 δ1 的 10/50 passed 成绩。
- 执行 §8.1 的基线/编码检查及 §8.3 冻结与路径审计，更新本 plan 状态/运行记录；本 PR 路径限制与未来 docs+具名测试限制分开。
- DoD：所有必需 pins 被收集且执行，无湖/回测；§9 生产零 diff；文档如实保留经济残留。未执行的命令写“未执行”，不得写通过。

---

## 8) Linux/CI isomorphic acceptance（真实路径；本 PR 静态核对，B/C 未来执行）

### 8.1 基线、文档编码与 whitespace（本 PR 可执行）

以下从仓库根目录用 Bash 执行。SHA 已由分支起点 `git rev-parse HEAD` 取证；这里解析同一 commit，不跟随移动的 master，不推断 merge-base。

```bash
set -euo pipefail
IMPLEMENTATION_BASE="$(git rev-parse --verify '1ad010cca013afe8186f20275cbdcca71e500823^{commit}')"
[[ "$IMPLEMENTATION_BASE" =~ ^[0-9a-f]{40}$ ]]
git merge-base --is-ancestor "$IMPLEMENTATION_BASE" HEAD
PLAN=docs/backtest/plan-industry-align-p3-d2-exdiv-2026-09-19.md
perl -MEncode=decode,FB_CROAK -e '
  local $/; open my $fh, "<:raw", $ARGV[0] or die $!;
  my $raw = <$fh>; die "BOM\n" if substr($raw,0,3) eq "\xEF\xBB\xBF";
  my $nul = () = $raw =~ /\x00/g; die "NUL=$nul\n" if $nul;
  decode("UTF-8", $raw, FB_CROAK); print "UTF-8 OK; BOM=0; NUL=0\n";
' "$PLAN"
git diff --check "$IMPLEMENTATION_BASE" HEAD
git diff --check
git diff --cached --check
```

### 8.2 未来 Slice C：环境、真实 pytest 路径及 gates

同构依据：`.github/workflows/python-tests.yml:27-43` / `:49-56` 使用受控 Python 3.12、requirements、四个 repo-only gates 和相同 pytest marker。本节是 **δ2 定向合同验收**，不冒称已经运行 CI 全量 suite。Linux 先准备项目 venv/CI setup-python 环境；遵循 AGENTS 的解释器优先级，不能隐式调用系统 python/pip。依赖准备属于环境前置，不在本 docs PR 安装依赖。

```bash
set -euo pipefail
P3_D2_PYTHON="${OSKH_MERGE_PYTHON:-${VANNA312_PYTHON:-${VANNA311_PYTHON:-}}}"
: "${P3_D2_PYTHON:?Set OSKH_MERGE_PYTHON to the controlled Python 3.12 executable}"
[[ -x "$P3_D2_PYTHON" ]]
"$P3_D2_PYTHON" -c 'import sys, pytest, pandas, numpy, pyarrow; assert sys.version_info[:2] == (3, 12); print(sys.executable)'

# Repo-only gates; same real paths as CI, no lake access.
"$P3_D2_PYTHON" scripts/gates/verify_oskh_data_contract.py
"$P3_D2_PYTHON" scripts/gates/verify_data_path_ssot.py
"$P3_D2_PYTHON" scripts/gates/verify_no_hardcoded_machine_paths.py
"$P3_D2_PYTHON" scripts/gates/verify_tr_bridge_import_ssot.py

# All proposed Slice B landing files already exist and must be collected here.
"$P3_D2_PYTHON" -m pytest -q -m "not production and not benchmark" \
  tests/test_exdiv_map.py \
  tests/test_exdiv_refprice_engines.py \
  tests/test_ashare_session.py \
  tests/test_csv_minute_backtest_v7.py

# Preserve δ1 fee contract + fixed hot-path fence; not δ2 wiring proof alone.
"$P3_D2_PYTHON" -m pytest -q -m "not production and not benchmark" \
  tests/test_ashare_fees.py \
  tests/test_ashare_fee_wiring.py \
  tests/test_ashare_simulate_import_fence.py
```

全部命令 exit 0 且 B1–B6 实际执行才可宣布未来 Slice C 通过；缺依赖/解释器记环境阻塞，不记代码失败或通过。不得通过静默 skip 必需 pin 凑绿。本 PR **不执行本节、不编造 pytest 结果**。

### 8.3 生产冻结与路径检查（本 PR / 未来 C 均适用）

先执行 §8.1 设置 `IMPLEMENTATION_BASE`；数组与 §9 一一对应，完整保留 δ1 十文件并扩展 E-R6/读取器/时钟面。

```bash
FROZEN_PRODUCTION_FILES=(
  backtest/research/ashare_fees.py
  backtest/research/csv_ledger.py
  backtest/research/csv_simulate_loop.py
  backtest/research/csv_daily_backtest.py
  backtest/research/csv_minute_backtest.py
  backtest/research/csv_minute_backtest_v7.py
  backtest/research/ashare_session.py
  backtest/research/market_layer.py
  backtest/research/csv_common.py
  backtest/research/csv_artifacts.py
  backtest/research/exdiv_map.py
  backtest/research/exdiv_hold_hits.py
  backtest/research/ashare_bars.py
  backtest/research/csv_daily_loader.py
  backtest/research/ashare_fill_clock.py
)
git diff --exit-code "$IMPLEMENTATION_BASE" HEAD -- "${FROZEN_PRODUCTION_FILES[@]}"
git diff --exit-code -- "${FROZEN_PRODUCTION_FILES[@]}"
git diff --cached --exit-code -- "${FROZEN_PRODUCTION_FILES[@]}"

# Audit all tracked/untracked paths too; the freeze list alone proves only its files.
git diff --name-only "$IMPLEMENTATION_BASE" HEAD
git diff --name-only
git diff --cached --name-only
git ls-files --others --exclude-standard
```

路径通过条件：本 PR 仅本 plan 与 `docs/architecture/reviews/2026-09-19/plan-industry-align-p3-d2-exdiv-codex-adv-r1/`（lanes / errata / host summary；可省略超大 stderr）；未来 A/B/C 仅本 plan、`docs/backtest/engine-ashare-correctness.md`、`docs/backtest/README.md` 与 B1–B6 四个具名测试文件。§8.2 费率/fence 回归只跑不改。任何其它路径变化先解释来源，不计作本刀通过；严禁用“冻结表未列出”授权修改其它生产文件。未来每个变更 `.md` 也要执行 UTF-8/BOM/NUL 检查，`.py` 同要求。

当前验收状态：**仅 plan 编写与静态核验阶段；未来 Slice B/C 未实施、未运行**。实际提交时的静态检查结论在 PR body 记录。

---

## 9) Frozen production file table（δ1 超集；默认零 diff）

| File | 冻结理由 / 来源 |
|---|---|
| `backtest/research/ashare_fees.py` | δ1：费率 SSOT 默认/asymmetry/floor 不回退 |
| `backtest/research/csv_ledger.py` | δ1 + δ2：成交现金/佣金/股数及 `rescale_position` 字段集合 |
| `backtest/research/csv_simulate_loop.py` | δ1 + δ2：chase/pool/台阶档位映射与原始 mark |
| `backtest/research/csv_daily_backtest.py` | δ1 + δ2：持仓缩放顺序、continuous-domain 跳过与费率覆写 |
| `backtest/research/csv_minute_backtest.py` | δ1 + δ2：扫描前缩放、数据源入口与默认费率 |
| `backtest/research/csv_minute_backtest_v7.py` | δ1 + δ2：独立 lot 字段缩放、现金股数/费率与产物 |
| `backtest/research/ashare_session.py` | δ1 + δ2：昨收映射、档位、T+1、context 加载 |
| `backtest/research/market_layer.py` | δ1：Decimal 档位、ST/未知板块政策 |
| `backtest/research/csv_common.py` | δ1 + δ2：bar/昨收前置条件与 book 档位包装 |
| `backtest/research/csv_artifacts.py` | δ1：产物 schema 不变，P2 挂起 |
| `backtest/research/exdiv_map.py` | δ2 扩展：事件门、阈值、有效行 LAG、k、缺失行为 |
| `backtest/research/exdiv_hold_hits.py` | δ2 扩展：exdiv_map 引用的 normalize_date；不改 NP2 探针 |
| `backtest/research/ashare_bars.py` | δ2 扩展：数据域/分钟切片与缺 bar 前提 |
| `backtest/research/csv_daily_loader.py` | δ2 扩展：none/front/back 与零量过滤前提 |
| `backtest/research/ashare_fill_clock.py` | δ2 扩展：P1 时钟命名面冻结；不改撮合窗口 |

冻结对照点固定为本 plan 的 IMPLEMENTATION_BASE。表内零 diff 只证明所列文件；§8.3 全路径审计另行约束全部新提交，不能声称此表已穷尽生产依赖。δ1 原计划及其冻结结论保持不动。

---

## 10) Short OSS analogy table（仅类比，不作行为证据）

| 类比 | 可借用概念 | 本仓界限 |
|---|---|---|
| 公司行动前后参考价格域转换 | 区分触发参考与成交/经济记账 | 不能从别的引擎推断本仓已增股、入现金或实现总回报 |
| 事件循环中的一次性处理 | 明确在扫描前对存量状态变换 | 不证明 helper 幂等，也不保证停牌事件自动回放；以 §2 源码为准 |

---

## 11) Changelog

- **v0.2 (2026-09-19)**：Host-parallel Codex adversarial r1（dissent-steelman / domain-safety / pattern-evidence，all rc=0）勘误回填 E-d2-01..09：因子恢复日错域残留与“映射到 D 域”前提收窄；决策时刻 PIT 未证；B3 helper/公开可达分层与混持 T+1；B4 Decimal 半分边界；step 加仓接线观察点；v7 trial-stop 夹具限度；`qlib_day`≠`qlib_1min` 与 B6 源组合矩阵；v7 接线沿革短注。人裁默认仍 A/A/A/A/A，无强制重开。`IMPLEMENTATION_BASE` 保持全 40 字符 `1ad010cca013afe8186f20275cbdcca71e500823`。记录：[codex-adv-r1](../architecture/reviews/2026-09-19/plan-industry-align-p3-d2-exdiv-codex-adv-r1/)。无生产/测试代码修改，无回测/湖读取。
- **v0.1 (2026-09-19)**：首次 docs-only δ2 plan；基线经 `git rev-parse HEAD` 核对为 `1ad010cca013afe8186f20275cbdcca71e500823`（PR #121 merge）。只承接 δ1 roadmap 的除权契约细化；列出 E-R6 已关面/经济残留、书与 v7 字段分叉、daily 连续域跳过的入口边界、五项待人裁 A/B/C、未来 A→B→C/data-free 验收与 δ1 超集冻结表。无生产/测试代码修改，无回测/湖读取，B/C 尚未实施。
