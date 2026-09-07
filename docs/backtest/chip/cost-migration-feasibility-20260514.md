# COST 筹码分布因子迁移可行性评估（修订版）

**报告编号**: INV-2026-0514-003  
**日期**: 2026-05-14  
**修订**: v1.2 — 2026-05-14（修正 ChipFactor 参数顺序、收敛"无需假设分布"措辞、去除固化样本数、验证计划脚本化）  
**评估对象**: `qlib_cost` → backtrader 回测系统  
**文档类型**: 立项可行性草案（非可直接实施的技术方案）

---

## 1. 背景

项目中 `qlib_cost/` 已有开源 QuantsPlaybook 的筹码分布算法实现，原生集成于 Qlib 框架。评估将 COST（筹码分布）因子迁移到 backtrader 回测体系的可行性。

---

## 2. qlib_cost 代码分层

### 2.1 纯算法层（零 Qlib 依赖，需适配列名和输入契约）

| 文件 | 行数 | 功能 | 依赖 | 迁移约束 |
|------|------|------|------|---------|
| `qlib_cost/scr/distribution_of_chips.py` | 189 | 三角/均匀分布 PDF、换手率衰减系数 | numpy, numba | 无 |
| `qlib_cost/scr/cyq.py` | 254 | `calc_dist_chips()`、`ChipFactor`（CYQK_C, ASR, CKDW, PRP） | numpy, pandas, numba | **列名契约**（见 2.1a） |
| `qlib_cost/scr/utils.py` | 73 | rolling_windows 工具 | numpy, numba, pandas | 无 |
| `qlib_cost/scr/plotting.py` | 431 | 筹码分布可视化 | matplotlib, seaborn | 无（非回测路径） |
| `qlib_cost/scr/factor_analyze.py` | 69 | 因子分组收益分析 | pandas, alphalens | 无（非回测路径） |

#### 2.1a cyq.py 输入契约与现有数据的断裂点

`cyq.py:100` 的 `calc_dist_chips()` 要求输入列名严格匹配：

```python
arr = arr[["close", "high", "low", "vol", "turnover_rate"]]
```

现有 backtest 数据的实际列名：

| cyq.py 期望 | backtest 实际 | 状态 |
|------------|-------------|------|
| `close` | `close` | ✅ 一致 |
| `high` | `high` | ✅ 一致 |
| `low` | `low` | ✅ 一致 |
| `vol` | **`volume`** | ❌ 列名不匹配 |
| `turnover_rate` | **缺失** | ❌ 列不存在 |

**结论**：不能直接复用。需要约 15 行的 adapter 函数做列名映射 + 换手率计算，之后再传入 `calc_dist_chips()`。

### 2.2 Qlib 封装层（需替换）

| 文件 | 行数 | 功能 | Qlib 依赖 |
|------|------|------|----------|
| `qlib_cost/scr/cyq_ops.py` | 559 | Qlib ExpressionOps 封装 | `qlib.data.base.ExpressionOps` |
| `qlib_cost/scr/turnover_coefficient_ops.py` | 159 | Qlib PairRolling 封装 | `qlib.data.ops.PairRolling` |
| `qlib_cost/scr/factor_expr.py` | 169 | Qlib DataHandlerLP | `qlib.contrib.data.handler.DataHandlerLP` |
| `qlib_cost/scr/qlib_workflow.py` | 386 | Qlib 训练+回测流水线 | 全部 Qlib 框架 |

---

## 3. 数据粒度与精度评估

### 3.1 当前数据资产

#### 日线数据（`stock_data/period=1d/`）

| 指标 | 值 |
|------|-----|
| 字段 | time, open, high, low, close, volume, amount |
| 换手率 | **缺失** — `get_market_data_ex()` 的 `field_list` 当前为 `['time','open','high','low','close','volume','amount']` |
| 复权类型 | back / front / none |
| 格式 | Apache Parquet + Snappy |

#### 分钟线数据（`stock_data/period=1m/`）

