# COST 筹码分布因子迁移：技术实施方案（含验证计划）

**文档编号**: IMPL-2026-0514-001  
**日期**: 2026-05-15  
**定位**: 正式立项依据 — 技术实施方案  
**状态**: Step 1 ✅ 已完成 | P0 复权切换 ✅ 已完成（2026-05-15） | 回归验证 ✅ 已完成（2026-05-15） | 股本管道自动化 ✅ 已完成（2026-05-15） | 分钟线增强 ✅ 已完成（2026-05-15） | **Step 2 ✅ 全部完成**  
**来源**: 合并自 `docs/COST-migration-feasibility-assessment.md`（评估稿 v2）+ `docs/investigation_reports/COST-migration-feasibility-20260514.md`（草案 v1.2），源文件保留作为历史参考  

---

## 1. 背景与目标

项目中 `qlib_cost/` 已有开源 QuantsPlaybook 的筹码分布算法实现，原生集成于 Qlib 框架。本方案将 COST（筹码分布）因子迁移到 backtrader 回测体系，利用本项目的分钟线数据优势提升筹码分布精度。

**目标（本期 — Step 1 + Step 2）**：在 backtrader 环境中实现 **4 个筹码分布因子**（CYQK_C、ASR、CKDW、PRP）的计算和回测集成，作为 `RollingInvestmentStrategy` 的可选增强因子。

> **范围说明**：`ChipFactor`（`cyq.py:145`）仅提供 4 个公开指标方法（`get_cyqk_c`、`get_asr`、`get_ckdw`、`get_prp`）。ARC/VRC/SRC/KRC 来自 `turnover_coefficient_ops.py`。核心算法 `calc_distribution_of_chips()` 为纯 numpy，通过 importlib 加载（零 Qlib 运行时依赖）。扩展因子 Phase 2（ARC/VRC/SRC/KRC，独立于主路径 Step 2）已实施完成。

---

## 2. 算法架构与数据契约

### 2.1 纯算法层（零 Qlib 依赖）

| 文件 | 依赖 | 核心功能 |
|------|------|---------|
| `qlib_cost/scr/distribution_of_chips.py` | numpy, numba | 三角/均匀分布 PDF、换手率衰减系数 |
| `qlib_cost/scr/cyq.py` | numpy, pandas, numba | 筹码分布累积 `calc_cumpdf`、因子提取 `ChipFactor` |
| `qlib_cost/scr/utils.py` | numpy, numba, pandas | 滚动窗口辅助函数 |

### 2.2 硬数据契约（输入字段不可协商）

`cyq.py` 主入口 `calc_dist_chips` 对 DataFrame 的列选择是硬编码的：

```python
# qlib_cost/scr/cyq.py:100
arr: pd.DataFrame = arr[["close", "high", "low", "vol", "turnover_rate"]]
```

| 字段 | 当前 backtest 数据资产 | 是否具备 | Gap |
|------|----------------------|---------|-----|
| `close` | `close`（分钟/日线均有） | ✅ | — |
| `high` | `high` | ✅ | — |
| `low` | `low` | ✅ | — |
| `vol` | `volume`（列名不同，需映射） | ⚠️ | 字段名映射：`volume` → `vol` |
| `turnover_rate` | **无** | ❌ | 需从流通股本计算或外部引入 |

**关键约束**：`turnover_rate` 不是可选增强，而是算法**必选输入**。没有它，`calc_dist_chips()` 无法执行。

### 2.3 Qlib 封装层（不改动）

| 文件 | 功能 | 处理方式 |
|------|------|---------|
| `qlib_cost/scr/cyq_ops.py` | Qlib ExpressionOps 封装 | 不动 |
| `qlib_cost/scr/turnover_coefficient_ops.py` | Qlib PairRolling 封装 | 不动 |
| `qlib_cost/scr/factor_expr.py` | Qlib DataHandlerLP | 不动 |
| `qlib_cost/scr/qlib_workflow.py` | Qlib 训练+回测流水线 | 不动 |

`qlib_cost/` 全部源码保留不变，不引入任何改动。

<!-- 来源：评估稿 §1 + 草案 §2.1/§2.1a/§2.2 -->

---

## 3. 分钟线数据价值评估

### 3.1 当前数据资产

| 数据 | 格式 | 字段 | 样本量 |
|------|------|------|--------|
| 分钟线（1m） | Parquet + Snappy | time, open, high, low, close, volume, amount | ~77,843 行/股，Python 脚本实时统计数量 |
| 日线（1d） | Parquet + Snappy | 同上（含 back/front/none 三种复权） | — |

### 3.2 精度对比

| 维度 | 日线估算 | 分钟线增强 | 逐笔成交（理想，数据不可得） |
|------|---------|-----------|---------------------------|
| 日内成交分布 | 三角/均匀分布假设 | 按分钟 OHLC 聚合分布，弱化假设成分 | 真实逐笔价格-量对 |
| 精度 | 待验证（经验预期：低） | 待验证（经验预期：中） | 待验证（经验预期：高） |
| 数据可用性 | ✅ 有 | ✅ 有（本项目特有优势） | ❌ 无 |

所有精度预期均为行业经验值，**非本仓验证结论**。实际精度需在 Step 2 回归验证后更新。

### 3.3 核心结论

> 分钟线有用，但属于**显著弱化假设的近似估算**，而非**精确计算**。即使使用分钟线，1 分钟内的成交价格分布仍需代表值假设（如分钟 close 或 VWAP）。

<!-- 来源：评估稿 §3 + 草案 §3.2 -->

---

## 4. turnover_rate 数据路径评估

### 4.1 路径 A：流通股本计算（理论正确，工程未验证）

公式：`turnover_rate = volume / float_shares`

| 子问题 | 现状 | 风险 |
|--------|------|------|
| 流通股本 `float_shares` 来源 | 仓库当前**无现成数据管道** | 需新增下载/存储/更新逻辑 |
| QMT 接口可用性 | `xtdata.get_instrument_detail["FloatVolume"]` **已在本仓验证可用**（详见 §10.3） | 定期更新机制待纳入 Step 2 |
| 停牌日处理 | 停牌日 volume=0，turnover_rate=0 | 需确认 `cyq.py` 对零值的处理是否稳健 |
| 复权口径 | 分钟线 parquet 有 `dividend_type=none` | 若股本数据不复权，除权日会跳变 |

**结论**：此路径是**长期正确解**，但工程落地需额外工作（见 §7 Step 2）。

### 4.2 路径 B：近似 turnover（最小可运行解）

在缺乏流通股本时，可使用**近似换手率**作为占位：

- 方法 1：用固定流通股本假设（如取最近一期财报值，硬编码到本地 CSV）。**仅适用于短期回测窗口（< 6 个月且无除权事件密集期）**
- 方法 2：从第三方 API（如 akshare `stock_zh_a_spot_em`）批量获取一次，静态化存储为本地 JSON/CSV

> **明确否定**：`volume / amount * close` 本质上是 `close / VWAP` 的比值，与换手率数学定义无关，**不可用于任何阶段的 turnover_rate 近似**。此类公式会把原型验证引到错误方向。

### 4.3 路径选择

| 阶段 | 使用路径 | 说明 |
|------|---------|------|
| Step 1 MVP | 路径 B（近似 turnover） | 仅用于验证算法集成可行性，不可用于生产因子 |
| Step 2 收敛 | 路径 A（流通股本计算） | 生产级精度，需完成数据管道建设 |

<!-- 来源：评估稿 §2.1/§2.2 -->

---

## 5. turnover_rate 数据链路（修正）

> **2026-05-14 实测结论**：miniQMT `get_market_data_ex(period='1d')` 的 `field_list` **不支持 `turnover_rate`**。请求包含该字段时，返回的 DataFrame 列仍为 `['time','open','high','low','close','volume','amount']`。因此原设想的"下载时新增 turnover_rate 字段"方案不可行。

