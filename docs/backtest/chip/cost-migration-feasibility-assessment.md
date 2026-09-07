# qlib_cost 筹码分布算法迁移至 backtrader 可行性评估（v2 修订版）

> **状态**：评审讨论稿 — 待数据契约收敛后升级为实施就绪稿  
> **修订说明**：根据专家审核意见（第二份报告）修订，重点修正数据契约改造成本低估、精度数字结论化、以及 turnover_rate 来源未闭环等问题。

---

## 一、qlib_cost 算法架构与数据契约

### 1.1 纯算法层（零 Qlib 依赖）

| 文件 | 依赖 | 核心功能 |
|------|------|---------|
| `qlib_cost/scr/distribution_of_chips.py` | numpy, numba | 三角/均匀分布 PDF、换手率衰减系数 |
| `qlib_cost/scr/cyq.py` | numpy, pandas, numba | 筹码分布累积 `calc_cumpdf`、因子提取 `ChipFactor` |
| `qlib_cost/scr/utils.py` | numpy, numba, pandas | 滚动窗口辅助函数 |

### 1.2 硬数据契约（输入字段不可协商）

`cyq.py` 主入口 `calc_dist_chips` 对 DataFrame 的列选择是硬编码的：

```python
# qlib_cost/scr/cyq.py
arr: pd.DataFrame = arr[["close", "high", "low", "vol", "turnover_rate"]]
```

| 字段 | 当前 backtest 数据资产 | 是否具备 |  Gap |
|------|----------------------|---------|------|
| `close` | `close`（分钟/日线均有） | ✅ | — |
| `high` | `high` | ✅ | — |
| `low` | `low` | ✅ | — |
| `vol` | `volume`（列名不同，需映射） | ⚠️ | 字段名映射：`volume` → `vol` |
| `turnover_rate` | **无** | ❌ | 需从流通股本计算或外部引入 |

**关键发现**：`turnover_rate` 不是可用可不用，而是 `cyq.py` 的**必选输入**。没有它，算法无法执行。

---

## 二、turnover_rate 数据路径评估（专家高优先级意见闭环）

### 2.1 路径 A：流通股本计算（理论正确，工程未验证）

公式：`turnover_rate = volume / float_shares`

| 子问题 | 现状 | 风险 |
|--------|------|------|
| 流通股本 `float_shares` 来源 | 仓库当前**无现成数据管道** | 需新增下载/存储/更新逻辑 |
| QMT 接口可用性 | `xtdata.get_stock_info` 理论上可获取 | 未在本仓验证字段名、复权口径、更新频率 |
| 停牌日处理 | 停牌日 volume=0，turnover_rate=0 | 需确认 `cyq.py` 对零值的处理是否稳健 |
| 复权口径 | 分钟线 parquet 有 `dividend_type=none` | 若股本数据不复权，turnover_rate 在除权日会跳变 |

**结论**：此路径是**长期正确解**，但工程落地需额外工作（见第四章）。

### 2.2 路径 B：近似 turnover（最小可运行解）

在缺乏流通股本时，可使用**近似换手率**作为占位：

- 方法 1：用固定流通股本假设（如取最近一期财报值，硬编码到本地 CSV）
- 方法 2：从第三方 API（如 akshare `stock_zh_a_spot_em`）批量获取一次，静态化存储为本地 JSON/CSV

> **注意**：`volume / amount * close` 这类公式本质上是 `close / VWAP` 的比值，与换手率数学定义无关，**不建议作为 turnover_rate 的近似**。此类公式会把原型验证引到错误方向。

**结论**：此路径**不可用于生产因子**，但可用于验证算法集成是否可行（字段映射、numba 编译、backtrader 指标封装）。

---

## 三、分钟线数据价值评估（修正版）

### 3.1 当前数据资产

```
stock_data/period=1m/dividend_type=none/symbol=000001_SZ/data.parquet
字段：['time', 'open', 'high', 'low', 'close', 'volume', 'amount']
样本量：约 77,843 行/股（2025-01-02 起）
```

### 3.2 分钟线对 COST 的作用

| 维度 | 日线估算 | 分钟线增强 | 逐笔成交（理想，数据不可得） |
|------|---------|-----------|---------------------------|
| **日内成交分布** | 三角/均匀分布假设 | 按分钟 OHLC 聚合分布，减少假设成分 | 真实逐笔价格-量对 |
| **精度** | 待验证（经验预期：低） | 待验证（经验预期：中） | 待验证（经验预期：高） |
| **数据可用性** | ✅ 有 | ✅ 有 | ❌ 无 |

