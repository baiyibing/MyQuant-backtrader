# Rust vs Python 换手阻力精度差异排查报告

> 排查日期：2026-06-01
> 排查目标：定位 Rust 版与 Python 版全市场换手阻力计算中 cyqk 差异 >1e-6 的根因

---

## 1. 背景

全市场 4594 只共同股票中，2000+ 只的 cyqk_T 差异超过 1e-6，最大差 0.039。已确认资本数值（`circulating_capital` / `FloatVolume`）完全一致，差异来自算法实现层面。

差异最大的 3 只股票：

| Stock | Rust cyqk_T | Python cyqk_T | diff |
|-------|------------|--------------|------|
| 002374.SZ | 0.5872 | 0.5481 | 0.0391 |
| 000727.SZ | 0.9019 | 0.8641 | 0.0378 |
| 000088.SZ | 0.1599 | 0.1964 | 0.0365 |

## 2. 排查方法

按 `docs/prompts/prompt-rust-python-precision-investigation.md` 要求，对 3 只股票逐环节对比中间值：

1. **窗口对齐**：T/T-1 窗口的起止日期、K 线条数
2. **curpdf（三角分布）**：中间一天的 curpdf 向量，首尾非零 bin
3. **cumpdf（衰减累积）**：最终 cumpdf 向量前 10 bin
4. **cyqk**：winner（收盘价以下筹码量）与 total（总筹码量）

### 2.1 工具

- **Rust 调试二进制**：`turnover-resist/src/debug_precision.rs`（`cargo build --release --bin debug-precision`）
- **Python 调试脚本**：`scripts/legacy/debug_precision.py`（内嵌 Rust 算法的纯 Python 复现，逐环节对比）

### 2.2 逐环节对比结果（002374.SZ）

| 环节 | Rust vs Python (同一数据) | 差异量级 |
|------|--------------------------|---------|
| 窗口对齐 | 完全一致：1001 union_bars，T/T-1 各 1000 天 | 0 |
| 价格网格 `xs` | `n_prices` 相同（499），但 `np.arange` 与 `min_p + i*step` 的浮点值不同 | ~2e-15/bin |
| curpdf | 完全一致（使用 Rust 网格时） | 0 |
| cumpdf | 完全一致（batch 与 manual 循环 max diff = 0） | 0 |
| cyqk winner bins | **219 vs 220**（1 bin 之差） | 0.039 |

## 3. 根因

### 3.1 首次出现 >1e-6 差异的环节：价格网格构建

**`np.arange(min_p, max_p + step, step)`** 与 Rust 的 **`min_p + i as f64 * step`** 在浮点累积路径上不同：

- **`np.arange`**：内部逐步累加 `current += step`，每次累加引入 ~1 ULP 舍入误差，到第 219 步时累积误差达 ~2e-15
- **`min_p + i * step`**：每步独立计算 `min_p + (i × step)`，无累积误差

### 3.2 边界 bin 翻转机制

当某个网格点 `xs[j]` 恰好等于收盘价 `close` 时，~2e-15 的网格偏差导致 `xs[j] <= close` 的真值翻转：

```
002374.SZ 边界 bin (j=219):
  close_t      = 0x1.e3d70a3d70a3ep+1  (3.7800000000000002)
  np.arange    = 0x1.e3d70a3d70a42p+1  (3.7800000000000020)  → xs[j] <= close = False ✗
  Rust grid    = 0x1.e3d70a3d70a3ep+1  (3.7800000000000002)  → xs[j] <= close = True  ✓
  差值：+1.776e-15 (约 2 ULP)
```

一个 bin 的差异在 cumpdf 中对应 ~26000 筹码量，经 `winner / total` 归一化后产生 **0.039 的 cyqk 偏差**。

### 3.3 三只股票验证

| Stock | `np.arange` 边界值 | Rust 边界值 | close | 方向 | Winner bins 差 |
|-------|-------------------|------------|-------|------|---------------|
| 002374.SZ | 3.780000000000002**0** | 3.78000000000000**02** | 3.78000000000000**02** | py 多排除 | +1 |
| 000727.SZ | 2.929999999999999**3** | 2.929999999999999**7** | 2.929999999999999**7** | py 多排除 | +1 |
| 000088.SZ | 4.4799999999999**86** | 4.4**80000000000** | 4.47999999999999**95** | py 多包含 | -1 |

## 4. 已排除的因素

通过逐环节对比，以下因素被确认为**不是差异来源**：