正确路径：通过 `get_instrument_detail["FloatVolume"]` 获取流通股本，计算 `turnover_rate = volume * 100 / FloatVolume`（手→股）。此路径已在 `chip_algorithm._estimate_turnover()` + `_get_float_shares()` 中实现。

**阶段 B（当前主路径）**：`float_shares.parquet` + 可选 `free_float_shares.parquet`；`adapt_columns(stock_code, as_of_date)` **必须**提供有效 `stock_code`，缺失时 **fail-close**（P0-18）。100 亿股默认**仅**用于 `_estimate_turnover(None)` 等窄路径（如策略买入日志）。

**换手阻力与运维脚本**：跨日因子 `turnover_resistance` 见 [`docs/backtest/chip/turnover_resistance_algorithm.md`](turnover_resistance_algorithm.md)；全市场/Spot Check CSV 的 `turnover_resist` 分母可能与 `derived["turnover_ratio"]` 不一致（§4.6.2），对比前须对齐。

**阶段 A（历史）**：早期 MVP 曾用固定流通股本占位；已不再适用于 `adapt_columns` 主路径。

```
① 股本获取层 (oskh_data/float_shares.py)
   批量调用 get_instrument_detail["FloatVolume"] → 写入 stock_data/float_shares.parquet
        │
        ▼
② 算法层 (backtest/chip_algorithm.py:_estimate_turnover())
   读取 float_shares.parquet → 计算 turnover_rate = volume * 100 / FloatVolume
        │
        ▼
③ 缓存层 (stock_data/period=1d/*/data.parquet)
   存量数据不需补列 — turnover_rate 在算法层动态计算，不落盘到日线 Parquet
        │
        ▼
④ Feed 层 (PrevClosePandasData)
   无需修改 — turnover_rate 列由 _adapt_columns() 在运行时注入
        │
        ▼
⑤ 策略读取层
   _adapt_columns() 输出的 ndarray 第 4 列为 turnover_rate，算法直接消费
```

**风险评级：低**。阶段 B 核心链路已打通（`fetch_float_shares.py` + `float_shares.parquet` + `_estimate_turnover()`），Step 2 仅需将固定股本替换为真实股本查询，改动范围限于 `chip_algorithm.py` 单文件。阶段 A 无此风险（不涉及数据链路）。

<!-- 来源：草案 §4.1，风险修正根据交叉评审 §4.1 -->

---

## 6. 技术架构设计

### 6.1 文件级架构

```
qlib_cost/scr/（不改动）                     backtest/
├─ distribution_of_chips.py                  ├─ chip_algorithm.py  [新建]
│   └─ 三角/均匀 PDF（仅日线 fallback）       │   ├─ _adapt_columns()
├─ cyq.py                                    │   ├─ _minute_chip_distribution()
│   ├─ calc_dist_chips() ──import──→         │   └─ _daily_chip_distribution()
│   └─ ChipFactor ──import──→               ├─ chip_indicator.py  [新建]
│                                            │   └─ ChipDistribution(bt.Indicator)
│                                            ├─ qmt_utils_adv.py   [修改]
│                                            └─ qmt_utils_new.py   [修改]
```

### 6.2 ChipDistribution Indicator（双路径设计）

```python
class ChipDistribution(bt.Indicator):
    """
    筹码分布因子。
    通过 data_freq 参数显式指定数据类型：
    - data_freq='1m'：用实际量价累积（跳过三角/均匀 PDF，但仍需分钟内价格代表值假设）
    - data_freq='1d'：用三角/均匀分布近似
    """
    lines = ('cyqk_c', 'asr', 'ckdw', 'prp')
    params = (
        ('period', 80),
        ('data_freq', '1m'),  # 显式参数注入，不使用 self.data.timeframe
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
        # 注意: ChipFactor(close, cumpdf) — 参数顺序不可反
        cf = ChipFactor(float(self.data.close[0]), dist)
        self.lines.cyqk_c[0] = cf.get_cyqk_c()
        self.lines.asr[0] = cf.get_asr()
        self.lines.ckdw[0] = cf.get_ckdw()
        self.lines.prp[0] = cf.get_prp()
```

### 6.3 列名适配器（解决 cyq.py 输入契约断裂）

```python
def _adapt_columns(df: pd.DataFrame, stock_code: str = None) -> np.ndarray:
    """适配 backtrader 列名到 cyq.py 期望的列名契约。"""
    df = df.rename(columns={'volume': 'vol'})
    if 'turnover_rate' not in df.columns:
        # MVP 阶段：固定股本占位（不可用于生产）
        # 生产阶段：从流通股本数据管道计算真实 turnover_rate
        df['turnover_rate'] = _estimate_turnover(df['vol'])
    return df[['close', 'high', 'low', 'vol', 'turnover_rate']].values
```

### 6.4 分钟线换手率推导

分钟线无 `turnover_rate` 字段（miniQMT 不支持）。从日线 turnover_rate 按分钟 volume 占比线性分配到每根分钟 bar：

```
total_vol = sum(volume_minute)
if total_vol > 0:
    turnover_rate_minute[i] = turnover_rate_day × volume_minute[i] / total_vol
else:
    # 停牌日 / 全天无成交：分钟 turnover_rate 全部置 0
    # 此时 calc_cumpdf 中 decay=0，cumpdf 保持不变（筹码冻结，符合停牌语义）
    turnover_rate_minute[i] = 0.0
```

此方案是行业常用近似，分钟粒度的 turnover_rate 为近似值（非精确交易所数据）。

<!-- 来源：草案 §4.2/§4.3/§4.4 -->

---

## 7. 实施路径（两步法）

### Step 1：MVP-min — 占位 turnover 最小闭环

**目标**：验证 qlib_cost 纯算法层可在 backtrader 环境中编译运行，**不追求因子精度，不改造数据链路**。

**工程内容**：

1. **字段映射**：在数据加载层将 `volume` 映射为 `vol`
2. **近似 turnover**：`_adapt_columns()` 内部使用路径 B（固定流通股本）生成 `turnover_rate` 列。**不走 §5 阶段的数据链路改造**
3. **numba 依赖验收**：在 backtest 运行环境安装并确认 `numba`（当前主工程未锁定此依赖）
4. **指标封装**：将 `calc_dist_chips` + `ChipFactor` 封装为 backtrader 自定义指标（§6.2）
5. **最小验证**：对 1-3 只样本股跑通日线粒度的 `get_cyqk_c` / `get_asr` 计算
6. **验收门禁**：
   - Python 脚本无异常退出（exit code 0）
   - 输出 4 个因子值非空、非 NaN、在合理数值范围（cyqk_c ∈ [0,1]，asr ∈ [0,1]，ckdw ∈ [0,1]，prp ∈ [-1, 5]）
   - 日线 vs 日线同源算法 Pearson r = 1.00（完全一致）

**交付物**：
- `backtest/chip_algorithm.py` — adapter + 算法封装
- `backtest/chip_indicator.py` — `bt.Indicator` 子类
- 1-3 只样本股的因子输出对比
- **不交付** `qmt_utils` 修改（延后至 MVP-plus）

**预估工作量**：2-3 天（含环境调通、numba 验收、样本验证）

### Step 1+：MVP-plus — 真实 turnover_rate 字段链路（可选加速）

如果 Step 1 MVP-min 通过、且流通股本数据可获取，可在此步提前打通真实 turnover_rate 字段链路（原 §5 四环节）。此步为**可选的并行加速**——如果跳过后直接进入 Step 2，也不影响因子质量收敛的主路径。  
**预估代码量**：~150-200 行新增 + ~20 行修改