> **修正说明**：上一版将精度写成"~70-80%"、"~85-90%"等结论化数字，缺少本仓复现实验。本次改为"待验证（经验预期）"，需在原型阶段通过样本池回归确定实际误差区间。

### 3.3 关键结论（未变）

> 分钟线有用，但属于**更精确的近似估算**，而非**精确计算**。即使使用分钟线，1 分钟内的成交价格分布仍然未知。

---

## 四、backtrader 回测架构现状

| 维度 | 现状 |
|------|------|
| 框架 | backtrader |
| 主策略 | `backtest/rolling_investment_strategy.py` |
| 数据频率 | 1 分钟 OHLCV（primary）+ 1 日 OHLCV（indicator） |
| 数据源 | MiniQMT `xtquant.xtdata` → parquet 缓存 |
| 数据加载 | `PrevClosePandasData(bt.feeds.PandasData)` |
| 自定义指标 | 仅 `bt.indicators.SMA`（MA5/MA10） |
| 与 live 系统耦合 | **零耦合** — 不依赖 oskh_core / Redis / SQLite Gateway |

---

## 五、迁移路径（专家意见：拆成两步）

### Step 1：字段映射与最小可运行原型（MVP）

**目标**：验证 qlib_cost 纯算法层可在 backtrader 环境中编译运行，不追求因子精度。

**工程内容**：
1. **字段映射**：在数据加载层将 `volume` 映射为 `vol`
2. **近似 turnover**：使用路径 B（如硬编码流通股本或固定 turnover 假设）生成 `turnover_rate` 列
3. **numba 依赖确认**：在 backtest 运行环境安装并验收 `numba`（当前主工程未锁定此依赖）
4. **指标封装**：将 `calc_dist_chips` + `ChipFactor` 封装为 backtrader 自定义指标/策略属性
5. **最小验证**：对 1-3 只样本股跑通日线粒度的 `get_cyqk_c` / `get_asr` 计算

**预期改动量**：~150-200 行（含数据加载改造、字段映射、指标封装、简单测试脚本）
> **修正说明**：上一版估为"~80 行"，经专家审核后上调。字段映射 + turnover 占位生成 + backtrader 指标封装 + 环境验收，综合工作量高于纯"封装"。

**预期时间**：3-5 天（含环境调通、样本验证）
> **修正说明**：上一版"1-2 天"过于乐观，未计入 turnover 数据缺口和 numba 环境验收。

### Step 2：流通股本口径收敛与回归验证

**目标**：将 MVP 中的近似 turnover 替换为真实 turnover_rate，建立可复用的因子质量基线。

**工程内容**：
1. **流通股本数据管道**：
   - 评估 `xtdata.get_stock_info` 字段可用性
   - 或从 akshare / tushare 批量下载，存储为本地 CSV/JSON
   - 处理复权、除权、停牌等边界场景
2. **turnover_rate 精确计算**：`volume / float_shares`，按日聚合后注入 DataFrame
3. **回归验证**：
   - 样本池：选取 50-100 只 A 股，覆盖大/中/小盘
   - 基准：与 Qlib 版 qlib_cost 输出进行皮尔逊相关系数对比
   - 误差定义：
     - 相对误差：`abs(f_b - f_q) / max(abs(f_q), 1e-6)`（epsilon 保护，避免分母为 0）
     - MAE（平均绝对误差）：`mean(abs(f_b - f_q))`
     - RankIC：`spearmanr(rank(f_b), rank(f_q))`（衡量排序一致性，对因子投资更关键）
   - 统计方法：分行业/市值分组，报告相对误差均值/标准差、MAE、RankIC
4. **分钟线增强（可选）**：在日线验证通过后，开发分钟级直方图聚合算法

**预期改动量**：~200-300 行（含数据管道、回归脚本、质量报告）
**预期时间**：1-2 周

---

## 六、必要条件 checklist（修正版）

| 条件 | 状态 | 说明 |
|------|------|------|
| 分钟线 OHLCV | ✅ | `stock_data/period=1m` 已存在 |
| 字段映射 `volume→vol` | ⚠️ | 需在数据加载层显式映射 |
| `turnover_rate`（真实） | ❌ | 需流通股本数据管道，当前无 |
| `turnover_rate`（近似） | ⚠️ | MVP 阶段可用占位值，但不可用于生产 |
| 流通股本数据源 | ❓ | 需验证 `xtdata.get_stock_info` 或引入第三方 API |
| numba 依赖 | ⚠️ | 需在 backtest 环境安装并验收，当前未锁定 |
| 回归验证脚本 | ❌ | Step 2 需补 |

---

## 七、开放问题与假设（新增章节）