| 指标 | 值 |
|------|-----|
| 符号数量 | 以 `python -c "import os; print(len([d for d in os.listdir('stock_data/period=1m/dividend_type=none/') if d.startswith('symbol=')]))"` 实时统计为准（本文档不固化单值） |
| 单只行数 | ~78,000 行（约 325 个交易日 × 240 分钟/日） |
| 时间范围 | 2025-01-02 ~ 2026-05-08 |
| 字段 | time, open, high, low, close, volume, amount |
| 复权 | none（分钟线不支持复权） |
| 换手率 | **缺失**（分钟线无此字段，需从日线推导） |

### 3.2 分钟线数据对 COST 精度的作用

**日线方案**（qlib_cost 当前做法）：
- 每日只有 open/high/low/close/volume 五个价格点
- 必须假设日内成交量服从三角分布或均匀分布
- 精度取决于分布假设与实际成交的偏差

**分钟线方案**（本项目特有优势）：
- 每日有 240 根分钟 K 线，每根有独立的 OHLCV
- 显著弱化日内分布假设——用每分钟的实际成交量作为筹码权重（但分钟内成交价格仍需代表值假设，如 close 或 VWAP）
- 从 1 个假设分布 → 240 个实际量价点，信息量提升 2 个数量级

**精度对比（概念性，待实测）**：

```
日线方案：  [low] ~~~~△~~~~ [high]    ← 一个三角分布假设
分钟线方案：[vol₁@px₁] [vol₂@px₂] ... [vol₂₄₀@px₂₄₀]  ← 240 个实际成交点
```

分钟线方案可跳过三角/均匀 PDF 假设函数，用实际量价构建筹码分布（但仍需假设分钟内成交价格代表值，如分钟 close 或 VWAP）。

### 3.3 缺乏的数据及补齐方案

| 数据 | 用途 | 补齐方式 | 改动范围 |
|------|------|---------|---------|
| `turnover_rate`（日线） | 筹码衰减系数 | 下载时在 `field_list` 中增加 `'turnover_rate'` | `qmt_utils_adv.py:467`、`qmt_utils_new.py:461` |
| `turnover_rate`（分钟线） | 每分钟筹码衰减 | miniQMT 分钟线不支持此字段。从日线 turnover_rate 按分钟 volume 占比线性分配 | `chip_algorithm.py` 新增换算逻辑 |
| 列名 `vol` → `volume` | cyq.py 入参 | adapter 函数做 rename | `chip_algorithm.py` 新增 ~5 行 |

---

## 4. 迁移架构方案

### 4.1 数据全链路改造（区别于初版的真实改造面）

初版将 qmt_utils 的改动描述为"加一个 line"，但实际需要改动**下载 → 缓存 → feed → 读取**四个环节：

```
① 下载层 (qmt_utils_adv.py:467 / qmt_utils_new.py:461)
   field_list 新增 'turnover_rate'
        │
        ▼
② 缓存层 (stock_data/period=1d/*/data.parquet)
   存量数据需重新下载（或增量下载含 turnover_rate 的数据）
        │
        ▼
③ Feed 层 (PrevClosePandasData)
   lines 新增 ('turnover_rate',)
   params 新增 ('turnover_rate', -1)
        │
        ▼
④ 策略读取层 (rolling_investment_strategy.py)
   self.data.turnover_rate[0] 可访问
```

**风险评级：中**。每一步都是低风险的单点修改，但链路长（4 个环节），任一环节遗漏都会导致运行时 KeyError。

### 4.2 总体架构

```
qlib_cost/scr/（不改动）                     backtest/
├─ distribution_of_chips.py                  ├─ chip_algorithm.py  [新建]
│   └─ 三角/均匀 PDF（仅日线 fallback）       │   ├─ _adapt_columns()
├─ cyq.py                                    │   │   └─ rename volume→vol
│   ├─ calc_dist_chips() ──import──→         │   │   └─ 确保 turnover_rate 列存在
│   └─ ChipFactor ──import──→               │   ├─ _minute_chip_distribution()
│                                            │   │   （分钟线直接量价累积，跳过 PDF）
│                                            │   └─ _daily_chip_distribution()
│                                            │       （日线三角/均匀 PDF fallback）
│                                            ├─ chip_indicator.py  [新建]
│                                            │   ├─ ChipDistribution(bt.Indicator)
│                                            │   └─ TurnoverChipFactor(bt.Indicator)
│                                            ├─ qmt_utils_adv.py   [修改]
│                                            │   ├─ field_list 加 turnover_rate
│                                            │   └─ PrevClosePandasData 加 line
│                                            └─ qmt_utils_new.py   [修改]
│                                                └─ 同上
```