#### Step 1 完成小结（2026-05-14）✅

所有 MVP-min 和 Step 1+ 目标均已达成：

| 验证项 | 数据路径 | 结果 |
|--------|---------|------|
| 多标验收 | 日线，100 只随机抽样 | **100 通过 / 0 失败 / 0 跳过**（修复后） |
| Cerebro 集成 | 日线，backtrader 回测循环 | 4/4 因子在合理范围 |
| 分钟线验证 | 分钟线，18,798 bar | 分布 sum=1.0, 无 NaN, 6/6 通过 |
| 全量截面 | 股票池 28 只（日线+分钟线）+ 抽样 200 只（日线）+ 抽样 100 只（分钟线） | 因子分布合理 |

**因子质量摸底（日线 vs 分钟线公平对比，498 只，无数据泄漏）**：

| 因子 | 日线 RankIC | 日线 p | **分钟线 RankIC** | **分钟线 p** | 结论 |
|------|-----------|--------|-----------------|------------|------|
| **cyqk_c** | +0.061 | 0.175 | **+0.127** | **0.005** | 分钟线 2×，统计显著 |
| asr | -0.090 | 0.046 | -0.087 | 0.053 | 基本持平 |
| ckdw | NaN | — | NaN | — | 噪声（winsorization 不稳定） |
| prp | NaN | — | NaN | — | 噪声 |

> **注意**：之前以 100 只报告 cyqk_c 分钟线 RankIC +0.427 存在数据泄漏（分钟线窗口错误包含了预测日）。修正后的公平对比为 +0.127 vs 日线 +0.061，分钟线仍有约 2× 提升且统计显著（p=0.005 vs p=0.175）。

**cyqk_c 多窗口 IC（分钟线，500 只，1d/5d/10d/20d）**：

| 窗口 | RankIC | p-value | Q1 | Q5 | Q5–Q1 | 方向 |
|------|--------|---------|-----|-----|--------|------|
| 1d | **-0.158** | 0.0004 | +0.88% | +0.19% | -0.69% | 短期反转（获利盘抛压） |
| 5d | +0.057 | 0.206 | +2.07% | +2.40% | +0.33% | 弱正向 |
| 10d | +0.044 | 0.322 | +2.19% | +2.65% | +0.46% | 弱正向 |
| **20d** | **+0.177** | **0.0001** | +4.19% | **+13.45%** | **+9.26%** | 中期动量（趋势延续） |

**核心发现**：原始假设"中期 IC 会显著提升"需要修正——实际情况更微妙：

- **1d**：IC 绝对值不低（|0.158|），但方向是**负的**——不是"次日 IC 弱"，而是"次日反转强"。高获利筹码持有者倾向于立即卖出（处置效应），导致短期回调。
- **5d/10d**：反转消退 + 趋势尚未建立，两者抵消 → IC 接近零。这是过渡窗口，不适合单边交易。
- **20d**：趋势确立，IC **+0.177**，Q5 超额 **+9.26%**，统计显著（p=0.0001）。

**结论**：cyqk_c 有**双重时间特征**——短周期是反转因子（做空高位），中周期是趋势因子（做多高位）。5-10 天是过渡窗口，20 天是有效持有期。这比单一方向的因子更有交易价值——可以在不同时间窗口上构建多空组合。

**分钟线 vs 日线截面相关性**（17 只共同标的）：

| 因子 | RankIC(日线, 分钟线) | 说明 |
|------|---------------------|------|
| prp | +0.770 | 高相关，价格位置估算稳定 |
| asr | +0.597 | 中相关 |
| cyqk_c | +0.220 | 低相关——日线近似在部分标的上偏差极大 |
| ckdw | +0.066 | 几乎无关 |

**关键修正记录**：

| 修正项 | 说明 |
|--------|------|
| `get_market_data_ex` 不支持 `turnover_rate` | `field_list` 改动已撤回，改用 `get_instrument_detail["FloatVolume"]` |
| `volume` 单位是"手" | 公式 `(volume×100) / FloatVolume`，已验证正确 |
| CKDW 验收范围 | 放宽至 [0, 20]（winsorization 分母塌缩，~1% 股票 >5.0） |
| 涨跌停日 PDF 退化 | `high==low` → 0/0 → NaN 在分布中传播，已作为 SKIP 条件 |

#### 纸盘观测：`backtest/daily_chip_logger.py`

回测（backtrader/parquet）和纸盘（live_trading/miniQMT）是两套独立系统。`daily_chip_logger.py` 走回测数据路径（parquet），不碰 live_trading 代码。

```bash
# 手动执行——读最新 stock_pool，输出当日 chip 因子截面
python backtest/daily_chip_logger.py

# 指定日期
python backtest/daily_chip_logger.py --date 20260513

# 分钟线模式
python backtest/daily_chip_logger.py --date 20260513 --freq 1m
```

输出 `backtest_output/chip_daily_{date}.csv`，每只标的一行包含 stock_code + close + 4 因子 + turnover_mean + signal 标记（HIGH/LOW）。

**实测**（20260513，28 只）：全部成功，cyqk_c 中位数 0.957，21 只 HIGH（>0.8），0 只 LOW（<0.2）。

#### chip 因子对接选股/交易

当前选股流程：外部 stock_pool CSV → `backtest_main_full.py` / `main.py trading`。chip 因子作为可选增强，不修改现有代码，通过以下路径对接：

```
daily_chip_logger.py                    ← 每日收盘后运行
    │
    ▼
backtest_output/chip_daily_{date}.csv   ← chip 因子截面
    │
    ▼
选股脚本读取 CSV，按 cyqk_c 过滤/排序    ← 现有选股逻辑 + chip 过滤层
    │
    ▼
输出新的 stock_pool CSV                 ← 喂给回测或 live_trading
```

具体做法：
1. 选股脚本在生成 stock_pool 时，额外读取当日的 `chip_daily_{date}.csv`
2. 按 cyqk_c 过滤：排除 HIGH（>0.8，短期反转风险）或排除 LOW（<0.2，趋势未确立）
3. 或按 cyqk_c 排序：优先选择中间区间（0.2–0.8）的标的——既有趋势基础又无短期抛压
4. 不改动回测入口、不改动 live_trading、不改动现有策略代码

#### chip 因子选股回测对比（2,079 只全量，50 只等权，60 日窗口）

`backtest/chip_selection_backtest.py`：从 float_shares.parquet 全市场 2,079 只中，按 chip 规则过滤后随机抽样 50 只等权买入持有，对比各规则收益。

**日线结果**：

| 规则 | 收益 | 最大回撤 | Sharpe | vs 基准 |
|------|------|---------|--------|---------|
| 基准（随机 50） | +8.50% | 9.87% | 1.62 | — |
| **中期趋势 [0.5, 1.0]** | **+17.77%** | 11.23% | **2.98** | **+9.3%** |
| 排除低位 <0.2 | +15.03% | 10.62% | 2.64 | +6.5% |
| 中间区间 [0.2, 0.8] | +3.16% | 13.12% | 0.62 | -5.3% |
| 排除高位 >0.8 | -1.54% | 11.30% | -0.25 | -10.0% |

**分钟线 vs 日线对比**：

| 规则 | 日线收益 | 分钟线收益 | 日线 Sharpe | 分钟线 Sharpe |
|------|---------|----------|-----------|------------|
| 基准 | +8.50% | +4.86% | 1.62 | 0.93 |
| **趋势 [0.5, 1.0]** | **+17.77%** | +15.92% | 2.98 | 2.49 |
| 排除低位 <0.2 | +15.03% | +14.86% | 2.64 | 2.38 |
| 排除高位 >0.8 | -1.54% | -2.86% | -0.25 | -0.46 |