| 因素 | 验证结论 |
|------|---------|
| 数据源（parquet vs DuckDB） | 二者均读同一 parquet 文件，front-adjusted 价格完全一致 |
| 窗口对齐（T/T-1 切分） | 两端均为 1001 union_bars，T/T-1 各 1000 天 |
| curpdf 三角分布算法 | 使用相同网格时 max diff = 0 |
| cumpdf 衰减累积 | batch (numpy) 与 manual (循环) max diff = 0 |
| 换手率公式 | `vol * 100 / float_shares` 两端一致 |
| 涨跌停检测阈值 | Rust `< 1e-12` vs Python `== 0`，对本例 3 只股票无影响 |
| c 参数边界 | Rust 有 `|c-1| < 1e-14` 保护，Python 无，但本例未触发 |

## 5. 解决方案

### 5.1 新增 `make_price_grid` 函数

在 `qlib_cost/distribution_of_chips.py` 中新增：

```python
def make_price_grid(min_p: float, max_p: float, step: float) -> np.ndarray:
    """构建价格网格，与 Rust `min_p + i as f64 * step` 逐点 IEEE-754 一致。"""
    n = int(np.ceil((max_p - min_p) / step)) + 1
    return min_p + np.arange(n) * step
```

### 5.2 替换所有 `np.arange` 网格构建

将所有 `np.arange(min_p, max_p + step, step)` 替换为 `make_price_grid(min_p, max_p, step)`：

| 文件 | 替换数 |
|------|-------|
| `qlib_cost/distribution_of_chips.py` | 4 |
| `qlib_cost/cyq.py` | 1 |
| `backtest/chip_algorithm.py` | 3 |
| `scripts/data/full_market_canonical_resist.py` | 1 |
| `scripts/data/full_market_equal_weight_resist.py` | 1 |
| **合计** | **10** |

### 5.3 验证结果

| Stock | Rust cyqk_T | 修正前 Python | 修正后 Python |
|-------|------------|-------------|-------------|
| 002374.SZ | 0.5872 | 0.5481 (diff=0.039) | **0.5872** ✓ |
| 000727.SZ | 0.9019 | 0.8641 (diff=0.038) | **0.9019** ✓ |
| 000088.SZ | 0.1599 | 0.1964 (diff=0.037) | **0.1599** ✓ |

## 6. 附带发现

### 6.1 Rust T-1 窗口使用 T 日资本（次要）

Rust 的 `compute_cyqk_from_curpdfs` 对 T 和 T-1 窗口使用**同一个** `circ_cap`（T 日的流通股本），而 Python 对 T-1 窗口使用前一日的 `circ_cap_prev`。

```rust
// Rust: 同一个 circ_cap 用于两个窗口
let (cyqk_circ_t, cyqk_circ_t_1) = compute_cyqk_from_curpdfs(
    ..., circ_cap, ...)?;
```

```python
# Python: T-1 用不同资本
turnover_circ_prev_arr = vol_arr * 100.0 / circ_cap_prev
```

**影响**：当流通股本在 T 和 T-1 之间发生变化（增发、解禁等）时，两端的 T-1 turnover 不同，导致 cumpdf_T-1 和 cyqk_T-1 产生差异。本例 3 只股票的 T/T-1 资本相同，故未触发。

**建议**：Rust 侧应加载 T-1 日的流通股本，与 Python 对齐。或在文档中明确约定两端统一使用 T 日资本。

### 6.2 cyqk 归一化顺序差异（可忽略）

- Python (`ChipFactor.get_winner`)：先 `cumpdf / total` 归一化为比例，再求和
- Rust (`calc_cyqk`)：先求 raw winner 和 raw total，再 `winner / total`

差异在 machine epsilon 级别（~1e-16），不影响最终 4 位小数输出。

### 6.3 `np.arange` 的已知陷阱

`np.arange` 的[官方文档](https://numpy.org/doc/stable/reference/generated/numpy.arange.html)明确警告：

> When using a non-integer step, such as 0.1, it is better to use `numpy.linspace`.

`np.arange` 内部通过逐步累加 step 生成序列，累积浮点误差可导致：
1. 元素数量不确定（比预期多 1 或少 1）
2. 元素值与 `start + i * step` 不同（本例的根因）

## 7. 调试工具清单

| 工具 | 路径 | 用途 |
|------|------|------|
| Rust debug binary | `turnover-resist/src/debug_precision.rs` | 打印单只股票每个环节的中间值 |
| Python debug script | `scripts/legacy/debug_precision.py` | 内嵌 Rust 算法复现，逐环节对比 |
| 排查 prompt | `docs/prompts/prompt-rust-python-precision-investigation.md` | 排查流程指引 |