### 4.3 双路径设计（分钟线优先，日线回退）

```python
class ChipDistribution(bt.Indicator):
    """
    筹码分布因子。
    通过 data_freq 参数显式指定数据类型，不依赖内部 timeframe 推断：
    - data_freq='1m'：用实际量价累积（跳过三角/均匀 PDF）
    - data_freq='1d'：用三角/均匀分布近似
    """
    lines = ('cyqk_c', 'asr', 'ckdw', 'prp')
    params = (
        ('period', 80),
        ('data_freq', '1m'),  # 显式参数，不使用 self.data.timeframe
    )

    def __init__(self):
        pass

    def next(self):
        if len(self.data) < self.p.period:
            return
        arr = self._collect_window()
        arr = _adapt_columns(arr)  # volume→vol, 补 turnover_rate
        if self.p.data_freq == '1m':
            dist = _minute_chip_distribution(arr)
        else:
            dist = calc_dist_chips(arr, method='triang')
        cf = ChipFactor(float(self.data.close[0]), dist)  # 注意签名: ChipFactor(close, cumpdf)
        self.lines.cyqk_c[0] = cf.get_cyqk_c()
        self.lines.asr[0] = cf.get_asr()
        self.lines.ckdw[0] = cf.get_ckdw()
        self.lines.prp[0] = cf.get_prp()
```

### 4.4 列名适配器（解决 cyq.py 输入契约问题）

```python
def _adapt_columns(df: pd.DataFrame) -> np.ndarray:
    """适配 backtrader 列名到 cyq.py 期望的列名契约。"""
    df = df.rename(columns={'volume': 'vol'})
    if 'turnover_rate' not in df.columns:
        # 从流通股本估算（fallback），或从日线 turnover_rate 按分钟 volume 占比分配
        df['turnover_rate'] = _estimate_turnover(df['vol'], stock_code)
    return df[['close', 'high', 'low', 'vol', 'turnover_rate']].values
```

---

## 5. 文件改动清单（修订后）

| # | 文件 | 改动 | 类型 | 风险 |
|---|------|------|------|------|
| 1 | `backtest/chip_algorithm.py` | 新建：adapter 函数 + 分钟线量价累积 + 日线 PDF fallback | 新增 | 低 |
| 2 | `backtest/chip_indicator.py` | 新建：2 个 `bt.Indicator` 子类，`data_freq` 参数注入 | 新增 | 低 |
| 3 | `backtest/qmt_utils_adv.py` | 下载增加 `turnover_rate` 字段；`PrevClosePandasData` 增加 line；存量缓存需重下载 | 修改 | **中** |
| 4 | `backtest/qmt_utils_new.py` | 同上 | 修改 | **中** |
| 5 | `backtest/rolling_investment_strategy.py` | 可选：注册 chip 因子 | 可选 | 低 |
| — | `stock_data/period=1d/*/data.parquet` | 存量数据不含 `turnover_rate`，需增量重下载 | 数据操作 | **中** |

---

## 6. 不改的部分

- `qlib_cost/` 全部源码：不动，保留 Qlib 原生集成能力
- `backtest/ProfitStrategy.py`：已有 5 版本策略逻辑，chip 因子作为可选增强
- Qlib workflow（`qlib_workflow.py`、`factor_expr.py`、`cyq_ops.py`）：不动

---

## 7. 风险与不确定性