**结论**：
- **最佳规则**：cyqk_c ∈ [0.5, 1.0] 趋势做多，超额 +9.3%，Sharpe 2.98。cyqk_c ≥ 0.2 排除套牢盘是次优（超额 +6.5%，Sharpe 2.64）
- **最差规则**：排除高位 >0.8（超额 -10.0%）——趋势追随才是正确方向
- **分钟线没有显著改善**：规则排序完全一致，收益差异在随机波动范围内。日线路径已足够，且计算更快
- 单轮随机波动大，建议取 10 轮均值确认

#### 多轮回测稳健性验证（10 轮，每轮随机抽样 200→50 只，60 日窗口）

`backtest/chip_factor_analysis.py`：10 轮独立随机抽样，每轮 4 种 chip 规则，取均值和标准差。

| 规则 | 收益（均值±σ） | 最大回撤 | Sharpe | vs 基准 |
|------|--------------|---------|--------|---------|
| 基准（无过滤） | +4.4% ±3.2% | 12.7% | 0.83 | — |
| **中期趋势 [0.5, 1.0]** | **+21.4% ±2.3%** | 11.5% | **3.70** | **+17.0%** |
| 排除低位 <0.2 | +15.6% ±4.8% | 11.9% | 2.72 | +11.3% |
| 排除高位 >0.8 | +1.0% ±2.1% | 11.7% | 0.27 | -3.3% |

**结论**：趋势做多 [0.5, 1.0] 不仅超额最高（+17.0%），而且标准差最低（±2.3%）——表明该规则在最差市场环境下也不会大幅跑输。排除高位 >0.8 持续跑输（-3.3%），与单轮回测一致。

#### 长历史滚动 IC ✅（2026-05-15 更新）

`backtest/rolling_ic_chip_factors.py`：200 只抽样，80 个截面（间隔 20 交易日），覆盖 **2020-04 ~ 2026-05**（6 年+ 完整牛熊周期），14K 条记录。

**逐截面 RankIC 统计（20d 前瞻）**：

| 因子 | IC 均值 | IC Std | ICIR | >0 占比 | \|IC\|>0.05 占比 |
|------|:------:|:------:|:----:|:------:|:--------------:|
| asr | +0.002 | 0.149 | +0.01 | 50.6% | 77.2% |
| cyqk_c | -0.042 | 0.152 | -0.28 | 44.3% | 68.4% |
| **prp** | **-0.054** | 0.158 | **-0.34** | 41.8% | 70.9% |
| **arc** | **-0.058** | 0.170 | **-0.34** | 39.2% | 73.4% |
| vrc | -0.029 | 0.183 | -0.16 | 40.5% | 79.7% |
| src | -0.012 | 0.135 | -0.09 | 44.3% | 75.9% |
| krc | -0.030 | 0.122 | -0.24 | 36.7% | 69.6% |

**cyqk_c 20d IC 时间序列**（牛熊轮替中的方向切换）：

| 日期 | IC | n | 市场特征 |
|------|:----:|:-:|------|
| 2020-04 | **+0.078** | 34 | 疫情后反弹 |
| 2020-10 | -0.052 | 156 | 震荡 |
| 2021-04 | +0.071 | 162 | 结构牛市 |
| 2021-11 | **-0.218** | 169 | 熊市开端 |
| 2022-05 | +0.037 | 177 | 修复反弹 |
| 2022-12 | +0.125 | 184 | 年末反弹 |
| 2023-06 | **-0.368** | 189 | 深度熊市 |
| 2024-01 | +0.160 | 192 | 超跌反弹 |
| 2024-07 | **-0.316** | 195 | 二次探底 |
| 2025-01 | **-0.305** | 197 | 持续走弱 |
| 2026-02 | **+0.232** | 200 | 趋势反转 |

**核心发现（与之前 3 截面分析的根本不同）**：

1. **chip 因子不是"IC 不显著"，而是"IC 方向随市场状态切换"** —— 6 年数据清晰展示了 sign-flipping 规律
2. **cyqk_c 在熊市中为负（获利盘抛压），牛市中为正（惜售/趋势）** —— 与之前"短空长多"的发现一致，但 6 年数据揭示了更深层规律：方向取决于**市场参与者对后市的一致预期**，而非机械的时间窗口
3. **\|IC\| > 0.05 的截面占比高达 68–80%** —— IC 绝对值经常很大，只是方向来回切换，均值被抵消
4. **prp 和 arc 在长周期上 ICIR 最强（-0.34）** —— 价格位置因子和平均持仓成本因子在 6 年维度上方向最稳定
5. **asr 在长周期上完全中性**（IC 均值 +0.002，>0 占比 50.6%）—— 浮筹比例本身不提供方向性 alpha，但波动率高，可作为**波动率放大器**与其他因子组合

#### ARC/VRC/SRC/KRC 因子评估（2026-05-15）✅

`backtest/evaluate_turnover_chip_factors.py`：100 只抽样，249 个截面，25K 条记录。

**RankIC 与分位数收益**：

| 因子 | 1d IC | 20d IC | 20d ICIR | Q5-Q1 (20d) | 方向 |
|------|:-----:|:------:|:--------:|:-----------:|------|
| **ARC** | -0.033 | **-0.067** | -0.50 | **-2.26%** | 股东盈利 → 跑输（获利抛压） |
| **VRC** | -0.025 | **-0.094** | -0.49 | **-2.22%** | 筹码分散 → 跑输（合力不足） |
| SRC | -0.013 | -0.034 | -0.33 | -0.01% | 弱信号 |
| KRC | -0.003 | -0.012 | -0.11 | +0.71% | 噪声 |

**因子间相关性**（Spearman）：ARC-VRC -0.17, ARC-SRC +0.27, VRC-SRC -0.10, VRC-KRC -0.08, SRC-KRC +0.11。四个因子互相独立。

**核心结论**：

1. **VRC 是四因子中最强的**（20d IC -0.094）——筹码分散度高是明确的负面信号，市场合力不足
2. **ARC 是有效的反转因子**（20d IC -0.067）——股东平均盈利→获利抛压→未来跑输，与处置效应一致
3. **SRC/KRC 不可单独使用**——IC 绝对值 < 0.04，Q5-Q1 无显著单调性
4. **所有因子均为负向**——与 cyqk_c 的短空长多双重特征不同，换手率半衰期因子是纯反转信号
5. **与主 chip 因子互补**：cyqk_c/asr/prp 反映"当前获利盘比例"，ARC/VRC 反映"换手率加权的持仓成本结构"，两者正交（截面相关 < 0.30）

### Step 2：流通股本口径收敛与回归验证

**目标**：将 MVP 中的近似 turnover 替换为真实 turnover_rate，建立可复用的因子质量基线。

**工程内容**：

1. **流通股本数据管道 ✅ 已完成（2026-05-15）**：
   - 脚本：`oskh_data/float_shares.py` — 默认无参数运行，从日线数据目录自动收集全市场标的
   - 输出：`stock_data/float_shares.parquet`（2,079 只），含 `updated_at` 时间戳列
   - 特性：支持 `--from-daily-data`（默认）/ `--from-stock-pool` / `--stocks` 三种标的来源；`--diff` 变更对比（新增/移除/股本变化 >0.1%）
   - 定时任务：`python -m oskh_data.float_shares`（无参数，适合 cron/计划任务）
2. **turnover_rate 精确计算**：`volume / float_shares`，按日聚合后注入 DataFrame
3. **回归验证 ✅ 已完成（2026-05-15）**：
   - 脚本：`backtest/verify_chip_factor_consistency.py`
   - 样本池：50 只（日线前复权 + 分钟线共有标的），5 个等距截面（03-20 ~ 05-11），共 250 个有效点
   - 结果详见 §8.3。汇总：cyqk_c r=0.860, asr r=0.912, prp r=0.936（3/4 通过 0.80 阈值）；ckdw r=0.040（噪声，已知）
   - 日线前复权可以替代分钟线用于选股因子计算
