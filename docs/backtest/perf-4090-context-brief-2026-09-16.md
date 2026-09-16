# 性能优化上下文简报：PR #57 评审 + 4090 讨论 + Qlib 对照（交 Codex）

> **落盘**：2026-09-16。**用途**：为后续性能相关工作（含 [PR #60](https://github.com/baiyibing/MyQuant-backtrader/pull/60) 的评审与实施）提供完整上下文；可独立阅读，不需要回翻会话。
> **基线**：master `b748b37`（#58 退场、#61 资金管理、#62 收口均已合入归档）。
> **性质**：简报（brefing），不是 plan；权威对象是各链接指向的 plan / 评审 / 工件。

---

## 1. PR #57 评审结论（2026-09-16，只读评审）

PR #57 = Opus 5 仓库自分析（[repo-analysis-opus5-next-2026-09-15.md](repo-analysis-opus5-next-2026-09-15.md)）。评审判定：**质量高、事实纪律好，三处硬声明经代码验证全部属实**，但为 09-15 快照，两条 G 禁区已被 09-16 人裁推翻。

### 1.1 核实通过（逐条对过代码）

| 声明 | 验证 | 结果 |
|------|------|------|
| 「13 个门禁、CI 只跑 4、9 个宿主 only 无清单」 | `ls scripts/gates/` 恰 13 个 `verify_*`；workflow L40-43 恰 4 个 | 数字精确 |
| 「numba trail 在真实 `simulate()` 结构性不可达」 | `csv_minute_backtest.py:638-644` `can_offload` 要求 `take_profit/sell_gate/reserve_state` 全 None；`:851` 每手构造 `reserve_state` | 属实 |
| R12 门禁脚本同名多副本 | `verify_minute_chip.py` 双份、`verify_turnover_resistance_alignment.py` 双份 | 属实 |

### 1.2 消费时的两个折扣

1. **G 禁区两条已被人裁取代**：「物理删除 Cerebro」（已做，PR #58）、「改 6/8 卖点」（已做，PR #61，业务 docx 驱动）。读 WP1–WP5 定优先级时必须带此滤镜。
2. **WP1 候选 (2) ROI 存疑**：compiled scan 要求 `take_profit is None`，而 **v6/v8/v9/v10 全部提供 callable take_profit**（band 阶梯是代码不是配置）——文档自己钉了这个事实但没连到 ROI 结论上。候选 (2) 帮不了当前任何在研究策略，除非把 band 语义原生编码进内核（见 §2.4）。

### 1.3 采纳的排序建议（与 #57 一致）

- **WP4 → WP2 已在本 PR 落地**（R11 root 指针 + 宿主门禁 cookbook）；这两项**与 PR #60 无关**。
- **WP1 排在 #61 合入之后**（同批文件）——现已满足。
- R11（`plan-pool-pipeline-r0r1` root 副本回潮）根因是分支合并清理时的 merge（`b67772a`）；#62 已归档两个新 plan 时同样注意：归档后 root 不得再回潮。

---

## 2. 4090 / GPU 性能优化讨论（来龙去脉）

### 2.1 起点

业务提出：高配机（RTX 4090，非本机）能否加速本仓回测。

### 2.2 判定：单次回测不值得 GPU（证据链）

- #54 实测（真实分钟 `simulate()`）：**卖环 75.51%**（逐 lot 逐 bar 分支状态机）+ 编排 18.6%；GPU 擅长的向量化数学占比极小。
- 量级：#54 场景全程 1.2s；D 烟测宿主实测（2026-09-16，本机 F 湖、master `a606070`）：**daily 全窗 18.7s、minute 全窗 ~90s**——单次回测分钟级，GPU 化无收益。
- 新证据持续强化：D 烟测后「分钟回测慢」的假设进一步存疑，PR #60 的 S0 判定门大概率判停（"不值得"是合法产出）。

**D 烟测事实卡**（[PR #62](https://github.com/baiyibing/MyQuant-backtrader/pull/62)，merge `b748b37`；运行于代码态 `a606070`、2026-09-16 本机 F 湖、按 M-R8 顺序先 daily 后分钟）：

| 项 | 结果 |
|----|------|
| daily per_name 全窗（20251023–20260909） | 期末 -28.65%，最大回撤 -37.57%，**18.7s**（加载 12.5s+模拟 4.7s） |
| minute per_name 全窗 | 期末 -23.31%，最大回撤 -28.50%，**~90s**（分钟湖 44.8s+模拟 17.5s） |
| 同 sizing 对照 | 末日分钟比日线 **+7.49%**（卖点时钟归因，caption 有效；分钟锚定回撤 810 次 vs 日线 215 次） |
| 引擎自检 | 两引擎 `sizing=per_name\|name_budget=1M`；加仓恒 0；`chase_buy_fail_shares=0` |
| 观测项 | skip_cash 3,972/3,546（名义 ~39 亿）；**宽度>21 现金上限天数 104/215（48%）**；止损滑出 n=41、中位 -30.00%、最差 -35.21% |
| 基线保护 | 切前分钟工件复制为 `csv_minute_v8_20251023_20260909_preswitch_dailyquota`（跨 sizing 仅 lot 级对照：272 lots×99.9 万 vs 3,438 lots×4.1 万） |
| 未跑 | P1 有/无武装 A/B（武装变体代码已删，需 scratch 补丁，后置非阻塞） |

数字全文见 [money-modes-v8-pername-smoke-2026-09-16.md](money-modes-v8-pername-smoke-2026-09-16.md)「宿主补跑」节。

### 2.3 判定矩阵（负载 → 工具）

| 负载 | 4090 适合度 | 正确工具 |
|------|------------|----------|
| 分钟卖环（75%） | ✗ 时间维串行、lot 维仅 10–40 个 | WP1(1) 缓存 → S3 compiled scan（CPU numba） |
| 参数网格/走窗扫描 | △ GPU 无用、多核 CPU 有用 | 进程池每 run 一进程（零代码） |
| **全市场分钟筹码直方图**（数千码×长窗=小时级 CPU） | ✓ 教科书 GPU 负载（原子累加） | CuPy 或 numba-cuda（S2，条件立项） |
| Rust TR（turnover-resist） | — | SSOT 不动 |

### 2.4 「原生编码 band 语义」是什么（S3 的实质）

- 现状：卖点=「规则即闭包」（书传 callable，每 bar Python 调用）→ numba 无法编译，开关结构性打不开（§1.1）。
- 目标：卖点=「**规则即数据**」（bands 表 lo[]/hi[]/floor[] + small_arm + peak_dd(arm,pct) + stop_pct + peak_gap_min + force_hm）+ **一个通用编译内核**查表解释。v6/v8/v9/v10 共用同一 kernel，差异全在表值。
- callable 保留为参照实现；**三向 parity 金测试是合入门**（复刻 `test_scan_held_day_numba_parity.py` 模式）。
- 边界：第一版只覆盖 band 型书；v3 reserve 状态机留 Python；日线引擎卖环（pending_exit）不动。
- 诚实预期（Amdahl）：卖环 75% × 内核 ~15-20× → 端到端 **3–4×**，非数量级魔法。
- 前置：PR #60 A-R6——S3 必须另开 dated plan + 多 agent 评审（新 parity 面）。

### 2.5 numba GPU 版本 vs CuPy

- numba 有 CUDA target（`@cuda.jit`），但 0.59+ 起**拆为 NVIDIA 维护的独立包 `numba-cuda`**（需另装 + CUDA 组件）；本机 vanna312 numba 0.65.1 import 路径通、`cuda.is_available()=False`（本机无 N 卡，正常——GPU 活都在高配机）。
- 两者对 S2 都可行：numba-cuda 优势=与现有 H15 kernel 同源循环体、三向 parity 自然；CuPy 优势=wheel 自带 CUDA 运行时、数组 API 省事。**选择推迟到 S2 启动时十分钟冒烟**（同一直方图 microbench 对比），plan 无需改。

### 2.6 术语澄清（防误读）

「本仓=向量化」是**架构定位词**（研究脸 vs 事件驱动 vs 真栈），不是实现承诺。主循环是纯 Python 状态机；numpy 只在 IO/聚合层（`volume==0` 过滤、H8 `searchsorted` 日卖索引）；numba 仅两处可选且默认关（chip cumpdf 可达、卖环不可达）。「快」来自 CSV/parquet 批装载 + 轻量账本。

### 2.7 落地产物：PR #60（已人裁 · 合入后归档）

[plan-gpu-accel-4090-2026-09-16.md](plan-gpu-accel-4090-2026-09-16.md)：S0 只读实测（真 F 湖两墙钟）→ P1 判定门（回测 <5min 且 chip 扫描不常跑 → **终止 GPU 项目**）→ S1（WP1(1) 引用 + CPU 并行 runbook）→ S2（chip CuPy/numba-cuda 第三后端 + 三向 parity + `requirements-gpu.txt` 隔离 + GPU 不进 CI）→ S3（另开 plan）。硬锁 A-R1–A-R7：默认 Python、S0 前禁止引用任何预期加速比、显存按码分批（全市场分钟窗 ~18GB 贴 24GB 上限）、直方图 int bin 或容差。

---

## 3. MyQuant Qlib 对照（为什么它快、本仓学什么）

Qlib 回测快**不靠 numba/GPU/编译内核**，靠四件事全压在向量化层：

1. **信号批量预计算**：模型一次对全市场×全日期出分（C++ learner），回测只消费宽表。
2. **每日决策=一次数组排序**：TopkDropoutStrategy 卖出=**排名淘汰（无状态）**，`argsort` 完事——「不加过滤条件就快」的本质是退化成纯数组运算。
3. **简单成交模型**：按 deal_price 一笔成交，无逐分钟撮合、无 lot 状态机。
4. **自研 .bin + mmap 二进制行情存储**，因子缓存回同格式。

**本质差异（不是技术水平差距，是语义取舍）**：本仓 75% 卖环对应的东西 Qlib 里不存在——金榕元 band 阶梯/T+1 追买/跌停 defer 正是本仓存在的理由；砍掉语义谁都快。两仓 SSOT 已停用 Qlib `PortAnaRecord`（成交模型过简、NAV 不可比）。

**可借鉴两点**：① parquet 列裁剪 + 已读 DataFrame 复用（=WP1(1)，若 S0 显示 IO 占比高）；② 「信号预计算→回测只消费」分层——本仓 pred 导出→契约日 CSV→`--pool-dir` 已等价对齐，无需动作。

---

## 4. 当前状态与行动项（给 Codex）

| 项 | 状态 | 下一步 |
|----|------|--------|
| #58 退场 / #61 资金管理 / #62 收口 | ✅ 已合入归档（`e89d1b8`/`a606070`/`b748b37`） | 无 |
| D 宿主烟测 | ✅ 已补跑（PR #62，merge `b748b37`；[烟测短记](money-modes-v8-pername-smoke-2026-09-16.md) 宿主节，事实卡见本简报 §2.2） | P1 有/无武装 A/B 后置（需 scratch 补丁） |
| **PR #60（GPU plan）** | ✅ v1.1 已人裁归档（回测 STOP / 关 S2 / 不开 S3） | 合入后迁 `_archive/plans/`；GPU 项目关闭；S1 可选笔记不构成立项 |
| #57 的 WP2（宿主门禁 cookbook）/ WP4（R11 de-dup） | ✅ 本 PR 落地，**与 #60 无关** | WP4 root 指针 → [WP2 cookbook](host-lake-gates-cookbook-2026-09-16.md) |
| #57 的 WP1(1)（prev-close/close-history 缓存） | ⬜ 未开工 | S0 数字支持时随 S1 做 |

**消费 #57 时的红线提醒**：其 G 禁区两条已被 09-16 人裁取代（§1.2）；WP1(2) 在「band 原生编码」落地前对本仓在研策略无收益（§1.2/§2.4）。