1. **流通股本数据来源优先级**：
   - 首选：`xtdata.get_stock_info`（与现有 MiniQMT 管道一致）
   - 次选：akshare / tushare（需新增 API 依赖）
   - 回退：硬编码最近财报值（仅用于 MVP）

2. **复权口径**：
   - 分钟线 parquet 当前为 `dividend_type=none`
   - 若 turnover_rate 使用不复权的流通股本，除权日会出现跳变
   - 建议：Step 2 中统一使用前复权口径的股本数据

3. **停牌日处理**：
   - 停牌日 `volume=0`，`turnover_rate=0`
   - 需确认 `calc_cumpdf` 对零 turnover 的处理是否会导致筹码分布停滞

4. **精度数字**：
   - 本报告所有精度预期均为行业经验值，**非本仓验证结论**
   - 实际精度需在 Step 2 回归验证后更新

---

## 八、专家审核意见响应摘要

| 专家意见 | 本版修订动作 |
|---------|------------|
| "80 行改动明显低估" | 上调为 ~150-200 行（MVP）+ ~200-300 行（Step 2） |
| "cyq.py 输入字段契约未闭环" | 新增 1.2 节硬数据契约表格，明确 `vol` 和 `turnover_rate` 的 Gap |
| "turnover_rate 单一路径论证不足" | 新增 2.1/2.2 双路径评估（流通股本计算 vs 近似 turnover） |
| "1-2 天出原型不可信" | 上调为 3-5 天（MVP），并拆分两步路径 |
| "numba 依赖偏乐观" | 改为 ⚠️ "需确认/补装并在回测环境验收" |
| "精度数字结论化" | 全部改为"待验证（经验预期）"，明确需回归脚本 |
| "缺少数据来源优先级与回退策略" | 新增第七章"开放问题与假设" |
| "建议拆成两步" | 第五章已按"MVP → 收敛验证"两步重排 |

---

*本报告为评审讨论稿，待 Step 1 MVP 验证通过、Step 2 回归验证完成后，可升级为实施就绪稿。*

---

## 附录：原始 v1 方案中的 8 因子说明

原始方案定义了 8 个筹码分布因子，来自 `qlib_cost` 的两个独立算法模块。经专家评审后，本期只实施 4 个。

### 模块 A：`cyq.py` → ChipFactor 类（4 因子，✅ 本期已实施）

基于三角/均匀分布 PDF → 累积筹码分布，从分布曲线提取：

| 因子 | 方法 | 公式 | 含义 |
|------|------|------|------|
| **CYQK_C** | `get_cyqk_c()` | `winner(close)` — 价格低于 close 的筹码占比 | 获利比例 |
| **ASR** | `get_asr()` | `winner(1.1×close) - winner(0.9×close)` | 活跃筹码比（±10% 区间） |
| **CKDW** | `get_ckdw()` | `(avg_cost - min_p) / (max_p - min_p)` | 筹码重心偏离度 |
| **PRP** | `get_prp()` | `close / avg_cost - 1` | 价格相对成本位置 |

### 模块 B：`turnover_coefficient_ops.py` → 换手率半衰期模型（4 因子，⏳ Phase 2）

基于换手率衰减权重 + 收益率统计矩，不依赖 OHLC 分布假设：

| 因子 | 公式 | 含义 |
|------|------|------|
| **ARC** | `Σ(weight × rc)` — 加权收益均值 | 平均持仓盈亏 |
| **VRC** | `N/(N-1) × Σ(weight × (rc-ARC)²)` | 筹码集中度（方差） |
| **SRC** | `N/(N-1) × Σ(weight × (rc-ARC)³) / VRC^1.5` | 盈亏分布偏度 |
| **KRC** | `N/(N-1) × Σ(weight × (rc-ARC)⁴) / VRC²` | 盈亏分布峰度 |

其中 `rc[i] = 1 - close[i] / close[-1]`（相对收益），`weight[i] = adj_turnover[i] / Σ(adj_turnover)`。

### 延后原因

`turnover_coefficient_ops.py` 继承自 Qlib 的 `PairRolling` 基类（`qlib.data.ops.PairRolling`），该基类与 Qlib 的 Expression 引擎深度耦合。迁移 ARC/VRC/SRC/KRC 需要：
1. 从 `turnover_coefficient_ops.py` 中提取纯算法部分（`calc_adj_turnover` 已在 `distribution_of_chips.py` 中，`calc_rc` 和统计矩计算在 `turnover_coefficient_ops.py` 中）
2. 封装为独立的 backtrader Indicator（类似 `ChipDistribution`）
3. 验证与 Qlib 侧输出的一致性

此工作列为 Phase 2，待 4 个 CYQ 因子在纸盘验证有效后启动。