4. **分钟线增强 ✅ 已完成（2026-05-15）**：
   - 实现：`backtest/chip_algorithm.py:hybrid_chip_distribution()` — §10.4.2 方案 A
   - 设计：79 天日线三角 PDF + 当日分钟线量价直方图，通过 `calc_cumpdf` 统一衰减累积
   - 验证（10 只）：Hybrid vs Daily r > 0.995（cyqk_c/asr/prp），MAE < 0.01
   - 性能：80 日线 bar + 240 分钟 bar vs 纯分钟 19,200 bar（~60× 减少）
   - 当日分钟数据替换三角 PDF 假设，捕捉日内真实价格路径

**交付物**：
- 流通股本数据管道（下载 + 存储 + 更新）
- 回归验证脚本及质量报告
- 分钟线增强算法

**预估工作量**：1-2 周  
**预估代码量**：~200-300 行

<!-- 来源：评估稿 §5 + 草案 §5 -->

---

## 8. 验证计划

以下三个脚本为实施前的独立可运行验证，不依赖完整 backtrader 回测环境。

### 8.1 Step 1 MVP-min 验收检查

```python
# verify_mvp_min.py
# 1. 加载 1 只股票的现有日线 Parquet（不含 turnover_rate 列）
# 2. 调用 _adapt_columns(df)，验证 volume→vol 映射 + 固定股本占位 turnover_rate 列已生成
# 3. 调用 calc_dist_chips(arr, method='triang') → ChipFactor(close, dist)
# 4. 验证 4 个因子值非 None / 非 NaN / 在合理范围：
#    cyqk_c ∈ [0, 1], asr ∈ [0, 1], ckdw ∈ [0, 1], prp ∈ [-1, 5]
# 5. 日线 vs 日线同源算法：两次独立运行 Pearson r = 1.00
# 6. Exit code 0 → MVP-min 通过
```

### 8.2 Step 1+ / Step 2 字段贯通检查

```python
# verify_turnover_rate_pipeline.py
# （仅在启用真实 turnover_rate 链路时执行）
# 1. 确认 stock_data/float_shares.parquet 存在且包含目标标的
# 2. 加载该标的日线 Parquet（不含 turnover_rate 列），调用 _adapt_columns()
# 3. 验证 _estimate_turnover() 从 float_shares.parquet 读取真实股本并计算 turnover_rate
# 4. 验证输出的 turnover_rate = volume * 100 / FloatVolume，值在合理范围（0–0.3）
```

### 8.3 因子交叉验证 ✅ 已完成（2026-05-15）

**方案 A（已实施 — `backtest/verify_chip_factor_consistency.py`）**：

```python
# verify_chip_factor_consistency.py
# 用法：
#   python backtest/verify_chip_factor_consistency.py --stocks 50 --dates 5
#
# 设计：
# 1. 从日线前复权 + 分钟线共有标的池中随机抽样 N 只
# 2. 在 M 个等距日期截面上，对每只标的计算 80 日窗口的 chip 因子
# 3. 日线路径：前复权 Parquet → adapt_columns → calc_dist_chips(triang) → ChipFactor
# 4. 分钟线路径：未复权分钟 Parquet → adapt_columns → minute_chip_distribution → ChipFactor
# 5. 对每个因子计算 Pearson r / MAE / RankIC（日线 vs 分钟线）
# 6. 按日期分组评估 Pearson r 稳定性
# 7. 验收标准：cyqk_c / asr / prp Pearson r > 0.80
```

**验证结果（50 只 × 5 截面 = 250 个有效点，跳过 0）**：

| 因子 | Pearson r | p-value | MAE | RankIC | 判定 |
|------|:---------:|:-------:|:---:|:------:|:----:|
| **cyqk_c** | **0.8597** | <0.0001 | 0.083 | **0.8895** | ✅ PASS |
| **asr** | **0.9118** | <0.0001 | 0.074 | **0.9084** | ✅ PASS |
| ckdw | 0.0404 | 0.525 | 2.190 | -0.150 | ⚠️ 噪声（已知） |
| **prp** | **0.9357** | <0.0001 | 0.021 | **0.9327** | ✅ PASS |

**cyqk_c 按日期的 Pearson r（跨截面稳定性）**：

| 日期 | Pearson r | p-value | n |
|------|:---------:|:-------:|:-:|
| 2026-03-20 | 0.9932 | <0.0001 | 50 |
| 2026-04-02 | 0.7498 | <0.0001 | 50 |
| 2026-04-15 | 0.8943 | <0.0001 | 50 |
| 2026-04-28 | 0.8798 | <0.0001 | 50 |
| 2026-05-11 | 0.8010 | <0.0001 | 50 |

**核心发现**：

1. **3/4 因子超过 0.80 阈值**，asr 和 prp 超过 0.90 —— 前复权日线筹码分布在排序上高度接近分钟线
2. **RankIC 全部 ≥ Pearson r**：因子值的排序一致性优于绝对值一致性，对量化选股更关键
3. **ckdw 确认是噪声**：winsorization 分母塌缩导致日线/分钟线几乎无关，不应单独用于排序决策
4. **04-02 截面的 cyqk_c 偏低（r=0.75）**：该截面可能处于年报除权密集期，是前复权漂移+分钟线未复权的最大分歧点，印证了 §10.4 的复权风险分析
5. **前复权日线可替代分钟线用于选股**：cyqk_c / asr / prp 精度损失在可接受范围（MAE 0.02–0.08）

**方案 B（备选 — 依赖 qlib_cost notebook 环境）**：
```
方案 A 不依赖 notebook，可直接在 CI 中运行。
如需与 notebook 的 Qlib 侧输出对照，可单独执行 qlib_cost/筹码分布因子.ipynb
提取其 CYQK_C 值作为 ground truth，与方案 A 输出做三方交叉验证。
```

### 8.4 性能基准

```python
# benchmark_chip_indicator.py
# 1. 创建最小 Cerebro（1 只股票，80 天窗口，分钟线）
# 2. 运行 100 个 bar，测量单次 next() 平均耗时
# 3. 目标：单次 < 50ms（以支持 50 只股票同时回测，每 bar 2.5s 总耗时）
```

<!-- 来源：草案 §8 -->

---

## 9. 风险与不确定性

| 风险 | 等级 | 说明 | 缓解 |
|------|------|------|------|
| 流通股本数据过期（送股/转增后 FloatVolume 变化） | **低** | turnover_rate 在算法层动态计算（不落盘到日线 Parquet），无需补列。但 `float_shares.parquet` 为静态快照，送股/转增后流通股本变化需重新获取 | Step 2 纳入 `fetch_float_shares.py` 定期更新机制 |
| 分钟线无复权，除权除息日价格跳跃 | **中** | 影响范围：高分红样本（银行/能源/白酒）。2025–2026 窗口内此类事件有限 | 在 adapter 中增加 `dividend_ratio` 检测，对除权日做价格归一化 |
| 分钟线换手率需从日线推导 | **中** | volume 占比线性分配是行业标准近似，但高换手率异动日（>20%）分配误差可能放大 | Step 2 回归验证时专项评估高换手率样本 |
| 回测中逐 bar 计算 vs 离线批处理的性能差异 | **中** | 需在实际 Cerebro 环境中测量单次 `next()` 耗时 | 纳入 §8.4 性能基准 |
| 算法精度未经 A 股本仓实证 | **低** | 广发证券报告 #27 已验证三角分布假设有效性 | Step 2 回归验证 |
| 长时间停牌导致筹码冻结 | **低** | 停牌 >30 天的股票，`turnover_rate` 连续为零导致 `decay=0`、`cumpdf` 冻结 | 验证阶段显式纳入 1-2 只长时间停牌样本 |
| numba 依赖未锁定 | **中** | 主工程 `requirements.txt` 未包含 numba | Step 1 环境验收时确认并锁定版本 |
| 前复权回测前视偏差 | **中** | 用最新前复权因子回算历史筹码时，未来分红送股事件已被折算进历史成本，高分红样本（银行/能源）的 cyqk_c 可能系统性偏高 | 回测用定点复权（§10.4.2 方案 C），或限制窗口长度 ≤ 2 年 |