| 风险 | 等级 | 说明 |
|------|------|------|
| 存量数据不含 turnover_rate，需全量重下载 | **高** | `stock_data/period=1d/` 全部缓存需重下载。日线数据量小（~46MB），但全量标的 × 全历史范围仍需一定时间。建议写增量下载脚本（已有数据只补列，不重下全量） |
| 分钟线无复权，除权除息日价格跳跃 | **中** | 影响范围：高分红样本（银行/能源/白酒）。2025–2026 窗口内此类事件有限。建议在 adapter 中增加 `dividend_ratio` 检测逻辑，对除权日的前后分钟 bar 做价格归一化 |
| 分钟线换手率需从日线推导 | **中** | volume 占比线性分配是行业标准近似方法，但高换手率异动日（>20%）分配误差可能放大 |
| 回测中逐 bar 计算 vs 离线批处理的性能差异 | **中** | 离线 numpy/numba 批处理（>1000 bar/s）vs backtrader 逐 bar 调用（~50 bar/s 取决于因子复杂度）。需在实际 Cerebro 环境中测量单次 `next()` 耗时 |
| 因子输出需与 Qlib 侧交叉验证 | 低 | 取同一只股票同一窗口，对比 Qlib 侧 CYQK_C 与 backtrader 侧输出的一致性，作为精度基准 |

---

## 8. 验证计划（新增）

本计划需在实施前执行，用于验证关键假设。所有脚本应为独立可复现的 Python 脚本。

### 8.1 字段贯通检查

```python
# verify_turnover_rate_pipeline.py
# 1. 下载 1 只股票的日线数据（含 turnover_rate）
# 2. 确认 Parquet 文件中存在 turnover_rate 列
# 3. 确认 PrevClosePandasData 可以正常读取
# 4. 确认 self.data.turnover_rate[0] 在 next() 中可访问
```

### 8.2 因子交叉验证

**方案 A（推荐 — 纯 Python 脚本，无 notebook 依赖）**：

```python
# verify_chip_factor_consistency.py
# 1. 从 qlib_cost.scr.cyq import calc_dist_chips, ChipFactor
# 2. 从 backtest.chip_algorithm import _minute_chip_distribution
# 3. 取同一只股票（如 000001.SZ），同一窗口（80天）
# 4. 日线方案：加载日线 Parquet → _adapt_columns → calc_dist_chips → ChipFactor
# 5. 分钟线方案：加载分钟线 Parquet → _minute_chip_distribution → ChipFactor
# 6. 对比 CYQK_C / ASR 输出，计算 Pearson r
# 7. 预期：日线 vs 分钟线 r > 0.80（分布不同但排序方向应一致）
# 8. 日线 vs 日线 r = 1.00（同源算法，应完全一致）
```

**方案 B（备选 — 依赖 qlib_cost notebook 环境）**：

```python
# 方案 A 不依赖 notebook，可直接在 CI 中运行。
# 如需与 notebook 的 Qlib 侧输出对照，可单独执行 qlib_cost/筹码分布因子.ipynb
# 提取其 CYQK_C 值作为 ground truth，与方案 A 输出做三方交叉验证。
```

### 8.3 性能基准

```python
# benchmark_chip_indicator.py
# 1. 创建最小 Cerebro（1 只股票，80 天窗口，分钟线）
# 2. 运行 100 个 bar，测量单次 next() 平均耗时
# 3. 目标：单次 < 50ms（以支持 50 只股票同时回测，每 bar 2.5s 总耗时）
```

---

## 9. 结论

**迁移可行性：可行，但需先完成验证计划（§8）中的三个脚本，确认字段贯通、因子一致性、性能基准后再进入实施。**

关键阻塞项（需在实施前解决）：
1. **存量数据重下载**：`stock_data/period=1d/` 需补 `turnover_rate` 列
2. **cyq.py 列名适配**：需写 adapter（`volume→vol` + 补 `turnover_rate`），不能直接传 backtrader DataFrame
3. **分钟线无复权**：需确认 2025–2026 窗口内除权除息事件的影响范围，评估是否需要在 adapter 中做价格归一化

与初版的关键差异：
- 初版称"可直接复用" → 修订版明确需要 adapter 层
- 初版风险评"低" → 修订版数据链路风险评为"中"
- 初版给出精度数字 → 修订版标注"待实测"，新增验证计划

---

*本报告为立项可行性草案。验证计划（§8）完成后可升级为技术实施方案。*