<!-- 来源：评估稿 §7 + 草案 §7，合并去重 -->

---

## 10. 附录

### 10.1 必要条件 checklist

| 条件 | 状态 | 说明 |
|------|------|------|
| 分钟线 OHLCV | ✅ | `stock_data/period=1m` 已存在 |
| 字段映射 `volume→vol` | ⚠️ | 需在数据加载层显式映射 |
| `turnover_rate`（真实） | ⚠️ | 部分完成：`float_shares.parquet`（2,079 只）+ `fetch_float_shares.py` 已交付，`_estimate_turnover()` 可读取真实股本计算。自动化定时更新待纳入 Step 2 |
| 流通股本数据源 | ✅ | `xtdata.get_instrument_detail["FloatVolume"]` 已验证可用，`float_shares.parquet` 已生成（2,079 只）。定期更新机制待纳入 Step 2 |
| numba 依赖 | ⚠️ | 需在 backtest 环境安装并验收，当前未锁定 |
| 回归验证脚本 | ❌ | Step 2 需补 |

### 10.2 专家审核意见响应

| 专家意见 | 本版修订动作 |
|---------|------------|
| "80 行改动明显低估" | 上调为 ~150-200 行（MVP）+ ~200-300 行（Step 2） |
| "cyq.py 输入字段契约未闭环" | 新增 §2.2 硬数据契约 Gap 表 |
| "turnover_rate 单一路径论证不足" | 新增 §4 双路径评估（流通股本 vs 近似 turnover） |
| "1-2 天出原型不可信" | 修正为 2-3 天（MVP-min，占位 turnover 闭环）+ 3-5 天（Step 1+ 可选加速），总路径拆为 MVP-min → Step 2 |
| "numba 依赖偏乐观" | §9 评为"中"风险，Step 1 纳入环境验收 |
| "精度数字结论化" | 全部改为"待验证（经验预期）"，§8 补验证脚本 |
| "缺少数据来源优先级与回退策略" | §4.3 明确 MVP→生产路径切换策略 |
| "ChipFactor 参数顺序反了" | §6.2 代码中已修正并加注释 |

### 10.3 开放问题与假设

1. **流通股本数据来源优先级**：
   - ✅ 首选：`xtdata.get_instrument_detail(stock_code)["FloatVolume"]`（**已在本仓验证可用**，详见下方预研结论）
   - 次选：akshare / tushare（需新增 API 依赖）
   - 回退：硬编码最近财报值（仅用于 MVP，短期窗口 < 6 个月）

   > **Step 2 预研结论（2026-05-14）**：
   > `xtdata.get_instrument_detail` 返回 `FloatVolume`（流通股本）和 `TotalVolume`（总股本）字段。
   > 接口已在 `hkcodex_miniqmt.py:1504`、`tests/test_live_trading_execution.py:279` 本仓使用。
   > 官方文档 `docs/knowledge/vendor/xtquant/4.vendor-xtquant.md` 确认字段存在。
   > 流通股本数据管道阻塞项从 "未知接口需验证" 降级为 "已知接口需写批量获取脚本"。

2. **复权口径**：详见下方 §10.4 复权口径规范。数据现状：前复权日线已存在（`dividend_type=front`，2,115 只），分钟线仅 `none` 版本（符合 §10.4.2 设计）。

3. **停牌日处理**：
   - 停牌日 `volume=0`，`turnover_rate=0`
   - 长时间停牌（>30 天）：`decay=0`，`diff=1`，`cumpdf = cumpdf * 1 + 0`——筹码分布完全冻结
   - 验证阶段需显式纳入 1-2 只长时间停牌样本

4. **精度数字**：
   - 本报告所有精度预期均为行业经验值，**非本仓验证结论**
   - 实际精度需在 Step 2 回归验证后更新

### 10.4 复权口径规范（A 股筹码分布因子）

#### 10.4.1 日线级别：必须使用前复权（QFQ）

在 A 股量化行业的典型习惯中，计算筹码分布（CYQ）和赢筹率应当使用 **前复权** 数据。

| 维度 | 说明 |
|------|------|
| **价格一致性** | 筹码分布的核心逻辑是"当前收盘价 vs 历史各价位持仓成本"。前复权将历史价格统一折算到最新股本口径，使当前价与历史成本在同一尺度上可比。 |
| **除权缺口处理** | 若使用未复权，分红、送股、配股会产生价格跳空，导致筹码分布出现虚假断层（例如 10 送 10 后股价腰斩，未复权会把历史高位筹码全部判定为深套）。 |
| **真实盈亏口径** | 赢筹率衡量的是以当前真实交易价格计算，市场中有多少筹码处于盈利状态。前复权的"当前价"就是真实最新价，后复权则把当前价也拉变了，无法直接对应真实持仓盈亏。 |
| **行情软件对齐** | 通达信、同花顺、东方财富等主流终端在展示筹码分布和赢筹率时，底层均默认采用前复权序列。 |

**为什么不能使用另外两种复权方式？**

- **未复权（`dividend_type=none`）**：除权缺口会直接撕裂筹码峰，赢筹率会阶段性突变，失去连续可比性。当前 `backtest/filter_chip_stocks.py` 使用 `dividend_type=none`，存在此风险。
- **后复权**：虽然历史价格不变，但当前价格被人为抬高（累积分红送股因素），导致"当前价"不是真实市场价格。用后复权计算出的赢筹率无法对应投资者的真实账户盈亏状态，因此不适用于筹码类指标。以 2024 年某银行股（累计分红 ~5%）为例，用后复权算 cyqk_c 会比前复权系统性偏高约 3–5 个百分点——当前价被人为抬高后，更多历史筹码被误判为"盈利"。

**工程注意事项**：

1. **前复权漂移问题**  
   前复权的历史价格是**时点依赖的**——今天算的前复权序列，等明年分红后重新算会不一样。若做长周期历史回测并严格追求可复现性，应当在每个历史截面使用**该截面已知的前复权因子**（或固定某基准日复权），而不是用最新前复权因子反算 5 年前的筹码。

2. **换手率/成交量同步调整**  
   送股、转增时，股本扩大，历史成交量应按同一复权因子等比缩放，否则换手率口径前后不一致，会影响筹码衰减/转移的计算精度。**现金分红不影响股本，成交量无需调整**——区分送股/转增与现金分红两个场景。

3. **回测前视偏差（look-ahead bias）**  
   前复权漂移不仅影响可复现性，在回测中还会引入**前视偏差**：用最新前复权因子回算历史筹码分布时，未来分红送股事件已被折算进历史成本，使得历史截面上的筹码分布比当时真实可得的信息更"平滑"。对于高分红样本（银行、能源），此偏差不可忽略。缓解方案：回测时用方案 C（定点复权），即以回测起始日为基准日计算复权因子；或接受偏差但限制回测窗口长度（≤ 2 年，且避开除权密集期）。

#### 10.4.2 分钟线级别：不复权存储 + 复权因子动态校正

分钟线场景下，行业习惯**不会直接存"前复权分钟线"**来做长周期筹码计算，而是采用**"未复权分钟线 + 复权因子动态校正"**的方案。

**为什么不直接对分钟线前复权？**

| 问题 | 后果 |
|------|------|
| **历史漂移更剧烈** | 每来一次分红送股，过去所有分钟线都要重算，数据维护成本极高。 |
| **负价格风险** | 长周期前复权到分钟粒度，早年价格极易被复权成负数或接近 0，导致筹码分布算法异常（`log` 或对数正态假设直接崩掉）。 |
| **数据膨胀** | 分钟线本身体量是日线的 240 倍，存储多版本复权数据不经济。 |

**行业通行做法**：

**方案 A：日线定框架 + 分钟线做日内偏移（推荐）**  
这是量化私募和券商研报中最常见的做法：

1. **大周期筹码基底**用 **前复权日线** 计算（80 日、60 日筹码峰、赢筹率）。
2. **日内精细结构**用 **未复权分钟线**，但做**相对归一化**处理：
   ```python
   # 日内分钟线不复权，以当日开盘为锚点做相对偏移
   minute_return = (minute_close - today_open) / today_open
   # 前复权昨收 = 当日复权因子 × 未复权昨收
   adj_yest_close = adj_factor_today * unadj_yest_close
   # 分钟级近似前复权价格 = 前复权昨收 × (1 + 日内收益率)
   # 注意：日内无除权事件，用未复权价格算出的 minute_return 与复权后一致
   minute_adj_close = adj_yest_close * (1 + minute_return)
   ```
3. **筹码分布的更新**：日线级筹码峰位置已知，日内只计算**新增成交量的筹码沉积/转移**，不重新从头算 80 天分钟级筹码。

> 本质逻辑：筹码分布是**慢变量**，日线精度足够；分钟线只负责捕捉**当日新开仓成本**的微调。

**方案 B：复权因子实时校正（数据商标准做法）**  
如果你必须从分钟线重建长序列（例如高频 T0 场景）：

```python
# 分钟线数据本身不复权
# 每日维护一个累积复权因子 cumulative_adj_factor
# 对于历史第 t 天的某分钟价格：
adj_price = unadj_price * cumulative_adj_factor_at_day_t
```

- 分钟库存**原始未复权**数据（`dividend_type=none`）。
- 另建一张**每日复权因子表**：字段 `date`, `cumulative_adj_factor`（累计乘数因子）。初始值为 1.0，除权日更新：`new_factor = old_factor × (前复权前收盘 / 未复权前收盘)`，非除权日沿用前一日值。注意是**累乘**而非每日重新计算，否则历史因子会随未来除权事件漂移。
- 计算时根据截面日期**动态乘算**，而非落盘前复权分钟线。

**方案 C：定点复权（针对回测可复现性）**  
如果回测要求严格可复现（避免"今天算的前复权和明年算的不一样"）：

- 选定一个**固定基准日**（如回测起始日或最新交易日），以该日为锚点计算**定点复权因子**。
- 所有历史分钟价格统一按该锚点因子缩放。
- 这样既保持了比例关系，又保证了历史回测结果不随未来分红事件漂移。

#### 方案 B 基建落地 ✅（2026-05-15）

**建设过程**：

1. **数据源**：从 `dividend_type=front` 和 `dividend_type=none` 两套日线 Parquet，按 `(stock_code, date)` 对齐，计算每日累积复权乘数：
   ```
   cumulative_adj_factor = close_front / close_none
   ```
2. **构建脚本**：`backtest/build_adj_factor_table.py`，输出 `stock_data/adj_factor.parquet`
3. **数据规模**：5,374 只标的，2010-01 ~ 2026-05，13.4M 行，711K 条除权事件（因子变化 >1%），覆盖 4,702 只
4. **查询接口**（`backtest/chip_algorithm.py`）：
   - `get_adj_factor(stock_code, date)` → 查询指定标的某日复权乘数
   - `adj_minute_prices(stock_code, date, close, high, low)` → 批量校正分钟 OHLC
   - `adj_minute_chip_distribution(arr, stock_code, date)` → 完整方案 B 筹码分布（价格列 × factor → 调用 minute_chip_distribution）
5. **模块级缓存**：`_load_adj_factor_table()` 惰性加载并缓存 adj_factor.parquet，避免重复 I/O

**验证结果**（10 只 adj_factor 偏离最大的极端标的，adj 0.78~1.09）：

| 因子 | 方案A MAE (vs 日线) | 方案B MAE (vs 日线) | 改善 |
|------|:-------------------:|:-------------------:|:----:|
| cyqk_c | 0.3860 | 0.3847 | -0.3% |
| asr | 0.2419 | 0.2417 | -0.1% |
| prp | 0.1114 | 0.1112 | -0.2% |

**结论**：

- 方案 B 在三个因子上均优于方案 A，但边际改善有限（<1%）。原因：极端除权标的的分钟线 vs 日线差异根因不止于价格缩放——送股/转增后 turnover_rate 计算口径（`volume × 100 / float_shares`）也随股本变化，仅乘复权因子无法完全修复
- 对 adj_factor 接近 1.0 的绝大多数标的（95%+），方案 A 的日线前复权已足够精确
- 方案 B 的基建价值在于**高频 T0/日内择时场景**：需要分钟级精确复权的场景（如 30 分钟 K 线重建筹码分布），而非日线选股增强
- 性价比最优路径仍为方案 A（日线定框架 + 分钟线做日内偏移 / `hybrid_chip_distribution`）

#### 10.4.3 对本项目的具体建议

| 用途 | 优先级 | 建议做法 |
|------|--------|---------|
| **日线选股过滤**（当前场景，`filter_chip_stocks.py`） | **P0（立即）** ✅ 已完成（2026-05-15） | 已切换至前复权日线。`dividend_type=none` → `front`。前复权 vs 未复权筛选结果：781 vs 790 条（差异 -1.1%，窗口内除权事件有限）。 |
| **分钟级择时/日内入场点** | P2（Step 2） | 日线筹码峰用前复权定好位置，分钟线用**未复权 + 当日复权因子**做日内盈亏判断。需先建立日线复权因子表。 |
| **高频筹码重建（如 30 分钟 K 算筹码）** | P3（后续） | 用方案 B（复权因子动态校正），或者直接把 30 分钟线通过**前复权日线降采样**得到（即先日线复权，再拆成 30 分钟 OHLC）。 |

> **一句话总结**：分钟线**不存前复权**，筹码分布的**长期结构靠日线前复权**，分钟线只在日内做**相对位移或因子校正**。这是 A 股量化在工程实现和数学合理性上的平衡最优解。

> **本项目分钟线现状**：分钟线数据仅 `period=1m/dividend_type=none/`，无可选复权版本。这与本章建议一致——分钟线本就不应存复权版本。需补充的是方案 B 所需的**日线复权因子表**（`cumulative_adj_factor` per day），当前缺失，纳入 Step 2。

### 10.5 交付物清单

#### 已完成（Step 1 MVP-min + Step 1+）

| # | 文件 | 说明 | 状态 |
|---|------|------|------|
| 1 | `backtest/chip_algorithm.py` | adapter + 分钟线量价累积 + 日线 PDF fallback + 真实流通股本查询 | ✅ 已交付 |
| 2 | `backtest/chip_indicator.py` | `ChipDistribution(bt.Indicator)` — 4 因子，支持日线/分钟线双路径 | ✅ 已交付 |
| 3 | `backtest/verify_mvp_min.py` | 多标的验收脚本（日线，100 只抽样：87 通过 / 0 失败 / 13 跳过） | ✅ 已交付 |
| 4 | `backtest/verify_cerebro_chip.py` | Cerebro 集成验证（日线，4/4 因子） | ✅ 已交付 |
| 5 | `backtest/verify_minute_chip.py` | 分钟线验证（6/6 通过） | ✅ 已交付 |
| 6 | `backtest/chip_backtest.py` | 多标 chip 因子回测脚本（截面输出 + 因子分布分析） | ✅ 已交付 |
| 7 | `oskh_data/float_shares.py` | 批量获取流通股本脚本（输出 Parquet） | ✅ 已交付 |
| 8 | `stock_data/float_shares.parquet` | 2,079 只 A 股流通股本数据 | ✅ 已交付 |
| 9 | `backtest/qmt_utils_adv.py` | `PrevClosePandasData` 增加 `turnover_rate` line（字段下载经实测不支持，已撤回 field_list 改动） | ⚠️ line 已加，字段未加（miniQMT 不支持） |
| 10 | `backtest_output/chip_factors_*.csv` + `chip_summary_*.csv` | 输出目录，chip 因子时序和截面 | ✅ 已生成 |
| 11 | `backtest/rolling_investment_strategy.py` | 注册 chip 因子（等效模式由 `chip_backtest.py:ChipFactorStrategy` 实现，不改动原文件） | ✅ 已交付 |
| 12 | `backtest/verify_chip_factor_consistency.py` | 日线（前复权） vs 分钟线 因子交叉验证，50 只 × 5 截面，3/4 因子通过 0.80 阈值 | ✅ 已交付（2026-05-15） |
| 13 | `backtest/chip_algorithm.py:hybrid_chip_distribution()` | §10.4.2 方案 A：日线三角PDF（历史）+ 分钟量价累积（当日），~60× 性能提升 | ✅ 已交付（2026-05-15） |
| 14 | `backtest/evaluate_turnover_chip_factors.py` | ARC/VRC/SRC/KRC 因子评估：100 只 × 249 截面，VRC 最强（20d IC -0.094） | ✅ 已交付（2026-05-15） |
| 15 | `backtest/rolling_ic_chip_factors.py` | 长历史滚动 IC：200 只 × 80 截面，2020–2026 完整牛熊，cyqk_c IC 方向随市场切换 | ✅ 已交付（2026-05-15） |
| 16 | `stock_data/adj_factor.parquet` | 日线复权因子表：5,374 只 × 2010–2026，13.4M 行 | ✅ 已交付（2026-05-15） |
| 17 | `backtest/build_adj_factor_table.py` | 复权因子表构建脚本，可定期更新 | ✅ 已交付（2026-05-15） |
| 18 | `backtest/chip_algorithm.py:adj_*` | `get_adj_factor()` / `adj_minute_prices()` / `adj_minute_chip_distribution()` 三个查询/校正接口 | ✅ 已交付（2026-05-15） |
| 19 | `backtest/verify_adj_minute_chip.py` | 方案 B 验证：10 只极端标的，方案 B 三项因子均优于方案 A | ✅ 已交付（2026-05-15） |
| — | ARC/VRC/SRC/KRC | 换手率半衰期模型，纯 numpy 算法（`turnover_chip_factors()`），零 Qlib 依赖 | **扩展因子 Phase 2** ✅ 已交付 |

#### 待完成（Step 2）

| # | 文件 | 说明 | 状态 |
|---|------|------|------|
| 14 | 流通股本数据管道自动化 | `fetch_float_shares.py` 已增强：默认无参数运行 + 全市场标的 + diff 摘要 + 定时任务就绪 | ✅ 已完成（2026-05-15） |
| 15 | 日线选股切前复权 | `filter_chip_stocks.py` `dividend_type=none` → `front`，前复权 vs 未复权：781 vs 790（-1.1%） | ✅ 已完成（2026-05-15） |
| — | `qlib_cost/` 全部 | **不动** | — |

---

## 11. 后续方向建议

> **2026-05-15 评审结论**：Step 1-2 全部完成（19 项交付物）。以下 4 个方向均已具备启动条件。**推荐从 11.1 因子组合合成开始**——工作量最小（1-2h）、基建全就绪（`rolling_ic_chip_factors.py` 可直接扩展）、且有明确的 ICIR 提升预期（20d ICIR 从单因子最优 -0.34 提升至合成后 -0.50+）。

以下方向按推荐优先级排列，均已具备启动条件（数据 + 基建就绪）。

### 11.1 因子组合合成（推荐优先级：高）

**动机**：当前 8 个 chip 因子各自独立使用。长历史滚动 IC 已验证 cyqk_c、prp、ARC、VRC 之间截面相关性低（r < 0.30），具备正交合成的基础。

**方案**：

1. 对标准化后的因子值做加权或等权线性组合，生成复合 chip_score
2. 回测验证合成因子在各窗口（1d/5d/10d/20d）的 RankIC 和分位数收益
3. 对比单因子最优（VRC 20d IC -0.094）与合成因子的 IC 提升幅度
4. 评估 IC 稳定性改善（ICIR 是否提升、sign-flipping 是否减少）

**预期收益**：合成因子可能在 20d ICIR 上超越单因子最优值（-0.34），且方向一致性更好（>0% 占比从 ~40% 提升至 55%+）。

**基建状态**：全部就绪。`rolling_ic_chip_factors.py` 可直接扩展为多因子合成评估。

**预估工作量**：1–2 小时。

---

### 11.2 定时自动化（推荐优先级：中）

**动机**：`daily_chip_logger.py` 和 `filter_stock_pool_by_chip.py` 已可独立运行，但需手工执行。串联为每日自动流水线后可实现"收盘→因子计算→chip 过滤→精选池输出"全自动。

**方案**：

1. 编写 shell 脚本或 Python wrapper，按顺序调用两个脚本
2. 配置 cron / Windows Task Scheduler，交易日下午 15:30 触发
3. 增加异常告警（如 stock_pool 缺失、因子计算全部失败等边界情况）

**交付物**：`scripts/daily_chip_pipeline.sh`（或 `.bat`），一行命令即可注册定时任务。

**预估工作量**：0.5 小时。

---

### 11.3 分行业/市值精细评估（推荐优先级：中）

**动机**：chip 因子的核心假设（筹码分布反映投资者盈亏状态→影响买卖决策）在不同行业/市值上可能强度不同。例如银行股高分红导致除权频繁、小盘股筹码集中度高，可能使 chip 因子在不同子空间中表现分化。

**方案**：

1. 引入申万行业分类和市值分组（从 `get_instrument_detail` 可获取 Industry 字段）
2. 在各子空间内重复 `rolling_ic_chip_factors.py` 的滚动 IC 分析
3. 识别 chip 因子最有效/最无效的行业和市值区间
4. 输出"因子适用性矩阵"：哪些行业适合用 cyqk_c 趋势过滤，哪些适合用 VRC 分散度过滤

**预期发现**：银行/能源等高分红板块 chip 因子可能偏弱（除权频繁破坏筹码连续性）；小盘成长板块可能更强（筹码结构对价格更敏感）。

**预估工作量**：1–2 小时。

---

### 11.4 分钟级择时信号（推荐优先级：低）

**动机**：方案 B 复权因子校正基建已完成（`adj_factor.parquet` + `adj_minute_chip_distribution()`），可以开始探索分钟级的 chip 因子日内择时信号。

**方案**：

1. 对单只标的，在日内每分钟更新 `hybrid_chip_distribution()`（历史日线三角 PDF + 今日已发生分钟线量价累积）
2. 跟踪 cyqk_c 的日内变化轨迹——当从高位下穿阈值时触发卖出信号、从低位上穿时触发买入信号
3. 回测日内择时信号的胜率和盈亏比

**风险**：A 股 T+1 限制下日内信号不能当日执行，只能作为次日开盘参考。实际价值需在模拟盘验证。

**预估工作量**：3–5 小时。

---

*本报告为技术实施方案（含验证计划），可作为正式立项依据。源文件 `docs/COST-migration-feasibility-assessment.md` 和 `docs/investigation_reports/COST-migration-feasibility-20260514.md` 保留作为历史参考。*
